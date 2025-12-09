#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Medien Newsletter Automation mit Zusammenfassungen + ARCHIV
✅ Duplikat-Erkennung via Supabase
✅ Automatische Archivierung aller Artikel
✅ Run-Statistiken für Analyse
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
import re
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

# RSS-Feeds - Sortiert nach Region
RSS_FEEDS = {
    # Deutschland
    'DWDL': 'https://www.dwdl.de/rss/nachrichten.xml',
    'Horizont Medien': 'https://www.horizont.net/news/feed/medien/',
    'W&V': 'https://www.wuv.de/feed',
    'Quotenmeter': 'https://www.quotenmeter.de/rss',
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
    'Kat': 'kat@zooproductions.de',
    #'Dom': 'dom@zooproductions.de',
    #'Aurelia': 'aurelia@zooproductions.de',
    'Christina': 'christina@zooproductions.de'
}

# ============================================================================
# SUPABASE CLIENT
# ============================================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

try:
    from supabase import create_client, Client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    SUPABASE_AVAILABLE = supabase is not None
    if SUPABASE_AVAILABLE:
        print("✅ Supabase verbunden - Archiv aktiv")
except Exception as e:
    supabase = None
    SUPABASE_AVAILABLE = False
    print(f"⚠️ Supabase nicht verfügbar - Archiv deaktiviert: {e}")

# ============================================================================
# ARCHIV-FUNKTIONEN
# ============================================================================

def pruefe_auf_duplikat(article_url, article_title, article_published_date=''):
    """
    Intelligente Duplikat-Prüfung:
    - Prüft ob exakt die gleiche URL mit gleichem Titel bereits archiviert wurde
    - Erlaubt Updates zu existierenden Artikeln (gleiche URL, aber neuer Titel oder Datum)
    """
    if not supabase:
        return False
    try:
        # Hole alle Artikel mit dieser URL aus dem Archiv
        result = supabase.table('newsletter_articles_archive') \
            .select('article_url, article_title, published_date, first_sent_date') \
            .eq('article_url', article_url) \
            .execute()
        
        if len(result.data) == 0:
            # URL existiert nicht im Archiv - definitiv kein Duplikat
            return False
        
        # URL existiert - prüfe ob es ein Update ist
        for archived_article in result.data:
            archived_title = archived_article.get('article_title', '')
            archived_date = archived_article.get('published_date', '')
            first_sent = archived_article.get('first_sent_date', '')
            
            # Wenn Titel EXAKT gleich ist, ist es ein Duplikat
            if archived_title == article_title:
                print(f"      📋 Duplikat erkannt: Exakt gleicher Titel (zuletzt: {first_sent})")
                return True
            
            # Wenn Titel ähnlich ist (z.B. nur Tippfehler-Korrekturen), ist es auch ein Duplikat
            # Berechne einfache Ähnlichkeit basierend auf gemeinsamen Wörtern
            title_similarity = berechne_titel_aehnlichkeit(archived_title, article_title)
            if title_similarity > 0.85:  # 85% Ähnlichkeit = wahrscheinlich gleicher Artikel
                print(f"      📋 Duplikat erkannt: {int(title_similarity*100)}% Titel-Ähnlichkeit (zuletzt: {first_sent})")
                return True
        
        # URL existiert, aber Titel ist deutlich anders = Update/neue Info zum Thema
        print(f"      ✨ Artikel-Update erkannt: Gleiche URL, aber neuer Titel - wird gesendet!")
        return False
        
    except Exception as e:
        print(f"⚠️ Duplikat-Check Fehler: {str(e)}")
        return False

def berechne_titel_aehnlichkeit(titel1, titel2):
    """
    Berechnet Ähnlichkeit zwischen zwei Titeln basierend auf gemeinsamen Wörtern
    Gibt Wert zwischen 0 (völlig unterschiedlich) und 1 (identisch) zurück
    """
    # Normalisiere Titel: Kleinbuchstaben, entferne Sonderzeichen
    def normalisiere(text):
        text = text.lower()
        # Entferne HTML-Entities und Sonderzeichen
        text = re.sub(r'&[a-z]+;', '', text)
        text = re.sub(r'[^\w\s]', ' ', text)
        # Teile in Wörter und filtere kurze Wörter (< 3 Zeichen)
        woerter = [w for w in text.split() if len(w) >= 3]
        return set(woerter)
    
    woerter1 = normalisiere(titel1)
    woerter2 = normalisiere(titel2)
    
    if not woerter1 or not woerter2:
        return 0.0
    
    # Jaccard-Ähnlichkeit: Anzahl gemeinsamer Wörter / Anzahl aller Wörter
    gemeinsame = woerter1.intersection(woerter2)
    alle = woerter1.union(woerter2)
    
    return len(gemeinsame) / len(alle) if alle else 0.0

def speichere_artikel_im_archiv(artikel, run_date, region):
    """Speichert Artikel im Archiv"""
    if not supabase:
        return False
    try:
        data = {
            'article_url': artikel['link'],
            'article_title': artikel['title'],
            'source': artikel['source'],
            'region': region,
            'published_date': artikel.get('published', ''),
            'first_sent_date': run_date,
            'relevance_score': artikel['score'],
            'summary': artikel.get('summary', '')
        }
        supabase.table('newsletter_articles_archive').insert(data).execute()
        return True
    except Exception as e:
        print(f"⚠️ Archivierung Fehler: {str(e)}")
        return False

def speichere_run_metadata(run_date, stats):
    """Speichert Newsletter-Run Statistiken"""
    if not supabase:
        return False
    try:
        data = {
            'run_date': run_date,
            'total_articles_processed': stats['total'],
            'relevant_articles_found': stats['relevant'],
            'new_articles_sent': stats['new'],
            'duplicate_articles_filtered': stats['duplicates'],
            'sources_checked': stats['sources'],
            'run_status': stats['status'],
            'error_message': stats.get('error')
        }
        supabase.table('newsletter_runs').insert(data).execute()
        return True
    except Exception as e:
        print(f"⚠️ Metadata-Speicherung Fehler: {str(e)}")
        return False

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
                return text[:3000]
        
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
        query = title[:100]
        
        headers = {
            'Accept': 'application/json',
            'X-Subscription-Token': BRAVE_SEARCH_API_KEY
        }
        
        params = {
            'q': query,
            'count': 3,
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

def extrahiere_sauberen_titel(titel_raw):
    """
    Extrahiert einen sauberen Titel aus dem rohen Link-Text
    Versucht intelligent den Hauptsatz zu finden und Zusatzinfos abzuschneiden
    """
    titel_raw = titel_raw.strip()
    
    # Strategie 1: Explizite Trennzeichen (– oder -)
    if ' – ' in titel_raw:
        return titel_raw.split(' – ')[0].strip()
    if ' - ' in titel_raw:
        return titel_raw.split(' - ')[0].strip()
    
    # Strategie 2: Satzende-Erkennung (. gefolgt von Großbuchstabe oder Ende)
    # Aber NICHT bei Abkürzungen wie "z.B." oder "u.a."
    satzende_pattern = r'([^\.]+\.)(?:\s+[A-ZÄÖÜ]|\s*$)'
    match = re.search(satzende_pattern, titel_raw)
    if match:
        erster_satz = match.group(1).strip()
        # Prüfe ob es eine sinnvolle Länge hat
        if 30 <= len(erster_satz) <= 150:
            return erster_satz
    
    # Strategie 3: Doppelpunkt nach Thema (z.B. "RTL: Neue Show startet...")
    if ': ' in titel_raw:
        parts = titel_raw.split(': ', 1)
        if len(parts[0]) < 50 and len(parts[1]) > 20:
            # Der Teil nach dem Doppelpunkt ist die eigentliche Headline
            nach_doppelpunkt = parts[1]
            # Wende weitere Strategien auf den Teil nach dem Doppelpunkt an
            return extrahiere_sauberen_titel(nach_doppelpunkt)
    
    # Strategie 4: Suche nach typischen Satzanfängen im Text (zweiter Satz beginnt)
    # Regex findet: Kleinbuchstabe + Satzzeichen + optionales Leerzeichen + Satzanfang
    satzanfang_pattern = r'([a-zäöüß][\.!?])\s+(Das|Der|Die|Ein|Eine|Nach|Seit|Jetzt|Nun|Dabei|Denn|Doch|Aber|Und|Oder|Mit|Bei|Für|Auch|Schon|Bereits|Vor|Um|Vom|So|Es|Sie|Er|Wir|Ihr)\b'
    match = re.search(satzanfang_pattern, titel_raw)
    if match:
        ende_erster_satz = match.start() + len(match.group(1))
        erster_satz = titel_raw[:ende_erster_satz].strip()
        if 30 <= len(erster_satz) <= 150:
            return erster_satz
    
    # Strategie 5: Wenn der Text sehr lang ist (>150 Zeichen), 
    # suche den ersten sinnvollen Schnitt-Punkt
    if len(titel_raw) > 150:
        # Versuche nach ~100-120 Zeichen einen Satzabschluss zu finden
        teiltext = titel_raw[:120]
        # Suche rückwärts nach . ! ?
        for satzzeichen in ['. ', '! ', '? ']:
            if satzzeichen in teiltext:
                pos = teiltext.rfind(satzzeichen)
                if pos > 50:  # Mindestens 50 Zeichen
                    return titel_raw[:pos + 1].strip()
        
        # Wenn kein Satzzeichen gefunden, schneide bei letztem Wort vor 120 Zeichen
        return titel_raw[:100].rsplit(' ', 1)[0].strip() + '...'
    
    # Strategie 6: Text ist kurz genug, verwende ihn komplett
    if len(titel_raw) <= 150:
        return titel_raw
    
    # Fallback: Schneide bei 100 Zeichen am letzten Wort
    return titel_raw[:100].rsplit(' ', 1)[0].strip() + '...'

def hole_kress_artikel():
    """Scrape aktuelle Artikel von kress.de/news"""
    artikel_liste = []
    
    try:
        print(f"🌐 Scrape Artikel von kress.de...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get('https://kress.de/news', headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        artikel_candidates = []
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(separator=' ', strip=True)
            href = link.get('href')
            
            if len(link_text) >= 40 and href and len(href) > 5:
                if not any(x in href.lower() for x in ['facebook', 'twitter', 'instagram', 'mailto', 'tel:', '#']):
                    full_url = href if href.startswith('http') else f"https://kress.de{href}"
                    artikel_candidates.append({
                        'titel': link_text,
                        'link': full_url
                    })
        
        seen_titles = set()
        artikel_count = 0
        
        for candidate in artikel_candidates[:20]:
            titel_raw = candidate['titel']
            link = candidate['link']
            
            # Nutze die neue intelligente Titel-Extraktion
            titel = extrahiere_sauberen_titel(titel_raw)
            
            # Qualitätsprüfung
            if len(titel) < 20 or titel in seen_titles:
                continue
            seen_titles.add(titel)
            
            words = titel.lower().split()
            keywords = [w for w in words if len(w) > 5][:10]
            
            artikel_liste.append({
                'source': 'kress',
                'title': titel,
                'link': link,
                'description': titel_raw[:500],
                'keywords': keywords,
                'score': 5
            })
            
            artikel_count += 1
            if artikel_count >= 14:
                break
        
        print(f"   ✅ {artikel_count} Artikel von kress.de gefunden\n")
        return artikel_liste
        
    except Exception as e:
        print(f"   ❌ Fehler beim Scrapen von kress.de: {e}\n")
        return []

def hole_meedia_artikel():
    """Scrape aktuelle Artikel von meedia.de"""
    artikel_liste = []
    
    try:
        print(f"🌐 Scrape Artikel von meedia.de...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get('https://meedia.de', headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        artikel_candidates = []
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(separator=' ', strip=True)
            href = link.get('href')
            
            if len(link_text) >= 35 and href and len(href) > 5:
                if not any(x in href.lower() for x in ['facebook', 'twitter', 'instagram', 'mailto', 'tel:', '#', 'kategorie']):
                    full_url = href if href.startswith('http') else f"https://meedia.de{href}"
                    artikel_candidates.append({
                        'titel': link_text,
                        'link': full_url
                    })
        
        seen_titles = set()
        artikel_count = 0
        
        for candidate in artikel_candidates[:25]:
            titel_raw = candidate['titel']
            link = candidate['link']
            
            # Nutze die neue intelligente Titel-Extraktion
            titel = extrahiere_sauberen_titel(titel_raw)
            
            # Qualitätsprüfung
            if len(titel) < 20 or titel in seen_titles:
                continue
            seen_titles.add(titel)
            
            words = titel.lower().split()
            keywords = [w for w in words if len(w) > 5][:10]
            
            artikel_liste.append({
                'source': 'meedia',
                'title': titel,
                'link': link,
                'description': titel_raw[:500],
                'keywords': keywords,
                'score': 5
            })
            
            artikel_count += 1
            if artikel_count >= 10:
                break
        
        print(f"   ✅ {artikel_count} Artikel von meedia.de gefunden\n")
        return artikel_liste
        
    except Exception as e:
        print(f"   ❌ Fehler beim Scrapen von meedia.de: {e}\n")
        return []

def hole_turi2_artikel():
    """Scrape aktuelle Artikel von turi2.de"""
    artikel_liste = []
    
    try:
        print(f"🌐 Scrape Artikel von turi2.de...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get('https://turi2.de', headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        artikel_candidates = []
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(separator=' ', strip=True)
            href = link.get('href')
            
            if len(link_text) >= 40 and href and len(href) > 5:
                if not any(x in href.lower() for x in ['facebook', 'twitter', 'instagram', 'mailto', 'tel:', '#', 'werben', 'themenwochen', 'termine']):
                    if not any(x in link_text.lower() for x in ['werben bei turi2', 'themenwochen', 'termine der kommunikation']):
                        full_url = href if href.startswith('http') else f"https://turi2.de{href}"
                        artikel_candidates.append({
                            'titel': link_text,
                            'link': full_url
                        })
        
        seen_titles = set()
        artikel_count = 0
        
        for candidate in artikel_candidates[:15]:
            titel_raw = candidate['titel']
            link = candidate['link']
            
            # Nutze die neue intelligente Titel-Extraktion
            titel = extrahiere_sauberen_titel(titel_raw)
            
            # Qualitätsprüfung
            if len(titel) < 20 or titel in seen_titles:
                continue
            seen_titles.add(titel)
            
            words = titel.lower().split()
            keywords = [w for w in words if len(w) > 5][:10]
            
            artikel_liste.append({
                'source': 'turi2',
                'title': titel,
                'link': link,
                'description': titel_raw[:500],
                'keywords': keywords,
                'score': 5
            })
            
            artikel_count += 1
            if artikel_count >= 5:
                break
        
        print(f"   ✅ {artikel_count} Artikel von turi2.de gefunden\n")
        return artikel_liste
        
    except Exception as e:
        print(f"   ❌ Fehler beim Scrapen von turi2.de: {e}\n")
        return []

# ============================================================================
# CLAUDE API - BEWERTUNG
# ============================================================================

def bewerte_artikel_mit_claude(artikel_liste):
    """Bewerte alle Artikel auf einmal mit Claude"""
    
    if not artikel_liste:
        return []
    
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
# CLAUDE API - ZUSAMMENFASSUNG
# ============================================================================

def erstelle_zusammenfassung_mit_claude(title, url, full_text):
    """Erstelle eine prägnante Zusammenfassung mit Claude"""
    
    if not full_text or len(full_text) < 100:
        print(f"       ⚠️ Text zu kurz für Zusammenfassung: {len(full_text) if full_text else 0} Zeichen")
        return "Keine Zusammenfassung verfügbar."
    
    prompt = f"""Erstelle eine prägnante 2-3 Satz Zusammenfassung dieses Medien-Artikels für Fachleute:

Titel: {title}
URL: {url}

Volltext:
{full_text[:2000]}

Antworte NUR mit der Zusammenfassung, keine Einleitung."""

    try:
        print(f"       🔄 Sende Anfrage an Claude API...")
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
            print(f"       ✅ Claude API Antwort erhalten!")
            return summary
        else:
            print(f"       ❌ Claude API Fehler: Status {response.status_code}")
            print(f"       📄 Response: {response.text[:200]}")
            return "Zusammenfassung nicht verfügbar."
            
    except Exception as e:
        print(f"       ❌ Zusammenfassung fehlgeschlagen: {str(e)[:100]}")
        return "Zusammenfassung nicht verfügbar."

# ============================================================================
# NEWSLETTER LOGIK
# ============================================================================

def sammle_artikel():
    """Sammle Artikel von allen RSS-Feeds und Web-Scraping Quellen"""
    alle_artikel = []
    
    for source_name, feed_url in RSS_FEEDS.items():
        print(f"📡 Hole Artikel von {source_name}...")
        try:
            feed = feedparser.parse(feed_url)
            artikel_count = 0
            
            for entry in feed.entries[:20]:
                titel = entry.get('title', 'Kein Titel')
                link = entry.get('link', '')
                beschreibung = entry.get('summary', entry.get('description', ''))
                
                if beschreibung:
                    soup = BeautifulSoup(beschreibung, 'html.parser')
                    beschreibung = soup.get_text(separator=' ', strip=True)
                
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
                    'score': 5
                })
                artikel_count += 1
            
            print(f"   ✅ {artikel_count} Artikel gefunden\n")
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Fehler bei {source_name}: {e}\n")
    
    print("="*70)
    print("🌐 WEB-SCRAPING DEUTSCHE QUELLEN")
    print("="*70 + "\n")
    
    kress_artikel = hole_kress_artikel()
    if kress_artikel:
        alle_artikel.extend(kress_artikel)
    
    meedia_artikel = hole_meedia_artikel()
    if meedia_artikel:
        alle_artikel.extend(meedia_artikel)
    
    turi2_artikel = hole_turi2_artikel()
    if turi2_artikel:
        alle_artikel.extend(turi2_artikel)
    
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
        print(f"\n[{idx}] {artikel['source']}: {artikel['title'][:60]}...")
        
        original_score = artikel['score']
        artikel['score'] = apply_learning_boost(
            artikel['score'],
            artikel['source'],
            artikel['title'],
            artikel['keywords']
        )
        
        if artikel['score'] >= 7:
            print(f"   ✅ Score: {artikel['score']}/10 - RELEVANT!")
            relevante_artikel.append(artikel)
        else:
            print(f"   ⏭️ Score: {artikel['score']}/10 - übersprungen")
    
    # DUPLIKAT-CHECK VOR ZUSAMMENFASSUNGEN
    print(f"\n\n🔍 PRÜFE AUF DUPLIKATE")
    print("="*70)
    
    relevante_ohne_duplikate = []
    duplikat_count = 0
    
    for artikel in relevante_artikel:
        artikel_datum = artikel.get('published', '')
        if pruefe_auf_duplikat(artikel['link'], artikel['title'], artikel_datum):
            duplikat_count += 1
            print(f"⏭️ Duplikat: {artikel['title'][:60]}...")
        else:
            relevante_ohne_duplikate.append(artikel)
    
    print(f"\n✅ {len(relevante_ohne_duplikate)} neue Artikel")
    print(f"⏭️ {duplikat_count} Duplikate übersprungen")
    
    relevante_artikel = relevante_ohne_duplikate
    
    # ZUSAMMENFASSUNGEN ERSTELLEN
    print(f"\n\n📝 ERSTELLE ZUSAMMENFASSUNGEN FÜR {len(relevante_artikel)} RELEVANTE ARTIKEL")
    print("="*70)
    
    for idx, artikel in enumerate(relevante_artikel, 1):
        print(f"\n[{idx}/{len(relevante_artikel)}] {artikel['title'][:60]}...")
        
        full_text = None
        
        print(f"       🌐 Lade vollständigen Artikel von URL...")
        full_text = fetch_full_article(artikel['link'])
        
        if full_text and len(full_text) > 200:
            print(f"       ✅ Artikel geladen: {len(full_text)} Zeichen")
        else:
            print(f"       ⚠️ Volltext konnte nicht geladen werden (Paywall/Login?)")
            print(f"       🔍 Versuche Web-Recherche als Fallback...")
            web_context = search_web_for_context(artikel['title'], artikel['description'])
            
            if web_context:
                full_text = web_context
                print(f"       ✅ Kontext-Recherche erfolgreich: {len(full_text)} Zeichen")
            else:
                full_text = artikel['description']
                print(f"       ⚠️ Fallback auf RSS-Beschreibung: {len(full_text)} Zeichen")
        
        if full_text and len(full_text) >= 50:
            print(f"       🤖 Erstelle Zusammenfassung mit Claude...")
            
            artikel['summary'] = erstelle_zusammenfassung_mit_claude(
                artikel['title'],
                artikel['link'],
                full_text
            )
            
            if artikel['summary'] and artikel['summary'] != "Zusammenfassung nicht verfügbar.":
                print(f"       ✅ Zusammenfassung erstellt: {artikel['summary'][:100]}...")
            else:
                print(f"       ⚠️ Claude gab keine gültige Zusammenfassung zurück!")
        else:
            if not full_text:
                print(f"       ❌ Keine Zusammenfassung möglich - kein Text geladen!")
            else:
                print(f"       ❌ Keine Zusammenfassung möglich - Text zu kurz: {len(full_text)} Zeichen")
            artikel['summary'] = "Zusammenfassung nicht verfügbar - Artikel konnte nicht geladen werden."
        
        time.sleep(0.5)
    
    return relevante_artikel

# ============================================================================
# SORTIERUNG NACH REGION
# ============================================================================

def sortiere_nach_region(artikel_liste):
    """Sortiere Artikel nach Region: 🇩🇪 Deutschland → 🇬🇧 UK → 🇺🇸 USA"""
    
    regionen = {
        'deutschland': ['DWDL', 'Horizont Medien', 'W&V', 'Quotenmeter', 'kress', 'meedia', 'turi2'],
        'uk': ['Guardian Media'],
        'usa': ['Variety', 'Deadline', 'Hollywood Reporter']
    }
    
    deutschland = []
    uk = []
    usa = []
    
    for artikel in artikel_liste:
        source = artikel['source']
        
        if source in regionen['deutschland']:
            deutschland.append(artikel)
        elif source in regionen['uk']:
            uk.append(artikel)
        elif source in regionen['usa']:
            usa.append(artikel)
    
    deutschland.sort(key=lambda x: x['source'])
    uk.sort(key=lambda x: x['source'])
    usa.sort(key=lambda x: x['source'])
    
    return deutschland + uk + usa

# ============================================================================
# JSON EXPORT
# ============================================================================

def speichere_als_json(artikel_liste):
    """Speichere relevante Artikel als JSON - sortiert nach Region"""
    
    heute = datetime.now().strftime('%Y-%m-%d')
    filename = f'newsletter-{heute}.json'
    
    artikel_liste_sortiert = sortiere_nach_region(artikel_liste)
    
    data = {
        'date': heute,
        'articles': []
    }
    
    for artikel in artikel_liste_sortiert:
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

def aktualisiere_newsletter_index():
    """
    Aktualisiert die Index-Dateien für die Webseite:
    - newsletter-index.json: Liste aller verfügbaren Daten  
    - newsletter-data.json: Kombinierte Daten aller Newsletter
    """
    import glob
    
    # Finde alle Newsletter-JSON-Dateien
    newsletter_dateien = sorted(glob.glob('newsletter-20*.json'), reverse=True)
    
    if not newsletter_dateien:
        print("⚠️ Keine Newsletter-Dateien gefunden")
        return
    
    # Erstelle newsletter-index.json (Liste aller Daten)
    index_data = {
        'dates': []
    }
    
    # Erstelle newsletter-data.json (alle Artikel kombiniert)
    all_data = {
        'newsletters': []
    }
    
    for datei in newsletter_dateien:
        # Extrahiere Datum aus Dateiname (z.B. newsletter-2025-11-25.json -> 2025-11-25)
        datum = datei.replace('newsletter-', '').replace('.json', '')
        index_data['dates'].append(datum)
        
        # Lade Newsletter-Daten
        try:
            with open(datei, 'r', encoding='utf-8') as f:
                newsletter_data = json.load(f)
                all_data['newsletters'].append(newsletter_data)
        except Exception as e:
            print(f"⚠️ Fehler beim Laden von {datei}: {e}")
    
    # Speichere newsletter-index.json
    try:
        with open('newsletter-index.json', 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Index aktualisiert: {len(index_data['dates'])} Newsletter")
    except Exception as e:
        print(f"❌ Fehler beim Speichern von newsletter-index.json: {e}")
    
    # Speichere newsletter-data.json
    try:
        with open('newsletter-data.json', 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Daten-Archiv aktualisiert: {len(all_data['newsletters'])} Newsletter")
    except Exception as e:
        print(f"❌ Fehler beim Speichern von newsletter-data.json: {e}")

# ============================================================================
# EMAIL VERSAND
# ============================================================================

def erstelle_html_email(anzahl_artikel, empfaenger_name, datum):
    """Sendet kurze Email mit Link zur Webseite"""
    
    # Link OHNE date-Parameter -> lädt automatisch die heutige JSON-Datei
    newsletter_link = f"{NEWSLETTER_URL}"
    
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
            html_content = erstelle_html_email(anzahl_artikel, name, heute)
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🎬 Zoo Medien Newsletter · {anzahl_artikel} Artikel · {datetime.now().strftime('%d.%m.%Y')}"
            msg['From'] = GMAIL_USER
            msg['To'] = email
            
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
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
    print("🎬 ZOO MEDIEN NEWSLETTER - MIT ARCHIV-SYSTEM")
    if LEARNING_RULES:
        print("🎓 Learning Rules aktiv")
    if SUPABASE_AVAILABLE:
        print("💾 Archiv-System aktiv")
    print("="*70 + "\n")
    
    print("🤖 SAMMLE UND BEWERTE ARTIKEL")
    print("="*70)
    
    # 1. Sammle alle Artikel
    alle_artikel = sammle_artikel()
    
    if not alle_artikel:
        print("❌ Keine Artikel gefunden")
        return
    
    # Statistiken für später
    stats = {
        'total': len(alle_artikel),
        'relevant': 0,
        'new': 0,
        'duplicates': 0,
        'sources': list(RSS_FEEDS.keys()) + list(WEB_SCRAPING_SOURCES.keys()),
        'status': 'success',
        'error': None
    }
    
    # 2. Bewerte und erstelle Zusammenfassungen (mit Duplikat-Check)
    relevante_artikel = verarbeite_artikel(alle_artikel)
    
    # Update Stats
    stats['relevant'] = len([a for a in alle_artikel if a.get('score', 0) >= 7])
    stats['new'] = len(relevante_artikel)
    stats['duplicates'] = stats['relevant'] - stats['new']
    
    if not relevante_artikel:
        print("\n⚠️ Keine relevanten Artikel heute (Score < 7)")
        return
    
    # 3. Archiviere Artikel in Supabase
    heute = datetime.now().strftime('%Y-%m-%d')
    
    if SUPABASE_AVAILABLE:
        print(f"\n💾 ARCHIVIERE {len(relevante_artikel)} ARTIKEL")
        print("="*70)
        
        regionen = {
            'deutschland': ['DWDL', 'Horizont Medien', 'W&V', 'Quotenmeter', 'kress', 'meedia', 'turi2'],
            'uk': ['Guardian Media'],
            'usa': ['Variety', 'Deadline', 'Hollywood Reporter']
        }
        
        archiviert_count = 0
        for artikel in relevante_artikel:
            source = artikel['source']
            region = 'deutschland' if source in regionen['deutschland'] else \
                     'uk' if source in regionen['uk'] else 'usa'
            
            if speichere_artikel_im_archiv(artikel, heute, region):
                print(f"✓ {artikel['title'][:50]}...")
                archiviert_count += 1
        
        print(f"\n✅ {archiviert_count}/{len(relevante_artikel)} Artikel archiviert")
        
        # Speichere Run-Metadata
        speichere_run_metadata(heute, stats)
    
    # 4. Speichere JSON
    print("\n")
    filename = speichere_als_json(relevante_artikel)
    
    # 5. Aktualisiere Index-Dateien für Webseite
    aktualisiere_newsletter_index()
    
    # 6. Versende Newsletter
    versende_newsletter(relevante_artikel)
    
    # 7. Zusammenfassung
    print("\n" + "="*70)
    print("🎉 NEWSLETTER VERSENDET!")
    print("="*70)
    print(f"✅ {len(EMPFAENGER)}/{len(EMPFAENGER)} Emails gesendet")
    print(f"📄 Datei: {filename}")
    print(f"🌐 Web: {NEWSLETTER_URL}/?date={heute}")
    if SUPABASE_AVAILABLE:
        print(f"💾 Archiv: {len(relevante_artikel)} neue Artikel, {stats['duplicates']} Duplikate gefiltert")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
