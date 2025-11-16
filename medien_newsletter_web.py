#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Medien Newsletter Automation - Mit Learning Rules & Web-Fetching
Generiert JSON-Daten und sendet kurze Email mit Link zur Webseite
+ Wendet automatisch gelernte Regeln an
+ Lädt vollständige Artikel für bessere Zusammenfassungen
"""

import feedparser
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import time
import sys
import os
import json

# ============================================================================
# LERN-REGELN IMPORTIEREN (falls vorhanden)
# ============================================================================

try:
    from learning_rules import apply_learning_rules
    USE_LEARNING = True
    print("✅ Learning Rules aktiv - System lernt aus Feedback!")
except ImportError:
    USE_LEARNING = False
    print("ℹ️ Keine Learning Rules gefunden - nutze nur Claude Base Scores")

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
NEWSLETTER_URL = os.environ.get('NEWSLETTER_URL', 'https://blue24skies.github.io/media-newsletter')

# RSS-Feeds
RSS_FEEDS = {
    'DWDL': 'https://www.dwdl.de/rss/allethemen.xml',
    'Horizont Medien': 'https://www.horizont.net/news/feed/medien/',
    'Variety': 'https://variety.com/feed/',
    'Deadline': 'https://deadline.com/feed/',
    'Hollywood Reporter': 'https://www.hollywoodreporter.com/feed/',
    'Guardian Media': 'https://www.theguardian.com/media/rss'
}

# Bewertungs-Schwellenwert
MIN_SCORE = 7

# ============================================================================
# CLAUDE API FUNKTIONEN
# ============================================================================

def bewerte_artikel_mit_claude(titel, beschreibung, quelle):
    """
    Bewertet Artikel-Relevanz (1-10) mit Claude API
    + Wendet Learning Rules an falls vorhanden
    """
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
                'messages': [{
                    'role': 'user',
                    'content': prompt
                }]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            score_text = response.json()['content'][0]['text'].strip()
            # Extrahiere Zahl
            base_score = int(''.join(filter(str.isdigit, score_text))[:2])
            base_score = min(max(base_score, 1), 10)
            
            # LEARNING RULES ANWENDEN
            if USE_LEARNING:
                final_score = apply_learning_rules(titel, quelle, base_score)
                if final_score != base_score:
                    print(f"   🎓 Learning: {base_score} → {final_score} (Regel angewendet!)")
                return final_score
            else:
                return base_score
        else:
            print(f"   ⚠️ API Error: {response.status_code}")
            return 5
            
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return 5


def hole_artikel_volltext(url):
    """Lädt den vollständigen Artikel von der URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Entferne unwichtige Elemente
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form']):
                element.decompose()
            
            # Versuche Hauptinhalt zu finden
            article = None
            for selector in ['article', '.article-content', '.post-content', '.entry-content', 'main']:
                article = soup.select_one(selector)
                if article:
                    break
            
            # Falls kein Hauptinhalt gefunden, nutze body
            if not article:
                article = soup.find('body')
            
            if article:
                # Extrahiere Text
                text = article.get_text(separator=' ', strip=True)
                
                # Bereinige Text
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                text = ' '.join(lines)
                
                # Limitiere auf erste 2500 Zeichen
                if len(text) > 2500:
                    text = text[:2500]
                
                return text if len(text) > 100 else None
        
        return None
        
    except Exception as e:
        print(f"      ⚠️ Web-Fetch Fehler: {e}")
        return None


def generiere_zusammenfassung(artikel):
    """Generiert intelligente Zusammenfassung - lädt Volltext falls nötig"""
    
    titel = artikel.get('titel', '').strip()
    beschreibung = artikel.get('beschreibung', '').strip()
    link = artikel.get('link', '').strip()
    
    # Entscheide ob wir Volltext laden müssen
    inhalt = beschreibung
    volltext_geladen = False
    
    if not beschreibung or beschreibung == "Keine Beschreibung" or len(beschreibung) < 80:
        # Beschreibung zu kurz oder fehlt - lade Volltext
        if link:
            print(f"      🌐 Lade Volltext...")
            volltext = hole_artikel_volltext(link)
            if volltext and len(volltext) > 100:
                inhalt = volltext
                volltext_geladen = True
                print(f"      ✅ Volltext geladen ({len(volltext)} Zeichen)")
            else:
                print(f"      ⚠️ Volltext konnte nicht geladen werden")
    
    # Fallback falls immer noch zu wenig Inhalt
    if not inhalt or len(inhalt) < 30:
        return f"Medien-News: {titel}. Für Details bitte Artikel öffnen."
    
    # Claude Zusammenfassung
    prompt = f"""Fasse diesen Medien-Artikel in 2-3 prägnanten Sätzen zusammen.

Titel: {titel}

Artikelinhalt:
{inhalt}

Schreibe eine professionelle, informative Zusammenfassung die das Wichtigste auf den Punkt bringt. 
Konzentriere dich auf konkrete Fakten und Entwicklungen."""

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
                'messages': [{
                    'role': 'user',
                    'content': prompt
                }]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            zusammenfassung = response.json()['content'][0]['text'].strip()
            return zusammenfassung
        else:
            # Fallback
            return inhalt[:250] + "..."
            
    except Exception as e:
        print(f"      ⚠️ Zusammenfassung-Fehler: {e}")
        return inhalt[:250] + "..."


def get_rss_articles(feed_url, source_name, max_items=20):
    """Holt Artikel aus einem RSS-Feed"""
    print(f"📡 Hole Artikel von {source_name}...")
    
    try:
        # User-Agent setzen
        import urllib.request
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        
        feed = feedparser.parse(feed_url)
        articles = []
        
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "")
            description = (entry.get("summary", "") or 
                          entry.get("description", "") or 
                          entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "")
            link = entry.get("link", "")
            
            if title and link:
                article = {
                    "quelle": source_name,
                    "titel": title,
                    "beschreibung": description[:500] if description else "",
                    "link": link,
                    "published": entry.get("published", entry.get("updated", ""))
                }
                articles.append(article)
        
        print(f"   ✅ {len(articles)} Artikel gefunden")
        return articles
    
    except Exception as e:
        print(f"   ❌ Fehler bei {source_name}: {e}")
        return []


def sammle_und_bewerte_alle_artikel():
    """Sammelt Artikel von allen Feeds und bewertet sie"""
    print("\n🤖 SAMMLE UND BEWERTE ARTIKEL")
    print("="*70)
    
    alle_artikel = []
    artikel_counter = 0
    
    # Alle RSS-Feeds durchgehen
    for source_name, feed_url in RSS_FEEDS.items():
        articles = get_rss_articles(feed_url, source_name)
        
        for article in articles:
            artikel_counter += 1
            print(f"\n[{artikel_counter}] {article['quelle']}: {article['titel'][:60]}...")
            
            # Claude Bewertung
            score = bewerte_artikel_mit_claude(
                article['titel'],
                article['beschreibung'],
                article['quelle']
            )
            
            article['score'] = score
            
            if score >= MIN_SCORE:
                print(f"   ✅ Score: {score}/10 - RELEVANT!")
                alle_artikel.append(article)
            else:
                print(f"   ⏭️ Score: {score}/10 - übersprungen")
            
            # Rate limiting
            time.sleep(0.5)
    
    return alle_artikel


def erstelle_newsletter_json(artikel_liste):
    """Erstellt JSON-Datei für Webseite mit Zusammenfassungen"""
    print("\n📄 ERSTELLE NEWSLETTER JSON")
    print("="*70)
    
    # Zusammenfassungen generieren
    for idx, artikel in enumerate(artikel_liste, 1):
        print(f"\n[{idx}/{len(artikel_liste)}] Zusammenfassung: {artikel['titel'][:50]}...")
        artikel['zusammenfassung'] = generiere_zusammenfassung(artikel)
        time.sleep(0.8)  # Rate limiting
    
    # JSON erstellen
    heute = datetime.now().strftime('%Y-%m-%d')
    newsletter_data = {
        'datum': heute,
        'artikel': artikel_liste,
        'anzahl': len(artikel_liste)
    }
    
    # JSON mit Datum im Namen speichern
    json_filename = f'newsletter-{heute}.json'
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(newsletter_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ JSON gespeichert: {json_filename}")
    return json_filename, heute


def sende_newsletter_email(empfaenger_name, empfaenger_email, anzahl_artikel, datum):
    """Sendet kurze Email mit Link zur Webseite"""
    
    newsletter_link = f"{NEWSLETTER_URL}?date={datum}"
    
    # HTML Email
    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #181716 0%, #2a2624 100%);
                color: #ffd01d;
                padding: 30px;
                border-radius: 10px;
                text-align: center;
            }}
            .stats {{
                background: #f6f6f6;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: center;
            }}
            .stats-number {{
                font-size: 48px;
                font-weight: bold;
                color: #181716;
            }}
            .button {{
                display: inline-block;
                background: #ffd01d;
                color: #181716;
                padding: 15px 40px;
                text-decoration: none;
                border-radius: 8px;
                font-weight: bold;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                color: #999;
                font-size: 12px;
                margin-top: 30px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎬 Zoo Medien Newsletter</h1>
                <p>Dein täglicher Überblick</p>
            </div>
            
            <p>Guten Morgen {empfaenger_name}!</p>
            
            <div class="stats">
                <div class="stats-number">{anzahl_artikel}</div>
                <p>relevante Artikel für dich heute</p>
            </div>
            
            <p>Dein personalisierter Newsletter ist bereit! Alle Artikel wurden intelligent zusammengefasst:</p>
            
            <center>
                <a href="{newsletter_link}" class="button">
                    Newsletter öffnen →
                </a>
            </center>
            
            <p><small>💡 Tipp: Bewerte die Artikel mit ✓ oder ✗ - das System lernt aus deinem Feedback!</small></p>
            
            <div class="footer">
                Zoo Productions | Automatisch generiert am {datetime.now().strftime('%d.%m.%Y um %H:%M')} Uhr
                {' | 🎓 Learning Rules aktiv!' if USE_LEARNING else ''}
            </div>
        </div>
    </body>
    </html>
    """
    
    # Email erstellen
    msg = MIMEMultipart('alternative')
    msg['From'] = GMAIL_USER
    msg['To'] = empfaenger_email
    msg['Subject'] = Header(f"📺 Zoo Newsletter - {anzahl_artikel} Artikel für dich ({datum})", 'utf-8')
    
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    # Senden
    try:
        print(f"📧 Sende Email an {empfaenger_name} ({empfaenger_email})...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"   ✅ Email erfolgreich gesendet!")
        return True
    except Exception as e:
        print(f"   ❌ Email-Fehler: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Hauptfunktion"""
    print("\n" + "="*70)
    print("🎬 ZOO MEDIEN NEWSLETTER - AUTOMATISIERUNG")
    if USE_LEARNING:
        print("🎓 LEARNING RULES AKTIV - System lernt aus Feedback!")
    print("🌐 WEB-FETCHING AKTIV - Lädt vollständige Artikel!")
    print("="*70)
    print(f"⏰ Gestartet: {datetime.now().strftime('%d.%m.%Y um %H:%M:%S Uhr')}")
    
    # API Key Check
    if not ANTHROPIC_API_KEY:
        print("❌ FEHLER: ANTHROPIC_API_KEY nicht gesetzt!")
        sys.exit(1)
    
    # Artikel sammeln und bewerten
    relevante_artikel = sammle_und_bewerte_alle_artikel()
    
    print("\n📊 ERGEBNIS")
    print("="*70)
    print(f"✅ {len(relevante_artikel)} relevante Artikel gefunden (Score ≥{MIN_SCORE})")
    
    if len(relevante_artikel) == 0:
        print("⚠️ Keine relevanten Artikel heute - Newsletter wird nicht versendet")
        return
    
    # JSON erstellen
    json_file, datum = erstelle_newsletter_json(relevante_artikel)
    
    # Emails versenden
    print("\n📧 VERSENDE EMAILS")
    print("="*70)
    
    erfolg_counter = 0
    for name, email in EMPFAENGER.items():
        if sende_newsletter_email(name, email, len(relevante_artikel), datum):
            erfolg_counter += 1
        time.sleep(1)
    
    print("\n" + "="*70)
    print("🎉 NEWSLETTER ERFOLGREICH VERSENDET!")
    print("="*70)
    print(f"✅ {erfolg_counter}/{len(EMPFAENGER)} Emails erfolgreich gesendet")
    print(f"📄 Newsletter-Daten: {json_file}")
    print(f"🌐 Webseite: {NEWSLETTER_URL}?date={datum}")
    if USE_LEARNING:
        print("🎓 Learning Rules wurden angewendet!")
    print("🌐 Volltext-Fetching für bessere Zusammenfassungen!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
