from pathlib import Path
import hashlib
import shutil
import typer
from archaeo.config import Config, load_config
from archaeo.providers.cdse import FixtureCatalog, Scene, read_scenes, search as query
from archaeo.pipeline import calculate
from archaeo.candidates import candidates
from archaeo.evaluation import evaluate
from archaeo.export import export
from archaeo.demo import generate

app = typer.Typer(pretty_exceptions_enable=False, help="Lokale statistische Prospektion")


def execute(config: Config, scenes: list[Scene]) -> None:
    (config.paths.output / "manifest.json").unlink(missing_ok=True)
    features, mask = calculate(config, scenes, config.paths.output)
    rows = candidates(features, mask, config, len(scenes))
    gaps = evaluate(rows, config)
    export(rows, config, scenes, gaps)
    typer.echo(f"{len(rows)} Kandidaten: {config.paths.output}")


@app.command()
def validate_config(config: Path = typer.Argument(Path("configs/example.yaml"))) -> None:
    try:
        load_config(config)
        typer.echo("Konfiguration gültig")
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def demo(output: Path = Path("exports/demo"), data: Path = Path("data/demo")) -> None:
    config, scenes = generate(data.resolve())
    config.paths.output = output.resolve()
    execute(config, scenes)


@app.command()
def search(config: Path = Path("configs/example.yaml"), catalog: Path | None = None) -> None:
    cfg = load_config(config)
    try:
        scenes = query(cfg, FixtureCatalog(read_scenes(catalog)) if catalog else None)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for scene in scenes:
        typer.echo(scene.id)


@app.command()
def fetch(config: Path = Path("configs/example.yaml"), catalog: Path | None = None) -> None:
    """Lokale Szenen in begrenzten, SHA256-adressierten Cache kopieren (MVP)."""
    cfg = load_config(config)
    try:
        scenes = query(cfg, FixtureCatalog(read_scenes(catalog)) if catalog else None)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    paths = list(dict.fromkeys(p for s in scenes for p in (s.red, s.nir, s.scl)))
    if sum(p.stat().st_size for p in paths) > cfg.limits.max_download_bytes:
        raise typer.BadParameter("Download-/Cache-Byte-Limit überschritten")
    cfg.paths.cache.mkdir(parents=True, exist_ok=True)
    replacements = {}
    for path in paths:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        target = cfg.paths.cache / f"{digest}{path.suffix}"
        if not target.exists():
            temp = target.with_suffix(".part")
            shutil.copyfile(path, temp)
            temp.replace(target)
        else:
            with target.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise typer.BadParameter("Cache-Prüfsumme ungültig")
        replacements[path] = target.resolve()
    for scene in scenes:
        scene.red, scene.nir, scene.scl = (
            replacements[p] for p in (scene.red, scene.nir, scene.scl)
        )
    import json

    cfg.paths.scenes.parent.mkdir(parents=True, exist_ok=True)
    cfg.paths.scenes.write_text(json.dumps([s.model_dump(mode="json") for s in scenes]))
    typer.echo(f"{len(scenes)} Szenen lokal gecacht: {cfg.paths.scenes}")


@app.command()
def run(config: Path = Path("configs/example.yaml")) -> None:
    cfg = load_config(config)
    try:
        scenes = query(cfg, FixtureCatalog(read_scenes(cfg.paths.scenes)))
        execute(cfg, scenes)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def review_images(
    folder: Path = typer.Argument(..., help="Lokale PNG/JPEG-Ausschnitte"),
    model: str = typer.Option(..., help="Installiertes lokales Ollama-Vision-Modell"),
    output: Path = Path("exports/local-review"),
    max_images: int = 20,
    port: int = 11434,
) -> None:
    """Bilder lokal vorprüfen; keine Cloud-Tokens und keine Score-Änderungen."""
    from archaeo.local_model import OllamaClient, review_images as review

    try:
        result = review(folder, output, OllamaClient(model, port=port), max_images)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Lokale Modellvorschläge: {result}")


@app.command()
def fetch_dem(config: Path = Path("configs/esselbach.yaml"), max_tiles: int = 64) -> None:
    """Bayerisches DGM1 für die AOI herunterladen; lokale Daten bleiben gitignored."""
    from archaeo.providers.dem import fetch_dem as download

    try:
        result = download(load_config(config), max_tiles=max_tiles)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Lokales DGM1-Manifest: {result}")


@app.command()
def prepare_terrain(
    config: Path = Path("configs/esselbach.yaml"),
    tile_size: int = 512,
    overlap: int = 64,
    max_pixels: int = 40000000,
) -> None:
    """Native DGM1-Hillshades und Bildpakete für lokale visuelle Prüfung erstellen."""
    from archaeo.terrain import prepare_terrain as prepare

    try:
        cfg = load_config(config)
        result = prepare(
            cfg, cfg.paths.cache / "dgm1" / "manifest.json", tile_size, overlap, max_pixels
        )
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Terrain und Bildpakete: {result}")


@app.command()
def review_batches(
    folder: Path = typer.Argument(...),
    model: str = typer.Option(...),
    output: Path = Path("exports/esselbach/local-review"),
    max_batches: int = 10,
) -> None:
    """Vorbereitete Terrain-Pakete sequenziell lokal prüfen; Cache ermöglicht Wiederaufnahme."""
    from archaeo.local_model import OllamaClient, review_images as review

    try:
        batches = sorted(p for p in folder.glob("batch-*") if p.is_dir())
        if not 1 <= max_batches <= 100 or not batches or len(batches) > max_batches:
            raise ValueError("Keine Bildpakete oder Paketlimit überschritten")
        client = OllamaClient(model)
        for i, batch in enumerate(batches, 1):
            result = review(batch, output / batch.name, client, max_images=20)
            typer.echo(f"{i}/{len(batches)}: {result}")
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def terrain_demo(
    output: Path = Path("exports/terrain-demo"), data: Path = Path("data/terrain-demo")
) -> None:
    """Offline-Terrainweg mit synthetischem Relief, ohne Download oder Vision-Modell."""
    from archaeo.demo import generate_terrain
    from archaeo.terrain import prepare_terrain as prepare

    try:
        cfg, source = generate_terrain(data.resolve())
        cfg.paths.output = output.resolve()
        result = prepare(cfg, source, tile_size=256, overlap=32)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Synthetische Terrain-Demo: {result}")
