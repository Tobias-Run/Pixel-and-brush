# Must-have: Bekannte Strukturen und wiederholte Sichtungen abgleichen

**Priorität: Must-have. Status: spezifiziert, noch nicht vollständig implementiert.**
Festgelegt am 2026-10-15. Verbindliche Voraussetzung, bevor eine priorisierte Liste
als fachlich vorgeprüfte Kandidatenliste verwendet wird. Ungeprüfte Software-/Demo-
Läufe dürfen weiterhin Ergebnisse erzeugen, müssen die fehlende Prüfung jedoch
im Bericht und Export ausdrücklich kennzeichnen. Dies ist eine Anforderung,
keine Beschreibung bereits vorhandener Funktionen.

## Ziel und fachliche Unterscheidung

Die Pipeline soll bekannte Strukturen nicht erneut als vermeintliche Neufunde
priorisieren und dieselbe Struktur nicht mehrfach zählen. Eine bekannte
archäologische Struktur ist kein statistischer Fehlalarm, aber kein neuer Kandidat.
Moderne Strukturen und Verarbeitungsartefakte sind mögliche andere Erklärungen.
**Kein Registertreffer bedeutet niemals „unentdeckt“.** Fehlende, eingeschränkte,
veraltete oder unvollständige Register begrenzen die Aussage ausdrücklich.

## Verbindliche Funktionen

1. **Lokale Referenzen abgleichen.** Rechtmäßig nutzbare Denkmal-/Fundstellenregister
   in GeoJSON/CSV importieren, CRS und Geometrien prüfen und vor der Priorisierung
   räumlich abgleichen. Für Esselbach Verfügbarkeit, Rechte und Datenstand beim
   Bayerischen Landesamt für Denkmalpflege prüfen; kein automatisches Scraping
   oder externer Registerabruf. Quelle, Lizenz, Stand und räumliche Abdeckung
   erfassen. Lageunsicherheit als konfigurierbaren Puffer in Metern in geeignetem
   projiziertem CRS behandeln. Pufferwert und Begründung exportieren; kein pauschaler
   wissenschaftlich validierter Standard wird behauptet. Direkte Überschneidung,
   reine Puffernähe und fachlich bestätigte Zuordnung getrennt speichern.
2. **Moderne Erklärungen berücksichtigen.** Lokale, lizenzierte Wege-, Gebäude-,
   Entwässerungs- und Landnutzungsdaten als Belege verwenden. Überschneidungen
   kennzeichnen und die Prüfpriorität nachvollziehbar beeinflussen; sie beweisen
   keine moderne Ursache und dürfen Kandidaten nicht stillschweigend löschen.
3. **Sichtungen zusammenführen.** Überlappende Tiles, mehrere Hillshade-Azimute,
   verschiedene Datenquellen und wiederholte Läufe als Beobachtungen derselben
   räumlichen Struktur verknüpfen. Deterministische Zuordnungsregeln mit
   konfigurierbaren Abstands-/Überlappungskriterien; keine Zusammenführung nur
   wegen ähnlicher Modelltexte. Nahe, aber getrennte Strukturen erhalten getrennte
   Identitäten. Konflikte und Mehrdeutigkeiten bleiben sichtbar.
4. **Dauerhaftes lokales Prüfprotokoll.** Stabile Kandidaten-IDs unabhängig von Rang
   und Laufzeit verwenden. Beobachtungen, Referenzzuordnungen und manuelle Urteile
   mit Datum, Prüfer, Begründung und Quellen versioniert erhalten. Geometrieänderungen,
   Splits/Merges und geänderte Referenzen nachvollziehbar behandeln; frühere Urteile
   nicht still auf veränderte Kandidaten übertragen oder überschreiben. Erneute
   Verarbeitung darf verworfene Sichtungen nicht als ungeprüfte Neuzugänge ausgeben.
5. **Belegte Status und transparente Priorisierung.** Registerabgleich,
   Erklärungsbewertung und Prüfstatus als getrennte Felder speichern, da sie
   gleichzeitig zutreffen können. Statistischen Anomalie-Score unverändert erhalten;
   fachliche Prüfpriorität mit separater Regel und Begründung ausgeben.

## Darstellung und Exporte

Folgende Kennzeichnungen müssen kombinierbar sein:

| Kennzeichnung | Voraussetzung |
| --- | --- |
| Registerüberschneidung | Direkte räumliche Überschneidung; Zuordnung noch nicht zwingend bestätigt |
| Register in Puffernähe | Nur der Unsicherheitspuffer trifft; keine bestätigte Identität |
| Bekannt zugeordnet | Fachlich bestätigte, belegte Zuordnung zu einer bekannten Struktur |
| Bereits geprüft | Lokales manuelles Urteil mit Prüfdatum und Begründung vorhanden |
| Moderne Erklärung plausibel | Belegte mögliche Erklärung; keine automatische Ausschlussdiagnose |
| Offen | Keine belastbare Zuordnung; keine Aussage über Neuheit |
| Nicht geprüft / Referenzlücke | Abgleich fehlt oder Abdeckung/Datenstand ist unzureichend |

GeoJSON, CSV, Bericht und Manifest enthalten Status, stabile ID, verknüpfte
Beobachtungs-IDs, verwendete Referenz-IDs/-Quellen, Datenstand, Puffer/Matchingregeln,
Zuordnungsbegründung und vorhandenes Prüfdatum. Bekannte und bereits geprüfte Fälle
bleiben einsehbar, erscheinen aber nicht als neue ungeprüfte Kandidaten. Sensible
Referenzen und Koordinaten bleiben lokal und gitignored. Die lokale Vision-KI
beschreibt sichtbare Formen; sie darf weder Neuheit noch Registerstatus erfinden.

## Abnahmekriterien (netzwerkfrei zu testen)

- [ ] Direkte Registerüberschneidung, reine Puffernähe und kein Treffer sind unterscheidbar.
- [ ] Kein Treffer wird als „offen“ mit dokumentierter Referenzabdeckung ausgegeben,
      niemals als „unentdeckt“; fehlende/veraltete Referenzen werden gekennzeichnet.
- [ ] Register mit abweichendem CRS werden explizit korrekt transformiert;
      fehlendes CRS/ungültige Geometrien führen zu geprüften Fehlern.
- [ ] Moderne Referenzüberschneidung erzeugt eine belegte Kennzeichnung, löscht
      keinen Kandidaten und verändert nicht den statistischen Anomalie-Score.
- [ ] Überlappende Tiles und vier Beleuchtungsrichtungen ergeben verknüpfte
      Beobachtungen statt vier unabhängiger Kandidaten.
- [ ] Wiederholte Läufe erhalten stabile IDs und Prüfstatus auch bei geänderter
      Rangfolge; getrennte nahe Strukturen bleiben getrennt.
- [ ] Geometrie-/Referenzänderungen und Split-/Merge-Konflikte sind im Protokoll
      nachvollziehbar und erfordern gegebenenfalls erneute Prüfung.
- [ ] Exporte enthalten vollständige Belege und sichtbare Prüfungslücken;
      bekannte Fälle bleiben auffindbar, ohne als ungeprüfte Neuzugänge zu erscheinen.
- [ ] Alle Fälle sind mit synthetischen Registern, Strukturen und Bewertungen
      prüfbar, ohne Zugangsdaten, Netzwerk oder Veröffentlichung echter Koordinaten.

## Aktueller Implementierungsstand

`evaluation.py` prüft derzeit lediglich direkte räumliche Überschneidung mit einem
optionalen lokalen Register und setzt `register_overlap`. Die Terrain-Ausgabe
enthält Bildpakete, noch keine klassifizierten Terrain-Kandidaten. Die
`candidate-0001`-IDs aus `candidates.py` sind rangabhängig und damit **noch keine
stabilen Identitäten**. Unsicherheitspuffer, getrennte Statusfelder, räumliche
Deduplizierung, dauerhafte Kandidatenverwaltung und Prüfprotokoll sind noch offen.
Die Vorlage `templates/manual-review.csv` ersetzt diese Funktionen nicht.
