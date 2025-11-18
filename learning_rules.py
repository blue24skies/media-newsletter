#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Learning Rules für Zoo Media Newsletter
Auto-generiert durch weekly_analysis.py
Letzte Aktualisierung: Noch keine Daten vorhanden

Diese Regeln werden automatisch beim Newsletter-Scoring angewendet.
Das System lernt auf THEMEN-Ebene, nicht nur auf Quellen-Ebene!
"""

# ============================================================================
# AKTIVE LERNREGELN
# ============================================================================

# Wird automatisch durch weekly_analysis.py befüllt
LEARNING_RULES = []

# Beispiel wie Regeln aussehen werden:
"""
LEARNING_RULES = [
    {
        'type': 'theme_bonus',
        'theme': 'ZDF Quote',
        'adjustment': 2,
        'confidence': 0.89,
        'sample_size': 12,
        'reasoning': "Thema 'ZDF Quote' hat 89.0% positive Bewertungen (12/13)"
    },
    {
        'type': 'theme_bonus',
        'theme': 'Netflix Deutschland',
        'adjustment': 1,
        'confidence': 0.75,
        'sample_size': 8,
        'reasoning': "Thema 'Netflix Deutschland' hat 75.0% positive Bewertungen (6/8)"
    },
    {
        'type': 'theme_malus',
        'theme': 'Kritik',
        'adjustment': -2,
        'confidence': 0.92,
        'sample_size': 5,
        'reasoning': "Thema 'Kritik' hat nur 8.0% positive Bewertungen (1/12)"
    },
    {
        'type': 'source_bonus',
        'source': 'DWDL',
        'adjustment': 1,
        'confidence': 0.87,
        'sample_size': 45,
        'reasoning': "Quelle 'DWDL' hat 87.0% positive Bewertungen (39/45)"
    }
]
"""

# ============================================================================
# REGEL-ANWENDUNG (wird von medien_newsletter_web.py genutzt)
# ============================================================================

def apply_learning_rules(article_title, article_source, base_score):
    """
    Wendet Lernregeln auf einen Artikel an
    
    Args:
        article_title: Artikel-Titel
        article_source: Artikel-Quelle
        base_score: Basis-Score von Claude
        
    Returns:
        (adjusted_score, applied_rules)
    """
    if not LEARNING_RULES:
        return base_score, []
    
    adjusted_score = base_score
    applied_rules = []
    title_lower = article_title.lower()
    
    # Themen-basierte Regeln
    for rule in LEARNING_RULES:
        if rule['type'] in ['theme_bonus', 'theme_malus']:
            theme = rule['theme'].lower()
            
            # Check ob Thema im Titel vorkommt
            if theme in title_lower:
                adjusted_score += rule['adjustment']
                applied_rules.append({
                    'type': rule['type'],
                    'theme': rule['theme'],
                    'adjustment': rule['adjustment']
                })
        
        # Quellen-basierte Regeln
        elif rule['type'] in ['source_bonus', 'source_malus']:
            if rule['source'] == article_source:
                adjusted_score += rule['adjustment']
                applied_rules.append({
                    'type': rule['type'],
                    'source': rule['source'],
                    'adjustment': rule['adjustment']
                })
    
    # Score zwischen 1-10 halten
    adjusted_score = max(1, min(10, adjusted_score))
    
    return adjusted_score, applied_rules

def get_rule_summary():
    """Gibt Zusammenfassung der aktiven Regeln zurück"""
    if not LEARNING_RULES:
        return "Noch keine aktiven Lernregeln vorhanden.\nBewerte Artikel um das System zu trainieren!"
    
    summary = f"{len(LEARNING_RULES)} aktive Lernregeln:\n\n"
    
    theme_rules = [r for r in LEARNING_RULES if 'theme' in r['type']]
    source_rules = [r for r in LEARNING_RULES if 'source' in r['type']]
    
    if theme_rules:
        summary += "📊 THEMEN-REGELN:\n"
        for i, rule in enumerate(theme_rules, 1):
            summary += f"{i}. {rule['theme']}: {rule['adjustment']:+d} Punkte\n"
            summary += f"   {rule['reasoning']}\n\n"
    
    if source_rules:
        summary += "\n📰 QUELLEN-REGELN:\n"
        for i, rule in enumerate(source_rules, 1):
            summary += f"{i}. {rule['source']}: {rule['adjustment']:+d} Punkte\n"
            summary += f"   {rule['reasoning']}\n\n"
    
    return summary

# ============================================================================
# STATUS
# ============================================================================

if __name__ == '__main__':
    print("="*70)
    print("🧠 Zoo Media Newsletter - Learning Rules")
    print("="*70)
    print()
    print(get_rule_summary())
    print("="*70)
