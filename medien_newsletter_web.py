#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Medien Newsletter - FINALE VERSION
+ Learning Rules
+ Intelligentes Web-Fetching
+ Web-Search Fallback bei Paywalls
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
import re

# ============================================================================
# LERN-REGELN IMPORTIEREN
# ============================================================================

try:
    from learning_rules import apply_learning_rules
    USE_LEARNING = True
    print("✅ Learning Rules aktiv")
except ImportError:
    USE_LEARNING = False
    print("ℹ️ Keine Learning Rules gefunden")

# ============================================================================
# KONFIGURATION
# ============================================================================

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GMAIL_USER = os.environ.get('GMAIL_USER', 'tom@zooproductions.de')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')

EMPFAENGER = {
    'Tom': 'tom@zooproductions.de',
    #'Kat': 'kat@zooproductions.de',
    #'Dom': 'dom@zooproductions.de',
    #'Aurelia': 'aurelia@zooproductions.de',
    #'Christina': 'christina@zooproductions.de'
}

NEWSLETTER_URL = os.environ.get('NEWSLETTER_URL', 'https://blue24skies.github.io/media-newsletter')

RSS_FEEDS = {
    'DWDL': 'https://www.dwdl.de/rss/allethemen.xml',
    'Horizont Medien': 'https://www.horizont.net/news/feed/medien/',
    'Variety': 'https://variety.com/feed/',
    'Deadline': 'https://deadline.com/feed/',
    'Hollywood Reporter': 'https://www.hollywoodreporter.com/feed/',
    'Guardian Media': 'https://www.theguardian.com/media/rss'
}

MIN_SCORE = 7

# ============================================================================
# WEB-SEARCH FUNKTIONEN
# ============================================================================

def web_search(query, max_results=3):
    """Sucht im Web nach einem Thema (Brave Search API)"""
    try:
        # Brave Search API Key aus Environment
        brave_api_key = os.environ.get('BRAVE_SEARCH_API_KEY', '')
        
        if not brave_api_key:
            print(f"      ℹ️ Keine BRAVE_SEARCH_API_KEY - überspringe Web-Suche")
            return []
        
        # Bereite Suchquery vor
        search_query = f"{query} medien tv nachrichten"
        
        # Brave Search API Call
        headers = {
            'Accept': 'application/json',
            'X-Subscription-Token': brave_api_key
        }
        
        params = {
            'q': search_query,
            'count': max_results,
            'text_decorations': False,
            'search_lang': 'de',
            'country': 'DE'
        }
        
        response = requests.get(
            'https://api.search.brave.com/res/v1/web/search',
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for result in data.get('web', {}).get('results', [])[:max_results]:
                results.append({
                    'title': result.get('title', ''),
                    'snippet': result.get('description', ''),
                    'url': result.get('url', '')
                })
            
            return results
        else:
            print(f"      ⚠️ Brave API Error: {response.status_code}")
            return []
        
    except Exception as e:
        print(f"      ⚠️ Web-Search Fehler: {e}")
        return []


def hole_artikel_volltext(url):
    """Lädt vollständigen Artikel - INTELLIGENT"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Entferne unwichtige Elemente
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form', 'button']):
                element.decompose()
            
            # MEHRERE Strategien um Hauptinhalt zu finden
            article_text = None
            
            # Strategie 1: Suche nach article tags
            for selector in ['article', '.article-body', '.article-content', '.post-content', '.entry-content', 'main article']:
                article = soup.select_one(selector)
                if article:
                    article_text = article.get_text(separator=' ', strip=True)
                    if len(article_text) > 300:
                        break
            
            # Strategie 2: Suche nach div mit viel Text
            if not article_text or len(article_text) < 300:
                divs = soup.find_all('div', class_=re.compile(r'(content|article|post|entry|story|text)'))
                for div in divs:
                    text = div.get_text(separator=' ', strip=True)
                    if len(text) > len(article_text or ''):
                        article_text = text
            
            # Strategie 3: Alle p-Tags im body
            if not article_text or len(article_text) < 300:
                paragraphs = soup.find_all('p')
                article_text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            
            # Bereinige Text
            if article_text:
                lines = [line.strip() for line in article_text.split('\n') if line.strip()]
                article_text = ' '.join(lines)
                
                # Entferne mehrfache Leerzeichen
                article_text = re.sub(r'\s+', ' ', article_text)
                
                # Limitiere auf 3000 Zeichen
                if len(article_text) > 3000:
                    article_text = article_text[:3000]
                
                return article_text if len(article_text) > 200 else None
        
        return None
        
    except Exception as e:
        print(f"      ⚠️ Web-Fetch Fehler: {e}")
        return None


def sammle_kontext_informationen(titel, quelle):
    """Sammelt Kontext-Informationen wenn Artikel nicht ladbar ist"""
    try:
        # Versuche Web-Suche
        print(f"      🔍 Suche Web-Kontext für: {titel[:60]}...")
        
        search_results = web_search(titel)
        
        if search_results:
            print(f"      ✅ {len(search_results)} Kontext-Quellen gefunden")
            kontext = "\n\n".join([r.get('snippet', '') for r in search_results])
            return kontext
        else:
            return None
            
    except Exception as e:
        print(f"      ⚠️ Kontext-Suche Fehler: {e}")
        return None


def generiere_zusammenfassung(artikel):
    """INTELLIGENTE Zusammenfassung mit mehreren Fallback-Strategien"""
    
    titel = artikel.get('titel', '').strip()
    beschreibung = artikel.get('beschreibung', '').strip()
    link = artikel.get('link', '').strip()
    quelle = artikel.get('quelle', '').strip()
    
    # STRATEGIE 1: RSS-Beschreibung wenn ausreichend
    if beschreibung and len(beschreibung) > 150:
        inhalt = beschreibung
        quelle_info = "RSS-Feed"
        print(f"      ✅ Nutze RSS-Beschreibung ({len(inhalt)} Zeichen)")
    
    # STRATEGIE 2: Lade Volltext von Original-URL
    elif link:
        print(f"      🌐 Lade Volltext von Original-URL...")
        volltext = hole_artikel_volltext(link)
        
        if volltext and len(volltext) > 500:
            inhalt = volltext
            quelle_info = "Volltext"
            print(f"      ✅ Volltext geladen ({len(volltext)} Zeichen)")
        
        # STRATEGIE 3: Web-Search Fallback
        elif volltext and len(volltext) < 500:
            print(f"      ⚠️ Volltext zu kurz ({len(volltext)} Zeichen) - Paywall/Login?")
            print(f"      🔍 Versuche Web-Recherche als Fallback...")
            
            kontext = sammle_kontext_informationen(titel, quelle)
            
            if kontext and len(kontext) > 200:
                # Kombiniere: Was wir haben + Web-Kontext
                inhalt = f"Original (teilweise): {volltext}\n\nZusätzlicher Kontext aus Web-Recherche:\n{kontext}"
                quelle_info = "Volltext + Web-Recherche"
                print(f"      ✅ Kontext-Recherche erfolgreich ({len(kontext)} Zeichen)")
            elif volltext:
                inhalt = volltext
                quelle_info = "Teiltext"
                print(f"      ⚠️ Nutze verfügbaren Teiltext")
            else:
                # Fallback: Nur Titel
                inhalt = f"Titel: {titel}\nQuelle: {quelle}"
                quelle_info = "Nur Titel"
                print(f"      ⚠️ Erstelle Zusammenfassung nur aus Titel")
        
        else:
            # Kein Volltext ladbar - versuche Web-Recherche
            print(f"      ❌ Volltext nicht ladbar")
            kontext = sammle_kontext_informationen(titel, quelle)
            
            if kontext:
                inhalt = f"Thema: {titel}\n\nKontext aus Web-Recherche:\n{kontext}"
                quelle_info = "Web-Recherche"
                print(f"      ✅ Nutze Web-Recherche ({len(kontext)} Zeichen)")
            else:
                inhalt = f"Titel: {titel}\nQuelle: {quelle}"
                quelle_info = "Nur Titel"
                print(f"      ⚠️ Nur Titel verfügbar")
    
    else:
        # Kein Link vorhanden
        inhalt = f"Titel: {titel}\nBeschreibung: {beschreibung if beschreibung else 'Keine'}"
        quelle_info = "RSS-Basis"
        print(f"      ℹ️ Kein Link verfügbar, nutze RSS-Daten")
    
    # CLAUDE ZUSAMMENFASSUNG
    if len(inhalt) < 50:
        return f"{titel} - Details nur im Original-Artikel verfügbar."
    
    prompt = f"""Du bist professioneller Medien-Journalist. Erstelle eine prägnante 2-3 Satz Zusammenfassung.

Titel: {titel}

Verfügbare Informationen ({quelle_info}):
{inhalt}

AUFGABE:
- Schreibe eine professionelle, informative Zusammenfassung
- Fokussiere auf konkrete Fakten und Kernaussagen  
- 2-3 prägnante Sätze
- Selbst bei wenig Info: Fasse zusammen was bekannt ist
- Falls nur Titel: Formuliere was das Thema behandelt

Schreibe NUR die Zusammenfassung."""

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
                'max_tokens': 350,
                'messages': [{
                    'role': 'user',
                    'content': prompt
                }]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text'].strip()
        else:
            return inhalt[:300] + "..."
            
    except Exception as e:
        print(f"      ❌ Claude API Fehler: {e}")
        return inhalt[:300] + "..."


# ============================================================================
# BEWERTUNG & RSS FUNKTIONEN (wie vorher)
# ============================================================================

def bewerte_artikel_mit_claude(titel, beschreibung, quelle):
    """Bewertet Artikel-Relevanz (1-10) mit Learning Rules"""
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
            base_score = int(''.join(filter(str.isdigit, score_text))[:2])
            base_score = min(max(base_score, 1), 10)
            
            if USE_LEARNING:
                final_score = apply_learning_rules(titel, quelle, base_score)
                if final_score != base_score:
                    print(f"   🎓 Learning: {base_score} → {final_score}")
                return final_score
            return base_score
        return 5
    except Exception as e:
        print(f"   ❌ Bewertungs-Fehler: {e}")
        return 5


def get_rss_articles(feed_url, source_name, max_items=20):
    """Holt Artikel aus RSS-Feed"""
    print(f"📡 Hole Artikel von {source_name}...")
    
    try:
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
                articles.append({
                    "quelle": source_name,
                    "titel": title,
                    "beschreibung": description[:500] if description else "",
                    "link": link,
                    "published": entry.get("published", entry.get("updated", ""))
                })
        
        print(f"   ✅ {len(articles)} Artikel gefunden")
        return articles
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return []


def sammle_und_bewerte_alle_artikel():
    """Sammelt und bewertet Artikel"""
    print("\n🤖 SAMMLE UND BEWERTE ARTIKEL")
    print("="*70)
    
    alle_artikel = []
    counter = 0
    
    for source_name, feed_url in RSS_FEEDS.items():
        articles = get_rss_articles(feed_url, source_name)
        
        for article in articles:
            counter += 1
            print(f"\n[{counter}] {article['quelle']}: {article['titel'][:60]}...")
            
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
            
            time.sleep(0.5)
    
    return alle_artikel


def erstelle_newsletter_json(artikel_liste):
    """Erstellt JSON mit intelligenten Zusammenfassungen"""
    print("\n📄 ERSTELLE NEWSLETTER JSON MIT ZUSAMMENFASSUNGEN")
    print("="*70)
    
    for idx, artikel in enumerate(artikel_liste, 1):
        print(f"\n[{idx}/{len(artikel_liste)}] {artikel['titel'][:60]}...")
        artikel['zusammenfassung'] = generiere_zusammenfassung(artikel)
        time.sleep(1)  # Rate limiting
    
    heute = datetime.now().strftime('%Y-%m-%d')
    newsletter_data = {
        'datum': heute,
        'artikel': artikel_liste,
        'anzahl': len(artikel_liste)
    }
    
    json_filename = f'newsletter-{heute}.json'
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(newsletter_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ JSON gespeichert: {json_filename}")
    return json_filename, heute


def sende_newsletter_email(empfaenger_name, empfaenger_email, anzahl_artikel, datum):
    """Sendet Email"""
    newsletter_link = f"{NEWSLETTER_URL}?date={datum}"
    
    html = f"""<html><head><style>
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;line-height:1.6;color:#333}}
    .container{{max-width:600px;margin:0 auto;padding:20px}}
    .header{{background:linear-gradient(135deg,#181716 0%,#2a2624 100%);color:#ffd01d;padding:30px;border-radius:10px;text-align:center}}
    .stats{{background:#f6f6f6;padding:20px;border-radius:10px;margin:20px 0;text-align:center}}
    .stats-number{{font-size:48px;font-weight:bold;color:#181716}}
    .button{{display:inline-block;background:#ffd01d;color:#181716;padding:15px 40px;text-decoration:none;border-radius:8px;font-weight:bold;margin:20px 0}}
    .footer{{text-align:center;color:#999;font-size:12px;margin-top:30px}}
    </style></head><body><div class="container">
    <div class="header"><h1>🎬 Zoo Medien Newsletter</h1><p>Dein täglicher Überblick</p></div>
    <p>Guten Morgen {empfaenger_name}!</p>
    <div class="stats"><div class="stats-number">{anzahl_artikel}</div><p>relevante Artikel für dich heute</p></div>
    <p>Dein personalisierter Newsletter mit intelligenten Zusammenfassungen ist bereit:</p>
    <center><a href="{newsletter_link}" class="button">Newsletter öffnen →</a></center>
    <p><small>💡 Bewerte Artikel - das System lernt aus deinem Feedback!</small></p>
    <div class="footer">Zoo Productions | {datetime.now().strftime('%d.%m.%Y %H:%M')} Uhr{' | 🎓 Learning aktiv' if USE_LEARNING else ''}</div>
    </div></body></html>"""
    
    msg = MIMEMultipart('alternative')
    msg['From'] = GMAIL_USER
    msg['To'] = empfaenger_email
    msg['Subject'] = Header(f"📺 Zoo Newsletter - {anzahl_artikel} Artikel ({datum})", 'utf-8')
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    try:
        print(f"📧 Sende an {empfaenger_name}...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"   ✅ Gesendet!")
        return True
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return False


def main():
    """Hauptfunktion"""
    print("\n" + "="*70)
    print("🎬 ZOO MEDIEN NEWSLETTER - INTELLIGENTE AUTOMATISIERUNG")
    if USE_LEARNING:
        print("🎓 Learning Rules aktiv")
    print("🌐 Intelligentes Web-Fetching + Recherche-Fallback")
    print("="*70)
    
    if not ANTHROPIC_API_KEY:
        print("❌ FEHLER: ANTHROPIC_API_KEY fehlt!")
        sys.exit(1)
    
    relevante_artikel = sammle_und_bewerte_alle_artikel()
    
    print("\n📊 ERGEBNIS")
    print("="*70)
    print(f"✅ {len(relevante_artikel)} relevante Artikel (Score ≥{MIN_SCORE})")
    
    if not relevante_artikel:
        print("⚠️ Keine relevanten Artikel - kein Newsletter")
        return
    
    json_file, datum = erstelle_newsletter_json(relevante_artikel)
    
    print("\n📧 VERSENDE EMAILS")
    print("="*70)
    
    erfolg = 0
    for name, email in EMPFAENGER.items():
        if sende_newsletter_email(name, email, len(relevante_artikel), datum):
            erfolg += 1
        time.sleep(1)
    
    print("\n" + "="*70)
    print("🎉 NEWSLETTER VERSENDET!")
    print("="*70)
    print(f"✅ {erfolg}/{len(EMPFAENGER)} Emails gesendet")
    print(f"📄 Datei: {json_file}")
    print(f"🌐 Web: {NEWSLETTER_URL}?date={datum}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
