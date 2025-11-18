#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTOMATISCH GENERIERTE LERN-REGELN
Erstellt: 2025-11-18 14:40:05
Anzahl Regeln: 40
"""

import re

# Themen-Keywords für Kategorisierung
THEMEN_KEYWORDS = {'formate': ['format', 'show', 'serie', 'sendung', 'programm', 'quiz', 'game'], 'streaming': ['netflix', 'amazon', 'disney', 'apple tv', 'paramount', 'max', 'hbo', 'prime'], 'quoten': ['quote', 'marktanteil', 'zuschauer', 'reichweite', 'rating', 'millionen'], 'personal': ['chef', 'ceo', 'geschäftsführer', 'leitung', 'wechsel', 'ernennung', 'personalien'], 'deals': ['übernahme', 'fusion', 'kauf', 'verkauf', 'investment', 'deal', 'beteiligung'], 'produktion': ['produktion', 'dreh', 'produktionsfirma', 'studio', 'dreht', 'gedreht'], 'promi': ['promi', 'celebrity', 'star', 'skandal', 'klatsch', 'privatleben']}

def kategorisiere_thema(titel):
    """Ordnet Artikel Themen-Kategorien zu"""
    titel_lower = titel.lower()
    kategorien = []
    
    for kategorie, begriffe in THEMEN_KEYWORDS.items():
        for begriff in begriffe:
            if begriff in titel_lower:
                kategorien.append(kategorie)
                break
    
    return kategorien

def apply_learning_rules(titel, quelle, base_score):
    """Wendet alle Lern-Regeln auf den Score an"""
    score = base_score
    titel_lower = titel.lower()
    
    # Extrahiere Keywords
    titel_clean = re.sub(r'[^\w\s]', ' ', titel_lower)
    woerter = titel_clean.split()
    
    
    
    return min(max(score, 1), 10)  # Score zwischen 1-10 halten

# Statistik
ANZAHL_REGELN = 40
