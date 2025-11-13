#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Newsletter - Wöchentliche Lern-Analyse
Analysiert Bewertungen und passt automatisch Bewertungskriterien an
"""

import os
import sys
from datetime import datetime, timedelta
from supabase import create_client, Client
import json

# ============================================================================
# KONFIGURATION
# ============================================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# Schwellenwerte für automatische Regeln
MIN_BEWERTUNGEN = 5  # Mindestanzahl Bewertungen für eine Regel
RELEVANT_THRESHOLD = 70  # % relevant für positive Regel
IRRELEVANT_THRESHOLD = 30  # % relevant für negative Regel

# ============================================================================
# SUPABASE CLIENT
# ============================================================================

def get_supabase_client() -> Client:
    """Erstellt Supabase Client"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ FEHLER: SUPABASE_URL oder SUPABASE_KEY fehlt!")
        sys.exit(1)
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================================
# ANALYSE FUNKTIONEN
# ============================================================================

def analysiere_zeitraum(supabase: Client, tage=7):
    """Analysiert Bewertungen der letzten X Tage"""
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=tage)
    
    print(f"\n🔍 ANALYSIERE ZEITRAUM: {start_date} bis {end_date}")
    print("="*70 + "\n")
    
    # Hole alle Bewertungen des Zeitraums
    response = supabase.table('artikel_bewertungen')\
        .select('*')\
        .gte('newsletter_datum', str(start_date))\
        .lte('newsletter_datum', str(end_date))\
        .execute()
    
    bewertungen = response.data
    
    if not bewertungen:
        print("⚠️  Keine Bewertungen im Zeitraum gefunden!")
        return None
    
    print(f"📊 {len(bewertungen)} Bewertungen gefunden\n")
    
    # Analyse nach Quelle
    quellen_stats = analyze_by_source(bewertungen)
    
    # Analyse nach Keywords im Titel
    keyword_stats = analyze_by_keywords(bewertungen)
    
    return {
        'zeitraum': {'start': start_date, 'end': end_date},
        'anzahl_bewertungen': len(bewertungen),
        'quellen': quellen_stats,
        'keywords': keyword_stats
    }


def analyze_by_source(bewertungen):
    """Analysiert Bewertungen gruppiert nach Quelle"""
    
    quellen = {}
    
    for b in bewertungen:
        quelle = b['artikel_quelle']
        if quelle not in quellen:
            quellen[quelle] = {'total': 0, 'relevant': 0, 'nicht_relevant': 0}
        
        quellen[quelle]['total'] += 1
        if b['bewertung'] == 'relevant':
            quellen[quelle]['relevant'] += 1
        else:
            quellen[quelle]['nicht_relevant'] += 1
    
    # Berechne Prozente
    for quelle, stats in quellen.items():
        stats['relevant_prozent'] = round((stats['relevant'] / stats['total']) * 100, 1)
    
    # Sortiere nach Anzahl
    quellen_sorted = dict(sorted(quellen.items(), key=lambda x: x[1]['total'], reverse=True))
    
    print("📰 ANALYSE NACH QUELLE:")
    print("-" * 70)
    for quelle, stats in quellen_sorted.items():
        emoji = "✅" if stats['relevant_prozent'] >= RELEVANT_THRESHOLD else "⚠️" if stats['relevant_prozent'] <= IRRELEVANT_THRESHOLD else "📊"
        print(f"{emoji} {quelle:20s} | {stats['total']:3d} Bewertungen | {stats['relevant_prozent']:5.1f}% relevant")
    print()
    
    return quellen_sorted


def analyze_by_keywords(bewertungen):
    """Analysiert Bewertungen nach Keywords im Titel"""
    
    # Wichtige Keywords zum Tracken
    keywords = [
        'streaming', 'netflix', 'prime', 'disney', 'sky',
        'format', 'quote', 'serie', 'show', 'dokumentation',
        'politik', 'trump', 'bbc', 'ceo', 'fusion',
        'künstliche intelligenz', 'ki', 'ai', 'tech'
    ]
    
    keyword_stats = {}
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        matches = [b for b in bewertungen if keyword_lower in b['artikel_titel'].lower()]
        
        if len(matches) >= MIN_BEWERTUNGEN:
            relevant_count = sum(1 for b in matches if b['bewertung'] == 'relevant')
            total = len(matches)
            prozent = round((relevant_count / total) * 100, 1)
            
            keyword_stats[keyword] = {
                'total': total,
                'relevant': relevant_count,
                'relevant_prozent': prozent
            }
    
    if keyword_stats:
        # Sortiere nach Anzahl
        keyword_stats = dict(sorted(keyword_stats.items(), key=lambda x: x[1]['total'], reverse=True))
        
        print("🔑 ANALYSE NACH KEYWORDS:")
        print("-" * 70)
        for keyword, stats in keyword_stats.items():
            emoji = "✅" if stats['relevant_prozent'] >= RELEVANT_THRESHOLD else "⚠️" if stats['relevant_prozent'] <= IRRELEVANT_THRESHOLD else "📊"
            print(f"{emoji} {keyword:20s} | {stats['total']:3d} Artikel | {stats['relevant_prozent']:5.1f}% relevant")
        print()
    
    return keyword_stats


# ============================================================================
# REGEL-GENERIERUNG
# ============================================================================

def generiere_regeln(analyse_daten, supabase: Client):
    """Generiert automatisch Lern-Regeln basierend auf Analyse"""
    
    print("🤖 GENERIERE AUTOMATISCHE REGELN")
    print("="*70 + "\n")
    
    neue_regeln = []
    aktualisierte_regeln = []
    
    # Regeln aus Quellen-Analyse
    for quelle, stats in analyse_daten['quellen'].items():
        if stats['total'] < MIN_BEWERTUNGEN:
            continue
        
        regel = None
        
        # Sehr relevant → Score erhöhen
        if stats['relevant_prozent'] >= RELEVANT_THRESHOLD:
            regel = {
                'regel_typ': 'quelle',
                'bedingung': quelle,
                'score_modifier': +1,
                'begründung': f"{stats['relevant_prozent']}% der Artikel als relevant bewertet ({stats['relevant']}/{stats['total']})",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': stats['relevant_prozent'],
                'aktiv': True
            }
            print(f"✅ NEUE REGEL: {quelle} → Score +1 (sehr relevant)")
        
        # Sehr irrelevant → Score senken
        elif stats['relevant_prozent'] <= IRRELEVANT_THRESHOLD:
            regel = {
                'regel_typ': 'quelle',
                'bedingung': quelle,
                'score_modifier': -2,
                'begründung': f"Nur {stats['relevant_prozent']}% der Artikel als relevant bewertet ({stats['relevant']}/{stats['total']})",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': stats['relevant_prozent'],
                'aktiv': True
            }
            print(f"⚠️  NEUE REGEL: {quelle} → Score -2 (oft irrelevant)")
        
        if regel:
            # Prüfe ob Regel schon existiert
            existing = supabase.table('lern_regeln')\
                .select('*')\
                .eq('regel_typ', regel['regel_typ'])\
                .eq('bedingung', regel['bedingung'])\
                .execute()
            
            if existing.data:
                # Update existierende Regel
                supabase.table('lern_regeln')\
                    .update(regel)\
                    .eq('id', existing.data[0]['id'])\
                    .execute()
                aktualisierte_regeln.append(regel)
            else:
                # Neue Regel erstellen
                supabase.table('lern_regeln')\
                    .insert(regel)\
                    .execute()
                neue_regeln.append(regel)
    
    # Regeln aus Keyword-Analyse
    for keyword, stats in analyse_daten['keywords'].items():
        regel = None
        
        if stats['relevant_prozent'] >= RELEVANT_THRESHOLD:
            regel = {
                'regel_typ': 'keyword',
                'bedingung': keyword,
                'score_modifier': +1,
                'begründung': f"{stats['relevant_prozent']}% als relevant bewertet ({stats['relevant']}/{stats['total']})",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': stats['relevant_prozent'],
                'aktiv': True
            }
            print(f"✅ NEUE REGEL: Keyword '{keyword}' → Score +1")
        
        elif stats['relevant_prozent'] <= IRRELEVANT_THRESHOLD:
            regel = {
                'regel_typ': 'keyword',
                'bedingung': keyword,
                'score_modifier': -1,
                'begründung': f"Nur {stats['relevant_prozent']}% als relevant bewertet ({stats['relevant']}/{stats['total']})",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': stats['relevant_prozent'],
                'aktiv': True
            }
            print(f"⚠️  NEUE REGEL: Keyword '{keyword}' → Score -1")
        
        if regel:
            existing = supabase.table('lern_regeln')\
                .select('*')\
                .eq('regel_typ', regel['regel_typ'])\
                .eq('bedingung', regel['bedingung'])\
                .execute()
            
            if existing.data:
                supabase.table('lern_regeln')\
                    .update(regel)\
                    .eq('id', existing.data[0]['id'])\
                    .execute()
                aktualisierte_regeln.append(regel)
            else:
                supabase.table('lern_regeln')\
                    .insert(regel)\
                    .execute()
                neue_regeln.append(regel)
    
    print()
    return neue_regeln, aktualisierte_regeln


def speichere_analyse_log(supabase: Client, analyse_daten, neue_regeln, aktualisierte_regeln):
    """Speichert Analyse-Log in Datenbank"""
    
    log_text = f"""
Analysezeitraum: {analyse_daten['zeitraum']['start']} bis {analyse_daten['zeitraum']['end']}
Bewertungen gesamt: {analyse_daten['anzahl_bewertungen']}

Quellen analysiert: {len(analyse_daten['quellen'])}
Keywords analysiert: {len(analyse_daten['keywords'])}

Neue Regeln: {len(neue_regeln)}
Aktualisierte Regeln: {len(aktualisierte_regeln)}
"""
    
    supabase.table('analyse_logs').insert({
        'analyse_datum': datetime.now().date().isoformat(),
        'zeitraum_von': str(analyse_daten['zeitraum']['start']),
        'zeitraum_bis': str(analyse_daten['zeitraum']['end']),
        'anzahl_bewertungen': analyse_daten['anzahl_bewertungen'],
        'neue_regeln': len(neue_regeln),
        'aktualisierte_regeln': len(aktualisierte_regeln),
        'log_text': log_text
    }).execute()


# ============================================================================
# CODE-GENERIERUNG
# ============================================================================

def generiere_python_code(supabase: Client):
    """Generiert Python-Code mit aktuellen Regeln"""
    
    # Hole alle aktiven Regeln
    response = supabase.table('lern_regeln')\
        .select('*')\
        .eq('aktiv', True)\
        .order('score_modifier', desc=True)\
        .execute()
    
    regeln = response.data
    
    if not regeln:
        print("\n⚠️  Keine aktiven Regeln vorhanden")
        return None
    
    print(f"\n📝 GENERIERE PYTHON-CODE MIT {len(regeln)} REGELN")
    print("="*70 + "\n")
    
    # Gruppiere Regeln
    quellen_plus = [r for r in regeln if r['regel_typ'] == 'quelle' and r['score_modifier'] > 0]
    quellen_minus = [r for r in regeln if r['regel_typ'] == 'quelle' and r['score_modifier'] < 0]
    keywords_plus = [r for r in regeln if r['regel_typ'] == 'keyword' and r['score_modifier'] > 0]
    keywords_minus = [r for r in regeln if r['regel_typ'] == 'keyword' and r['score_modifier'] < 0]
    
    code = """
# ============================================================================
# AUTOMATISCH GENERIERTE LERN-REGELN
# Letzte Aktualisierung: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """
# ============================================================================

def apply_learning_rules(titel, quelle, base_score):
    \"\"\"Wendet gelernte Regeln auf den Score an\"\"\"
    score = base_score
    titel_lower = titel.lower()
    
"""
    
    # Quellen-Regeln (positiv)
    if quellen_plus:
        code += "    # Quellen mit hoher Relevanz\n"
        for regel in quellen_plus:
            code += f"    if quelle == '{regel['bedingung']}':\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        code += "\n"
    
    # Quellen-Regeln (negativ)
    if quellen_minus:
        code += "    # Quellen mit niedriger Relevanz\n"
        for regel in quellen_minus:
            code += f"    if quelle == '{regel['bedingung']}':\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        code += "\n"
    
    # Keyword-Regeln (positiv)
    if keywords_plus:
        code += "    # Keywords mit hoher Relevanz\n"
        for regel in keywords_plus:
            code += f"    if '{regel['bedingung']}' in titel_lower:\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        code += "\n"
    
    # Keyword-Regeln (negativ)
    if keywords_minus:
        code += "    # Keywords mit niedriger Relevanz\n"
        for regel in keywords_minus:
            code += f"    if '{regel['bedingung']}' in titel_lower:\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        code += "\n"
    
    code += """    # Begrenze Score auf 1-10
    return max(1, min(10, score))
"""
    
    return code


# ============================================================================
# HAUPTPROGRAMM
# ============================================================================

def main():
    """Hauptfunktion"""
    
    print("\n" + "="*70)
    print("🤖 ZOO NEWSLETTER - WÖCHENTLICHE LERN-ANALYSE")
    print("="*70)
    
    # Initialisiere Supabase
    supabase = get_supabase_client()
    
    # Analysiere letzte 7 Tage
    analyse_daten = analysiere_zeitraum(supabase, tage=7)
    
    if not analyse_daten:
        print("\n⚠️  Keine Daten zum Analysieren vorhanden")
        sys.exit(0)
    
    # Generiere Regeln
    neue_regeln, aktualisierte_regeln = generiere_regeln(analyse_daten, supabase)
    
    # Speichere Log
    speichere_analyse_log(supabase, analyse_daten, neue_regeln, aktualisierte_regeln)
    
    # Generiere Python-Code
    python_code = generiere_python_code(supabase)
    
    if python_code:
        # Speichere in Datei
        with open('learning_rules.py', 'w', encoding='utf-8') as f:
            f.write(python_code)
        
        print("✅ Python-Code gespeichert in: learning_rules.py")
        print("\n💡 NÄCHSTE SCHRITTE:")
        print("1. Prüfe learning_rules.py")
        print("2. Kopiere den Code in medien_newsletter_web.py")
        print("3. Integriere apply_learning_rules() in bewerte_artikel_mit_claude()")
    
    # Zusammenfassung
    print("\n" + "="*70)
    print("🎉 ANALYSE ABGESCHLOSSEN")
    print("="*70)
    print(f"✅ {analyse_daten['anzahl_bewertungen']} Bewertungen analysiert")
    print(f"✅ {len(neue_regeln)} neue Regeln erstellt")
    print(f"✅ {len(aktualisierte_regeln)} Regeln aktualisiert")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
