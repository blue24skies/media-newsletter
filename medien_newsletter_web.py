#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Medien Newsletter Automation mit Zusammenfassungen
FIXED: Erstellt jetzt Zusammenfassungen für jeden Artikel!
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
from bs4 import BeautifulSoup
from urllib.parse import quote

# ============================================================================
# KONFIGURATION
# ============================================================================

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
NEWSLETTER_URL = os.environ.get('NEWSLETTER_URL', 'https://blue24skies.github.io/media-newsletter')
BRAVE_SEARCH_API_KEY = os.environ.get('BRAVE_SEARCH_API_KEY', '')

# RSS-Feeds
RSS_FEEDS = {
    'DWDL': 'https://www.dwdl.de/rss/nachrichten.xml',
    'Horizont Medien': 'https://www.horizont.net/feed/kategorie/medien/rss.xml',
    'Variety': 'https://variety.com/feed/',
    'Deadline': 'https://deadline.com/feed/',
    'Hollywood Reporter': 'https://www.hollywoodreporter.com/feed/',
    'Guardian Media': 'https://www.theguardian.com/media/rss'
}

# Empfänger - TEST: Nur Tom
EMPFAENGER = {
    'Tom': os.environ.get('GMAIL_USER', '')
}

# ============================================================================
# LEARNING RULES SYSTEM
# ============================================================================

def load_learning_rules():
    """Lade die Learning Rules aus learning_rules.py falls vorhanden"""
    try:
        if os.path.exists('learning_rules.py'):
            with open('learning_rules.py', 'r', encoding='utf-8') as f:
                code = f.read()
                local_vars = {}
                exec(code, {}, local_vars)
                if 'LEARNING_RULES' in local_vars:
                    print("✅ Learning Rules aktiv")
                    return local_vars['LEARNING_RULES']
    except Exception as e:
        print(f"⚠️ Konnte Learning Rules nicht laden: {e}")
    return {}

LEARNING_RULES = load_learning_rules()

def apply_learning_boost(score, source, title, keywords):
    """Wende Learning Boost auf Score an"""
    original_score = score
    
    # Source-spezifische Regeln
    if source in LEARNING_RULES.get('source_boosts', {}):
        source_boost = LEARNING_RULES['source_boosts'][source]
        score = min(10, score + source_boost)
        if source_boost != 0:
            print(f"    🎓 Learning: {original_score} → {score}")
            return score
    
    # Keyword-Boosts
    title_lower = title.lower()
    keywords_lower = [k.lower() for k in keywords]
    for keyword, boost in LEARNING_RULES.get('keyword_boosts', {}).items():
        if keyword.lower() in title_lower or keyword.lower() in ' '.join(keywords_lower):
            score = min(10, score + boost)
            if boost != 0:
                print(f"    🎓 Learning: {original_score} → {score}")
                return score
    
    return score

# ============================================================================
# WEB-FETCHING + BRAVE SEARCH FALLBACK
# ============================================================================

def fetch_full_article(url):
    """
    Versuche den Volltext eines Artikels zu laden
    3-Stufen-Strategie für maximale Erfolgsrate
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Entferne Scripte, Styles, Nav, Footer
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header']):
            tag.decompose()
        
        # Strategie 1: Suche nach <article> Tag
        article = soup.find('article')
        if article:
            text = article.get_text(separator=' ', strip=True)
            if len(text) > 200:
                return text[:3000]  # Ersten 3000 Zeichen
        
        # Strategie 2: Suche nach gängigen Content-Klassen
        content_selectors = [
            'div.article-content',
            'div.post-content',
            'div.entry-content',
            'div.content',
            'div.story-body',
            'div.article-body',
            'main'
        ]
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                text = content.get_text(separator=' ', strip=True)
                if len(text) > 200:
                    return text[:3000]
        
        # Strategie 3: Alle <p> Tags im Body
        paragraphs = soup.find_all('p')
        if paragraphs:
            text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            if len(text) > 200:
                return text[:3000]
        
        return None
        
    except Exception as e:
        return None

def search_web_for_context(title, description):
    """
    Brave Search Fallback wenn Artikel nicht geladen werden kann
    """
    if not BRAVE_SEARCH_API_KEY:
        return None
    
    try:
        # Erstelle Suchquery aus Titel
        query = title[:100]  # Max 100 Zeichen
        
        headers = {
            'Accept': 'application/json',
            'X-Subscription-Token': BRAVE_SEARCH_API_KEY
        }
        
        params = {
            'q': query,
            'count': 3,  # Top 3 Ergebnisse
            'text_decorations': False
        }
        
        response = requests.get(
            'https://api.search.brave.com/res/v1/web/search',
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Sammle Snippets von Top-Ergebnissen
            snippets = []
            if 'web' in data and 'results' in data['web']:
                for result in data['web']['results'][:3]:
                    if 'description' in result and result['description']:
                        snippets.append(result['description'])
            
            if snippets:
                context = ' '.join(snippets)
                print(f"       ✅ Kontext-Recherche erfolgreich ({len(context)} Zeichen)")
                return context
        
        return None
        
    except Exception as e:
        print(f"       ❌ Recherche fehlgeschlagen: {e}")
        return None

# ============================================================================
# CLAUDE API - BEWERTUNG
# ============================================================================

def bewerte_artikel_mit_claude(artikel_liste):
    """Bewerte alle Artikel auf einmal mit Claude"""
    
    if not artikel_liste:
        return []
    
    # Erstelle kompakten Prompt
    artikel_text = ""
    for idx, artikel in enumerate(artikel_liste, 1):
        artikel_text += f"\n[{idx}] Quelle: {artikel['source']}\n"
        artikel_text += f"Titel: {artikel['title']}\n"
        artikel_text += f"Beschreibung: {artikel['description'][:300]}...\n"
    
    prompt = f"""Bewerte diese {len(artikel_liste)} Medien-Artikel für Zoo Productions (deutsche Produktionsfirma für TV-Serien/Dokus).

**Bewertungsskala (1-10):**
- 9-10: Strategisch wichtig (Produktionstrends, Streaming-Deals, Senderstrategien)
- 7-8: Relevant (Medienmarkt, Quotenanalysen, Programmierungen)
- 4-6: Bedingt interessant (Standard-News, internationale Stories)
- 1-3: Nicht relevant (Celebrity-News, reine Entertainment-Stories)

Artikel:
{artikel_text}

Antworte NUR mit JSON:
{{"scores": [score1, score2, ...]}}"""

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
                'max_tokens': 1000,
                'messages': [{
                    'role': 'user',
                    'content': prompt
                }]
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            text = data['content'][0]['text'].strip()
            
            # Parse JSON
            text = text.replace('```json', '').replace('```', '').strip()
            result = json.loads(text)
            
            return result.get('scores', [])
        else:
            print(f"❌ Claude API Fehler: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Fehler bei Claude API: {e}")
        return []

# ============================================================================
# CLAUDE API - ZUSAMMENFASSUNG (DAS WAR DAS PROBLEM!)
# ============================================================================

def erstelle_zusammenfassung_mit_claude(title, url, full_text):
    """
    Erstelle eine prägnante Zusammenfassung mit Claude
    DIES IST DIE FEHLENDE FUNKTION!
    """
    
    if not full_text or len(full_text) < 100:
        return "Keine Zusammenfassung verfügbar."
    
    prompt = f"""Erstelle eine prägnante 2-3 Satz Zusammenfassung dieses Medien-Artikels für Fachleute:

Titel: {title}
URL: {url}

Volltext:
{full_text[:2000]}

Antworte NUR mit der Zusammenfassung, keine Einleitung."""

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
            data = response.json()
            summary = data['content'][0]['text'].strip()
            return summary
        else:
            return "Zusammenfassung nicht verfügbar."
            
    except Exception as e:
        print(f"       ❌ Zusammenfassung fehlgeschlagen: {e}")
        return "Zusammenfassung nicht verfügbar."

# ============================================================================
# NEWSLETTER LOGIK
# ============================================================================

def sammle_artikel():
    """Sammle Artikel von allen RSS-Feeds"""
    alle_artikel = []
    
    for source_name, feed_url in RSS_FEEDS.items():
        print(f"📡 Hole Artikel von {source_name}...")
        try:
            feed = feedparser.parse(feed_url)
            artikel_count = 0
            
            for entry in feed.entries[:20]:  # Max 20 pro Feed
                titel = entry.get('title', 'Kein Titel')
                link = entry.get('link', '')
                beschreibung = entry.get('summary', entry.get('description', ''))
                
                # Bereinige HTML aus Beschreibung
                if beschreibung:
                    soup = BeautifulSoup(beschreibung, 'html.parser')
                    beschreibung = soup.get_text(separator=' ', strip=True)
                
                # Extrahiere Keywords
                keywords = []
                if beschreibung:
                    words = beschreibung.lower().split()
                    keywords = [w for w in words if len(w) > 5][:10]
                
                alle_artikel.append({
                    'source': source_name,
                    'title': titel,
                    'link': link,
                    'description': beschreibung,
                    'keywords': keywords,
                    'score': 5  # Default
                })
                artikel_count += 1
            
            print(f"   ✅ {artikel_count} Artikel gefunden\n")
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Fehler bei {source_name}: {e}\n")
    
    return alle_artikel

def verarbeite_artikel(artikel_liste):
    """Bewerte Artikel und erstelle Zusammenfassungen"""
    
    print(f"\n🤖 BEWERTE {len(artikel_liste)} ARTIKEL MIT CLAUDE")
    print("="*70)
    
    # Batch-Bewertung
    scores = bewerte_artikel_mit_claude(artikel_liste)
    
    if len(scores) == len(artikel_liste):
        for artikel, score in zip(artikel_liste, scores):
            artikel['original_score'] = score
            artikel['score'] = score
    
    # Wende Learning Boosts an und zeige Ergebnisse
    relevante_artikel = []
    
    for idx, artikel in enumerate(artikel_liste, 1):
        # Zeige Artikel
        print(f"\n[{idx}] {artikel['source']}: {artikel['title'][:60]}...")
        
        # Learning Boost
        original_score = artikel['score']
        artikel['score'] = apply_learning_boost(
            artikel['score'],
            artikel['source'],
            artikel['title'],
            artikel['keywords']
        )
        
        # Entscheidung
        if artikel['score'] >= 7:
            print(f"   ✅ Score: {artikel['score']}/10 - RELEVANT!")
            relevante_artikel.append(artikel)
        else:
            print(f"   ⏭️ Score: {artikel['score']}/10 - übersprungen")
    
    # JETZT DER WICHTIGE TEIL: ZUSAMMENFASSUNGEN ERSTELLEN!
    print(f"\n\n📝 ERSTELLE ZUSAMMENFASSUNGEN FÜR {len(relevante_artikel)} RELEVANTE ARTIKEL")
    print("="*70)
    
    for idx, artikel in enumerate(relevante_artikel, 1):
        print(f"\n[{idx}/{len(relevante_artikel)}] {artikel['title'][:60]}...")
        
        # 3-Stufen Web-Fetching Strategie
        full_text = None
        
        # Stufe 1: Prüfe RSS-Beschreibung
        if len(artikel['description']) > 150:
            full_text = artikel['description']
            print(f"       ✅ RSS-Beschreibung ausreichend ({len(full_text)} Zeichen)")
        
        # Stufe 2: Lade Volltext
        if not full_text:
            print(f"       🌐 Lade Volltext von Original-URL...")
            full_text = fetch_full_article(artikel['link'])
            
            if full_text and len(full_text) > 500:
                print(f"       ✅ Volltext geladen ({len(full_text)} Zeichen)")
            elif full_text:
                print(f"       ⚠️ Volltext zu kurz ({len(full_text)} Zeichen) - Paywall/Login?")
        
        # Stufe 3: Brave Search Fallback
        if not full_text or len(full_text) < 500:
            print(f"       🔍 Versuche Web-Recherche als Fallback...")
            web_context = search_web_for_context(artikel['title'], artikel['description'])
            
            if web_context:
                # Kombiniere Teiltext + Web-Kontext
                full_text = (artikel['description'] or '') + ' ' + web_context
        
        # JETZT: Erstelle Zusammenfassung mit Claude!
        if full_text and len(full_text) >= 100:
            print(f"       🤖 Erstelle Zusammenfassung mit Claude...")
            artikel['summary'] = erstelle_zusammenfassung_mit_claude(
                artikel['title'],
                artikel['link'],
                full_text
            )
            print(f"       ✅ Zusammenfassung erstellt!")
        else:
            artikel['summary'] = "Zusammenfassung nicht verfügbar - Artikel konnte nicht vollständig geladen werden."
            print(f"       ⚠️ Keine Zusammenfassung möglich")
        
        time.sleep(0.5)  # Rate limiting
    
    return relevante_artikel

# ============================================================================
# JSON EXPORT
# ============================================================================

def speichere_als_json(artikel_liste):
    """Speichere relevante Artikel als JSON"""
    
    heute = datetime.now().strftime('%Y-%m-%d')
    filename = f'newsletter-{heute}.json'
    
    data = {
        'date': heute,
        'articles': []
    }
    
    for artikel in artikel_liste:
        data['articles'].append({
            'source': artikel['source'],
            'title': artikel['title'],
            'link': artikel['link'],
            'summary': artikel.get('summary', 'Keine Zusammenfassung verfügbar'),
            'score': artikel['score']
        })
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ JSON gespeichert: {filename}")
    
    return filename

# ============================================================================
# EMAIL VERSAND
# ============================================================================

def erstelle_html_email(artikel_liste, empfaenger_name):
    """Erstelle HTML Email mit Feedback-Buttons"""
    
    heute = datetime.now().strftime('%d.%m.%Y')
    
    artikel_html = ""
    for artikel in artikel_liste:
        # URL-encode für Feedback
        feedback_url_base = f"{NEWSLETTER_URL}/?article={quote(artikel['title'])}"
        
        artikel_html += f"""
        <div style="margin-bottom: 30px; padding: 20px; background-color: #f8f9fa; border-left: 4px solid #007bff;">
            <h3 style="margin-top: 0; color: #333;">
                <a href="{artikel['link']}" style="color: #007bff; text-decoration: none;">
                    {artikel['title']}
                </a>
            </h3>
            <p style="color: #666; font-size: 14px; margin: 5px 0;">
                📰 {artikel['source']}
            </p>
            <p style="color: #333; line-height: 1.6; margin: 15px 0;">
                {artikel.get('summary', 'Keine Zusammenfassung verfügbar')}
            </p>
            <p style="color: #888; font-size: 13px; margin: 10px 0 15px 0;">
                ⭐ Relevanz-Score: {artikel['score']}/10
            </p>
            <div style="margin-top: 15px;">
                <a href="{feedback_url_base}&feedback=relevant" 
                   style="display: inline-block; padding: 10px 20px; background-color: #28a745; 
                          color: white; text-decoration: none; border-radius: 5px; margin-right: 15px;">
                    👍 Relevant
                </a>
                <a href="{feedback_url_base}&feedback=not_relevant" 
                   style="display: inline-block; padding: 10px 20px; background-color: #dc3545; 
                          color: white; text-decoration: none; border-radius: 5px;">
                    👎 Nicht relevant
                </a>
            </div>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #007bff; color: white; padding: 30px; text-align: center; margin-bottom: 30px;">
            <h1 style="margin: 0;">🎬 Zoo Medien Newsletter</h1>
            <p style="margin: 10px 0 0 0; font-size: 16px;">Dein persönlicher Medien-Überblick · {heute}</p>
        </div>
        
        <div style="padding: 20px;">
            <p style="font-size: 16px;">Hallo {empfaenger_name},</p>
            <p>hier sind die {len(artikel_liste)} wichtigsten Medien-News für heute:</p>
            
            {artikel_html}
            
            <div style="margin-top: 40px; padding: 20px; background-color: #e9ecef; border-radius: 5px; text-align: center;">
                <p style="margin: 0; color: #666;">
                    💡 <strong>Dein Feedback hilft!</strong><br>
                    Klicke auf die Buttons um das System zu verbessern.
                </p>
            </div>
            
            <div style="margin-top: 30px; text-align: center; color: #999; font-size: 12px;">
                <p>Zoo Productions · Automatisiert mit KI-Unterstützung</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def versende_newsletter(artikel_liste):
    """Versende Newsletter an alle Empfänger"""
    
    if not artikel_liste:
        print("⚠️ Keine relevanten Artikel - kein Newsletter versendet")
        return
    
    print(f"\n📧 VERSENDE EMAILS")
    print("="*70)
    
    heute = datetime.now().strftime('%d.%m.%Y')
    
    for name, email in EMPFAENGER.items():
        print(f"📧 Sende an {name}...")
        
        try:
            # Erstelle personalisierte Email
            html_content = erstelle_html_email(artikel_liste, name)
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🎬 Zoo Medien Newsletter · {heute}"
            msg['From'] = GMAIL_USER
            msg['To'] = email
            
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # Versende
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                server.send_message(msg)
            
            print(f"   ✅ Gesendet!\n")
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Fehler: {e}\n")

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*70)
    print("🎬 ZOO MEDIEN NEWSLETTER - INTELLIGENTE AUTOMATISIERUNG")
    if LEARNING_RULES:
        print("🎓 Learning Rules aktiv")
    print("🌐 Intelligentes Web-Fetching + Recherche-Fallback")
    print("📝 Mit Zusammenfassungen!")
    print("="*70 + "\n")
    
    print("🤖 SAMMLE UND BEWERTE ARTIKEL")
    print("="*70)
    
    # 1. Sammle alle Artikel
    alle_artikel = sammle_artikel()
    
    if not alle_artikel:
        print("❌ Keine Artikel gefunden")
        return
    
    # 2. Bewerte und erstelle Zusammenfassungen
    relevante_artikel = verarbeite_artikel(alle_artikel)
    
    if not relevante_artikel:
        print("\n⚠️ Keine relevanten Artikel heute (Score < 7)")
        return
    
    # 3. Speichere JSON
    print("\n")
    filename = speichere_als_json(relevante_artikel)
    
    # 4. Versende Newsletter
    versende_newsletter(relevante_artikel)
    
    # 5. Zusammenfassung
    print("\n" + "="*70)
    print("🎉 NEWSLETTER VERSENDET!")
    print("="*70)
    print(f"✅ {len(EMPFAENGER)}/{len(EMPFAENGER)} Emails gesendet")
    print(f"📄 Datei: {filename}")
    print(f"🌐 Web: {NEWSLETTER_URL}/?date={datetime.now().strftime('%Y-%m-%d')}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
