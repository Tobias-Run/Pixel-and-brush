# CDSE: Prüfung vor Phase 2

Offizielle Dokumentation am 2026-10-14 gelesen (nur Dokumentationsabruf, keine
AOI-Abfrage, Anmeldung oder Rohdatenübertragung):

- [STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html): aktueller
  Endpoint `https://stac.dataspace.copernicus.eu/v1/`, STAC 1.1.0; der alte
  `catalogue.dataspace.copernicus.eu/stac` ist seit November 2025 abgekündigt.
  Suche muss L2A-Collection, Raum-/Zeitfilter, Pagination und Datenverfügbarkeit prüfen.
- [OData](https://documentation.dataspace.copernicus.eu/APIs/OData.html): Produktkatalog
  und `download.dataspace.copernicus.eu/odata/v1/Products(UUID)/Nodes` für Inhalte;
  authentifizierter Produktdownload mit Bearer-Token über `$value` bzw. `$zip`.
  Band-/Assetzugriff (SAFE-Nodes, S3 oder STAC-Assets) ist getrennt vom Katalog zu planen.
- [Token](https://documentation.dataspace.copernicus.eu/APIs/Token.html): die gelesene
  OData-Anleitung dokumentiert `client_id=cdse-public`, Passwort-Grant und ggf. TOTP.
  Das ist **kein Nachweis**, dass `CDSE_CLIENT_ID`/`CDSE_SECRET` als Client-Credentials
  diesen Downloadweg autorisieren. Kein stiller Wechsel auf Benutzerpasswörter.
  Vor Phase 2 passenden OAuth-/Assetdienst für diese Variablen verifizieren.
- [Quotas](https://documentation.dataspace.copernicus.eu/Quotas.html): Tabelle für
  allgemeine Nutzer nennt für S3/OData/STAC 4 gleichzeitige IAD-Verbindungen,
  20 MB/s je Verbindung, 12 TB im rollierenden 30-Tage-Fenster und 2000 Requests/min
  (Fußnoten beachten). Tokenlaufzeit 10 min, Refreshfenster 60 min. Quotas und
  Dienstklassen können sich ändern: unmittelbar vor Umsetzung erneut prüfen.
- [Bedingungen](https://dataspace.copernicus.eu/terms-and-conditions): Sentinel-Daten
  frei/voll/offen, mit Verweis auf den Sentinel Data Legal Notice; Drittanbieter-
  und abgeleitete Daten können andere Rechte haben. Attribution Copernicus/ESA.

MVP: mockbarer `Catalog`-Vertrag und lokaler `FixtureCatalog`, keine Live-HTTP-
Implementierung. Tests prüfen leere Treffer, räumlich/zeitliche Filter und Limits.

Phase 2 benötigt zusätzlich: dokumentierten OAuth-Vertrag, vertrauliche env-only
Credentials, Tokenrefresh ohne Secret-Logs, Host-/Redirectkontrolle bei Bearer-Tokens,
Streamingdownloads mit tatsächlichem Byte-Limit, atomare Cache-Dateien und Hashprüfung,
Pagination, begrenzte Retries/429-Backoff sowie Produkt-IDs, Original-URLs und
Bandauflösungen als Herkunft. Roh-DN-Kalibrierung einschließlich BOA-Offsets,
SCL-Nearestrasterung und AOI-Zielgitter dürfen nicht implizit geraten werden.
Reale Anmeldung optional und niemals Teil der Tests.
