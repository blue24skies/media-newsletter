#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatisch generierte Lern-Regeln für Zoo Medien Newsletter
Generiert am: 2025-11-14 11:24:02
Anzahl Regeln: 1
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
    if quelle == 'DWDL':
        score += 1  # 81% der DWDL-Artikel wurden als relevant bewertet

    # Regeln nach Keywords

    # Score im gültigen Bereich halten (1-10)
    score = max(1, min(10, score))
    
    return score


# Statistik über aktive Regeln
ANZAHL_REGELN = 1
QUELLEN_REGELN = 1
KEYWORD_REGELN = 0
