#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Medien Newsletter - VERBESSERTE Wöchentliche Lern-Analyse
Analysiert Bewertungen und generiert intelligente Multi-Faktor-Regeln:
- Einzelne Keywords
- Keyword-Paare (2-Wörter)
- Quellen-Keyword-Kombinationen
- Themen-Kategorien
"""

import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ Supabase nicht installiert - nutze Dummy-Daten für Test")

# ============================================================================
# KONFIGURATION
# ============================================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# Schwellenwerte für Regel-Generierung (OPTIMIERT!)
MIN_BEWERTUNGEN_KEYWORD = 3      # Min. 3 Bewertungen für Keyword-Regeln
MIN_BEWERTUNGEN_QUELLE = 5       # Min. 5 Bewertungen für Quellen-Regeln
MIN_BEWERTUNGEN_COMBO = 3        # Min. 3 für Kombinationen
MIN_BEWERTUNGEN_GESAMT = 20      # Min. 20 Gesamtbewertungen für Analyse

RELEVANT_SCHWELLE = 0.70         # 70% = positiv bewerten
IRRELEVANT_SCHWELLE = 0.30       # 30% = negativ bewerten

# Stoppwörter (werden bei Keyword-Analyse ignoriert)
STOPWORDS = {
    'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'einem',
    'und', 'oder', 'aber', 'auch', 'mit', 'von', 'zu', 'in', 'im', 'am', 'um',
    'auf', 'bei', 'für', 'nach', 'vor', 'über', 'unter', 'aus', 'an', 'als',
    'ist', 'sind', 'war', 'waren', 'wird', 'werden', 'wurde', 'wurden', 'hat',
    'haben', 'hatte', 'hatten', 'sich', 'nicht', 'noch', 'nur', 'so', 'wie',
    'mehr', 'gegen', 'zwischen', 'während', 'bis', 'seit'
}

# Themen-Kategorien
THEMEN_KEYWORDS = {
    'formate': ['format', 'show', 'serie', 'sendung', 'programm', 'quiz', 'game'],
    'streaming': ['netflix', 'amazon', 'disney', 'apple tv', 'paramount', 'max', 'hbo', 'prime'],
    'quoten': ['quote', 'marktanteil', 'zuschauer', 'reichweite', 'rating', 'millionen'],
    'personal': ['chef', 'ceo', 'geschäftsführer', 'leitung', 'wechsel', 'ernennung', 'personalien'],
    'deals': ['übernahme', 'fusion', 'kauf', 'verkauf', 'investment', 'deal', 'beteiligung'],
    'produktion': ['produktion', 'dreh', 'produktionsfirma', 'studio', 'dreht', 'gedreht'],
    'promi': ['promi', 'celebrity', 'star', 'skandal', 'klatsch', 'privatleben']
}

# ============================================================================
# HELPER FUNKTIONEN
# ============================================================================

def extrahiere_keywords(titel):
    """Extrahiert relevante Keywords aus Titel (ohne Stoppwörter)"""
    # Lowercase und Tokenisierung
    titel_lower = titel.lower()
    # Entferne Sonderzeichen, behalte nur Buchstaben, Zahlen, Leerzeichen
    titel_clean = re.sub(r'[^\w\s]', ' ', titel_lower)
    # Split in Wörter
    woerter = titel_clean.split()
    # Filtere Stoppwörter und kurze Wörter
    keywords = [w for w in woerter if w not in STOPWORDS and len(w) > 3]
    return keywords


def finde_keyword_paare(keywords):
    """Findet 2-Wort-Kombinationen"""
    paare = []
    for i in range(len(keywords) - 1):
        paar = f"{keywords[i]} {keywords[i+1]}"
        paare.append(paar)
    return paare


def kategorisiere_thema(titel):
    """Ordnet Artikel einer Themen-Kategorie zu"""
    titel_lower = titel.lower()
    kategorien = []
    
    for kategorie, begriffe in THEMEN_KEYWORDS.items():
        for begriff in begriffe:
            if begriff in titel_lower:
                kategorien.append(kategorie)
                break  # Nur einmal pro Kategorie
    
    return kategorien


# ============================================================================
# DATENBANK / SUPABASE
# ============================================================================

def get_supabase_client() -> Client:
    """Initialisiert Supabase Client"""
    if not SUPABASE_AVAILABLE:
        return None
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ FEHLER: SUPABASE_URL oder SUPABASE_KEY nicht gesetzt!")
        sys.exit(1)
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def hole_bewertungen_letzte_woche(supabase):
    """Holt alle Bewertungen der letzten 7 Tage"""
    heute = datetime.now().date()
    vor_7_tagen = heute - timedelta(days=7)
    
    try:
        response = supabase.table('artikel_bewertungen')\
            .select('*')\
            .gte('newsletter_datum', vor_7_tagen.isoformat())\
            .lte('newsletter_datum', heute.isoformat())\
            .execute()
        
        bewertungen = response.data
        print(f"\n📊 {len(bewertungen)} Bewertungen gefunden ({vor_7_tagen} bis {heute})")
        
        return bewertungen, vor_7_tagen, heute
    
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Bewertungen: {e}")
        return [], vor_7_tagen, heute


# ============================================================================
# ANALYSE-FUNKTIONEN
# ============================================================================

def analysiere_nach_quelle(bewertungen):
    """Analysiert Bewertungen nach Quelle"""
    quellen_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'artikel': []})
    
    for b in bewertungen:
        quelle = b['artikel_quelle']
        bewertung = b['bewertung']
        
        quellen_stats[quelle]['artikel'].append(b['artikel_titel'])
        
        if bewertung == 'relevant':
            quellen_stats[quelle]['relevant'] += 1
        else:
            quellen_stats[quelle]['nicht_relevant'] += 1
    
    return quellen_stats


def analysiere_nach_keywords(bewertungen):
    """Analysiert Bewertungen nach Keywords"""
    keyword_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'artikel': []})
    
    for b in bewertungen:
        titel = b['artikel_titel']
        bewertung = b['bewertung']
        keywords = extrahiere_keywords(titel)
        
        for keyword in keywords:
            keyword_stats[keyword]['artikel'].append(titel)
            
            if bewertung == 'relevant':
                keyword_stats[keyword]['relevant'] += 1
            else:
                keyword_stats[keyword]['nicht_relevant'] += 1
    
    return keyword_stats


def analysiere_keyword_paare(bewertungen):
    """Analysiert 2-Wort-Kombinationen"""
    paar_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'artikel': []})
    
    for b in bewertungen:
        titel = b['artikel_titel']
        bewertung = b['bewertung']
        keywords = extrahiere_keywords(titel)
        paare = finde_keyword_paare(keywords)
        
        for paar in paare:
            paar_stats[paar]['artikel'].append(titel)
            
            if bewertung == 'relevant':
                paar_stats[paar]['relevant'] += 1
            else:
                paar_stats[paar]['nicht_relevant'] += 1
    
    return paar_stats


def analysiere_quelle_keyword_kombis(bewertungen):
    """Analysiert Kombinationen von Quelle + Keyword"""
    kombi_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'artikel': []})
    
    for b in bewertungen:
        titel = b['artikel_titel']
        quelle = b['artikel_quelle']
        bewertung = b['bewertung']
        keywords = extrahiere_keywords(titel)
        
        for keyword in keywords[:3]:  # Nur Top-3 Keywords pro Artikel
            kombi = f"{quelle}+{keyword}"
            kombi_stats[kombi]['artikel'].append(titel)
            
            if bewertung == 'relevant':
                kombi_stats[kombi]['relevant'] += 1
            else:
                kombi_stats[kombi]['nicht_relevant'] += 1
    
    return kombi_stats


def analysiere_themen(bewertungen):
    """Analysiert nach Themen-Kategorien"""
    themen_stats = defaultdict(lambda: {'relevant': 0, 'nicht_relevant': 0, 'artikel': []})
    
    for b in bewertungen:
        titel = b['artikel_titel']
        bewertung = b['bewertung']
        kategorien = kategorisiere_thema(titel)
        
        for kategorie in kategorien:
            themen_stats[kategorie]['artikel'].append(titel)
            
            if bewertung == 'relevant':
                themen_stats[kategorie]['relevant'] += 1
            else:
                themen_stats[kategorie]['nicht_relevant'] += 1
    
    return themen_stats


# ============================================================================
# REGEL-GENERIERUNG
# ============================================================================

def generiere_regeln(quellen_stats, keyword_stats, paar_stats, kombi_stats, themen_stats):
    """
    Generiert Lern-Regeln basierend auf Statistiken
    
    WICHTIG: Bewertet NUR Inhalte (Keywords, Themen), NICHT Quellen!
    Quellen wie DWDL, Kress, etc. sollen NICHT bewertet werden.
    """
    regeln = []
    
    print("\n🎓 GENERIERE LERN-REGELN (CONTENT-BASIERT)")
    print("=" * 70)
    
    # QUELLEN-REGELN SIND DEAKTIVIERT!
    # Wir bewerten Inhalte, nicht Dienstleister
    print("\n1️⃣ QUELLEN-REGELN: DEAKTIVIERT ❌")
    print("   → Quellen werden nicht bewertet, nur Inhalte!")
    
    # 2. KEYWORD-REGELN (Einzelne Themen/Begriffe)
    print("\n2️⃣ KEYWORD-REGELN (Themen-basiert):")
    keyword_items = sorted(keyword_stats.items(), key=lambda x: x[1]['relevant'], reverse=True)
    count = 0
    for keyword, stats in keyword_items:
        if count >= 20:  # Max 20 Keyword-Regeln (erhöht von 15)
            break
        
        gesamt = stats['relevant'] + stats['nicht_relevant']
        
        if gesamt >= MIN_BEWERTUNGEN_KEYWORD:
            prozent_relevant = stats['relevant'] / gesamt
            
            if prozent_relevant >= RELEVANT_SCHWELLE:
                boost = 1 if prozent_relevant < 0.85 else 2
                regeln.append({
                    'typ': 'keyword',
                    'wert': keyword,
                    'aktion': boost,
                    'grund': f"{int(prozent_relevant*100)}% relevant ({stats['relevant']}/{gesamt})"
                })
                print(f"   ✅ '{keyword}': +{boost} ({int(prozent_relevant*100)}%)")
                count += 1
            
            elif prozent_relevant <= IRRELEVANT_SCHWELLE:
                regeln.append({
                    'typ': 'keyword',
                    'wert': keyword,
                    'aktion': -1,
                    'grund': f"nur {int(prozent_relevant*100)}% relevant ({stats['relevant']}/{gesamt})"
                })
                print(f"   ❌ '{keyword}': -1 ({int(prozent_relevant*100)}%)")
                count += 1
    
    # 3. KEYWORD-PAAR-REGELN (Spezifischere Themen)
    print("\n3️⃣ KEYWORD-PAAR-REGELN (Spezifische Themen):")
    paar_items = sorted(paar_stats.items(), key=lambda x: x[1]['relevant'], reverse=True)
    count = 0
    for paar, stats in paar_items:
        if count >= 15:  # Max 15 Paar-Regeln (erhöht von 10)
            break
        
        gesamt = stats['relevant'] + stats['nicht_relevant']
        
        if gesamt >= MIN_BEWERTUNGEN_COMBO:
            prozent_relevant = stats['relevant'] / gesamt
            
            if prozent_relevant >= 0.80:  # Höhere Schwelle für Paare!
                regeln.append({
                    'typ': 'keyword_paar',
                    'wert': paar,
                    'aktion': 2,
                    'grund': f"{int(prozent_relevant*100)}% relevant ({stats['relevant']}/{gesamt})"
                })
                print(f"   ✅ '{paar}': +2 ({int(prozent_relevant*100)}%)")
                count += 1
    
    # 4. QUELLEN-KEYWORD-KOMBINATIONEN → DEAKTIVIERT!
    # Diese waren quellen-abhängig, was wir nicht wollen
    print("\n4️⃣ QUELLEN-KEYWORD-KOMBIS: DEAKTIVIERT ❌")
    print("   → Wurden entfernt da quellen-abhängig")
    
    # 5. THEMEN-REGELN
    print("\n5️⃣ THEMEN-REGELN:")
    for thema, stats in sorted(themen_stats.items()):
        gesamt = stats['relevant'] + stats['nicht_relevant']
        
        if gesamt >= MIN_BEWERTUNGEN_KEYWORD:
            prozent_relevant = stats['relevant'] / gesamt
            
            if prozent_relevant >= RELEVANT_SCHWELLE:
                boost = 1
                regeln.append({
                    'typ': 'thema',
                    'wert': thema,
                    'aktion': boost,
                    'grund': f"{int(prozent_relevant*100)}% relevant ({stats['relevant']}/{gesamt})"
                })
                print(f"   ✅ Thema '{thema}': +{boost} ({int(prozent_relevant*100)}%)")
            
            elif prozent_relevant <= IRRELEVANT_SCHWELLE:
                regeln.append({
                    'typ': 'thema',
                    'wert': thema,
                    'aktion': -1,
                    'grund': f"nur {int(prozent_relevant*100)}% relevant ({stats['relevant']}/{gesamt})"
                })
                print(f"   ❌ Thema '{thema}': -1 ({int(prozent_relevant*100)}%)")
    
    print(f"\n✅ {len(regeln)} Regeln generiert!")
    return regeln


def generiere_learning_rules_py(regeln):
    """
    Generiert learning_rules.py im Dictionary-Format
    Kompatibel mit medien_newsletter_web.py
    
    WICHTIG: Enthält NUR content-basierte Regeln (Keywords, Themen)
    KEINE quellen-basierten Regeln!
    """
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Erstelle nur Keyword-Dictionary (KEINE source_boosts!)
        keyword_boosts = {}
        
        # Keyword-Regeln
        keyword_regeln = [r for r in regeln if r['typ'] == 'keyword']
        for regel in keyword_regeln:
            keyword_boosts[regel['wert']] = regel['aktion']
        
        # Keyword-Paare
        paar_regeln = [r for r in regeln if r['typ'] == 'keyword_paar']
        for regel in paar_regeln:
            keyword_boosts[regel['wert']] = regel['aktion']
        
        # Themen-Regeln: Alle Begriffe der Kategorie hinzufügen
        themen_regeln = [r for r in regeln if r['typ'] == 'thema']
        for regel in themen_regeln:
            if regel['wert'] in THEMEN_KEYWORDS:
                for begriff in THEMEN_KEYWORDS[regel['wert']]:
                    keyword_boosts[begriff] = regel['aktion']
        
        # Code generieren
        keyword_lines = []
        for keyword, boost in keyword_boosts.items():
            keyword_lines.append(f"        '{keyword}': {boost},")
        
        code = f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
AUTOMATISCH GENERIERTE LERN-REGELN (CONTENT-BASIERT)
Erstellt: {timestamp}
Anzahl Regeln: {len(regeln)}

WICHTIG: Nur Inhalte werden bewertet, NICHT Quellen!
Keywords und Themen bekommen Boosts basierend auf Team-Feedback.

Format: Dictionary für medien_newsletter_web.py
\"\"\"

# Learning Rules im Dictionary-Format
LEARNING_RULES = {{
    'source_boosts': {{
        # QUELLEN-BOOSTS SIND DEAKTIVIERT
        # Wir bewerten Inhalte (Keywords/Themen), nicht Dienstleister
    }},
    'keyword_boosts': {{
{chr(10).join(keyword_lines) if keyword_lines else "        # Noch keine Keywords gelernt"}
    }}
}}

# Statistik
ANZAHL_QUELLEN = 0  # Quellen werden nicht mehr bewertet
ANZAHL_KEYWORDS = {len(keyword_boosts)}
ANZAHL_REGELN_GESAMT = {len(regeln)}
"""
        
        # Datei schreiben
        with open('learning_rules.py', 'w', encoding='utf-8') as f:
            f.write(code)
        
        print(f"\n✅ learning_rules.py erfolgreich erstellt!")
        print(f"   Quellen-Boosts: 0 (DEAKTIVIERT)")
        print(f"   Keyword-Boosts: {len(keyword_boosts)}")
        print(f"   Gesamt: {len(keyword_boosts)} anwendbare Regeln (content-basiert)")
        
    except Exception as e:
        print(f"❌ Fehler beim Generieren von learning_rules.py: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Hauptfunktion"""
    print("\n" + "="*70)
    print("🤖 ZOO MEDIEN NEWSLETTER - VERBESSERTE WÖCHENTLICHE ANALYSE")
    print("="*70)
    
    if not SUPABASE_AVAILABLE:
        print("❌ Supabase nicht installiert!")
        return
    
    # Supabase Client
    supabase = get_supabase_client()
    
    # Bewertungen abrufen
    bewertungen, start, ende = hole_bewertungen_letzte_woche(supabase)
    
    if len(bewertungen) < MIN_BEWERTUNGEN_GESAMT:
        print(f"\n⚠️ Zu wenig Bewertungen ({len(bewertungen)}) für eine Analyse")
        print(f"   Minimum: {MIN_BEWERTUNGEN_GESAMT} Bewertungen")
        print("   Warte bis nächste Woche!")
        return
    
    print(f"✅ Genug Daten vorhanden - starte Analyse!")
    
    # Analysen durchführen
    print("\n📊 FÜHRE ANALYSEN DURCH...")
    quellen_stats = analysiere_nach_quelle(bewertungen)
    keyword_stats = analysiere_nach_keywords(bewertungen)
    paar_stats = analysiere_keyword_paare(bewertungen)
    kombi_stats = analysiere_quelle_keyword_kombis(bewertungen)
    themen_stats = analysiere_themen(bewertungen)
    
    # User-spezifische Analyse (informativ, wird nicht für Regeln verwendet)
    user_stats = analysiere_pro_user(bewertungen)
    
    # Regeln generieren (TEAM-weit, nicht user-spezifisch)
    regeln = generiere_regeln(quellen_stats, keyword_stats, paar_stats, kombi_stats, themen_stats)
    
    if not regeln:
        print("\n⚠️ Keine Regeln generiert - Schwellenwerte nicht erreicht")
        return
    
    # learning_rules.py generieren
    generiere_learning_rules_py(regeln)
    
    print("\n" + "="*70)
    print("🎉 ANALYSE ABGESCHLOSSEN!")
    print("="*70)
    print(f"📅 Zeitraum: {start} bis {ende}")
    print(f"📊 Bewertungen: {len(bewertungen)}")
    print(f"🎓 Regeln: {len(regeln)}")
    print("="*70 + "\n")


def analysiere_pro_user(bewertungen):
    """
    Analysiert Bewertungen pro User separat
    Zeigt unterschiedliche Präferenzen der Team-Mitglieder
    """
    user_stats = defaultdict(lambda: {
        'total': 0,
        'relevant': 0,
        'nicht_relevant': 0,
        'top_keywords': defaultdict(int),
        'top_themen': defaultdict(int)
    })
    
    # Sammle Daten pro User
    for b in bewertungen:
        user = b['user_name']
        user_stats[user]['total'] += 1
        
        if b['bewertung'] == 'relevant':
            user_stats[user]['relevant'] += 1
            # Extrahiere Keywords für relevante Artikel
            keywords = extrahiere_keywords(b['artikel_titel'])
            for kw in keywords[:5]:
                user_stats[user]['top_keywords'][kw] += 1
            # Themen
            themen = kategorisiere_thema(b['artikel_titel'])
            for thema in themen:
                user_stats[user]['top_themen'][thema] += 1
        else:
            user_stats[user]['nicht_relevant'] += 1
    
    # Ausgabe
    print("\n👥 USER-SPEZIFISCHE PRÄFERENZEN")
    print("=" * 70)
    
    for user, stats in sorted(user_stats.items()):
        prozent = (stats['relevant'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"\n{user}:")
        print(f"  📊 {stats['relevant']}/{stats['total']} relevant ({prozent:.0f}%)")
        
        # Top Keywords
        if stats['top_keywords']:
            top_kw = sorted(stats['top_keywords'].items(), key=lambda x: x[1], reverse=True)[:5]
            print(f"  🔑 Top Keywords: {', '.join([f'{kw}({cnt})' for kw, cnt in top_kw])}")
        
        # Top Themen
        if stats['top_themen']:
            top_th = sorted(stats['top_themen'].items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"  📂 Top Themen: {', '.join([f'{th}({cnt})' for th, cnt in top_th])}")
    
    print("\n💡 HINWEIS: Aktuelles Learning ist TEAM-weit, nicht user-spezifisch!")
    print("   → Alle Bewertungen aller User werden zusammen analysiert")
    print("   → Future: Per-User Learning für personalisierte Newsletter?")
    
    return user_stats


if __name__ == "__main__":
    main()
