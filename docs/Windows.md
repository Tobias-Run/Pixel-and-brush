# Nächste Woche: Windows 11 / RTX 5060 Ti (16 GB)

Code und Anleitungen liegen öffentlich im GitHub-Repo. Daten und Bilder werden
lokal erzeugt oder heruntergeladen; keine Artefakte werden auf GitHub veröffentlicht.
Die hier heruntergeladenen Esselbach-Daten liegen im Cloud-Workspace; das Skript
lädt dieselben Quellen auf deinem PC neu. Kein Transfer privater Ergebnisse nötig.

## 1. Einmalige Installation

Aktuellen NVIDIA-Treiber, Git, Python **3.12 (64 Bit, mit Python Launcher)** und
Ollama für Windows installieren. Noch keine CUDA-/PyTorch-Installation nötig:
Ollama verwaltet die Inferenzlaufzeit selbst. PowerShell im gewünschten Arbeitsordner:

```powershell
git clone https://github.com/Tobias-Run/Pixel-and-brush.git
cd Pixel-and-brush
.\scripts\windows-start.ps1 -Stage Setup
```

Wenn PowerShell Skripte wegen der Execution Policy blockiert, die lokale Richtlinie
zuerst prüfen. Alternativ die Einzelbefehle aus dem Skript ausführen; keine globale
Lockerung erforderlich. Das Skript aktiviert die venv nicht, sondern nutzt ihre
Programme direkt. Keine Administratorrechte für das Projekt erforderlich.

`Setup` installiert Abhängigkeiten, prüft Ruff/mypy/pytest, Konfiguration und die
Offline-NDVI-Demo. Zusätzlicher Offline-Terrainweg:

```powershell
.\.venv\Scripts\archaeo.exe terrain-demo
```

Diese Reliefstruktur ist synthetisch und kein Fundstellen-Trainingsdatensatz.

## 2. Esselbach-Daten und Vorschau

```powershell
.\scripts\windows-start.ps1 -Stage Data
Start-Process .\exports\esselbach\terrain\overview.html
```

Der Erstdownload umfasst für die konfigurierte AOI derzeit **36 Kacheln, ca. 126 MB**.
Cache-/Kachellimits gelten auch bei Wiederholung. Für Daten, Mosaik, vier Hillshade-
Bänder, PNGs und virtuelle Umgebung mindestens 3 GB freien Speicher vorsehen;
Modellgewichte benötigen zusätzlichen Platz. Die Bildübersicht funktioniert lokal
ohne externe Karten oder Webdienste. Quelle: Bayerische Vermessungsverwaltung,
DGM1/DTM, 1 m, EPSG:25832, DHHN2016, CC BY 4.0. Aufnahmejahre noch prüfen.

Jedes PNG zeigt denselben Ausschnitt unter vier Beleuchtungsrichtungen. Panels
werden nicht auf 10 m heruntergerechnet; 1 Bildpixel entspricht 1 m Gelände.
Überlappende Ausschnitte zeigen teilweise dieselbe Struktur, nicht unabhängige Belege.
Schwache Strukturen können beim modellinternen Bildresize verloren gehen.

## 3. Modell vorinstallieren, anschließend Cloud abschalten

Ausgangspunkt: `qwen2.5vl:7b` (quantisiert). 16 GB VRAM sollten für einen einzelnen
Ausschnitt gut geeignet sein, aber VRAM-Verbrauch und Qualität sind noch nicht auf
deinem PC getestet. Zunächst keine parallelen Modellaufrufe.

```powershell
ollama pull qwen2.5vl:7b
ollama show qwen2.5vl:7b
```

Für offline Inferenz **Ollama aus dem Tray vollständig beenden**. In einer separaten
PowerShell starten und dieses Fenster geöffnet lassen:

```powershell
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
ollama serve
```

Eine Umgebungsvariable in einem anderen Fenster ändert keinen bereits laufenden
Server. Das Projekt startet/stoppt bestehende Dienste nicht und lädt keine Modelle
automatisch. Nach dem Modelldownload lässt sich Inferenz zusätzlich ohne externen
Netzzugang testen. Loopback muss erreichbar bleiben.

## 4. Kleiner Test, dann ganze Bildpakete

Im Projektfenster zunächst das erste Paket (maximal 20 Bilder):

```powershell
.\.venv\Scripts\archaeo.exe review-images `
  exports/esselbach/terrain/tiles/batch-001 --model qwen2.5vl:7b `
  --output exports/esselbach/local-review/batch-001
```

Während des Laufs in einem anderen Fenster `ollama ps` prüfen: GPU-Zuordnung
kontrollieren. Danach alle Pakete sequenziell prüfen:

```powershell
.\scripts\windows-start.ps1 -Stage Review
```

Caches werden wiederverwendet. `reviews.json` je Paket enthält Laufzeiten und
`cache_hit`, Modellfingerabdruck, Bildhashes und Befunde. Erst prüfen, ob das Modell
überhaupt subtile Geländeformen sinnvoll beschreibt. Ohne diese Prüfung keinen
mehrstündigen Gesamtlauf als aussagekräftige Erkennung betrachten.
Wenn VRAM knapp wird: andere GPU-Verbraucher schließen, neu starten, kleinere
Bildpakete/Ausschnitte prüfen. Das 180-s-Timeout pro Bild kann langsame CPU-Fallbacks
abbrechen. `Stage All` kombiniert Setup/Data/Review, setzt aber einen bereits
installierten und korrekt gestarteten lokalen Modellserver voraus.

## 5. Fachliche Sichtung und nächster Ausbau

Bildprüfung und Modellvorschläge sind getrennt von der NDVI-Kandidatenliste.
Prüfe Wege, Entwässerung, Forstwirtschaft, Feldgrenzen und Raster-/NoData-Artefakte
als Alternativerklärungen. Kein Modellurteil macht eine Struktur archäologisch.
Eine Vorlage für manuelle Bewertungen liegt unter `templates/manual-review.csv`;
gefüllte Bewertungen unter `data/` oder `exports/` ablegen.

Danach: Aufnahmejahre/LiDAR-Qualität klären, lokale Register und Landnutzung mit
korrekten Lizenzen einbeziehen, kontrollierte bekannte/nichtarchäologische Beispiele
bewerten und erst dann Regeln/Prompts anpassen. Sentinel-CDSE bleibt eine getrennte,
noch offene Integration; ein Live-NDVI-Lauf wird hier nicht vorgetäuscht.

PowerShell-Skript wurde in dieser Linux-Umgebung geschrieben und durchgesehen,
aber noch nicht auf Windows ausgeführt. Tests prüfen Python-Software, nicht
archäologische Leistung oder GPU-Kompatibilität. Vor Feldarbeit zuständige
Denkmalbehörde kontaktieren. Koordinaten/Ergebnisse nicht veröffentlichen.
