#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Weekly Learning Analysis für Zoo Media Newsletter
Analysiert Feedback und generiert intelligente Lernregeln auf Basis von THEMEN, nicht nur Quellen
"""

import os
import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import anthropic
from supabase import create_client, Client

# ============================================================================
# KONFIGURATION
# ============================================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# Mindestanzahl Bewertungen für eine Regel
MIN_FEEDBACK_COUNT = 3

# Confidence Threshold für Regeln (% positive Bewertungen)
HIGH_CONFIDENCE_THRESHOLD = 0.75  # 75%+ positiv → bonus
LOW_CONFIDENCE_THRESHOLD = 0.25   # 25%- positiv → malus

# ============================================================================
# SUPABASE CLIENT
# ============================================================================

def get_supabase_client() -> Client:
    """Erstellt Supabase Client"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL und SUPABASE_KEY müssen gesetzt sein")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================================
# FEEDBACK DATEN LADEN
# ============================================================================

def load_feedback_data(days_back: int = 30) -> list:
    """
    Lädt Feedback-Daten der letzten X Tage aus Supabase
    
    Args:
        days_back: Anzahl Tage zurück
        
    Returns:
        Liste von Feedback-Einträgen
    """
    supabase = get_supabase_client()
    
    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    try:
        response = supabase.table('artikel_bewertungen') \
            .select('*') \
            .gte('newsletter_datum', cutoff_date) \
            .execute()
        
        print(f"✅ {len(response.data)} Bewertungen geladen (letzte {days_back} Tage)")
        return response.data
        
    except Exception as e:
        print(f"❌ Fehler beim Laden der Daten: {e}")
        return []

# ============================================================================
# THEMEN-EXTRAKTION MIT CLAUDE
# ============================================================================

def extract_themes_from_titles(titles: list) -> dict:
    """
    Verwendet Claude API um Themen/Keywords aus Artikel-Titeln zu extrahieren
    
    Args:
        titles: Liste von Artikel-Titeln
        
    Returns:
        Dict mit {titel: [themen_liste]}
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Batch-Verarbeitung: Alle Titel auf einmal
    titles_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)])
    
    prompt = f"""Analysiere diese TV/Medien-Artikel-Titel und extrahiere die HAUPTTHEMEN.

Artikel-Titel:
{titles_text}

Aufgabe:
1. Identifiziere für JEDEN Titel die 2-4 wichtigsten Themen/Keywords
2. Fokus auf: Sender, Formate, Personen, Konzepte, Länder
3. Normalisiere ähnliche Begriffe (z.B. "ZDF" = "Zweites Deutsches Fernsehen")
4. Verwende deutsche und englische Begriffe wie sie im Kontext üblich sind

Beispiele:
- "RTL Quote sinkt auf Rekordtief" → ["RTL", "Quote", "Rating", "Deutschland"]
- "Netflix Deutschland plant neue Serie" → ["Netflix", "Deutschland", "Serie", "Streaming"]
- "BBC Drama gewinnt Emmy" → ["BBC", "Drama", "Emmy", "Award", "UK"]

Antworte NUR mit einem JSON-Array im Format:
[
  {{"titel_nummer": 1, "themen": ["Theme1", "Theme2", "Theme3"]}},
  {{"titel_nummer": 2, "themen": ["Theme1", "Theme2"]}}
]

WICHTIG: Antworte NUR mit dem JSON-Array, ohne zusätzlichen Text!"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text.strip()
        
        # Parse JSON
        themes_data = json.loads(response_text)
        
        # Mappe zurück zu Titeln
        result = {}
        for item in themes_data:
            titel_idx = item['titel_nummer'] - 1
            if 0 <= titel_idx < len(titles):
                result[titles[titel_idx]] = item['themen']
        
        print(f"✅ Themen für {len(result)} Artikel extrahiert")
        return result
        
    except Exception as e:
        print(f"❌ Fehler bei Themen-Extraktion: {e}")
        return {}

# ============================================================================
# THEMEN-ANALYSE
# ============================================================================

def analyze_theme_feedback(feedback_data: list) -> dict:
    """
    Analysiert Feedback auf Themen-Ebene
    
    Args:
        feedback_data: Feedback-Einträge aus Supabase
        
    Returns:
        Dict mit Themen-Statistiken
    """
    if not feedback_data:
        print("⚠️ Keine Feedback-Daten vorhanden")
        return {}
    
    # Extrahiere alle Titel
    all_titles = [entry['artikel_titel'] for entry in feedback_data]
    
    # Hole Themen von Claude
    title_themes = extract_themes_from_titles(all_titles)
    
    if not title_themes:
        print("⚠️ Keine Themen extrahiert")
        return {}
    
    # Zähle Feedback pro Thema
    theme_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'total': 0})
    
    for entry in feedback_data:
        titel = entry['artikel_titel']
        bewertung = entry['bewertung']
        
        if titel in title_themes:
            themes = title_themes[titel]
            
            for theme in themes:
                theme_stats[theme]['total'] += 1
                
                if bewertung == 'relevant':
                    theme_stats[theme]['relevant'] += 1
                else:
                    theme_stats[theme]['nicht_relevant'] += 1
    
    return dict(theme_stats)

# ============================================================================
# QUELLEN-ANALYSE (Fallback)
# ============================================================================

def analyze_source_feedback(feedback_data: list) -> dict:
    """
    Analysiert Feedback auf Quellen-Ebene (als Fallback)
    
    Args:
        feedback_data: Feedback-Einträge aus Supabase
        
    Returns:
        Dict mit Quellen-Statistiken
    """
    source_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'total': 0})
    
    for entry in feedback_data:
        quelle = entry['artikel_quelle']
        bewertung = entry['bewertung']
        
        source_stats[quelle]['total'] += 1
        
        if bewertung == 'relevant':
            source_stats[quelle]['relevant'] += 1
        else:
            source_stats[quelle]['nicht_relevant'] += 1
    
    return dict(source_stats)

# ============================================================================
# REGEL-GENERIERUNG
# ============================================================================

def generate_learning_rules(theme_stats: dict, source_stats: dict) -> list:
    """
    Generiert Lernregeln basierend auf Themen- und Quellen-Statistiken
    
    Args:
        theme_stats: Themen-Statistiken
        source_stats: Quellen-Statistiken
        
    Returns:
        Liste von Lernregeln
    """
    rules = []
    
    # ========================================
    # THEMEN-BASIERTE REGELN (Priorität!)
    # ========================================
    
    for theme, stats in theme_stats.items():
        if stats['total'] < MIN_FEEDBACK_COUNT:
            continue
        
        positive_ratio = stats['relevant'] / stats['total']
        
        # Stark positive Themen → Bonus
        if positive_ratio >= HIGH_CONFIDENCE_THRESHOLD:
            adjustment = 2 if positive_ratio >= 0.9 else 1
            
            rules.append({
                'type': 'theme_bonus',
                'theme': theme,
                'adjustment': adjustment,
                'confidence': positive_ratio,
                'sample_size': stats['total'],
                'reasoning': f"Thema '{theme}' hat {positive_ratio*100:.1f}% positive Bewertungen ({stats['relevant']}/{stats['total']})"
            })
        
        # Stark negative Themen → Malus
        elif positive_ratio <= LOW_CONFIDENCE_THRESHOLD:
            adjustment = -2 if positive_ratio <= 0.1 else -1
            
            rules.append({
                'type': 'theme_malus',
                'theme': theme,
                'adjustment': adjustment,
                'confidence': 1 - positive_ratio,
                'sample_size': stats['total'],
                'reasoning': f"Thema '{theme}' hat nur {positive_ratio*100:.1f}% positive Bewertungen ({stats['relevant']}/{stats['total']})"
            })
    
    # ========================================
    # QUELLEN-BASIERTE REGELN (Fallback)
    # ========================================
    
    for source, stats in source_stats.items():
        if stats['total'] < MIN_FEEDBACK_COUNT * 2:  # Höhere Anforderung für Quellen
            continue
        
        positive_ratio = stats['relevant'] / stats['total']
        
        # Nur sehr extreme Quellen-Präferenzen
        if positive_ratio >= 0.85:
            rules.append({
                'type': 'source_bonus',
                'source': source,
                'adjustment': 1,
                'confidence': positive_ratio,
                'sample_size': stats['total'],
                'reasoning': f"Quelle '{source}' hat {positive_ratio*100:.1f}% positive Bewertungen ({stats['relevant']}/{stats['total']})"
            })
        
        elif positive_ratio <= 0.15:
            rules.append({
                'type': 'source_malus',
                'source': source,
                'adjustment': -1,
                'confidence': 1 - positive_ratio,
                'sample_size': stats['total'],
                'reasoning': f"Quelle '{source}' hat nur {positive_ratio*100:.1f}% positive Bewertungen ({stats['relevant']}/{stats['total']})"
            })
    
    # Sortiere Regeln nach Confidence
    rules.sort(key=lambda x: x['confidence'], reverse=True)
    
    return rules

# ============================================================================
# REGELN SPEICHERN
# ============================================================================

def save_learning_rules(rules: list):
    """
    Speichert Lernregeln in learning_rules.py
    
    Args:
        rules: Liste von Lernregeln
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    file_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Learning Rules für Zoo Media Newsletter
Auto-generiert am: {timestamp}

Diese Regeln werden automatisch beim Newsletter-Scoring angewendet.
"""

# ============================================================================
# AKTIVE LERNREGELN
# ============================================================================

LEARNING_RULES = {json.dumps(rules, indent=4, ensure_ascii=False)}

# ============================================================================
# REGEL-ANWENDUNG
# ============================================================================

def apply_learning_rules(article_title: str, article_source: str, base_score: int) -> int:
    """
    Wendet Lernregeln auf einen Artikel an
    
    Args:
        article_title: Artikel-Titel
        article_source: Artikel-Quelle
        base_score: Basis-Score von Claude
        
    Returns:
        Angepasster Score
    """
    adjusted_score = base_score
    applied_rules = []
    
    # Themen-basierte Regeln
    for rule in LEARNING_RULES:
        if rule['type'] in ['theme_bonus', 'theme_malus']:
            theme = rule['theme'].lower()
            title_lower = article_title.lower()
            
            # Check ob Thema im Titel vorkommt
            if theme in title_lower:
                adjusted_score += rule['adjustment']
                applied_rules.append(f"{{rule['type']}}: {{rule['theme']}} ({{rule['adjustment']:+d}})")
        
        # Quellen-basierte Regeln
        elif rule['type'] in ['source_bonus', 'source_malus']:
            if rule['source'] == article_source:
                adjusted_score += rule['adjustment']
                applied_rules.append(f"{{rule['type']}}: {{rule['source']}} ({{rule['adjustment']:+d}})")
    
    # Score zwischen 1-10 halten
    adjusted_score = max(1, min(10, adjusted_score))
    
    if applied_rules:
        print(f"  📊 Regeln angewendet: {{', '.join(applied_rules)}} → Score: {{base_score}} → {{adjusted_score}}")
    
    return adjusted_score

def get_rule_summary() -> str:
    """Gibt Zusammenfassung der aktiven Regeln zurück"""
    if not LEARNING_RULES:
        return "Keine aktiven Lernregeln."
    
    summary = f"{{len(LEARNING_RULES)}} aktive Lernregeln:\\n\\n"
    
    for i, rule in enumerate(LEARNING_RULES, 1):
        summary += f"{{i}}. "
        
        if rule['type'] in ['theme_bonus', 'theme_malus']:
            summary += f"Thema '{{rule['theme']}}': {{rule['adjustment']:+d}} Punkte\\n"
        elif rule['type'] in ['source_bonus', 'source_malus']:
            summary += f"Quelle '{{rule['source']}}': {{rule['adjustment']:+d}} Punkte\\n"
        
        summary += f"   {{rule['reasoning']}}\\n\\n"
    
    return summary
'''
    
    # Speichere Datei
    with open('learning_rules.py', 'w', encoding='utf-8') as f:
        f.write(file_content)
    
    print(f"✅ {len(rules)} Lernregeln gespeichert in learning_rules.py")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Hauptfunktion"""
    print("=" * 80)
    print("🧠 Zoo Media Newsletter - Weekly Learning Analysis")
    print("=" * 80)
    print()
    
    # 1. Lade Feedback-Daten
    print("📊 Lade Feedback-Daten...")
    feedback_data = load_feedback_data(days_back=30)
    
    if not feedback_data:
        print("⚠️ Keine Feedback-Daten vorhanden. Analyse beendet.")
        return
    
    print(f"✅ {len(feedback_data)} Bewertungen geladen")
    print()
    
    # 2. Analysiere Themen
    print("🔍 Analysiere Themen-Feedback...")
    theme_stats = analyze_theme_feedback(feedback_data)
    print(f"✅ {len(theme_stats)} verschiedene Themen gefunden")
    print()
    
    # 3. Analysiere Quellen (Fallback)
    print("🔍 Analysiere Quellen-Feedback...")
    source_stats = analyze_source_feedback(feedback_data)
    print(f"✅ {len(source_stats)} verschiedene Quellen analysiert")
    print()
    
    # 4. Generiere Regeln
    print("⚙️ Generiere Lernregeln...")
    rules = generate_learning_rules(theme_stats, source_stats)
    print(f"✅ {len(rules)} Regeln generiert")
    print()
    
    # 5. Ausgabe Details
    if rules:
        print("📋 Generierte Regeln:")
        print("-" * 80)
        for i, rule in enumerate(rules, 1):
            print(f"{i}. {rule['reasoning']}")
            print(f"   Typ: {rule['type']}, Anpassung: {rule['adjustment']:+d}, Confidence: {rule['confidence']:.1%}")
            print()
    else:
        print("⚠️ Keine Regeln generiert (zu wenig Daten oder keine starken Muster)")
        print()
    
    # 6. Speichere Regeln
    print("💾 Speichere Regeln...")
    save_learning_rules(rules)
    print()
    
    print("=" * 80)
    print("✅ Analyse abgeschlossen!")
    print("=" * 80)

if __name__ == '__main__':
    main()
