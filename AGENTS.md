# Arbeitsregeln
- Nur lokales Repo: kein Remote, Upload oder Publizieren ohne ausdrückliche Anweisung.
- Keine Zugangsdaten, Rohdaten, Registerdaten oder Kandidatenkoordinaten committen.
- CDSE_CLIENT_ID und CDSE_SECRET ausschließlich als Umgebungsvariablen.
- Netzwerkfreie Tests; reale Anmeldung nie in Tests.
- Fensterweise Rasterverarbeitung, bilinear für kontinuierliche Werte, nearest für Klassen.
- Ungültige Daten und Rasterabweichungen als geprüfte Fehler behandeln.
- Keine archäologischen Wahrscheinlichkeiten behaupten. Parameter sind unvalidierte Defaults.
- Vor Abschluss: ruff check, mypy --strict, pytest und Offline-Demo ausführen.
