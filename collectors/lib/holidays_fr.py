"""
lib/holidays_fr.py

Calendrier des jours fériés français - utilisé par market_reset.py et
market_check.py pour exclure samedi/dimanche/jours fériés du calcul des
variations de cours (décision du 12/08/2026, voir la conversation de
design : simplification assumée - ne correspond pas exactement aux jours
de fermeture des marchés US, mais reste le référentiel le plus simple à
maintenir sans base de données de jours fériés par place boursière).
"""

from datetime import date, timedelta


def _easter_sunday(year: int) -> date:
    """Algorithme de Gauss/Meeus (anonyme gregorien) - standard, sans
    dépendance externe."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def french_holidays(year: int) -> set:
    easter = _easter_sunday(year)
    return {
        date(year, 1, 1),                      # Jour de l'an
        easter + timedelta(days=1),             # Lundi de Pâques
        date(year, 5, 1),                      # Fête du travail
        date(year, 5, 8),                      # Victoire 1945
        easter + timedelta(days=39),            # Ascension
        easter + timedelta(days=50),            # Lundi de Pentecôte
        date(year, 7, 14),                     # Fête nationale
        date(year, 8, 15),                     # Assomption
        date(year, 11, 1),                     # Toussaint
        date(year, 11, 11),                    # Armistice
        date(year, 12, 25),                    # Noël
    }


def is_market_day(d: date) -> bool:
    """False le week-end ou un jour férié français - voir docstring du
    module pour la limite assumée (calendrier FR uniquement)."""
    if d.weekday() >= 5:  # 5=samedi, 6=dimanche
        return False
    return d not in french_holidays(d.year)
