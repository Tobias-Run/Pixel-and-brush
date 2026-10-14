import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from pyproj import Transformer

from archaeo.config import AOI, Config
from archaeo.errors import PipelineError
from archaeo.providers.dem import parse_metalink, sha256, checked_url
from archaeo.terrain import hillshade, prepare_terrain


def fixture(tmp_path: Path) -> tuple[Config, Path]:
    transform = from_origin(538000, 5522000, 1, 1)
    inverse = Transformer.from_crs(25832, 4326, always_xy=True)
    x0, y0 = inverse.transform(538002, 5521802)
    x1, y1 = inverse.transform(538198, 5521998)
    cfg = Config(aoi=AOI(bbox=(x0, y0, x1, y1)), start=date(2025, 1, 1), end=date(2025, 12, 31))
    cfg.paths.output = tmp_path / "out"
    z = np.ones((200, 200), dtype="float32") * 300
    z[90:95, 50:150] += 2
    z[10:12, 10:12] = -9999
    path = tmp_path / "terrain.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=200,
        width=200,
        count=1,
        dtype="float32",
        crs="EPSG:25832",
        transform=transform,
        nodata=-9999,
    ) as dst:
        dst.write(z, 1)
    manifest = tmp_path / "sources.json"
    manifest.write_text(json.dumps({"tiles": [{"path": str(path), "sha256": sha256(path)}]}))
    return cfg, manifest


def test_metalink_and_host_control() -> None:
    raw = b"""<metalink xmlns="urn:ietf:params:xml:ns:metalink"><file name="538_5521.tif">
    <url>https://download1.bayernwolke.de/a/dgm/dgm1/538_5521.tif</url></file></metalink>"""
    assert len(parse_metalink(raw, 1)) == 1
    with pytest.raises(PipelineError):
        parse_metalink(raw.replace(b"538_5521.tif", b"../unsafe.tif"), 1)
    with pytest.raises(PipelineError):
        parse_metalink(raw.replace(b"download1.bayernwolke.de", b"unknown.example"), 1)
    with pytest.raises(PipelineError):
        parse_metalink(b"<wrong/>", 10)
    with pytest.raises(PipelineError):
        parse_metalink(b"<!DOCTYPE foo><foo/>", 10)
    with pytest.raises(PipelineError):
        checked_url("http://download1.bayernwolke.de/a.tif")


def test_hillshade_geometry() -> None:
    flat = np.zeros((5, 5))
    np.testing.assert_allclose(hillshade(flat, 1, 45), np.sin(np.radians(35)))
    east_slope = np.tile(np.arange(5.0), (5, 1))
    assert hillshade(east_slope, 1, 270).mean() > hillshade(east_slope, 1, 90).mean()
    south_slope = east_slope.T
    assert hillshade(south_slope, 1, 0).mean() > hillshade(south_slope, 1, 180).mean()
    with pytest.raises(PipelineError):
        hillshade(flat, 0, 45)


def test_terrain_end_to_end(tmp_path: Path) -> None:
    cfg, sources = fixture(tmp_path)
    result = prepare_terrain(cfg, sources, tile_size=128, overlap=32)
    manifest = json.loads(result.read_text())
    assert manifest["resolution_m"] == 1 and manifest["tiles"]
    assert manifest["azimuths"] == [45, 135, 225, 315]
    with rasterio.open(result.parent / "hillshade.tif") as src:
        assert src.crs.to_epsg() == 25832 and src.count == 4
        pixels = src.read()
        assert (pixels == 0).any()
        assert (pixels > 0).any()
        # Unebenheit muss in verschiedenen Richtungen verschieden erscheinen.
        assert not np.array_equal(pixels[0], pixels[2])
    for record in manifest["tiles"]:
        assert sha256(result.parent / record["image"]) == record["sha256"]


def test_terrain_errors(tmp_path: Path) -> None:
    cfg, sources = fixture(tmp_path)
    with pytest.raises(PipelineError, match="Pixellimit"):
        prepare_terrain(cfg, sources, max_pixels=1)
    with pytest.raises(PipelineError, match="Tilegröße"):
        prepare_terrain(cfg, sources, tile_size=128, overlap=128)
    entry = json.loads(sources.read_text())
    entry["tiles"][0]["sha256"] = "wrong"
    sources.write_text(json.dumps(entry))
    with pytest.raises(PipelineError, match="Prüfsumme"):
        prepare_terrain(cfg, sources)


def test_download_cache_and_byte_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    from archaeo.providers import dem

    cfg, _ = fixture(tmp_path)
    cfg.paths.cache = tmp_path / "cache"
    raw = b"""<metalink xmlns="urn:ietf:params:xml:ns:metalink"><file name="538_5521.tif">
    <url>https://download1.bayernwolke.de/a/dgm/dgm1/538_5521.tif</url></file></metalink>"""

    class Opener:
        downloads = 0

        def open(self, request, timeout):
            if not isinstance(request, str):
                assert request.data.startswith(b"SRID=4326;POLYGON")
                return io.BytesIO(raw)
            self.downloads += 1
            return io.BytesIO(b"synthetic-raster-bytes")

    opener = Opener()
    monkeypatch.setattr(dem, "build_opener", lambda *args: opener)
    manifest = dem.fetch_dem(cfg)
    assert json.loads(manifest.read_text())["tiles"][0]["sha256"]
    dem.fetch_dem(cfg)
    assert opener.downloads == 1
    # Beschädigten Cache erneut herunterladen, nicht still verwenden.
    (cfg.paths.cache / "dgm1/538_5521.tif").write_bytes(b"corrupt")
    dem.fetch_dem(cfg)
    assert opener.downloads == 2
    cfg.paths.cache = tmp_path / "small-cache"
    cfg.limits.max_download_bytes = 1
    with pytest.raises(PipelineError, match="Byte-Limit"):
        dem.fetch_dem(cfg)
    assert not list(cfg.paths.cache.rglob("*.part"))


def test_invalid_terrain(tmp_path: Path) -> None:
    cfg, manifest = fixture(tmp_path)
    entry = json.loads(manifest.read_text())
    path = Path(entry["tiles"][0]["path"])
    with rasterio.open(path, "r+") as dst:
        dst.write(np.full((200, 200), -9999, dtype="float32"), 1)
    entry["tiles"][0]["sha256"] = sha256(path)
    manifest.write_text(json.dumps(entry))
    with pytest.raises(PipelineError, match="vollständig ungültig"):
        prepare_terrain(cfg, manifest)


def test_terrain_demo_cli_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import socket
    from typer.testing import CliRunner
    from archaeo.cli import app

    monkeypatch.setattr(
        socket, "create_connection", lambda *a, **k: pytest.fail("Netzwerk in Demo")
    )
    result = CliRunner().invoke(
        app, ["terrain-demo", "--data", str(tmp_path / "data"), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "out/terrain/overview.html").exists()
