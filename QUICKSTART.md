# 🚀 Quick Start Guide - Newsletter Webseite

## Was du bekommst:

1. **Moderne Webseite** statt langer HTML-Emails
2. **Kurze Email** jeden Morgen mit Link
3. **Direkt bewerten** auf der Webseite (funktioniert!)
4. **Archiv** aller vergangenen Newsletter
5. **Statistiken** - wie viele Artikel bewertet?

---

## ⚡ 5-Minuten-Setup

### Schritt 1: GitHub Repository erstellen

1. Gehe zu https://github.com/new
2. **Repository name**: `media-newsletter`
3. ✅ **Public** (für kostenlose GitHub Pages)
4. ✅ **Add a README file**
5. **Create repository**

### Schritt 2: Dateien hochladen

**Via GitHub Website (Einfachste Methode):**

1. Klicke auf **"Add file"** → **"Upload files"**

2. **Ziehe diese Dateien rein:**
   - `medien_newsletter_web.py`
   - `index.html`
   - `README.md`

3. Klicke **"Commit changes"**

4. **Erstelle `.github/workflows/` Ordner:**
   - Klicke **"Add file"** → **"Create new file"**
   - Dateiname: `.github/workflows/newsletter.yml`
   - Kopiere Inhalt aus der `newsletter.yml` Datei
   - **Commit changes**

### Schritt 3: GitHub Pages aktivieren

1. Gehe zu **Settings** (oben rechts)
2. Linke Seite: **Pages**
3. **Source**: `Deploy from a branch`
4. **Branch**: `main`
5. **Folder**: `/ (root)` → **Save**

**Deine URL:** `https://DEIN-USERNAME.github.io/media-newsletter/`

### Schritt 4: Secrets hinzufügen

1. **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** (4x klicken):

```
Name: ANTHROPIC_API_KEY
Value: sk-ant-api03-...

Name: GMAIL_USER  
Value: tom@zooproductions.de

Name: GMAIL_APP_PASSWORD
Value: abcd efgh ijkl mnop

Name: NEWSLETTER_URL
Value: https://DEIN-USERNAME.github.io/media-newsletter
```

### Schritt 5: Ersten Newsletter generieren (Test)

1. Gehe zu **Actions** (oben)
2. Links: **"Daily Newsletter Generator"**
3. Rechts: **"Run workflow"** → **"Run workflow"**
4. Warte 3-5 Minuten...
5. ✅ **Fertig!** Newsletter wurde generiert

### Schritt 6: Webseite öffnen

Öffne: `https://DEIN-USERNAME.github.io/media-newsletter/`

🎉 **Fertig!**

---

## 📧 Wie sieht die Email aus?

**Vorher:**
```
[Riesige HTML-Email mit allen Artikeln]
[Scrollen... scrollen... scrollen...]
[JavaScript funktioniert nicht]
```

**Jetzt:**
```
📺 Zoo Medien Newsletter

Hallo Tom,

dein täglicher Newsletter vom 10.11.2025 steht bereit!

✨ 7 relevante Artikel
🎯 Kuratiert von Claude AI  
💡 Bewerte direkt auf der Webseite

        [📰 Jetzt Newsletter lesen]
                  ↓
    https://deine-url.github.io/media-newsletter
```

**Klick → Webseite → Artikel lesen → Bewerten → Fertig!**

---

## 🎨 Features der Webseite

### Was funktioniert JETZT:

✅ **Responsive Design** - Mobile, Tablet, Desktop
✅ **Bewertungs-Buttons** - Klick auf "Relevant" / "Nicht relevant"  
✅ **Sofortiges Feedback** - Buttons färben sich grün/rot
✅ **Lokale Speicherung** - Bewertungen bleiben gespeichert
✅ **Archiv-Funktion** - Alle Newsletter der letzten Tage/Wochen
✅ **Echtzeit-Stats** - "5 von 7 Artikeln bewertet"
✅ **Datum-Auswahl** - Dropdown für alle Newsletter
✅ **Smooth Animationen** - Modern & professionell

### Was kommt als nächstes:

📊 **Hitlisten-Seite**
   - Top 10 Artikel diese Woche
   - Top 10 Artikel diesen Monat
   - Meistbewertete Quellen

🔍 **Suchfunktion**
   - Durchsuche alle Newsletter
   - Filter nach Quelle, Datum, Score

📈 **Team-Analytics**
   - Was bewertet das Team als relevant?
   - Welche Quellen sind am wertvollsten?

🔔 **Browser-Benachrichtigungen**
   - "Neuer Newsletter verfügbar!"

---

## 🐛 Probleme?

### "Webseite zeigt 404"
→ GitHub Pages braucht 1-2 Minuten nach Aktivierung
→ Prüfe ob Branch auf `main` steht

### "Newsletter nicht gefunden"
→ GitHub Actions noch nicht gelaufen? Schaue unter "Actions"
→ Manuell triggern mit "Run workflow"

### "Keine Email erhalten"
→ Prüfe Gmail Secrets (richtig eingetragen?)
→ Schaue in GitHub Actions Logs nach Fehlern

### "Bewertungen verschwinden"
→ Bewertungen sind im Browser-localStorage
→ Pro Gerät/Browser separat gespeichert
→ Cookies löschen → Bewertungen weg

---

## 📊 Wie funktioniert das System?

```
Jeden Morgen 7:00 Uhr:
    ↓
GitHub Actions startet
    ↓
Python-Script läuft:
  - Holt 120 Artikel von 6 RSS-Feeds
  - Claude bewertet jeden (Score 1-10)
  - Filtert relevante (Score ≥7)
  - Erstellt Zusammenfassungen
  - Generiert JSON-Datei
    ↓
JSON wird committed & gepusht
    ↓
Email-Versand:
  - 5 kurze Emails an Team
  - Mit Link zur Webseite
    ↓
Team öffnet Webseite:
  - Liest Artikel
  - Bewertet direkt
  - Bewertungen werden lokal gespeichert
    ↓
Fertig! 🎉
```

---

## 💾 Datenformat

### JSON-Datei-Struktur:

**newsletter-2025-11-10.json:**
```json
{
  "id": "2025-11-10",
  "datum": "10.11.2025",
  "anzahl_artikel": 7,
  "artikel": [
    {
      "id": 0,
      "titel": "Netflix kündigt neue Serie an",
      "quelle": "Variety",
      "link": "https://...",
      "zusammenfassung": "Netflix hat heute...",
      "score": 8
    }
  ]
}
```

**newsletter-index.json:**
```json
{
  "newsletter": [
    {
      "id": "2025-11-10",
      "datum": "10.11.2025",
      "anzahl_artikel": 7,
      "url": "newsletter-2025-11-10.json"
    }
  ]
}
```

---

## 🎯 Nächste Schritte

1. ✅ **Teste die Webseite** auf verschiedenen Geräten
2. ✅ **Sammle Team-Feedback** - was fehlt noch?
3. 📊 **Baue Hitlisten-Feature** (nächstes Update!)
4. 🔍 **Füge Suche hinzu**
5. 💾 **Optional: Datenbank** für persistente Team-Bewertungen

---

## 💰 Kosten

- **GitHub Pages**: Kostenlos ✅
- **GitHub Actions**: 2000 Min/Monat kostenlos ✅  
- **Claude API**: ~$0.50-1.00/Tag = ~$15-30/Monat
- **Gmail**: Kostenlos ✅

**Total: ~$15-30/Monat** 💸

---

## 🚀 Pro-Tipp

**Für schnelleres Testing:**

Ändere in `.github/workflows/newsletter.yml`:

```yaml
on:
  schedule:
    - cron: '0 6 * * 1-5'
  workflow_dispatch:  # ← Das hier aktivieren!
```

Dann kannst du unter **Actions** manuell testen ohne auf 7:00 Uhr zu warten!

---

**Viel Erfolg! Bei Fragen einfach melden! 💪**
