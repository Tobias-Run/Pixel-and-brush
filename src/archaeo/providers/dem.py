"""Begrenzter Download des bayerischen 1-m-DTM (DHHN2016, CC BY 4.0).

Offizielle Metalink-Auswahl, atomarer Cache, HTTPS-Hostkontrolle und lokale SHA256.
SRTM/Copernicus DSM sind keine gleichwertige Quelle für kleine Erdwerke.
"""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from archaeo.config import Config
from archaeo.errors import PipelineError

API = "https://geoservices.bayern.de/services/poly2metalink/metalink/dgm1"
HOSTS = {
    "geoservices.bayern.de",
    "download1.bayernwolke.de",
    "download2.bayernwolke.de",
    "geodaten.bayern.de",
}
NS = {"m": "urn:ietf:params:xml:ns:metalink"}


def checked_url(url: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise PipelineError("DEM-URL außerhalb der erlaubten offiziellen HTTPS-Hosts")
    return url


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_metalink(raw: bytes, max_tiles: int) -> list[tuple[str, str]]:
    if len(raw) > 2 * 1024 * 1024 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise PipelineError("Unzulässiges Metalink-Dokument")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise PipelineError("Ungültiges Metalink-XML") from exc
    tiles = []
    for entry in root.findall("m:file", NS):
        name = entry.get("name", "")
        if not re.fullmatch(r"[0-9]+_[0-9]+\.tif", name):
            raise PipelineError("Unsicherer oder unerwarteter DEM-Dateiname")
        urls = [v.text for v in entry.findall("m:url", NS) if v.text]
        if not urls:
            raise PipelineError("DEM-Kachel ohne Download-URL")
        tiles.append((name, checked_url(urls[0])))
    if not tiles or len(tiles) > max_tiles or len({name for name, _ in tiles}) != len(tiles):
        raise PipelineError("Keine Kacheln, doppelte Namen oder Kachellimit überschritten")
    return sorted(tiles)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch_dem(config: Config, max_tiles: int = 64) -> Path:
    if not 1 <= max_tiles <= 256:
        raise PipelineError("DEM-Kachellimit muss zwischen 1 und 256 liegen")
    geom = config.aoi.geometry()
    ewkt = f"SRID=4326;{geom.wkt}"  # type: ignore[attr-defined]
    opener = build_opener(OfficialRedirect())
    request = Request(API, data=ewkt.encode(), headers={"Content-Type": "text/plain"})
    with opener.open(request, timeout=60) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    tiles = parse_metalink(raw, max_tiles)
    cache = config.paths.cache / "dgm1"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "selection.meta4").write_bytes(raw)
    manifest_path = cache / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    previous = {v["name"]: v for v in old.get("tiles", [])}
    records = []
    total = 0
    for name, url in tiles:
        path = cache / name
        valid_cache = (
            path.exists() and name in previous and sha256(path) == previous[name]["sha256"]
        )
        if valid_cache:
            total += path.stat().st_size
            if total > config.limits.max_download_bytes:
                raise PipelineError("DEM-Byte-Limit überschritten")
        else:
            temp = path.with_suffix(".part")
            try:
                with (
                    opener.open(checked_url(url), timeout=60) as response,
                    temp.open("wb") as stream,
                ):
                    while block := response.read(1024 * 1024):
                        total += len(block)
                        if total > config.limits.max_download_bytes:
                            raise PipelineError("DEM-Byte-Limit überschritten")
                        stream.write(block)
                if temp.stat().st_size == 0:
                    raise PipelineError("Leere DEM-Kachel")
                temp.replace(path)
            finally:
                temp.unlink(missing_ok=True)
        record = {
            "name": name,
            "url": url,
            "path": str(path.resolve()),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        records.append(record)
        # Fortschritt bleibt nach Unterbrechung wiederverwendbar.
        saved = {**previous, **{v["name"]: v for v in records}}
        manifest_path.write_text(json.dumps({"tiles": list(saved.values())}))
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "selection_api": API,
        "aoi": config.aoi.model_dump(mode="json"),
        "tiles": records,
        "crs": "EPSG:25832",
        "resolution_m": 1,
        "model": "DTM",
        "vertical_datum": "DHHN2016",
        "license": "CC BY 4.0",
        "attribution": "Bayerische Vermessungsverwaltung – www.geodaten.bayern.de",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "acquisition_date": "nicht aus Metalink ersichtlich; fachlich nachprüfen",
        "bytes": total,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest_path
