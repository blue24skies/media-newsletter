#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Medien Newsletter - Verbesserte Wöchentliche Lern-Analyse
Analysiert Bewertungen und generiert intelligente Lern-Regeln
- Einzelne Keywords
- Keyword-Kombinationen (2-Wörter)
- Quellen-Keyword-Kombinationen
- Themen-Kategorien
"""

import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from supabase import create_client, Client

# ============================================================================
# KONFIGURATION
# ============================================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# Schwellenwerte für Regel-Generierung (GESENKT für mehr Regeln!)
MIN_BEWERTUNGEN_KEYWORD = 3  # Minimum 3 Bewertungen für Keyword-Regeln
MIN_BEWERTUNGEN_QUELLE = 5   # Minimum 5 Bewertungen für Quellen-Regeln
MIN_BEWERTUNGEN_COMBO = 3    # Minimum 3 für Kombinationen

RELEVANT_SCHWELLE = 0.70     # 70% = als relevant markieren
IRRELEVANT_SCHWELLE = 0.30   # 30% = als irrelevant markieren

# Themen-Kategorien (erweitert!)
THEMEN_KEYWORDS = {
    'formate': ['format', 'show', 'serie', 'sendung', 'programm'],
    'streaming': ['netflix', 'amazon', 'disney', 'apple tv', 'paramount', 'max', 'hbo'],
    'quoten': ['quote', 'marktanteil', 'zuschauer', 'reichweite', 'rating'],
    'personal': ['chef', 'ceo', 'geschäftsführer', 'leitung', 'wechsel', 'ernennung'],
    'deals': ['übernahme', 'fusion', 'kauf', 'verkauf', 'investment', 'deal'],
    'produktion': ['produktion', 'dreh', 'produktionsfirma', 'studio'],
    'promi': ['promi', 'celebrity', 'star', 'celebrity', 'skandal', 'klatsch']
}

# ============================================================================
# FUNKTIONEN
# ============================================================================

def get_supabase_client() -> Client:
    """Initialisiert Supabase Client"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ FEHLER: SUPABASE_URL oder SUPABASE_KEY nicht gesetzt!")
        sys.exit(1)
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def hole_bewertungen_letzte_woche(supabase: Client, tage=7):
    """Holt alle Bewertungen der letzten X Tage"""
    ende = datetime.now().date()
    start = ende - timedelta(days=tage)
    
    print(f"\n📊 Analysiere Bewertungen von {start} bis {ende}")
    print("="*70)
    
    try:
        response = supabase.table('artikel_bewertungen') \
            .select('*') \
            .gte('newsletter_datum', start.isoformat()) \
            .lte('newsletter_datum', ende.isoformat()) \
            .execute()
        
        bewertungen = response.data
        print(f"✅ {len(bewertungen)} Bewertungen gefunden")
        return bewertungen, start, ende
        
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Bewertungen: {e}")
        return [], start, ende


def extrahiere_keywords(titel, min_length=4):
    """Extrahiert relevante Keywords aus einem Titel"""
    # Stop-Wörter (erweitert)
    stopwords = {
        'der', 'die', 'das', 'und', 'oder', 'aber', 'doch', 'ein', 'eine', 'einem', 'einen',
        'mit', 'von', 'nach', 'bei', 'für', 'auf', 'aus', 'über', 'unter', 'ist', 'sind',
        'hat', 'haben', 'wird', 'werden', 'wurde', 'wurden', 'sein', 'im', 'am', 'zur', 'zum',
        'the', 'a', 'an', 'and', 'or', 'but', 'of', 'to', 'in', 'for', 'on', 'at', 'by', 'with',
        'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had'
    }
    
    titel_lower = titel.lower()
    
    # Entferne Sonderzeichen, behalte nur Buchstaben und Leerzeichen
    import re
    titel_clean = re.sub(r'[^\w\s]', ' ', titel_lower)
    
    # Extrahiere einzelne Wörter
    words = [w.strip() for w in titel_clean.split() 
            if len(w) >= min_length and w.lower() not in stopwords]
    
    return words


def extrahiere_keyword_paare(titel):
    """Extrahiert 2-Wort-Kombinationen (Bigrams)"""
    words = extrahiere_keywords(titel, min_length=3)
    
    paare = []
    for i in range(len(words) - 1):
        paar = f"{words[i]} {words[i+1]}"
        paare.append(paar)
    
    return paare


def erkenne_thema(titel):
    """Erkennt Themen-Kategorie aus Titel"""
    titel_lower = titel.lower()
    
    erkannte_themen = []
    for thema, keywords in THEMEN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in titel_lower:
                erkannte_themen.append(thema)
                break
    
    return erkannte_themen


def analysiere_nach_quelle(bewertungen):
    """Analysiert Bewertungen nach Quelle"""
    quellen_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'total': 0})
    
    for bew in bewertungen:
        quelle = bew['artikel_quelle']
        quellen_stats[quelle]['total'] += 1
        if bew['bewertung'] == 'relevant':
            quellen_stats[quelle]['relevant'] += 1
        else:
            quellen_stats[quelle]['nicht_relevant'] += 1
    
    # Prozente berechnen
    for quelle, stats in quellen_stats.items():
        stats['relevant_prozent'] = stats['relevant'] / stats['total'] if stats['total'] > 0 else 0
    
    return dict(quellen_stats)


def analysiere_nach_keywords(bewertungen):
    """Analysiert Bewertungen nach einzelnen Keywords"""
    keyword_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'total': 0})
    
    for bew in bewertungen:
        titel = bew['artikel_titel']
        keywords = extrahiere_keywords(titel)
        
        for keyword in keywords:
            keyword_stats[keyword]['total'] += 1
            if bew['bewertung'] == 'relevant':
                keyword_stats[keyword]['relevant'] += 1
            else:
                keyword_stats[keyword]['nicht_relevant'] += 1
    
    # Prozente berechnen & filtern
    result = {}
    for keyword, stats in keyword_stats.items():
        if stats['total'] >= MIN_BEWERTUNGEN_KEYWORD:
            stats['relevant_prozent'] = stats['relevant'] / stats['total']
            result[keyword] = stats
    
    return result


def analysiere_keyword_paare(bewertungen):
    """Analysiert 2-Wort-Kombinationen"""
    paar_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'total': 0})
    
    for bew in bewertungen:
        titel = bew['artikel_titel']
        paare = extrahiere_keyword_paare(titel)
        
        for paar in paare:
            paar_stats[paar]['total'] += 1
            if bew['bewertung'] == 'relevant':
                paar_stats[paar]['relevant'] += 1
            else:
                paar_stats[paar]['nicht_relevant'] += 1
    
    # Prozente berechnen & filtern
    result = {}
    for paar, stats in paar_stats.items():
        if stats['total'] >= MIN_BEWERTUNGEN_COMBO:
            stats['relevant_prozent'] = stats['relevant'] / stats['total']
            result[paar] = stats
    
    return result


def analysiere_quelle_keyword_kombos(bewertungen):
    """Analysiert Quellen + Keyword Kombinationen"""
    combo_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'total': 0})
    
    for bew in bewertungen:
        quelle = bew['artikel_quelle']
        titel = bew['artikel_titel']
        keywords = extrahiere_keywords(titel)
        
        # Nur Top-Keywords kombinieren (häufigste)
        for keyword in keywords[:3]:  # Max 3 Keywords pro Artikel
            combo = f"{quelle}:{keyword}"
            combo_stats[combo]['total'] += 1
            if bew['bewertung'] == 'relevant':
                combo_stats[combo]['relevant'] += 1
            else:
                combo_stats[combo]['nicht_relevant'] += 1
    
    # Prozente berechnen & filtern
    result = {}
    for combo, stats in combo_stats.items():
        if stats['total'] >= MIN_BEWERTUNGEN_COMBO:
            stats['relevant_prozent'] = stats['relevant'] / stats['total']
            result[combo] = stats
    
    return result


def analysiere_themen(bewertungen):
    """Analysiert nach Themen-Kategorien"""
    themen_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'total': 0})
    
    for bew in bewertungen:
        titel = bew['artikel_titel']
        themen = erkenne_thema(titel)
        
        for thema in themen:
            themen_stats[thema]['total'] += 1
            if bew['bewertung'] == 'relevant':
                themen_stats[thema]['relevant'] += 1
            else:
                themen_stats[thema]['nicht_relevant'] += 1
    
    # Prozente berechnen
    result = {}
    for thema, stats in themen_stats.items():
        if stats['total'] >= MIN_BEWERTUNGEN_COMBO:
            stats['relevant_prozent'] = stats['relevant'] / stats['total']
            result[thema] = stats
    
    return result


def generiere_regeln(quellen_stats, keyword_stats, paar_stats, combo_stats, themen_stats):
    """Generiert intelligente Lern-Regeln aus allen Analysen"""
    regeln = []
    
    # 1. QUELLEN-REGELN
    for quelle, stats in quellen_stats.items():
        if stats['total'] < MIN_BEWERTUNGEN_QUELLE:
            continue
        
        prozent = stats['relevant_prozent']
        
        if prozent >= RELEVANT_SCHWELLE:
            modifier = +2 if prozent >= 0.85 else +1
            regeln.append({
                'regel_typ': 'quelle',
                'bedingung': quelle,
                'score_modifier': modifier,
                'begründung': f"{int(prozent*100)}% der {quelle}-Artikel wurden als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 1
            })
        
        elif prozent <= IRRELEVANT_SCHWELLE:
            modifier = -2 if prozent <= 0.15 else -1
            regeln.append({
                'regel_typ': 'quelle',
                'bedingung': quelle,
                'score_modifier': modifier,
                'begründung': f"Nur {int(prozent*100)}% der {quelle}-Artikel wurden als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 1
            })
    
    # 2. KEYWORD-REGELN (Einzelwörter)
    for keyword, stats in keyword_stats.items():
        prozent = stats['relevant_prozent']
        
        if prozent >= RELEVANT_SCHWELLE:
            modifier = +2 if prozent >= 0.85 else +1
            regeln.append({
                'regel_typ': 'keyword',
                'bedingung': keyword,
                'score_modifier': modifier,
                'begründung': f"Artikel mit '{keyword}' wurden zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 2
            })
        
        elif prozent <= IRRELEVANT_SCHWELLE:
            modifier = -2 if prozent <= 0.15 else -1
            regeln.append({
                'regel_typ': 'keyword',
                'bedingung': keyword,
                'score_modifier': modifier,
                'begründung': f"Artikel mit '{keyword}' wurden nur zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 2
            })
    
    # 3. KEYWORD-PAAR-REGELN (2-Wort-Kombinationen)
    for paar, stats in paar_stats.items():
        prozent = stats['relevant_prozent']
        
        if prozent >= RELEVANT_SCHWELLE:
            modifier = +2 if prozent >= 0.85 else +1
            regeln.append({
                'regel_typ': 'keyword_paar',
                'bedingung': paar,
                'score_modifier': modifier,
                'begründung': f"Artikel mit '{paar}' wurden zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 3
            })
        
        elif prozent <= IRRELEVANT_SCHWELLE:
            modifier = -1
            regeln.append({
                'regel_typ': 'keyword_paar',
                'bedingung': paar,
                'score_modifier': modifier,
                'begründung': f"Artikel mit '{paar}' wurden nur zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 3
            })
    
    # 4. QUELLEN-KEYWORD-KOMBINATIONEN (z.B. "DWDL:format" vs "DWDL:promi")
    for combo, stats in combo_stats.items():
        prozent = stats['relevant_prozent']
        
        if prozent >= RELEVANT_SCHWELLE:
            modifier = +2 if prozent >= 0.85 else +1
            quelle, keyword = combo.split(':')
            regeln.append({
                'regel_typ': 'quelle_keyword',
                'bedingung': combo,
                'score_modifier': modifier,
                'begründung': f"{quelle}-Artikel über '{keyword}' wurden zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 4
            })
        
        elif prozent <= IRRELEVANT_SCHWELLE:
            modifier = -2 if prozent <= 0.15 else -1
            quelle, keyword = combo.split(':')
            regeln.append({
                'regel_typ': 'quelle_keyword',
                'bedingung': combo,
                'score_modifier': modifier,
                'begründung': f"{quelle}-Artikel über '{keyword}' wurden nur zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 4
            })
    
    # 5. THEMEN-REGELN
    for thema, stats in themen_stats.items():
        prozent = stats['relevant_prozent']
        
        if prozent >= RELEVANT_SCHWELLE:
            modifier = +2 if prozent >= 0.85 else +1
            regeln.append({
                'regel_typ': 'thema',
                'bedingung': thema,
                'score_modifier': modifier,
                'begründung': f"Artikel zum Thema '{thema}' wurden zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 2
            })
        
        elif prozent <= IRRELEVANT_SCHWELLE:
            modifier = -2 if prozent <= 0.15 else -1
            regeln.append({
                'regel_typ': 'thema',
                'bedingung': thema,
                'score_modifier': modifier,
                'begründung': f"Artikel zum Thema '{thema}' wurden nur zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2),
                'prioritaet': 2
            })
    
    return regeln


def speichere_regeln(supabase: Client, regeln):
    """Speichert oder aktualisiert Regeln in Supabase"""
    neue_regeln = 0
    aktualisierte_regeln = 0
    
    for regel in regeln:
        try:
            # Prüfe ob Regel bereits existiert
            existing = supabase.table('lern_regeln') \
                .select('*') \
                .eq('regel_typ', regel['regel_typ']) \
                .eq('bedingung', regel['bedingung']) \
                .execute()
            
            # Entferne prioritaet vor dem Speichern (nur für Sortierung)
            regel_to_save = {k: v for k, v in regel.items() if k != 'prioritaet'}
            
            if existing.data:
                # Update
                supabase.table('lern_regeln') \
                    .update(regel_to_save) \
                    .eq('regel_typ', regel['regel_typ']) \
                    .eq('bedingung', regel['bedingung']) \
                    .execute()
                aktualisierte_regeln += 1
            else:
                # Insert
                supabase.table('lern_regeln').insert(regel_to_save).execute()
                neue_regeln += 1
        
        except Exception as e:
            print(f"⚠️ Fehler beim Speichern der Regel {regel['bedingung']}: {e}")
    
    return neue_regeln, aktualisierte_regeln


def generiere_python_code(supabase: Client):
    """Generiert intelligente learning_rules.py aus Datenbank-Regeln"""
    try:
        response = supabase.table('lern_regeln') \
            .select('*') \
            .eq('aktiv', True) \
            .execute()
        
        regeln = response.data
        
        if not regeln:
            print("ℹ️ Keine aktiven Regeln gefunden - learning_rules.py wird nicht erstellt")
            return
        
        # Nach Typ gruppieren
        quellen_regeln = [r for r in regeln if r['regel_typ'] == 'quelle']
        keyword_regeln = [r for r in regeln if r['regel_typ'] == 'keyword']
        paar_regeln = [r for r in regeln if r['regel_typ'] == 'keyword_paar']
        combo_regeln = [r for r in regeln if r['regel_typ'] == 'quelle_keyword']
        themen_regeln = [r for r in regeln if r['regel_typ'] == 'thema']
        
        # Python Code generieren
        code = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatisch generierte Lern-Regeln für Zoo Medien Newsletter
Generiert am: {timestamp}
Anzahl Regeln: {anzahl}
- Quellen-Regeln: {quellen}
- Keyword-Regeln: {keywords}
- Keyword-Paar-Regeln: {paare}
- Quellen-Keyword-Kombos: {kombos}
- Themen-Regeln: {themen}
"""

import re

# Themen-Keywords für Erkennung
THEMEN_KEYWORDS = {themen_dict}

def erkenne_thema(titel):
    """Erkennt Themen-Kategorie aus Titel"""
    titel_lower = titel.lower()
    erkannte_themen = []
    
    for thema, keywords in THEMEN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in titel_lower:
                erkannte_themen.append(thema)
                break
    
    return erkannte_themen

def apply_learning_rules(titel, quelle, base_score):
    """
    Wendet gelernte Regeln auf einen Artikel an
    
    Args:
        titel (str): Artikel-Titel
        quelle (str): Artikel-Quelle
        base_score (int): Basis-Score von Claude (1-10)
    
    Returns:
        int: Angepasster Score (1-10)
    """
    score = base_score
    titel_lower = titel.lower()
    
    # Bereinige Titel für Keyword-Matching
    titel_clean = re.sub(r'[^\\w\\s]', ' ', titel_lower)
    
    # 1. QUELLEN-REGELN (Priorität 1)
'''.format(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            anzahl=len(regeln),
            quellen=len(quellen_regeln),
            keywords=len(keyword_regeln),
            paare=len(paar_regeln),
            kombos=len(combo_regeln),
            themen=len(themen_regeln),
            themen_dict=str(THEMEN_KEYWORDS)
        )
        
        # Quellen-Regeln
        for regel in quellen_regeln:
            code += f"    if quelle == '{regel['bedingung']}':\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        
        code += "\n    # 2. THEMEN-REGELN (Priorität 2)\n"
        code += "    themen = erkenne_thema(titel)\n"
        for regel in themen_regeln:
            code += f"    if '{regel['bedingung']}' in themen:\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        
        code += "\n    # 3. KEYWORD-REGELN (Priorität 3)\n"
        for regel in keyword_regeln:
            code += f"    if '{regel['bedingung']}' in titel_lower:\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        
        code += "\n    # 4. KEYWORD-PAAR-REGELN (Priorität 4)\n"
        for regel in paar_regeln:
            paar = regel['bedingung']
            code += f"    if '{paar}' in titel_lower:\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        
        code += "\n    # 5. QUELLEN-KEYWORD-KOMBINATIONEN (Priorität 5 - Spezifischste)\n"
        for regel in combo_regeln:
            quelle_cond, keyword_cond = regel['bedingung'].split(':')
            code += f"    if quelle == '{quelle_cond}' and '{keyword_cond}' in titel_lower:\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        
        code += '''
    # Score im gültigen Bereich halten (1-10)
    score = max(1, min(10, score))
    
    return score


# Statistik über aktive Regeln
ANZAHL_REGELN = {anzahl}
QUELLEN_REGELN = {quellen}
KEYWORD_REGELN = {keywords}
KEYWORD_PAAR_REGELN = {paare}
QUELLEN_KEYWORD_REGELN = {kombos}
THEMEN_REGELN = {themen}
'''.format(
            anzahl=len(regeln),
            quellen=len(quellen_regeln),
            keywords=len(keyword_regeln),
            paare=len(paar_regeln),
            kombos=len(combo_regeln),
            themen=len(themen_regeln)
        )
        
        # Datei schreiben
        with open('learning_rules.py', 'w', encoding='utf-8') as f:
            f.write(code)
        
        print(f"✅ learning_rules.py erstellt ({len(regeln)} Regeln)")
        print(f"   - {len(quellen_regeln)} Quellen-Regeln")
        print(f"   - {len(themen_regeln)} Themen-Regeln")
        print(f"   - {len(keyword_regeln)} Keyword-Regeln")
        print(f"   - {len(paar_regeln)} Keyword-Paar-Regeln")
        print(f"   - {len(combo_regeln)} Quellen-Keyword-Kombos")
        
    except Exception as e:
        print(f"❌ Fehler beim Generieren von learning_rules.py: {e}")


def speichere_analyse_log(supabase: Client, start, ende, anzahl_bewertungen, 
                          neue_regeln, aktualisierte_regeln, log_text):
    """Speichert Analyse-Log in Datenbank"""
    try:
        log_entry = {
            'analyse_datum': datetime.now().date().isoformat(),
            'zeitraum_von': start.isoformat(),
            'zeitraum_bis': ende.isoformat(),
            'anzahl_bewertungen': anzahl_bewertungen,
            'neue_regeln': neue_regeln,
            'aktualisierte_regeln': aktualisierte_regeln,
            'log_text': log_text
        }
        
        supabase.table('analyse_logs').insert(log_entry).execute()
        print("✅ Analyse-Log gespeichert")
        
    except Exception as e:
        print(f"⚠️ Fehler beim Speichern des Logs: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Hauptfunktion"""
    print("\n" + "="*70)
    print("🤖 ZOO MEDIEN NEWSLETTER - INTELLIGENTE LERN-ANALYSE")
    print("="*70)
    
    # Supabase Client
    supabase = get_supabase_client()
    
    # Bewertungen abrufen
    bewertungen, start, ende = hole_bewertungen_letzte_woche(supabase)
    
    if len(bewertungen) < MIN_BEWERTUNGEN_KEYWORD:
        print(f"\n⚠️ Zu wenig Bewertungen ({len(bewertungen)}) für eine Analyse")
        print(f"   Minimum: {MIN_BEWERTUNGEN_KEYWORD} Bewertungen")
        print("   Warte bis nächste Woche!")
        return
    
    # ALLE Analysen durchführen
    print("\n📈 ANALYSE NACH QUELLE")
    print("-"*70)
    quellen_stats = analysiere_nach_quelle(bewertungen)
    for quelle, stats in sorted(quellen_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        prozent = int(stats['relevant_prozent'] * 100)
        print(f"{quelle:30} | {stats['total']:3} Bewertungen | {prozent:3}% relevant")
    
    print("\n📈 ANALYSE NACH EINZELNEN KEYWORDS")
    print("-"*70)
    keyword_stats = analysiere_nach_keywords(bewertungen)
    for keyword, stats in sorted(keyword_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:15]:
        prozent = int(stats['relevant_prozent'] * 100)
        print(f"{keyword:30} | {stats['total']:3} Bewertungen | {prozent:3}% relevant")
    
    print("\n📈 ANALYSE NACH KEYWORD-PAAREN (2-Wörter)")
    print("-"*70)
    paar_stats = analysiere_keyword_paare(bewertungen)
    for paar, stats in sorted(paar_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:10]:
        prozent = int(stats['relevant_prozent'] * 100)
        print(f"{paar:40} | {stats['total']:3} Bewertungen | {prozent:3}% relevant")
    
    print("\n📈 ANALYSE NACH QUELLEN-KEYWORD-KOMBOS")
    print("-"*70)
    combo_stats = analysiere_quelle_keyword_kombos(bewertungen)
    for combo, stats in sorted(combo_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:10]:
        prozent = int(stats['relevant_prozent'] * 100)
        print(f"{combo:40} | {stats['total']:3} Bewertungen | {prozent:3}% relevant")
    
    print("\n📈 ANALYSE NACH THEMEN")
    print("-"*70)
    themen_stats = analysiere_themen(bewertungen)
    for thema, stats in sorted(themen_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        prozent = int(stats['relevant_prozent'] * 100)
        print(f"{thema:30} | {stats['total']:3} Bewertungen | {prozent:3}% relevant")
    
    # Regeln generieren
    print("\n🎯 GENERIERE INTELLIGENTE LERN-REGELN")
    print("-"*70)
    regeln = generiere_regeln(quellen_stats, keyword_stats, paar_stats, combo_stats, themen_stats)
    
    if not regeln:
        print("ℹ️ Keine neuen Regeln generiert (Schwellenwerte nicht erreicht)")
        return
    
    print(f"✅ {len(regeln)} Regeln generiert")
    
    # Regeln nach Typ gruppiert anzeigen
    for regel_typ in ['quelle', 'thema', 'keyword', 'keyword_paar', 'quelle_keyword']:
        typ_regeln = [r for r in regeln if r['regel_typ'] == regel_typ]
        if typ_regeln:
            print(f"\n   [{regel_typ.upper()}]:")
            for regel in typ_regeln:
                operator = "+" if regel['score_modifier'] > 0 else ""
                print(f"      {regel['bedingung']:40} → Score {operator}{regel['score_modifier']} ({regel['begründung']})")
    
    # Regeln speichern
    print("\n💾 SPEICHERE REGELN")
    print("-"*70)
    neue_regeln, aktualisierte_regeln = speichere_regeln(supabase, regeln)
    print(f"✅ {neue_regeln} neue Regeln erstellt")
    print(f"✅ {aktualisierte_regeln} Regeln aktualisiert")
    
    # Python Code generieren
    print("\n🐍 GENERIERE PYTHON CODE")
    print("-"*70)
    generiere_python_code(supabase)
    
    # Log speichern
    log_text = f"Intelligente Analyse abgeschlossen: {len(bewertungen)} Bewertungen, {len(regeln)} Regeln generiert"
    speichere_analyse_log(supabase, start, ende, len(bewertungen), neue_regeln, aktualisierte_regeln, log_text)
    
    # Zusammenfassung
    print("\n" + "="*70)
    print("🎉 INTELLIGENTE ANALYSE ABGESCHLOSSEN")
    print("="*70)
    print(f"✅ {len(bewertungen)} Bewertungen analysiert")
    print(f"✅ {len(regeln)} Regeln generiert")
    print(f"✅ {neue_regeln} neue + {aktualisierte_regeln} aktualisierte Regeln")
    print("\n💡 DAS SYSTEM LERNT JETZT:")
    print("   - Welche Quellen generell relevant sind")
    print("   - Welche Themen-Kategorien relevant sind")
    print("   - Welche Keywords relevant sind")
    print("   - Welche Keyword-Kombinationen relevant sind")
    print("   - Welche Quellen-Keyword-Kombos relevant sind")
    print("   → JEDER ARTIKEL WIRD INDIVIDUELL BEWERTET!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
