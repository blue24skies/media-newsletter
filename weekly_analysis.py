#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Medien Newsletter - Wöchentliche Lern-Analyse
Analysiert Bewertungen und generiert automatisch Lern-Regeln
"""

import os
import sys
from datetime import datetime, timedelta
from supabase import create_client, Client

# ============================================================================
# KONFIGURATION
# ============================================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# Schwellenwerte für Regel-Generierung
MIN_BEWERTUNGEN = 5  # Minimum Bewertungen für eine Regel
RELEVANT_SCHWELLE = 0.70  # 70% = als relevant markieren
IRRELEVANT_SCHWELLE = 0.30  # 30% = als irrelevant markieren

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


def analysiere_nach_quelle(bewertungen):
    """Analysiert Bewertungen nach Quelle"""
    quellen_stats = {}
    
    for bew in bewertungen:
        quelle = bew['artikel_quelle']
        if quelle not in quellen_stats:
            quellen_stats[quelle] = {'relevant': 0, 'nicht_relevant': 0, 'total': 0}
        
        quellen_stats[quelle]['total'] += 1
        if bew['bewertung'] == 'relevant':
            quellen_stats[quelle]['relevant'] += 1
        else:
            quellen_stats[quelle]['nicht_relevant'] += 1
    
    # Prozente berechnen
    for quelle, stats in quellen_stats.items():
        stats['relevant_prozent'] = stats['relevant'] / stats['total'] if stats['total'] > 0 else 0
    
    return quellen_stats


def analysiere_nach_keywords(bewertungen):
    """Analysiert Bewertungen nach häufigen Keywords im Titel"""
    # Häufige Stop-Wörter
    stopwords = {'der', 'die', 'das', 'und', 'oder', 'ein', 'eine', 'mit', 'von', 
                 'in', 'für', 'auf', 'ist', 'im', 'the', 'a', 'an', 'and', 'or', 
                 'of', 'to', 'in', 'for', 'on', 'at', 'by'}
    
    keyword_stats = {}
    
    for bew in bewertungen:
        titel = bew['artikel_titel'].lower()
        # Extrahiere Wörter (min 4 Zeichen)
        words = [w.strip('.,!?:;') for w in titel.split() 
                if len(w) > 3 and w.lower() not in stopwords]
        
        for word in words:
            if word not in keyword_stats:
                keyword_stats[word] = {'relevant': 0, 'nicht_relevant': 0, 'total': 0}
            
            keyword_stats[word]['total'] += 1
            if bew['bewertung'] == 'relevant':
                keyword_stats[word]['relevant'] += 1
            else:
                keyword_stats[word]['nicht_relevant'] += 1
    
    # Prozente berechnen
    for keyword, stats in keyword_stats.items():
        stats['relevant_prozent'] = stats['relevant'] / stats['total'] if stats['total'] > 0 else 0
    
    # Nur Keywords mit genug Bewertungen
    keyword_stats = {k: v for k, v in keyword_stats.items() if v['total'] >= MIN_BEWERTUNGEN}
    
    return keyword_stats


def generiere_regeln(quellen_stats, keyword_stats):
    """Generiert Lern-Regeln basierend auf Statistiken"""
    regeln = []
    
    # Regeln für Quellen
    for quelle, stats in quellen_stats.items():
        if stats['total'] < MIN_BEWERTUNGEN:
            continue
        
        prozent = stats['relevant_prozent']
        
        if prozent >= RELEVANT_SCHWELLE:
            # Quelle ist oft relevant → Score erhöhen
            modifier = +2 if prozent >= 0.85 else +1
            regeln.append({
                'regel_typ': 'quelle',
                'bedingung': quelle,
                'score_modifier': modifier,
                'begründung': f"{int(prozent*100)}% der {quelle}-Artikel wurden als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2)
            })
        
        elif prozent <= IRRELEVANT_SCHWELLE:
            # Quelle ist oft irrelevant → Score senken
            modifier = -2 if prozent <= 0.15 else -1
            regeln.append({
                'regel_typ': 'quelle',
                'bedingung': quelle,
                'score_modifier': modifier,
                'begründung': f"Nur {int(prozent*100)}% der {quelle}-Artikel wurden als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2)
            })
    
    # Regeln für Keywords
    for keyword, stats in keyword_stats.items():
        if stats['total'] < MIN_BEWERTUNGEN:
            continue
        
        prozent = stats['relevant_prozent']
        
        if prozent >= RELEVANT_SCHWELLE:
            modifier = +2 if prozent >= 0.85 else +1
            regeln.append({
                'regel_typ': 'keyword',
                'bedingung': keyword,
                'score_modifier': modifier,
                'begründung': f"Artikel mit '{keyword}' wurden zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2)
            })
        
        elif prozent <= IRRELEVANT_SCHWELLE:
            modifier = -2 if prozent <= 0.15 else -1
            regeln.append({
                'regel_typ': 'keyword',
                'bedingung': keyword,
                'score_modifier': modifier,
                'begründung': f"Artikel mit '{keyword}' wurden nur zu {int(prozent*100)}% als relevant bewertet",
                'anzahl_bewertungen': stats['total'],
                'relevant_prozent': round(prozent * 100, 2)
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
            
            if existing.data:
                # Update
                supabase.table('lern_regeln') \
                    .update(regel) \
                    .eq('regel_typ', regel['regel_typ']) \
                    .eq('bedingung', regel['bedingung']) \
                    .execute()
                aktualisierte_regeln += 1
            else:
                # Insert
                supabase.table('lern_regeln').insert(regel).execute()
                neue_regeln += 1
        
        except Exception as e:
            print(f"⚠️ Fehler beim Speichern der Regel {regel['bedingung']}: {e}")
    
    return neue_regeln, aktualisierte_regeln


def generiere_python_code(supabase: Client):
    """Generiert learning_rules.py aus Datenbank-Regeln"""
    try:
        response = supabase.table('lern_regeln') \
            .select('*') \
            .eq('aktiv', True) \
            .execute()
        
        regeln = response.data
        
        if not regeln:
            print("ℹ️ Keine aktiven Regeln gefunden - learning_rules.py wird nicht erstellt")
            return
        
        # Python Code generieren
        code = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatisch generierte Lern-Regeln für Zoo Medien Newsletter
Generiert am: {timestamp}
Anzahl Regeln: {anzahl}
"""

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
    
    # Regeln nach Quelle
'''.format(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            anzahl=len(regeln)
        )
        
        # Quellen-Regeln
        quellen_regeln = [r for r in regeln if r['regel_typ'] == 'quelle']
        for regel in quellen_regeln:
            code += f"    if quelle == '{regel['bedingung']}':\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        
        code += "\n    # Regeln nach Keywords\n"
        
        # Keyword-Regeln
        keyword_regeln = [r for r in regeln if r['regel_typ'] == 'keyword']
        for regel in keyword_regeln:
            code += f"    if '{regel['bedingung']}' in titel_lower:\n"
            code += f"        score += {regel['score_modifier']}  # {regel['begründung']}\n"
        
        code += '''
    # Score im gültigen Bereich halten (1-10)
    score = max(1, min(10, score))
    
    return score


# Statistik über aktive Regeln
ANZAHL_REGELN = {anzahl}
QUELLEN_REGELN = {quellen}
KEYWORD_REGELN = {keywords}
'''.format(
            anzahl=len(regeln),
            quellen=len(quellen_regeln),
            keywords=len(keyword_regeln)
        )
        
        # Datei schreiben
        with open('learning_rules.py', 'w', encoding='utf-8') as f:
            f.write(code)
        
        print(f"✅ learning_rules.py erstellt ({len(regeln)} Regeln)")
        print(f"   - {len(quellen_regeln)} Quellen-Regeln")
        print(f"   - {len(keyword_regeln)} Keyword-Regeln")
        
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
    print("🤖 ZOO MEDIEN NEWSLETTER - WÖCHENTLICHE ANALYSE")
    print("="*70)
    
    # Supabase Client
    supabase = get_supabase_client()
    
    # Bewertungen abrufen
    bewertungen, start, ende = hole_bewertungen_letzte_woche(supabase)
    
    if len(bewertungen) < MIN_BEWERTUNGEN:
        print(f"\n⚠️ Zu wenig Bewertungen ({len(bewertungen)}) für eine Analyse")
        print(f"   Minimum: {MIN_BEWERTUNGEN} Bewertungen")
        print("   Warte bis nächste Woche!")
        return
    
    # Statistiken erstellen
    print("\n📈 ANALYSE NACH QUELLE")
    print("-"*70)
    quellen_stats = analysiere_nach_quelle(bewertungen)
    for quelle, stats in sorted(quellen_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        prozent = int(stats['relevant_prozent'] * 100)
        print(f"{quelle:30} | {stats['total']:3} Bewertungen | {prozent:3}% relevant")
    
    print("\n📈 ANALYSE NACH KEYWORDS")
    print("-"*70)
    keyword_stats = analysiere_nach_keywords(bewertungen)
    # Top 10 Keywords
    for keyword, stats in sorted(keyword_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:10]:
        prozent = int(stats['relevant_prozent'] * 100)
        print(f"{keyword:30} | {stats['total']:3} Bewertungen | {prozent:3}% relevant")
    
    # Regeln generieren
    print("\n🎯 GENERIERE LERN-REGELN")
    print("-"*70)
    regeln = generiere_regeln(quellen_stats, keyword_stats)
    
    if not regeln:
        print("ℹ️ Keine neuen Regeln generiert (Schwellenwerte nicht erreicht)")
        return
    
    print(f"✅ {len(regeln)} Regeln generiert")
    
    for regel in regeln:
        operator = "+" if regel['score_modifier'] > 0 else ""
        print(f"   [{regel['regel_typ']:8}] {regel['bedingung']:30} → Score {operator}{regel['score_modifier']} ({regel['begründung']})")
    
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
    log_text = f"Analyse abgeschlossen: {len(bewertungen)} Bewertungen, {len(regeln)} Regeln generiert"
    speichere_analyse_log(supabase, start, ende, len(bewertungen), neue_regeln, aktualisierte_regeln, log_text)
    
    # Zusammenfassung
    print("\n" + "="*70)
    print("🎉 ANALYSE ABGESCHLOSSEN")
    print("="*70)
    print(f"✅ {len(bewertungen)} Bewertungen analysiert")
    print(f"✅ {len(regeln)} Regeln generiert")
    print(f"✅ {neue_regeln} neue + {aktualisierte_regeln} aktualisierte Regeln")
    
    if neue_regeln > 0 or aktualisierte_regeln > 0:
        print("\n💡 NÄCHSTE SCHRITTE:")
        print("1. Prüfe learning_rules.py")
        print("2. Kopiere den Code in medien_newsletter.py")
        print("3. Integriere apply_learning_rules() in bewerte_artikel_mit_claude()")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
