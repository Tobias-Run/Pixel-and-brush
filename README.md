# Pixel-and-brush

Satellitenpixel treffen archäologische Spurensuche.

GitHub: https://github.com/Tobias-Run/Pixel-and-brush (öffentlich).
Python-Paket: `archaeo-prospektion`, CLI: `archaeo`.

Lokale, reproduzierbare Pipeline für **statistische Kandidaten**, keine automatische
Entdeckung von Ruinen. „Auffällig“ ist eine Statistik, „archäologisch“ eine fachliche
Prüfung und „unentdeckt“ eine Registerfrage. Standardparameter sind wissenschaftlich
nicht validiert. Tests belegen Softwarekorrektheit, keine Erkennungsleistung.

## Installation (Python 3.11+)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check src tests
mypy --strict src
pytest -q
```

Direkte Abhängigkeiten sind in `pyproject.toml` gepinnt. `requirements-lock.txt`
fixiert zusätzlich die getestete Python-3.12-Laufzeit einschließlich transitiver
Abhängigkeiten; auf anderen Python-Versionen müssen Wheel-Kompatibilitäten geprüft werden.
Die Installation benötigt Paketdownloads; **Demo und Tests benötigen danach kein Netz**.

## Offline-Demo und CLI

Im Repo werden keine Raster eingecheckt. Der Generator erstellt fünf deterministische
64×64-Szenen (Seed 42) mit Wolken, NoData und einer schmalen synthetischen Struktur
über der Fenstergrenze. Diese Struktur ist kein Modell einer archäologischen Fundstelle.

```bash
archaeo validate-config configs/example.yaml
archaeo demo
archaeo search --config configs/example.yaml --catalog data/demo/scenes.json
archaeo fetch --config configs/example.yaml --catalog data/demo/scenes.json
archaeo run --config configs/example.yaml
```

`demo` schreibt nach `exports/demo/`, `run` nach `exports/run/`:

- `candidates.geojson`: priorisierte Polygone in WGS84 (RFC 7946).
- `candidates.csv`: gleiche Belege einschließlich Polygon und Herkunft.
- `report.md`, `map.png`: lokale statische Karte, Formel, Parameter und Datenlücken.
- `manifest.json`: UTC-Zeit, Versionen, Konfiguration, Quellen und SHA256 der Eingangsraster.
- `features.tif`: Median, Standardabweichung, signierte Abweichung, Beobachtungszahl,
  Wolkenanteil, Bewertbarkeit (Bänder 1–6); `anomalies.tif`: binäre Auswahl.

`demo --output … --data …` erlaubt andere lokale Pfade. Pfade in YAML beziehen sich
auf das Verzeichnis der Konfigurationsdatei; GeoJSON-AOI als Polygon/MultiPolygon
oder einzelnes Feature in WGS84. BBox ist ebenfalls WGS84. Zeitgrenzen sind inklusive.
Unbekannte YAML-Felder, leere AOI, ungültiges CRS, umgekehrte Zeiträume und Limits
werden abgewiesen. Die Beispiel-AOI umfasst ausschließlich einen synthetischen Test.

## Reale lokale Daten und Phase 2

**Live-CDSE-Suche und Downloads sind im MVP noch nicht implementiert.** `search` und
`fetch` verwenden mit `--catalog` einen lokalen Katalogadapter; ohne ihn liefern sie
 einen erklärten Fehler. `fetch` kopiert lokal in einen SHA256-adressierten Cache,
prüft Szenen-/Byte-Limits und erzeugt das Szenenmanifest für `run`. Keine Anmeldung,
kein Remote und keine Veröffentlichung. [CDSE-Prüfnotiz](docs/CDSE.md) beschreibt
geprüfte offizielle Quellen und die noch offene Authentifizierungsentscheidung.

Für einen realen **lokalen** Lauf: eigenes AOI, Zeitraum und Zielraster konfigurieren;
vorhandene L2A-B04/B08/SCL-Raster explizit ausrichten und ein JSON-Szenenmanifest
angeben. Struktur: Liste von Objekten mit `id`, `date` (ISO-Datum), `red`, `nir`, `scl`
(Dateipfade relativ zum Manifest), `bbox` (WGS84), `source_urls` und
`band_resolution_m`. Kontinuierliche Bänder müssen kalibrierte, offsetkorrigierte
Reflektanzen enthalten; rohe DN-Werte sind ohne die produktspezifische Kalibrierung
ungeeignet. Die Pipeline prüft Ausrichtung und lehnt Abweichungen ab.
`archaeo.preprocessing.resample` bietet explizite Reprojektion: bilinear für Werte,
nearest für Masken, NoData als NaN. Die MVP-CLI richtet Rohprodukte nicht automatisch aus.

B02/B03/B04/B08: 10 m; B05–B07/B8A/B11/B12 und SCL: 20 m. Der MVP verwendet nur
B04/B08/SCL. Hochskalieren erzeugt keine Details. Wenn einheitliche 20-m-Analyse
nötig ist, kontinuierliche 10-m-Bänder explizit auf 20 m resampeln und sowohl
Original- als auch Zielauflösung dokumentieren. Keine stillen Raster-Fallbacks.

## Methode und Fehlerpfade

NDVI = `(B08 − B04)/(B08 + B04)`. Nicht endliche Werte, negative Reflektanzen,
Nullnenner und SCL 0/1/3/8/9/10/11 sind ungültig. Schatten/Wolkenanteil umfasst
SCL 3/8/9/10, nicht sämtliche NoData-Werte. Zeitmedian und Standardabweichung
werden aus gültigen Beobachtungen gebildet. Der räumliche Kontext ist der lokale
Median im quadratischen Fenster (Radius aus Konfiguration), außerhalb der AOI
und am Rasterrand werden fehlende Nachbarn ignoriert.

Anomalie: Betrag der Abweichung vom lokalen Median ≥ Schwelle und ausreichende
Beobachtungszahl. Vierfach zusammenhängende Komponenten, Mindestgröße in Pixeln.
**Score = mittlerer Abweichungsbetrag × mittlere Beobachtungszahl / Szenenanzahl.**
„Konfidenz“ ist nur Datenabdeckung. Der Wolkenanteil mittelt alle verwendeten Szenen.
Zu wenige Beobachtungen: nicht bewertbar, keine Anomalie. Komplett ungültige Raster,
keine Treffer, CRS-/Auflösungs-/Ausrichtungsfehler und überschrittene Limits führen
zu geprüften Fehlern. Es gibt keine archäologische Wahrscheinlichkeit.

Die zeitlichen Berechnungen lesen begrenzte Fenster mit Kontextrand; Ergebnisse
liegen gekachelt auf Platte. GDAL polygonisiert das Rasterband über Fenstergrenzen.
Komponentenstatistiken werden blockweise aggregiert. Speicher für Polygongeometrien
steigt dennoch mit deren Komplexität; Pixel-/Szenenlimits bleiben erforderlich.
Kandidaten enthalten alle verwendeten Szenen als Herkunft, nicht nur die pro Pixel
sichtbaren Szenen. Bei abgebrochenen Läufen können Teilausgaben verbleiben; nur ein
vollständiger Lauf mit neuem Manifest gilt als Ergebnis. Nicht gleichzeitig in
 dasselbe Ausgabe-/Cache-Verzeichnis schreiben.

## Referenzen, DEM und fachliche Bewertung

Optionale `paths.register` (GeoJSON oder CSV mit `longitude,latitude` in WGS84)
markiert lokale räumliche Überschneidungen, ohne daraus „bekannt/unbekannt“ abzuleiten.
`paths.landuse` und `paths.historical_map` werden als lokale Referenzen im Bericht
vermerkt; fachlicher Abgleich bleibt manuell. Fehlende Referenzen sind dokumentierte
Lücken. Bewerte Kandidaten anhand der Quellen und dokumentiere Kontrollen und
manuelle Urteile getrennt von statistischen Scores. Kein externer Registerabruf.

Bayerisches DGM1 kann jetzt heruntergeladen und als vier 1-m-Hillshades für die
lokale Bildprüfung vorbereitet werden (`fetch-dem`, `prepare-terrain`). Terrain-
Klassifikation und Kombination mit NDVI-Scores sind noch nicht implementiert. SRTM/Copernicus DEM sind grobe
Oberflächenmodelle (Rasterweite und DSM/DTM bei Verwendung dokumentieren).
Keine gleichwertige Erkennung kleiner Erdwerke behaupten. Vorhandene hochauflösende
Laserscan-DTM und daraus berechnetes Hillshading haben Vorrang.
Feldgrenzen, Bewirtschaftung, Feuchte, Vegetation und technische Artefakte können
Anomalien erzeugen; ohne Kontrollfälle fehlt jede Aussage über Erkennungsleistung.

## Rechte und Datenschutz

Vor Feldarbeit die zuständige Denkmalbehörde kontaktieren. Denkmalschutz ist
gebietsabhängig; in Deutschland ist Bodeneingriff ohne Genehmigung unzulässig,
auch oberirdische Prospektion kann genehmigungspflichtig sein.
Registerdaten sind urheberrechtlich geschützt, Landnutzung ist lizenzabhängig.
Sentinel-Daten unterliegen den Copernicus-Nutzungsbedingungen: kostenlos,
Attribution **Copernicus/ESA** (gegebenenfalls Jahr und Verarbeitung ergänzen).
Keine Kandidatenkoordinaten oder Rohdaten ohne ausdrückliche Anweisung veröffentlichen.
Daten, Cache, Credentials und Exporte sind gitignored. `CDSE_CLIENT_ID` und
`CDSE_SECRET` sind ausschließlich für die spätere Integration als Umgebungsvariablen
vorgesehen; niemals einchecken oder in Logs schreiben.

Nicht enthalten: Deep Learning, Earth Engine, Weboberfläche, interaktive Karten,
automatischer externer Registerabgleich.

## Erstes reales Arbeitsgebiet

[Esselbach (97839) und Umgebung](docs/Esselbach.md) ist mit ungefähr 5 × 5 km
in `configs/esselbach.yaml` vorbereitet. Validierung:
`archaeo validate-config configs/esselbach.yaml`. Der erste angenommene Zeitraum
ist April–September 2025. DGM1-Daten wurden lokal heruntergeladen und 144 Bildpakete vorbereitet; reale
Sentinel-Szenen und archäologisch bewertete Ergebnisse liegen noch nicht vor.
Bayerisches DGM1 (1 m, CC BY 4.0) ist als bevorzugte Terrainquelle dokumentiert.

## Lokales Vision-Modell

`archaeo review-images` prüft vorbereitete PNG/JPEG-Bildausschnitte über einen
lokalen Ollama-Vision-Server und exportiert kompakte, gecachte JSON-Befunde.
Keine Cloud-Tokens, kein automatischer Modelldownload; statistische Scores bleiben
unverändert. [Einrichtung und Grenzen](docs/LocalModel.md).

GitHub darf ausschließlich Code, Tests und Dokumentation enthalten. Rohdaten,
Koordinatenexporte, Bildausschnitte und Modellgewichte bleiben lokal. Die GitHub-
Actions prüfen synthetische Daten und veröffentlichen keine Ergebnisartefakte.

## Windows-Startpaket und Terrain-Vorbereitung

[Windows 11 / RTX 5060 Ti: Schrittfolge](docs/Windows.md).
`./scripts/windows-start.ps1 -Stage Setup` installiert und prüft das Projekt;
`-Stage Data` lädt DGM1 und erzeugt eine lokale Bildübersicht; `-Stage Review`
prüft die Bildpakete sequenziell mit einem vorinstallierten lokalen Vision-Modell.

Auch ohne Downloads/Modell läuft `archaeo terrain-demo` mit synthetischem Relief.
`archaeo review-batches` verarbeitet mehrere Pakete und verwendet vorhandene Caches.
Die Terrain-Pipeline ist separat vom Sentinel-Workflow; sie liefert Bildmaterial
zur Prüfung und noch keine automatischen Terrain-Kandidaten.
