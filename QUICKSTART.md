# 🚀 Quick Start - Archiv-System Integration

## ✅ Was ist fertig:

1. **medien_newsletter_web.py** - Erweitert mit Duplikat-Erkennung und Archivierung
2. **docs/archive.html** - Neue Archiv-Übersichtsseite
3. **docs/index.html** - Mit Archiv-Navigation
4. **requirements.txt** - Supabase dependency hinzugefügt
5. **supabase_archive_setup.sql** - SQL für Tabellen

## 📋 Installation in 5 Schritten:

### Schritt 1: SQL in Supabase ausführen ⚡

```sql
-- Kopiere den Inhalt von supabase_archive_setup.sql
-- Füge ihn ein in: Supabase Dashboard → SQL Editor → New Query
-- Klicke: Run
```

✅ Erstellt 2 Tabellen: `newsletter_articles_archive` + `newsletter_runs`

### Schritt 2: Supabase URLs in HTML eintragen 🔧

**In `docs/archive.html` (Zeile ~320):**
```javascript
const SUPABASE_URL = 'https://deinproject.supabase.co';  // ← Deine URL
const SUPABASE_ANON_KEY = 'eyJhbGciOiJ...';  // ← Dein Key
```

**In `docs/index.html` (Zeile ~540):**
```javascript
const SUPABASE_URL = 'https://deinproject.supabase.co';  // ← Deine URL
const SUPABASE_ANON_KEY = 'eyJhbGciOiJ...';  // ← Dein Key
```

💡 Keys findest du in: Supabase Dashboard → Settings → API

### Schritt 3: Dateien zu GitHub pushen 📤

```bash
# Option A: Alle auf einmal
git add medien_newsletter_web.py docs/ requirements.txt
git commit -m "✨ Add archive system with duplicate detection"
git push origin main

# Option B: Einzeln
git add medien_newsletter_web.py
git commit -m "✨ Add Supabase archive integration"

git add docs/archive.html docs/index.html
git commit -m "✨ Add archive page and navigation"

git add requirements.txt
git commit -m "📦 Add supabase dependency"

git push origin main
```

### Schritt 4: Testen 🧪

**Lokaler Test (optional):**
```bash
# Installiere dependencies
pip install supabase --break-system-packages

# Setze environment variables
export SUPABASE_URL="https://deinproject.supabase.co"
export SUPABASE_KEY="dein-service-key"

# Teste das Script
python medien_newsletter_web.py
```

**Erwartete Ausgabe:**
```
✅ Supabase verbunden - Archiv aktiv
🤖 SAMMLE UND BEWERTE ARTIKEL
...
🔍 PRÜFE AUF DUPLIKATE
✅ 25 neue Artikel
⏭️ 5 Duplikate übersprungen
💾 ARCHIVIERE 25 ARTIKEL
✓ Artikel archiviert...
```

### Schritt 5: Archiv-Seite öffnen 🌐

https://blue24skies.github.io/media-newsletter/archive.html

✅ Sollte alle Newsletter anzeigen
✅ Filter funktionieren
✅ Klick auf Newsletter lädt historische Ansicht

## 🎯 Das war's!

Ab jetzt:
- ✅ Keine Duplikate mehr
- ✅ Alle Artikel im Archiv
- ✅ Statistiken verfügbar
- ✅ Team kann alte Newsletter durchsuchen

## 🆘 Probleme?

### "⚠️ Supabase nicht verfügbar"
→ Prüfe GitHub Secrets: SUPABASE_URL und SUPABASE_KEY

### "⚠️ Duplikat-Check Fehler"
→ Prüfe ob SQL-Script ausgeführt wurde

### Archiv-Seite zeigt Fehler
→ Prüfe Browser Console (F12)
→ Sind URLs in HTML korrekt?

### "UNIQUE constraint violation"
→ Normal! Artikel existiert bereits (Duplikat)

## 📁 Datei-Übersicht:

```
✅ medien_newsletter_web.py     - Haupt-Script (erweitert)
✅ docs/index.html              - Newsletter-Seite (mit Navigation)
✅ docs/archive.html            - Archiv-Übersicht (neu)
✅ requirements.txt             - Dependencies (supabase added)
✅ supabase_archive_setup.sql  - SQL Setup
📖 INTEGRATION_COMPLETE.md     - Ausführliche Doku
📖 QUICK_START.md              - Diese Datei
```

## 🎬 Fertig!

Dein Newsletter-System ist jetzt komplett mit Archiv. Viel Erfolg! 🚀
