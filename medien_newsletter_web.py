#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Medien Newsletter Automation - Webseiten-Version
Generiert JSON-Daten und sendet kurze Email mit Link zur Webseite
"""

import feedparser
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import time
import sys
import os
import json

# ============================================================================
# KONFIGURATION
# ============================================================================

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GMAIL_USER = os.environ.get('GMAIL_USER', 'tom@zooproductions.de')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')

# Team-Empfänger
EMPFAENGER = {
    'Tom': 'tom@zooproductions.de',
    'Kat': 'kat@zooproductions.de',
    'Dom': 'dom@zooproductions.de',
    'Aurelia': 'aurelia@zooproductions.de',
    'Christina': 'christina@zooproductions.de'
}

# Newsletter-Webseite URL
NEWSLETTER_URL = os.environ.get('NEWSLETTER_URL', 'https://tomelstner.github.io/media-newsletter')

# RSS-Feeds
RSS_FEEDS = {
    'DWDL': 'https://www.dwdl.de/rss/allethemen.xml',
    'Horizont Medien': 'https://www.horizont.net/news/feed/medien/',
    'Variety': 'https://variety.com/feed/',
    'Deadline': 'https://deadline.com/feed/',
    'Hollywood Reporter': 'https://www.hollywoodreporter.com/feed/',
    'Guardian Media': 'https://www.theguardian.com/media/rss'
}

# ============================================================================
# CLAUDE API FUNKTIONEN
# ============================================================================

def bewerte_artikel_mit_claude(titel, beschreibung):
    """Bewertet Artikel-Relevanz (1-10)"""
    prompt = f"""Du bist Experte für die Medienindustrie. Bewerte diesen Artikel auf seine Relevanz für einen deutschen TV-Produzenten.

Artikel:
Titel: {titel}
Beschreibung: {beschreibung}

Bewerte auf einer Skala von 1-10:
10 = Extrem relevant (neue Formatideen, Quotenrekorde, wichtige Personalentscheidungen)
7-9 = Relevant (interessante Shows, signifikante Entwicklungen)
4-6 = Mäßig interessant
1-3 = Nicht relevant

Antworte NUR mit einer Zahl zwischen 1 und 10."""

    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 50,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            score_text = response.json()['content'][0]['text'].strip()
            score = int(''.join(filter(str.isdigit, score_text))[:2])
            return min(max(score, 1), 10)
        return 0
    except:
        return 0


def erstelle_zusammenfassung_mit_claude(titel, volltext):
    """Erstellt prägnante Zusammenfassung"""
    prompt = f"""Fasse diesen Medien-Artikel in 2-3 prägnanten Sätzen zusammen für einen TV-Produzenten.

Titel: {titel}
Text: {volltext[:2000]}

Antworte NUR mit der Zusammenfassung."""

    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 300,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text'].strip()
        return "Zusammenfassung konnte nicht erstellt werden."
    except:
        return "Zusammenfassung konnte nicht erstellt werden."


def hole_volltext_von_url(url):
    """Holt Volltext von URL"""
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        return response.text[:3000] if response.status_code == 200 else ""
    except:
        return ""


# ============================================================================
# RSS FUNKTIONEN
# ============================================================================

def hole_rss_artikel(feed_name, feed_url, max_items=20):
    """Holt Artikel aus RSS-Feed"""
    try:
        feed = feedparser.parse(feed_url)
        artikel = []
        
        for entry in feed.entries[:max_items]:
            artikel.append({
                'titel': entry.get('title', 'Kein Titel'),
                'beschreibung': entry.get('description', entry.get('summary', 'Keine Beschreibung')),
                'link': entry.get('link', ''),
                'quelle': feed_name,
                'datum': entry.get('published', 'Unbekannt')
            })
        
        return artikel
    except Exception as e:
        print(f"   ⚠️  Fehler bei {feed_name}: {str(e)}")
        return []


# ============================================================================
# JSON GENERIERUNG
# ============================================================================

def generiere_newsletter_json(relevante_artikel):
    """Generiert JSON-Datei für die Webseite"""
    datum = datetime.now().strftime("%Y-%m-%d")
    datum_lesbar = datetime.now().strftime("%d.%m.%Y")
    
    newsletter_data = {
        'id': datum,
        'datum': datum_lesbar,
        'generiert_am': datetime.now().isoformat(),
        'anzahl_artikel': len(relevante_artikel),
        'artikel': []
    }
    
    for i, artikel in enumerate(relevante_artikel):
        newsletter_data['artikel'].append({
            'id': i,
            'titel': artikel['titel'],
            'quelle': artikel['quelle'],
            'link': artikel['link'],
            'zusammenfassung': artikel['zusammenfassung'],
            'score': artikel['score'],
            'datum': artikel.get('datum', '')
        })
    
    # Speichere JSON-Datei
    filename = f"newsletter-{datum}.json"
    filepath = filename  # Speichere im aktuellen Verzeichnis
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(newsletter_data, f, ensure_ascii=False, indent=2)
    
    print(f"   ✅ JSON gespeichert: {filename}")
    
    # Update index.json (Liste aller Newsletter)
    index_path = 'newsletter-index.json'  # Auch im aktuellen Verzeichnis
    
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
    else:
        index = {'newsletter': []}
    
    # Füge neuen Newsletter hinzu (wenn nicht schon vorhanden)
    if not any(n['id'] == datum for n in index['newsletter']):
        index['newsletter'].insert(0, {
            'id': datum,
            'datum': datum_lesbar,
            'anzahl_artikel': len(relevante_artikel),
            'url': f"newsletter-{datum}.json"
        })
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    print(f"   ✅ Index aktualisiert")
    
    return filename


# ============================================================================
# EMAIL FUNKTIONEN
# ============================================================================

def sende_benachrichtigungs_email(empfaenger_name, empfaenger_email, anzahl_artikel):
    """Sendet kurze Email mit Link zur Webseite"""
    datum = datetime.now().strftime("%d.%m.%Y")
    datum_id = datetime.now().strftime("%Y-%m-%d")
    
    # Newsletter-URL mit Datum
    newsletter_link = f"{NEWSLETTER_URL}/?date={datum_id}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f6f6f6;
            }}
            .container {{
                background-color: #ffffff;
                border-radius: 10px;
                padding: 40px;
                border-top: 5px solid #ffd01d;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .logo {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .logo img {{
                height: 60px;
                width: auto;
            }}
            h1 {{
                color: #181716;
                margin: 0 0 20px 0;
                font-size: 24px;
            }}
            .greeting {{
                font-size: 18px;
                margin-bottom: 20px;
            }}
            .stats {{
                background-color: #ffd01d;
                color: #181716;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .button {{
                display: inline-block;
                background-color: #ffd01d;
                color: #181716;
                padding: 16px 40px;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 16px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #666;
                font-size: 14px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">
                <img src="{NEWSLETTER_URL}/logo-full.png" alt="Zoo Productions" />
            </div>
            
            <h1>Medien Newsletter</h1>
            
            <div class="greeting">
                Hallo {empfaenger_name},
            </div>
            
            <p>dein täglicher Newsletter vom <strong>{datum}</strong> steht bereit!</p>
            
            <div class="stats">
                ✨ <strong>{anzahl_artikel} relevante Artikel</strong> aus Deutschland, UK und USA<br>
                🎯 Kuratiert von Claude AI<br>
                💡 Bewerte direkt auf der Webseite
            </div>
            
            <center>
                <a href="{newsletter_link}" class="button">
                    📰 Jetzt Newsletter lesen
                </a>
            </center>
            
            <div class="footer">
                <strong>Neu:</strong> Archiv-Funktion! Durchsuche alle vergangenen Newsletter.<br><br>
                Zoo Productions | Powered by Claude AI
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = GMAIL_USER
        msg['To'] = empfaenger_email
        msg['Subject'] = f'📺 Zoo Medien Newsletter - {datum}'
        
        html_part = MIMEText(html, 'html', 'utf-8')
        msg.attach(html_part)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, empfaenger_email, msg.as_string())
        server.quit()
        
        print(f"   ✅ Email an {empfaenger_name} gesendet")
        return True
    except Exception as e:
        print(f"   ❌ Fehler bei {empfaenger_name}: {str(e)}")
        return False


# ============================================================================
# HAUPTPROGRAMM
# ============================================================================

def main():
    """Hauptfunktion"""
    
    if not ANTHROPIC_API_KEY or not GMAIL_APP_PASSWORD:
        print("❌ FEHLER: API Keys fehlen!")
        sys.exit(1)
    
    print("\n" + "="*70)
    print("🚀 ZOO MEDIEN NEWSLETTER - WEBSEITEN-VERSION")
    print("="*70 + "\n")
    
    # Schritt 1: RSS-Feeds holen
    alle_artikel = []
    for feed_name, feed_url in RSS_FEEDS.items():
        print(f"📡 Hole Artikel von {feed_name}...")
        artikel = hole_rss_artikel(feed_name, feed_url)
        alle_artikel.extend(artikel)
        print(f"   ✅ {len(artikel)} Artikel gefunden")
    
    print(f"\n📊 Gesamt: {len(alle_artikel)} Artikel gesammelt")
    
    if not alle_artikel:
        print("❌ Keine Artikel gefunden!")
        sys.exit(1)
    
    # Schritt 2: Mit Claude bewerten
    print("\n" + "="*70)
    print("🤖 BEWERTE ARTIKEL MIT CLAUDE API")
    print("="*70 + "\n")
    
    relevante_artikel = []
    
    for i, artikel in enumerate(alle_artikel, 1):
        titel_kurz = artikel['titel'][:60] + "..." if len(artikel['titel']) > 60 else artikel['titel']
        print(f"[{i}/{len(alle_artikel)}] {artikel['quelle']}: {titel_kurz}")
        
        score = bewerte_artikel_mit_claude(artikel['titel'], artikel['beschreibung'])
        
        if score >= 7:
            print(f"   ✅ Score: {score} - RELEVANT!")
            
            print("   📄 Lade Volltext...")
            volltext = hole_volltext_von_url(artikel['link'])
            
            print("   ✍️  Erstelle Zusammenfassung...")
            zusammenfassung = erstelle_zusammenfassung_mit_claude(artikel['titel'], volltext)
            
            artikel['score'] = score
            artikel['zusammenfassung'] = zusammenfassung
            relevante_artikel.append(artikel)
            
            time.sleep(1)
        else:
            print(f"   ⏭️  Score: {score} - übersprungen")
        
        time.sleep(0.5)
    
    print(f"\n📈 {len(relevante_artikel)} von {len(alle_artikel)} Artikeln relevant")
    
    # Schritt 3: JSON generieren
    if relevante_artikel:
        print("\n" + "="*70)
        print("📝 GENERIERE JSON-DATEN")
        print("="*70 + "\n")
        
        generiere_newsletter_json(relevante_artikel)
        
        # Schritt 4: Benachrichtigungs-Emails senden
        print("\n" + "="*70)
        print("📧 SENDE BENACHRICHTIGUNGS-EMAILS")
        print("="*70 + "\n")
        
        erfolge = []
        for name, email in EMPFAENGER.items():
            erfolg = sende_benachrichtigungs_email(name, email, len(relevante_artikel))
            erfolge.append(erfolg)
            time.sleep(2)
        
        print("\n" + "="*70)
        print("🎉 FERTIG!")
        print("="*70)
        print(f"✅ {len(alle_artikel)} Artikel analysiert")
        print(f"✅ {len(relevante_artikel)} relevante Artikel gefunden")
        print(f"✅ JSON-Datei generiert")
        print(f"✅ {sum(erfolge)}/{len(EMPFAENGER)} Emails versendet")
        print("="*70 + "\n")
    else:
        print("\n❌ Keine relevanten Artikel gefunden")
        sys.exit(1)


if __name__ == "__main__":
    main()
