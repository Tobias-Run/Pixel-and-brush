import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from typer.testing import CliRunner

from archaeo.cli import app, execute
from archaeo.config import AOI, load_config
from archaeo.demo import generate
from archaeo.errors import PipelineError
from archaeo.features import features
from archaeo.pipeline import calculate
from archaeo.preprocessing import ndvi, resample, assert_aligned
from archaeo.providers.cdse import FixtureCatalog, search
from archaeo.candidates import candidates


def test_mask_and_zero():
    red = np.array([[0.0, 0.2, 0.2, np.nan, 0.2]])
    nir = np.array([[0.0, 0.5, 0.5, 0.5, 0.5]])
    result, cloud = ndvi(red, nir, np.array([[4.0, 9, 3, 4, 4]]))
    assert np.isnan(result[0, :4]).all()
    assert result[0, 4] == pytest.approx(3 / 7)
    assert cloud.tolist() == [[False, True, True, False, False]]


def test_config():
    cfg = load_config(Path(__file__).parents[1] / "configs/example.yaml")
    assert cfg.grid.resolution == 10
    with pytest.raises(ValueError):
        AOI(bbox=(1, 2, 1, 3))
    with pytest.raises(ValueError):
        AOI(bbox=(0, 0, float("nan"), 3))


def test_no_hit(tmp_path):
    cfg, scenes = generate(tmp_path / "data")
    assert search(cfg, FixtureCatalog(scenes)) == scenes
    with pytest.raises(PipelineError, match="Keine Katalogtreffer"):
        search(cfg, FixtureCatalog([]))
    with pytest.raises(PipelineError, match="Phase 2"):
        search(cfg)


def test_alignment(tmp_path):
    cfg, scenes = generate(tmp_path / "data")
    with rasterio.open(scenes[0].red) as a:
        for update in ({"crs": "EPSG:3857"}, {"transform": from_origin(500000, 5539200, 20, 20)}):
            profile = a.profile.copy()
            profile.update(update)
            path = tmp_path / "mismatch.tif"
            with rasterio.open(path, "w", **profile) as dst:
                dst.write(a.read())
            with rasterio.open(path) as b, pytest.raises(PipelineError):
                assert_aligned(a, b)


def test_resampling():
    source = np.array([[0.0, 10.0], [20.0, 30.0]])
    args = (
        source,
        from_origin(0, 40, 20, 20),
        from_origin(0, 40, 10, 10),
        "EPSG:32632",
        "EPSG:32632",
        (4, 4),
    )
    nearest = resample(*args, categorical=True)
    bilinear = resample(*args)
    assert set(np.unique(nearest)) == {0, 10, 20, 30}
    assert not np.array_equal(nearest, bilinear)
    assert bilinear[1, 1] == pytest.approx(7.5)


def test_insufficient_observations():
    stack = np.full((2, 5, 5), np.nan)
    stack[0, 2, 2] = 0.9
    result = features(stack, np.zeros(stack.shape, dtype=bool), 1, 2)
    assert not result[5].any()
    assert np.isnan(result[2]).all()


def test_invalid_raster(tmp_path):
    cfg, scenes = generate(tmp_path / "data")
    for scene in scenes:
        with rasterio.open(scene.red, "r+") as dst:
            dst.write(np.full((64, 64), np.nan), 1)
    with pytest.raises(PipelineError, match="ungültige Raster"):
        calculate(cfg, scenes, tmp_path / "out")


def test_components(tmp_path):
    cfg, _ = generate(tmp_path / "data")
    cfg.parameters.min_pixels = 1
    profile = dict(
        driver="GTiff",
        width=4,
        height=4,
        count=1,
        crs=cfg.grid.crs,
        transform=from_origin(0, 40, 10, 10),
        dtype="uint8",
    )
    mask = np.zeros((4, 4), dtype="uint8")
    mask[0, 0] = 1
    mask[1, 1:3] = 1
    with rasterio.open(tmp_path / "mask.tif", "w", **profile) as dst:
        dst.write(mask, 1)
    profile.update(count=6, dtype="float64")
    values = np.ones((6, 4, 4))
    values[2] = 0.2
    values[3] = 5
    values[4] = 0
    with rasterio.open(tmp_path / "feat.tif", "w", **profile) as dst:
        dst.write(values)
    rows = candidates(tmp_path / "feat.tif", tmp_path / "mask.tif", cfg, 5)
    assert sorted(r["pixels"] for r in rows) == [1, 2]
    from shapely.geometry import shape

    assert shape(rows[0]["geometry"]).intersection(shape(rows[1]["geometry"])).area == 0


def test_demo_roundtrip_and_window_invariance(tmp_path, monkeypatch):
    import socket

    monkeypatch.setattr(
        socket, "create_connection", lambda *a, **k: pytest.fail("Netzwerk in Demo")
    )
    cfg, scenes = generate(tmp_path / "data")
    cfg.paths.output = tmp_path / "out"
    execute(cfg, scenes)
    output = cfg.paths.output
    frame = gpd.read_file(output / "candidates.geojson")
    assert frame.crs.to_epsg() == 4326
    assert len(frame) == 1
    assert frame.iloc[0]["pixels"] == 40
    assert {
        "source_ids",
        "source_urls",
        "scene_bboxes",
        "parameters",
        "observations",
        "cloud_fraction",
        "anomaly_score",
        "ndvi_deviation",
    } <= set(frame.columns)
    assert frame.geometry.is_valid.all()
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["candidate_count"] == 1
    assert manifest["input_sha256"]
    assert (output / "report.md").exists() and (output / "map.png").exists()
    with rasterio.open(output / "features.tif") as src:
        first = src.read()
    cfg.grid.window_size = 64
    second, _ = calculate(cfg, scenes, tmp_path / "second")
    with rasterio.open(second) as src:
        np.testing.assert_allclose(first, src.read(), equal_nan=True)


def test_cli(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        app, ["demo", "--output", str(tmp_path / "out"), "--data", str(tmp_path / "data")]
    )
    assert result.exit_code == 0, result.output
    root = Path(__file__).parents[1]
    result = runner.invoke(app, ["validate-config", str(root / "configs/example.yaml")])
    assert result.exit_code == 0
    result = runner.invoke(app, ["search", "--config", str(root / "configs/example.yaml")])
    assert result.exit_code != 0 and "Phase 2" in result.output


def test_catalog_filters_and_limits(tmp_path):
    from datetime import date

    cfg, scenes = generate(tmp_path / "data")
    cfg.limits.max_scenes = 3
    assert len(search(cfg, FixtureCatalog(scenes))) == 3
    scenes[0].date = date(2020, 1, 1)
    scenes[1].bbox = (0, 0, 1, 1)
    assert [s.id for s in search(cfg, FixtureCatalog(scenes))] == [s.id for s in scenes[2:]]


def test_local_fetch_cache_and_limit(tmp_path):
    import yaml

    root = Path(__file__).parents[1]
    _, _ = generate(tmp_path / "data")
    config = yaml.safe_load((root / "configs/example.yaml").read_text())
    config["paths"] = {"cache": "cache", "scenes": "cached-scenes.json", "output": "out"}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config))
    args = ["fetch", "--config", str(path), "--catalog", str(tmp_path / "data/scenes.json")]
    runner = CliRunner()
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    times = {p: p.stat().st_mtime_ns for p in (tmp_path / "cache").iterdir()}
    assert runner.invoke(app, args).exit_code == 0
    assert times == {p: p.stat().st_mtime_ns for p in (tmp_path / "cache").iterdir()}
    assert runner.invoke(app, ["run", "--config", str(path)]).exit_code == 0
    config["limits"]["max_download_bytes"] = 1
    path.write_text(yaml.safe_dump(config))
    assert "Byte-Limit" in runner.invoke(app, args).output


def test_empty_geojson_and_crs(tmp_path):
    from archaeo.config import Grid

    path = tmp_path / "empty.geojson"
    path.write_text(json.dumps({"type": "Polygon", "coordinates": []}))
    with pytest.raises(ValueError):
        AOI(geojson=path).geometry()
    with pytest.raises(ValueError):
        Grid(crs="EPSG:4326")
    with pytest.raises(ValueError):
        Grid(resolution=float("inf"))


def test_local_register_and_gaps(tmp_path):
    from archaeo.evaluation import evaluate
    from shapely.geometry import box, mapping

    cfg, _ = generate(tmp_path / "data")
    path = tmp_path / "register.geojson"
    gpd.GeoDataFrame(geometry=[box(0, 0, 10, 10)], crs=cfg.grid.crs).to_file(path, driver="GeoJSON")
    cfg.paths.register_file = path
    rows = [{"geometry": mapping(box(5, 5, 15, 15))}]
    gaps = evaluate(rows, cfg)
    assert rows[0]["register_overlap"]
    assert len(gaps) == 2
