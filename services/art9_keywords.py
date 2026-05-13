"""
Art-9-DSGVO-Keyword-Liste fuer den Anonymisierungs-Filter.
Quelle: DSGVO Art. 9 Abs. 1, BayLDA-Auditierbarkeit.
Letzte Aktualisierung: 2026-05-13
Kategorien: Gesundheit, Religion, Gewerkschaft, Sexuelle_Orientierung,
            Politische_Ueberzeugung, Ethnische_Herkunft
"""
from typing import Dict, List

ART9_KEYWORDS: Dict[str, List[str]] = {
    'Gesundheit': [
        # Diagnosen und Krankheiten (~50 Keywords)
        'krebs', 'tumor', 'diabetes', 'hiv', 'aids', 'depression', 'burnout',
        'angststoerung', 'schizophrenie', 'epilepsie', 'demenz', 'alzheimer',
        'herzinfarkt', 'schlaganfall', 'parkinson', 'multiple sklerose',
        'rheuma', 'arthritis', 'asthma', 'allergie', 'chemo', 'chemotherapie',
        'bestrahlung', 'dialyse', 'transplantation', 'herzschrittmacher',
        # Medizinische Einrichtungen und Behandlung
        'krankenhaus', 'klinik', 'psychiatrie', 'rehabilitation', 'reha',
        'therapie', 'psychotherapie', 'arzt', 'aerztin', 'chirurg', 'onkologe',
        'facharzt', 'hausarzt', 'krankenversicherung', 'pflegestufe', 'pflegegrad',
        # Symptome und Zustaende
        'schwangerschaft', 'fehlgeburt', 'behinderung', 'beeintraechtigung',
        'krankschreibung', 'arbeitsunfaehigkeit', 'sucht', 'abhaengigkeit',
        'medikament', 'tabletten', 'antidepressivum', 'schmerzmittel',
        'insulin', 'blutdruck', 'herzrhythmus', 'blutungen', 'infektion',
        'covid', 'long covid', 'corona', 'impfung', 'impfschaden',
        'psychose', 'manie', 'bipolaar', 'bipolar', 'zwangsstoerung',
    ],
    'Religion': [
        # Konfessionen und Religionen (~30 Keywords)
        'katholisch', 'evangelisch', 'muslimisch', 'islamisch', 'juedisch',
        'buddhistisch', 'hinduistisch', 'konfession', 'taufe', 'kommunion',
        'kirche', 'moschee', 'synagoge', 'tempel', 'gottesdienst',
        'glaube', 'beten', 'gebet', 'bibel', 'koran', 'torah',
        'ramadan', 'fastenzeit', 'freikirche', 'orden',
        'missionierung', 'atheist', 'agnostiker', 'religionsgemeinschaft',
        'kirchenmitglied', 'kirchensteuer',
    ],
    'Gewerkschaft': [
        # Gewerkschaftliche Aktivitaeten (~20 Keywords)
        'gewerkschaft', 'ig metall', 'verdi', 'dgb', 'dbb', 'betriebsrat',
        'streik', 'tarifvertrag', 'tarif', 'lohnverhandlung', 'tarifverhandlung',
        'arbeitsniederlegung', 'solidaritaet', 'betriebsraetswahl',
        'mitbestimmung', 'gesamtbetriebsrat', 'arbeitnehmervertreter',
        'gewerkschaftsmitglied', 'streikposten', 'aussperrung',
    ],
    'Sexuelle_Orientierung': [
        # Sexuelle Orientierung und Identitaet (~15 Keywords)
        'schwul', 'lesbisch', 'homosexuell', 'bisexuell', 'queer', 'lgbtq',
        'transgender', 'transsexuell', 'intersexuell', 'nicht-binaer',
        'gleichgeschlechtlich', 'gleichgeschlechtliche partnerschaft',
        'lebenspartnerschaft', 'pride', 'coming out',
    ],
    'Politische_Ueberzeugung': [
        # Parteien und politische Ueberzeugungen (~30 Keywords)
        'cdu', 'csu', 'spd', 'gruene', 'fdp', 'afd', 'linke', 'bsw',
        'npd', 'rechtsextrem', 'linksextrem', 'konservativ', 'sozialist',
        'kommunist', 'anarchist', 'liberaler', 'neonazi', 'nazi',
        'antifa', 'pegida', 'reichsbuerger', 'querdenker',
        'partei', 'parteimitglied', 'politische gesinnung', 'weltanschauung',
        'politische ueberzeugung', 'wahlverhalten', 'kandidatur',
        'abgeordneter', 'mdb', 'mep', 'verfassungsschutz',
    ],
    'Ethnische_Herkunft': [
        # Ethnische und nationale Herkunft mit Kontext-Markern (~30 Keywords)
        'migrationshintergrund', 'migrant', 'fluechtling', 'asylbewerber',
        'asylsuchender', 'abschiebung', 'aufenthaltstitel', 'visum',
        'herkunftsland', 'ethnie', 'volksgruppe', 'minderheit',
        'sinti', 'roma', 'kurde', 'kurden', 'tuerke', 'tuerken',
        'arabisch', 'afrikanisch', 'rassismus', 'diskriminierung',
        'antisemitismus', 'islamophobie', 'fremdenfeindlichkeit',
        'einbuergerung', 'staatsangehoerig', 'doppelte staatsangehoerig',
        'volkszugehoerigkeit', 'stammeszugehoerigkeit',
    ],
}
