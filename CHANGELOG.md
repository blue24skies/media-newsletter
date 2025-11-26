# Changelog

Alle wesentlichen Änderungen am Zoo Medien Newsletter System werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [Unreleased]

### Geplant
- Erweiterung der Quellen um weitere internationale Medien
- Dashboard für Newsletter-Statistiken
- Personalisierte Relevanz-Scores pro Team-Mitglied

---

## [1.3.0] - 2025-11-26

### 🐛 Fixed - Cache-Problem bei Newsletter-Anzeige

**Problem:** Beim Öffnen des Newsletter-Links wurde eine leere Seite angezeigt ("Keine Artikel verfügbar"). Nach einem Browser-Refresh (Strg+R) wurden die Artikel korrekt geladen.

**Ursache:** Browser und GitHub Pages cachten die JSON-Dateien aggressiv, wodurch veraltete oder leere Versionen angezeigt wurden.

**Lösung:** 
- Implementierung von Cache-Busting mit dynamischen Timestamp-Parametern
- `fetch('newsletter-2025-11-26.json')` → `fetch('newsletter-2025-11-26.json?t=1732615358924')`
- Jeder Request erhält eine einzigartige URL → Cache wird umgangen

**Betroffene Dateien:**
- `docs/index.html` - Zeile ~535

**Ergebnis:** Newsletter lädt sofort die aktuellste Version, kein manueller Refresh mehr nötig.

---

## [1.2.0] - 2025-11-25

### 🐛 Fixed - Fehlende Index-Aktualisierung

**Problem:** Newsletter-Link zeigte leere Seite. Artikel waren nur über den Umweg "Archiv → Datum klicken" erreichbar.

**Ursache:** Nach dem Newsletter-Lauf wurden die Index-Dateien (`newsletter-index.json` und `newsletter-data.json`) nicht aktualisiert. Git Commit enthielt nur die tagesaktuelle JSON-Datei, wodurch die Webseite nicht wusste, dass ein neuer Newsletter existiert.

**Lösung:**
- Neue Funktion `aktualisiere_newsletter_index()` erstellt
- Funktion wird automatisch nach jedem Newsletter-Lauf aufgerufen
- Scannt alle vorhandenen `newsletter-*.json` Dateien
- Aktualisiert beide Index-Dateien automatisch

**Betroffene Dateien:**
- `medien_newsletter_web.py`:
  - Neue Funktion: `aktualisiere_newsletter_index()` (Zeile ~967)
  - Aufruf in `main()` nach `speichere_als_json()` (Zeile ~1278)

**Ergebnis:** Git Commits enthalten jetzt 3 Dateien statt 1:
- `newsletter-YYYY-MM-DD.json`
- `newsletter-index.json`
- `newsletter-data.json`

---

## [1.1.0] - 2025-11-24

### 🚀 Improved - Intelligente Duplikat-Erkennung

**Problem:** Von 60 relevanten Artikeln wurden 55 als Duplikate gefiltert, nur 5 wurden versendet. Das System war zu aggressiv beim Filtern.

**Ursache:** Die alte Duplikat-Erkennung prüfte nur URLs. Artikel-Updates mit gleicher URL aber neuem Titel/Inhalt wurden fälschlicherweise als Duplikate markiert.

**Beispiel:**
```
Archiv:  "RTL verliert Champions League an Paramount+"
Heute:   "RTL-Chef kommentiert Champions League Verlust"
         → Gleiche URL → ALT: Duplikat ✗
                      → NEU: Update ✓
```

**Lösung:**
- Neue intelligente Duplikat-Erkennung mit Titel-Ähnlichkeitsberechnung
- Verwendet Jaccard-Ähnlichkeit auf Wortbasis
- Threshold: 85% Ähnlichkeit = Duplikat
- URLs mit deutlich unterschiedlichen Titeln (<85%) werden als Updates durchgelassen

**Betroffene Dateien:**
- `medien_newsletter_web.py`:
  - `pruefe_auf_duplikat()` - erweitert um Titel-Vergleich
  - `berechne_titel_aehnlichkeit()` - neue Hilfsfunktion
  - Funktionsaufruf angepasst: übergibt jetzt Titel und Datum

**Ergebnis:**
- **Vorher:** 55 Duplikate gefiltert (92%), 5 Artikel versendet
- **Nachher:** ~10-15 Duplikate gefiltert (17-25%), ~45-50 Artikel versendet
- **9x mehr Content** im Newsletter!

### Detailliertes Logging

Die neue Duplikat-Erkennung gibt aufschlussreiches Feedback:
```
📋 Duplikat erkannt: Exakt gleicher Titel (zuletzt: 2025-11-20)
📋 Duplikat erkannt: 87% Titel-Ähnlichkeit (zuletzt: 2025-11-21)
✨ Artikel-Update erkannt: Gleiche URL, aber neuer Titel - wird gesendet!
```

---

## [1.0.0] - 2025-11-13

### 🎉 Initial Release - Komplett automatisiertes Newsletter-System

**Features:**
- Automatische Artikel-Sammlung aus 11 Quellen (DE, UK, USA)
- KI-basierte Relevanz-Bewertung mit Claude API
- Intelligente Zusammenfassungen aller Artikel
- Supabase-Integration für Archivierung und Learning
- GitHub Actions Automation (täglich 09:00 Uhr)
- Web-Interface mit Rating-System
- Email-Versand an 5 Team-Mitglieder

**Quellen:**
- **Deutschland (7):** DWDL, Horizont Medien, W&V, Quotenmeter, kress, meedia, turi2
- **UK (1):** Guardian Media
- **USA (3):** Variety, Deadline, Hollywood Reporter

**Architektur:**
- **Backend:** Python 3.11, GitHub Actions
- **Database:** Supabase (PostgreSQL)
- **AI:** Anthropic Claude API
- **Frontend:** HTML/CSS/JavaScript, GitHub Pages
- **Email:** Gmail SMTP

---

## Bekannte Einschränkungen

### Aktuelle Limitations:
- W&V und Quotenmeter RSS-Feeds liefern aktuell 0 Artikel (Feed-Problem bei Publishern)
- turi2 Web-Scraping findet keine Artikel (Website-Struktur geändert?)
- Learning-System lernt nur aus Feedback innerhalb des aktuellen Projekts

### Geplante Verbesserungen:
- Monitoring für fehlerhafte Feeds
- Fallback-Mechanismen bei Feed-Ausfällen
- Erweiterte Analytics und Reporting

---

## Migration & Updates

### Von 1.0.0 zu 1.1.0+ (Empfohlen)
```bash
# 1. Backup der Supabase-Datenbank
# Falls vorhanden, altes Archiv sichern

# 2. Datenbank zurücksetzen (optional, für Clean Start)
DELETE FROM newsletter_articles_archive;
DELETE FROM newsletter_runs;

# 3. Files aktualisieren
git pull origin main

# 4. Nächster Newsletter-Lauf testet alle Fixes
```

### Breaking Changes
Keine breaking changes zwischen Versionen. Alle Updates sind rückwärtskompatibel.

---

## Support & Troubleshooting

### Häufige Probleme

**Problem: Zu viele/wenige Duplikate?**
```python
# In medien_newsletter_web.py, Zeile ~115
if title_similarity > 0.85:  # Anpassen: 0.80-0.95
```
- **Höher (0.90):** Weniger streng → mehr Updates durchlassen
- **Niedriger (0.80):** Strenger → mehr als Duplikate filtern

**Problem: Leere Seite trotz Fixes?**
1. Browser DevTools → Network Tab öffnen
2. Prüfen ob `?t=...` Parameter vorhanden
3. Status sollte 200 sein (nicht 304)
4. Hard Refresh: Strg+Shift+R (Chrome) / Cmd+Shift+R (Mac)

**Problem: Git committed nur 1 Datei?**
1. GitHub Actions Logs prüfen
2. Nach Fehlermeldungen bei `aktualisiere_newsletter_index()` suchen
3. Prüfen ob `glob` Modul verfügbar ist

### Logs & Monitoring

**GitHub Actions Logs:** 
```
Repository → Actions → Newsletter Run → Logs
```

**Wichtige Log-Meldungen:**
```
✅ JSON gespeichert: newsletter-YYYY-MM-DD.json
✅ Index aktualisiert: X Newsletter
✅ Daten-Archiv aktualisiert: X Newsletter
```

---

## Contributors

**Entwicklung & Maintenance:**
- Tom @ Zoo Productions

**AI Assistant:**
- Claude (Anthropic) - Code-Entwicklung und Bugfixes

---

## License

Proprietary - Zoo Productions GmbH  
Nur für internen Gebrauch bei Zoo Productions.

---

## Kontakt

Bei Fragen oder Problemen:
- **Email:** tom@zooproductions.de
- **Repository:** https://github.com/blue24skies/media-newsletter
