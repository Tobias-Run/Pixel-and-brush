# Arbeitsregeln
- GitHub-Migration ist vom Nutzer autorisiert. Zielkonto und Sichtbarkeit vor Erstellung klären.
- Nur Code, Tests und Dokumentation pushen; keine Daten, Bilder, Modellgewichte oder Exporte.
- Keine Zugangsdaten, Rohdaten, Registerdaten oder Kandidatenkoordinaten committen.
- CDSE_CLIENT_ID und CDSE_SECRET ausschließlich als Umgebungsvariablen.
- Netzwerkfreie Tests; reale Anmeldung nie in Tests.
- Fensterweise Rasterverarbeitung, bilinear für kontinuierliche Werte, nearest für Klassen.
- Ungültige Daten und Rasterabweichungen als geprüfte Fehler behandeln.
- Keine archäologischen Wahrscheinlichkeiten behaupten. Parameter sind unvalidierte Defaults.
- Vor Abschluss: ruff check, mypy --strict, pytest und Offline-Demo ausführen.

- Visuelle Vorprüfung über lokale Modelle: Ollama mit OLLAMA_NO_CLOUD=1, nur Loopback.
- Modellvorschläge getrennt von statistischen Scores; keine Fundstellenerkennung behaupten.
