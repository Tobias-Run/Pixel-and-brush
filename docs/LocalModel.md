# Lokale visuelle Vorprüfung

NDVI, Masken, räumliche Statistiken und Connected Components laufen bereits in
Python ohne KI-API. Eine zusätzliche lokale Vision-KI kann vorbereitete Hillshade-
oder Luftbildausschnitte beschreiben und zur menschlichen Prüfung vorsortieren.
Dies spart Cloud-Tokens bei visueller Prüfung; es validiert keine archäologische
Erkennungsleistung. Training, Objektsegmentierung und automatische Fundstellen-
klassifikation sind nicht implementiert.

## Lokaler Betrieb mit Ollama

Ollama auf dem eigenen Rechner installieren. Ein Vision-Modell muss vorher
installiert sein. Modellwahl/Quantisierung an RAM, GPU/VRAM und Bildgröße anpassen;
noch wurde kein konkretes Modell auf Nutzerhardware geprüft. Qwen2.5-VL oder
Gemma-3 mit Vision-Unterstützung sind mögliche Ausgangspunkte, keine Empfehlung
auf Basis von Erkennungstests. Kleine Modelle sind günstiger, subtile Reliefdetails
können aber bei Bildverkleinerung oder Quantisierung verloren gehen.

Server **mit abgeschalteter Cloud** starten (bestehenden Dienst entsprechend
konfigurieren/neustarten, nicht versehentlich einen zweiten Server starten):

```bash
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

Nach einmaligem Modelldownload kann für den Inferenzbetrieb zusätzlich der externe
Netzzugang gesperrt werden. Der Python-Client verwendet ausschließlich Loopback,
keine HTTP-Proxies und keine Redirects. Cloud-Modellnamen und deklarierte Remote-
Modelle werden abgewiesen; die Serverkonfiguration muss trotzdem offline sein.
Hier im Cloud-Workspace läuft kein Ollama-Server und kein installiertes Vision-Modell.
Für „lokal“ die Befehle auf dem eigenen Rechner ausführen.

Vorbereitete PNG/JPEG-Ausschnitte unter `data/esselbach/tiles/` ablegen:

```bash
archaeo review-images data/esselbach/tiles \
  --model NAME_DES_INSTALLIERTEN_VISION_MODELLS \
  --output exports/esselbach/local-review --max-images 20
```

Bilder sollten einen nachvollziehbaren Ausschnitt und einen Maßstab haben. Bei
Hillshade dieselbe Geländeform mit mehreren Beleuchtungsrichtungen betrachten.
Automatischer DGM-Download, Hillshade-Erstellung und Kandidaten-Cropping sind
noch nicht integriert. Für diese Vorprüfung müssen die Bilder bereits vorliegen.
Ein synthetischer Transport-/CLI-Test kann `exports/demo/map.png` verwenden;
diese Karte ist keine Grundlage zur Prüfung von Geländestrukturen.

## Ergebnisse und reproduzierbare Wiederverwendung

`reviews.json` enthält Bildnamen/-SHA256, Modellname und Gewichtsfingerabdruck,
Prompt, Parameter und validierte Befunde. Pro Bild:

- `recommendation`: inspect, uncertain oder low_priority.
- Sichtbare Strukturen, alternative Erklärungen und Grenzen der Bildqualität.
- Kurze Begründung; kein archäologischer Wahrscheinlichkeitswert.

Beurteilungen verändern die NDVI-Kandidatenliste und Scores nicht. Menschliche
Prüfung ist erforderlich. Cached Antworten sind an Bildinhalt, Modellgewichte,
Prompt und Schema gebunden. Temperatur 0 garantiert keine bitidentische Inferenz
über verschiedene Geräte/Runtimeversionen. Gleiche Gewichte und bestehender Cache
vermeiden erneute Bildverarbeitung. Grenzen: 100 Bilder maximal, Default 20,
10 MiB pro Bild, 1 MiB Serverantwort, Timeout 180 Sekunden je Anfrage.
Ungültiges JSON, falsches Antwortschema und Cloud-/Textmodelle führen zu Fehlern.
Nicht parallel in dasselbe Review-Verzeichnis schreiben.

Gewichte, Bildausschnitte und Review-Ergebnisse bleiben gitignored. Nur kompakte,
fachlich geprüfte Befunde gezielt in einen Chat übernehmen; Koordinaten bleiben
lokal. Tests verwenden Mocks und benötigen weder Ollama noch Modellgewichte.

API-Referenzen: [Ollama API](https://docs.ollama.com/api),
[Vision](https://docs.ollama.com/capabilities/vision),
[FAQ / Cloud deaktivieren](https://docs.ollama.com/faq).
