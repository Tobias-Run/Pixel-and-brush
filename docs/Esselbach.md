# Erstes Gebiet: Esselbach (97839), Bayern

Lokale Konfiguration: `configs/esselbach.yaml`. Mittelpunkt ungefähr
9.533333° Ost, 49.850000° Nord (öffentliche Ortskoordinaten aus
[Esselbach](https://de.wikipedia.org/wiki/Esselbach), geprüft am 2026-10-14).
Die BBox wurde aus ±2500 m um diesen Mittelpunkt in UTM32N abgeleitet.
Sie umfasst ungefähr 25 km², keine exakte Gemeindegrenze; dies sind AOI-Koordinaten,
keine Fundstellen oder Kandidaten. Zeitraum April–September 2025 ist eine
Arbeitsannahme für den ersten Vegetationsvergleich. Mehrjährige Auswertung folgt
nach belastbarem Datenzugang.

```bash
archaeo validate-config configs/esselbach.yaml
# Erst nach Bereitstellung kalibrierter, ausgerichteter lokaler Szenen:
archaeo run --config configs/esselbach.yaml
```

Szenen, Cache und Exporte sind getrennt von der synthetischen Demo. Es wurden
keine realen Szenen heruntergeladen oder statistischen Kandidaten berechnet.
Die konfigurierte 10-m-Auflösung gilt für Sentinel-NDVI, nicht für DGM1.

## Vorrangige Terrainquelle

Die Bayerische Vermessungsverwaltung bietet bayernweit das **DGM1**, ein
Geländemodell ohne Vegetation und Bebauung, als OpenData an:

- Gitterweite 1 m; GeoTIFF-Kacheln 1 × 1 km.
- CRS ETRS89 / UTM32, **EPSG:25832** (vom NDVI-Ziel-CRS getrennt behandeln).
- Laut Katalog ungefähr 4 MB pro Kachel; Datenaktualität losweise.
- Lizenz **CC BY 4.0**: Quellenangabe, Lizenzverweis und Änderungen dokumentieren.
- Für den Einstieg DGM1 in nativer Auflösung und mehrere Beleuchtungsrichtungen
  für Hillshade verwenden. Nicht erst auf 10 m vergröbern. DGM-Gitterweite ist
  keine Garantie, dass Erdwerke bestimmter Größe erkannt werden.

Quellen, am 2026-10-14 gelesen:
[offizielle Produktseite](https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=dgm1),
[offizieller Metadatenkatalog](https://geodaten.bayern.de/opengeodata/json/opengeodata_datensaetze.json),
[Datenhinweise](https://www.geodaten.bayern.de/odd/m/3/html/datenhinweise/datenhinweise_dgm.html).
Die Produktverfügbarkeit ist bestätigt; konkrete Kacheln, Aufnahmejahre,
Höhenbezug und lokale Qualität sind vor Verwendung noch zu prüfen.
DEM-Download, Hillshade und Terrain-Auswertung sind derzeit nicht implementiert.

Für die weitere Datenarbeit ist DGM1-Hillshade die bevorzugte Ergänzung zur
Sentinel-Zeitserie; grobes SRTM ist hier nicht die erste Wahl. Registerabgleich
bleibt lokal und fachlich zu prüfen. Vor Feldarbeit zuständige Denkmalbehörde
kontaktieren; nichts veröffentlichen.
