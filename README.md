# 📺 Zoo Medien Newsletter - Webseiten-Version

## 🎯 Was ist das?

Ein automatisiertes Newsletter-System mit:
- ✅ Python-Script analysiert täglich Medien-RSS-Feeds
- ✅ Claude AI bewertet Relevanz und erstellt Zusammenfassungen
- ✅ Generiert JSON-Dateien für die Webseite
- ✅ Sendet kurze Email-Benachrichtigungen mit Link
- ✅ Moderne Webseite mit Bewertungsfunktion
- ✅ Archiv aller vergangenen Newsletter
- ✅ Lokale Speicherung der Bewertungen

## 🚀 Setup - Schritt für Schritt

### 1. GitHub Repository erstellen

```bash
# Erstelle neues Repository auf GitHub.com
# Name: media-newsletter
# Public oder Private (für GitHub Pages beide möglich)
```

### 2. GitHub Pages aktivieren

1. Gehe zu Repository → **Settings**
2. Links: **Pages**
3. **Source**: Deploy from a branch
4. **Branch**: `main` / **Folder**: `/ (root)`
5. **Save**

Deine Webseite ist dann unter:
```
https://DEIN-USERNAME.github.io/media-newsletter/
```

### 3. Dateien hochladen

#### Lokales Repository vorbereiten:

```bash
cd ~/Documents/Zoo_Media_Newsletter

# Erstelle Verzeichnisstruktur
mkdir -p docs
cp website/index.html docs/

# Git initialisieren
git init
git add .
git commit -m "Initial commit - Newsletter Website"

# Mit GitHub verbinden
git remote add origin https://github.com/DEIN-USERNAME/media-newsletter.git
git branch -M main
git push -u origin main
```

### 4. Python-Script konfigurieren

Aktualisiere die GitHub Actions Workflow-Datei:

**`.github/workflows/newsletter.yml`:**

```yaml
name: Daily Newsletter

on:
  schedule:
    - cron: '0 6 * * 1-5'  # Montag-Freitag um 7:00 MEZ
  workflow_dispatch:  # Manueller Trigger für Tests

jobs:
  generate-newsletter:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install feedparser requests
    
    - name: Generate Newsletter
      env:
        ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        GMAIL_USER: ${{ secrets.GMAIL_USER }}
        GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
        NEWSLETTER_URL: ${{ secrets.NEWSLETTER_URL }}
      run: |
        python medien_newsletter_web.py
    
    - name: Commit and Push JSON files
      run: |
        git config user.name "Newsletter Bot"
        git config user.email "bot@zooproductions.de"
        git add docs/newsletter-*.json docs/newsletter-index.json
        git commit -m "Newsletter $(date +%Y-%m-%d)" || exit 0
        git push
```

### 5. GitHub Secrets setzen

Gehe zu Repository → **Settings** → **Secrets and variables** → **Actions**

Füge hinzu:

1. **ANTHROPIC_API_KEY**: `sk-ant-api03-...`
2. **GMAIL_USER**: `tom@zooproductions.de`
3. **GMAIL_APP_PASSWORD**: `abcd efgh ijkl mnop`
4. **NEWSLETTER_URL**: `https://tomelstner.github.io/media-newsletter`

### 6. Dateien organisieren

```
media-newsletter/
├── .github/
│   └── workflows/
│       └── newsletter.yml          # GitHub Actions
├── docs/                           # GitHub Pages Verzeichnis
│   ├── index.html                  # Webseite
│   ├── newsletter-index.json       # Index aller Newsletter
│   ├── newsletter-2025-11-10.json  # Tägliche Newsletter
│   └── newsletter-2025-11-11.json
├── medien_newsletter_web.py        # Python-Script
├── requirements.txt
└── README.md
```

**Wichtig:** GitHub Pages serviert aus dem `docs/` Ordner!

### 7. Python-Script anpassen

In `medien_newsletter_web.py` die JSON-Speicherung anpassen:

```python
# Ändere JSON-Speicherpfad
filename = f"newsletter-{datum}.json"
filepath = os.path.join('/docs', filename)  # → docs/ Ordner!

# Gleiches für index.json
index_path = '/docs/newsletter-index.json'
```

## 📧 Email-Template

Die Email sieht so aus:

```
📺 Zoo Medien Newsletter

Hallo Tom,

dein täglicher Newsletter vom 10.11.2025 steht bereit!

✨ 7 relevante Artikel aus Deutschland, UK und USA
🎯 Kuratiert von Claude AI
💡 Bewerte direkt auf der Webseite

[📰 Jetzt Newsletter lesen]
     ↓
https://tomelstner.github.io/media-newsletter/?date=2025-11-10
```

## 🎨 Features der Webseite

### Haupt-Features:
- **Responsive Design** - funktioniert auf allen Geräten
- **Direkte Bewertung** - Klick auf Relevant/Nicht relevant
- **Lokale Speicherung** - Bewertungen bleiben im Browser
- **Archiv-Funktion** - Alle vergangenen Newsletter durchsuchen
- **Echtzeit-Statistiken** - Wie viele Artikel bewertet?
- **Schnell & Modern** - Smooth Animationen

### Geplante Features (Optional):
- 📊 **Hitlisten-Seite** - Top 10 Artikel der Woche/des Monats
- 🔍 **Suchfunktion** - Durchsuche alle Newsletter
- 📈 **Analytics** - Welche Quellen sind am relevantesten?
- 👥 **Team-View** - Sieh was das Team bewertet hat
- 🔔 **Push-Notifications** - Browser-Benachrichtigungen

## 🔄 Workflow

### Jeden Morgen um 7:00 Uhr:

1. **GitHub Actions** startet automatisch
2. **Python-Script**:
   - Holt RSS-Feeds von 6 Quellen
   - Claude bewertet jeden Artikel (1-10)
   - Erstellt Zusammenfassungen für relevante Artikel (Score ≥7)
   - Generiert JSON-Datei: `newsletter-2025-11-10.json`
   - Aktualisiert `newsletter-index.json`
   - Committed & pushed zu GitHub
3. **Email-Versand**:
   - Sendet kurze Benachrichtigung an alle 5 Teammitglieder
   - Mit Link zur Webseite
4. **Webseite**:
   - Lädt automatisch neueste JSON-Datei
   - Team kann Artikel lesen und bewerten

## 🐛 Troubleshooting

### "JSON nicht gefunden"
- Prüfe ob GitHub Actions erfolgreich gelaufen ist
- Schaue in Actions → Logs
- JSON-Dateien müssen im `docs/` Ordner sein

### "GitHub Pages zeigt 404"
- GitHub Pages braucht 1-2 Minuten zum Aktivieren
- Prüfe Settings → Pages ob aktiviert
- Branch muss `main` sein, Folder `/docs` oder `/ (root)`

### "Emails kommen nicht an"
- Prüfe Gmail App-Passwort
- Schaue in GitHub Actions Logs
- SMTP-Fehler? → Gmail-Sicherheitseinstellungen prüfen

### "Bewertungen verschwinden"
- Bewertungen werden im localStorage gespeichert
- Pro Browser/Gerät separat
- Cookies löschen → Bewertungen weg
- → Später: Datenbank-Backend für persistente Speicherung

## 📊 Datenstruktur

### newsletter-index.json
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

### newsletter-2025-11-10.json
```json
{
  "id": "2025-11-10",
  "datum": "10.11.2025",
  "generiert_am": "2025-11-10T07:00:00",
  "anzahl_artikel": 7,
  "artikel": [
    {
      "id": 0,
      "titel": "Netflix kündigt neue Serie an",
      "quelle": "Variety",
      "link": "https://variety.com/...",
      "zusammenfassung": "Netflix hat...",
      "score": 8,
      "datum": "Fri, 10 Nov 2025 06:30:00 GMT"
    }
  ]
}
```

## 🎯 Nächste Schritte

1. ✅ Teste das System manuell mit `workflow_dispatch`
2. ✅ Schicke Test-Newsletter an dich selbst
3. ✅ Prüfe Webseite auf allen Geräten
4. ✅ Sammle Feedback vom Team
5. 📊 Baue Hitlisten-Feature
6. 🔍 Füge Suchfunktion hinzu
7. 💾 Optional: Datenbank für persistente Bewertungen

## 💰 Kosten

- GitHub Pages: **Kostenlos**
- GitHub Actions: **2000 Minuten/Monat kostenlos**
- Anthropic Claude API: **~$0.50-1.00/Tag**
- Gmail: **Kostenlos**

**Total: ~$15-30/Monat** (nur Claude API)

## 🤝 Support

Bei Fragen oder Problemen:
- Schaue in GitHub Actions Logs
- Prüfe Browser Console (F12)
- Teste lokal: `python medien_newsletter_web.py`

---

**Viel Erfolg! 🚀**
