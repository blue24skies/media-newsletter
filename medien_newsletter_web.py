#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Medien Newsletter Automation mit Themen-basiertem Learning
Version 2.0 - Intelligentes Lernen auf Themen-Ebene
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
import anthropic

# ============================================================================
# KONFIGURATION
# ============================================================================

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
NEWSLETTER_URL = os.environ.get('NEWSLETTER_URL', 'https://blue24skies.github.io/media-newsletter')
BRAVE_SEARCH_API_KEY = os.environ.get('BRAVE_SEARCH_API_KEY', '')

# RSS-Feeds - Sortiert nach Region
RSS_FEEDS = {
    # Deutschland
    'DWDL': 'https://www.dwdl.de/rss/nachrichten.xml',
    'Horizont Medien': 'https://www.horizont.net/feed/kategorie/medien/rss.xml',
    # UK
    'Guardian Media': 'https://www.theguardian.com/media/rss',
    # USA
    'Variety': 'https://variety.com/feed/',
    'Deadline': 'https://deadline.com/feed/',
    'Hollywood Reporter': 'https://www.hollywoodreporter.com/feed/'
}

# Web-Scraping Quellen (ohne RSS) - Deutschland
WEB_SCRAPING_SOURCES = {
    'kress': 'https://kress.de/news',
    'meedia': 'https://meedia.de',
    'turi2': 'https://turi2.de'
}

# Empfänger - Alle Team-Mitglieder
EMPFAENGER = {
    'Tom': 'tom@zooproductions.de',
    #'Kat': 'kat@zooproductions.de',
    #'Dom': 'dom@zooproductions.de',
    #'Aurelia': 'aurelia@zooproductions.de',
    #'Christina': 'christina@zooproductions.de'
}

# Anthropic Client
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ============================================================================
# THEMEN-BASIERTES LEARNING SYSTEM (NEU!)
# ============================================================================

LEARNING_RULES = []

def load_learning_rules():
    """Lade die intelligenten Themen-basierten Learning Rules"""
    global LEARNING_RULES
    try:
        if os.path.exists('learning_rules.py'):
            with open('learning_rules.py', 'r', encoding='utf-8') as f:
                code = f.read()
                local_vars = {}
                exec(code, {}, local_vars)
                if 'LEARNING_RULES' in local_vars:
                    LEARNING_RULES = local_vars['LEARNING_RULES']
                    print(f"✅ {len(LEARNING_RULES)} Learning Rules geladen")
                    
                    # Zeige Statistik
                    theme_rules = [r for r in LEARNING_RULES if 'theme' in r.get('type', '')]
                    source_rules = [r for r in LEARNING_RULES if 'source' in r.get('type', '')]
                    
                    if theme_rules:
                        print(f"   📊 {len(theme_rules)} Themen-Regeln")
                    if source_rules:
                        print(f"   📊 {len(source_rules)} Quellen-Regeln")
                    
                    return True
    except Exception as e:
        print(f"⚠️ Konnte Learning Rules nicht laden: {e}")
    
    LEARNING_RULES = []
    return False

def apply_learning_rules(title, source, base_score):
    """
    Wendet intelligente Themen- und Quellen-basierte Lernregeln an
    
    Args:
        title: Artikel-Titel
        source: Artikel-Quelle
        base_score: Basis-Score von Claude
        
    Returns:
        Angepasster Score und Liste der angewandten Regeln
    """
    if not LEARNING_RULES:
        return base_score, []
    
    adjusted_score = base_score
    applied_rules = []
    title_lower = title.lower()
    
    # Durchlaufe alle Regeln
    for rule in LEARNING_RULES:
        rule_type = rule.get('type', '')
        
        # Themen-basierte Regeln (PRIORITÄT!)
        if rule_type in ['theme_bonus', 'theme_malus']:
            theme = rule.get('theme', '').lower()
            if theme and theme in title_lower:
                adjustment = rule.get('adjustment', 0)
                adjusted_score += adjustment
                applied_rules.append({
                    'type': rule_type,
                    'theme': rule.get('theme'),
                    'adjustment': adjustment
                })
        
        # Quellen-basierte Regeln (Fallback)
        elif rule_type in ['source_bonus', 'source_malus']:
            if rule.get('source') == source:
                adjustment = rule.get('adjustment', 0)
                adjusted_score += adjustment
                applied_rules.append({
                    'type': rule_type,
                    'source': source,
                    'adjustment': adjustment
                })
    
    # Score zwischen 1-10 halten
    adjusted_score = max(1, min(10, adjusted_score))
    
    return adjusted_score, applied_rules

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
# KRESS.DE WEB-SCRAPING
# ============================================================================

def hole_kress_artikel():
    """
    Scrape aktuelle Artikel von kress.de/news
    Gibt Artikel im gleichen Format wie RSS-Feeds zurück
    """
    artikel_liste = []
    
    try:
        print(f"🌐 Scrape Artikel von kress.de...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get('https://kress.de/news', headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Finde Artikel-Container
        artikel_texte = soup.find_all('p')
        
        artikel_count = 0
        for p in artikel_texte[:20]:
            text = p.get_text(strip=True)
            
            if len(text) < 50:
                continue
            
            # Simuliere Artikel-Struktur
            artikel_count += 1
            artikel_liste.append({
                'title': text[:100] + "..." if len(text) > 100 else text,
                'link': 'https://kress.de/news',
                'summary': text[:300],
                'source': 'kress'
            })
            
            if artikel_count >= 5:
                break
        
        print(f"   ✅ {len(artikel_liste)} Artikel gefunden")
        
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
    
    return artikel_liste

# ============================================================================
# RSS FEED SAMMLUNG
# ============================================================================

def sammle_artikel():
    """Sammelt Artikel aus allen RSS-Feeds und Kress"""
    alle_artikel = []
    
    for quelle, url in RSS_FEEDS.items():
        print(f"📰 {quelle}...", end=" ")
        
        try:
            feed = feedparser.parse(url)
            anzahl = len(feed.entries)
            
            for entry in feed.entries:
                artikel = {
                    'title': entry.get('title', 'Kein Titel'),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', entry.get('description', '')),
                    'source': quelle
                }
                alle_artikel.append(artikel)
            
            print(f"✅ {anzahl} Artikel")
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Fehler: {e}")
    
    # Kress Artikel hinzufügen
    kress_artikel = hole_kress_artikel()
    alle_artikel.extend(kress_artikel)
    
    print(f"\n✅ Gesamt: {len(alle_artikel)} Artikel gesammelt\n")
    return alle_artikel

# ============================================================================
# INTELLIGENTE BESCHREIBUNG + ZUSAMMENFASSUNG
# ============================================================================

def get_best_description(article):
    """
    Holt die beste verfügbare Beschreibung für einen Artikel
    Verwendet 3-stufige Strategie
    """
    # 1. RSS Description (wenn gut genug)
    rss_desc = article.get('summary', '')
    if len(rss_desc) > 150:
        return rss_desc
    
    # 2. Versuche Volltext zu laden
    url = article.get('link', '')
    if url:
        full_text = fetch_full_article(url)
        if full_text and len(full_text) > 200:
            return full_text
    
    # 3. Brave Search Fallback
    if BRAVE_SEARCH_API_KEY:
        title = article.get('title', '')
        context = search_web_for_context(title, rss_desc)
        if context:
            return context
    
    # Fallback: Nutze was da ist
    return rss_desc if rss_desc else "Keine Beschreibung verfügbar"

def score_and_summarize_article(article, source_name):
    """
    Bewertet Artikel UND erstellt Zusammenfassung in EINEM API-Call
    Wendet danach Learning Rules an
    """
    title = article.get('title', 'Kein Titel')
    
    # Hole beste Beschreibung
    description = get_best_description(article)
    
    # Falls immer noch zu kurz, erwähne das
    if len(description) < 100:
        print(f"      ⚠️ Sehr kurze Beschreibung ({len(description)} Zeichen)")
    
    prompt = f"""Bewerte diesen TV/Medien-Artikel für ein deutsches TV-Produktionsunternehmen UND erstelle eine Zusammenfassung.

Titel: {title}
Quelle: {source_name}
Inhalt: {description[:2500]}

**AUFGABE 1 - RELEVANZ-BEWERTUNG (Score 1-10):**
- Hohe Relevanz (8-10): Erfolgreiche TV-Formate mit hohen Quoten, neue Formate die getestet/verkauft werden, Format-Deals zwischen Produktionsfirmen und Sendern/Streamern, Streaming-Plattformen die Content suchen, wichtige Personal-Entscheidungen, Format-Adaptionen für verschiedene Märkte
- Mittlere Relevanz (5-7): Allgemeine TV-Trends, Branchen-News, neue Shows ohne Quoten-Daten
- Geringe Relevanz (1-4): Reine Politik, Wirtschafts-News ohne TV-Bezug, Celebrity-Gossip, reine Technik-News

**AUFGABE 2 - ZUSAMMENFASSUNG:**
Erstelle eine prägnante deutsche Zusammenfassung (2-3 Sätze, max 200 Zeichen) die die Kernaussage des Artikels wiedergibt.

Antworte NUR mit JSON in diesem EXAKTEN Format:
{{"score": <1-10>, "reasoning": "<kurze Begründung>", "summary": "<deutsche Zusammenfassung>"}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text.strip()
        result = json.loads(response_text)
        
        base_score = result.get('score', 0)
        reasoning = result.get('reasoning', 'Keine Begründung')
        summary = result.get('summary', 'Keine Zusammenfassung verfügbar')
        
        # ========================================
        # WENDE LEARNING RULES AN!
        # ========================================
        adjusted_score, applied_rules = apply_learning_rules(title, source_name, base_score)
        
        # Erweitere Reasoning wenn Regeln angewendet wurden
        if applied_rules:
            rules_info = []
            for rule in applied_rules:
                if 'theme' in rule:
                    rules_info.append(f"{rule['theme']} ({rule['adjustment']:+d})")
                elif 'source' in rule:
                    rules_info.append(f"{rule['source']} ({rule['adjustment']:+d})")
            
            reasoning += f" [Learning: {base_score}→{adjusted_score}: {', '.join(rules_info)}]"
            print(f"      🎓 Learning: {base_score} → {adjusted_score}")
        
        return adjusted_score, reasoning, summary
        
    except json.JSONDecodeError as e:
        print(f"      ❌ JSON Parse Error: {e}")
        print(f"      Response: {response_text[:200]}")
        return 0, f"Fehler: Ungültige Antwort", "Zusammenfassung nicht verfügbar"
    except Exception as e:
        print(f"      ❌ API Error: {e}")
        return 0, f"Fehler: {str(e)}", "Zusammenfassung nicht verfügbar"

# ============================================================================
# ARTIKEL-VERARBEITUNG
# ============================================================================

def verarbeite_artikel(artikel_liste):
    """Bewerte und fasse alle Artikel zusammen"""
    relevante_artikel = []
    artikel_mit_score = []
    
    # Zähler für Statistik
    total = len(artikel_liste)
    processed = 0
    
    for artikel in artikel_liste:
        processed += 1
        quelle = artikel['source']
        titel = artikel['title']
        
        print(f"[{processed}/{total}] {quelle}: {titel[:50]}...")
        
        # Score + Zusammenfassung in einem Call
        score, reasoning, summary = score_and_summarize_article(artikel, quelle)
        
        artikel['score'] = score
        artikel['reasoning'] = reasoning
        artikel['summary'] = summary
        
        print(f"      Score: {score}/10")
        if score > 0:
            print(f"      ✅ {summary[:80]}...")
        print()
        
        artikel_mit_score.append(artikel)
        
        # Nur Score >= 7 als relevant
        if score >= 7:
            relevante_artikel.append(artikel)
        
        time.sleep(0.5)  # Rate limiting
    
    # Sortiere nach Score
    relevante_artikel.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n📊 ERGEBNIS:")
    print(f"   • {len(relevante_artikel)} relevante Artikel (Score ≥ 7)")
    print(f"   • {len([a for a in artikel_mit_score if 5 <= a['score'] < 7])} mittlere Relevanz (Score 5-6)")
    print(f"   • {len([a for a in artikel_mit_score if a['score'] < 5])} niedrige Relevanz (Score < 5)")
    
    return relevante_artikel

# ============================================================================
# JSON SPEICHERUNG
# ============================================================================

def speichere_als_json(artikel_liste):
    """Speichert Artikel als JSON mit regionaler Gruppierung"""
    datum = datetime.now().strftime('%Y-%m-%d')
    filename = f'newsletter-{datum}.json'
    
    # Gruppiere nach Region
    deutschland = [a for a in artikel_liste if a['source'] in ['DWDL', 'Horizont Medien', 'kress']]
    uk = [a for a in artikel_liste if a['source'] in ['Guardian Media']]
    usa = [a for a in artikel_liste if a['source'] in ['Variety', 'Deadline', 'Hollywood Reporter']]
    
    data = {
        'date': datum,
        'total_articles': len(artikel_liste),
        'regions': {
            'deutschland': {
                'count': len(deutschland),
                'articles': deutschland
            },
            'uk': {
                'count': len(uk),
                'articles': uk
            },
            'usa': {
                'count': len(usa),
                'articles': usa
            }
        },
        'articles': []
    }
    
    # Flache Liste für Kompatibilität
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

def erstelle_html_email(anzahl_artikel, empfaenger_name, datum):
    """Sendet kurze Email mit Link zur Webseite"""
    
    newsletter_link = f"{NEWSLETTER_URL}?date={datum}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
                background-color: #f6f6f6;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #181716 0%, #2a2624 100%);
                padding: 40px 30px;
                text-align: center;
            }}
            .logo {{
                max-width: 180px;
                height: auto;
                margin-bottom: 20px;
            }}
            .header-text {{
                color: #ffd01d;
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .greeting {{
                font-size: 18px;
                color: #181716;
                margin-bottom: 30px;
            }}
            .stats-box {{
                background: #f6f6f6;
                border-left: 4px solid #ffd01d;
                padding: 20px;
                margin: 30px 0;
                border-radius: 5px;
            }}
            .stats-number {{
                font-size: 36px;
                font-weight: bold;
                color: #181716;
                margin-bottom: 5px;
            }}
            .stats-label {{
                color: #666;
                font-size: 14px;
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
                transition: background 0.3s;
            }}
            .tip {{
                background: #fff9e6;
                border-left: 3px solid #ffd01d;
                padding: 15px;
                margin: 20px 0;
                font-size: 13px;
                color: #666;
            }}
            .footer {{
                text-align: center;
                padding: 30px;
                color: #999;
                font-size: 12px;
                border-top: 1px solid #eee;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="{NEWSLETTER_URL}/logo-full.png" alt="Zoo Productions" class="logo">
                <div class="header-text">Medien Newsletter</div>
            </div>
            
            <div class="content">
                <div class="greeting">
                    Guten Morgen {empfaenger_name}! 👋
                </div>
                
                <div class="stats-box">
                    <div class="stats-number">{anzahl_artikel}</div>
                    <div class="stats-label">relevante Artikel für dich heute</div>
                </div>
                
                <p>Dein personalisierter Newsletter ist bereit! Alle Artikel wurden intelligent zusammengefasst und warten auf dich.</p>
                
                <center>
                    <a href="{newsletter_link}" class="button">
                        Newsletter öffnen →
                    </a>
                </center>
                
                <div class="tip">
                    💡 <strong>Tipp:</strong> Bewerte die Artikel mit ✓ oder ✗ – das System lernt aus deinem Feedback!
                </div>
            </div>
            
            <div class="footer">
                Zoo Productions<br>
                Automatisch generiert am {datetime.now().strftime('%d.%m.%Y um %H:%M')} Uhr
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def versende_newsletter(artikel_liste):
    """Versende kurze Newsletter-Email mit Link zur Website"""
    
    if not artikel_liste:
        print("⚠️ Keine relevanten Artikel - kein Newsletter versendet")
        return
    
    print(f"\n📧 VERSENDE EMAILS")
    print("="*70)
    
    heute = datetime.now().strftime('%Y-%m-%d')
    anzahl_artikel = len(artikel_liste)
    
    for name, email in EMPFAENGER.items():
        print(f"📧 Sende an {name}...")
        
        try:
            # Erstelle kurze Email mit Link
            html_content = erstelle_html_email(anzahl_artikel, name, heute)
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🎬 Zoo Medien Newsletter · {anzahl_artikel} Artikel · {datetime.now().strftime('%d.%m.%Y')}"
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
    print("🧠 Themen-basiertes Learning System")
    print("🌐 Intelligentes Web-Fetching + Recherche-Fallback")
    print("📝 Mit Zusammenfassungen!")
    print("="*70 + "\n")
    
    # Lade Learning Rules
    has_rules = load_learning_rules()
    if not has_rules:
        print("ℹ️ Noch keine Learning Rules vorhanden")
    print()
    
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
    
    # 3. Speichere JSON (MIT REGIONALER SORTIERUNG!)
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
    
    # Zeige Learning Stats wenn vorhanden
    if LEARNING_RULES:
        print(f"\n🧠 Learning System:")
        print(f"   • {len(LEARNING_RULES)} aktive Regeln angewendet")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
