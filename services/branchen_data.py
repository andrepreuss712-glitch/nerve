"""
services/branchen_data.py
────────────────────────────────────────────────────────────────────
Phase 08.20 D-02: Branchen-spezifische PreCall-Hints fuer _generiere_briefing().

Exports:
  - build_branchen_hint(user_branche: str) -> str
      Returns 3-5 vertriebsspezifische Recherche-Bausteine als Text-Block.
      ALWAYS returns non-empty string (Default-Block als Fallback).
      Deterministisch + idempotent (pure function, no I/O).

Architektur-Trennung:
  - 08.20: branchen_data.py — PreCall-Hints fuer _generiere_briefing()
  - 08.21: sales_wisdom_data.py — EWB-Wisdom-Bausteine (separates Modul)
  NICHT zusammenlegen — separate Fachdomaenen, separate Wartungszyklen.

Side-effect-free beim Import: keine I/O, keine DB-Zugriffe, keine Threads.
Token-Budget: max 200-300 Token pro Block (cache-stable, Teil des System-Prompts).
"""
from __future__ import annotations


# ── Branchen-Cluster-Map ──────────────────────────────────────────────────────
# Keys: Normalisierte Branchen-Strings (lowercase) — matchen gegen basis.branche
# aus dem User-Profil (Produkt-/Dienstleistungs-Branche des Beraters, NICHT Lead-Branche).
# 7 Cluster + Default. Kein dynamisches Generieren — statische Bausteine aus
# .planning/research/branchen-precall-spezifika.md (08.18 Research).

_BRANCHEN_HINTS: dict[str, str] = {
    'maschinenbau': (
        "Branchen-Kontext Maschinenbau / Industrietechnik:\n"
        "- Recherchiere: Northdata.de / Bundesanzeiger für Umsatz + Mitarbeiterzahl. "
        "LinkedIn-Mitarbeiter nach Maschinenbediener/Werksleiter durchsuchen (nennen oft Hersteller im Haus).\n"
        "- Investitionssignale: Google News '[Firmenname] Investition / Erweiterung / Neubau'. "
        "Stellenausschreibungen für Produktionspersonal = Kapazitätsausbau-Signal.\n"
        "- Typische Einwände: Langjähriger Lieferant (Wechselkosten hoch), Preis zu hoch / Fernost-Konkurrenz "
        "(TCO-Argument), Investitionsstopp (Leasing/Förderung), Buying Committee 3-5 Personen.\n"
        "- Fachbegriffe: OEE, CAPEX, TCO, Retrofit, SPS, CNC, Kaizen, ISO 9001, CE-Kennzeichnung, "
        "VDMA-Norm, Predictive Maintenance, Industry 4.0, IIoT."
    ),
    'it-saas': (
        "Branchen-Kontext IT / Software / SaaS:\n"
        "- Recherchiere: Crunchbase (Funding-Status), LinkedIn-Stellenausschreibungen "
        "(nennen explizit verwendete Tools), Builtwith.com (Frontend-Tech-Stack), G2/Capterra-Bewertungen.\n"
        "- Pain-Signals: Glassdoor-Kommentare zu internen Prozessen, G2-Reviews auf aktuelle Probleme, "
        "Twitter/LinkedIn des Management-Teams.\n"
        "- Typische Einwände: Selbst bauen (TCO Entwicklung vs. Buy), Bereits mit Wettbewerber zufrieden "
        "(Switching Costs), Budget vergeben (Q4-Planung), DSGVO / EU-Serverstandort.\n"
        "- Fachbegriffe: MRR, ARR, Churn, CAC, LTV, PLG, SLG, API, SSO, SAML, AVV, SLA, POC, ROI, "
        "Seat-Based Pricing, Freemium."
    ),
    'versicherung': (
        "Branchen-Kontext Versicherung / Finanzdienstleistungen:\n"
        "- Recherchiere: Northdata.de / Bundesanzeiger für Risikoprofil-Ersteinschätzung (Umsatz, Mitarbeiterzahl). "
        "LinkedIn-Profil des Risk Managers oder CFO nach aktuellem Anbieter durchsuchen.\n"
        "- Aktuelle Risiko-News: GDV-Website (gdv.de) für Branchen-Schadensquoten, "
        "Asscompact.de für Markt-News, Versicherungsjournal.de.\n"
        "- Typische Einwände: Langjähriger Makler (keine Ablösung, sondern Deckungslücken-Analyse), "
        "Prämie zu hoch (Leistungsvergleich nicht nur Preis), kein Schaden (Statistik-Argumentation).\n"
        "- Fachbegriffe: Police, Prämie, Deckungssumme, Selbstbeteiligung, bAV, bKV, D&O, Cyber-Versicherung, "
        "Makler §84 HGB, Courtage, BaFin, VVG, GDV-Bedingungswerk, Loss Ratio."
    ),
    'finanzdienstleistung': (
        "Branchen-Kontext Versicherung / Finanzdienstleistungen:\n"
        "- Recherchiere: Northdata.de / Bundesanzeiger für Risikoprofil-Ersteinschätzung. "
        "LinkedIn-Profil des CFO oder Risk Managers nach aktuellem Anbieter durchsuchen.\n"
        "- Aktuelle Risiko-News: GDV-Website, Asscompact.de, Cash-Online.de für Finanzvertrieb.\n"
        "- Typische Einwände: Makler-Treue, Prämie/Zins zu hoch, Komplexität (vereinfachen auf 3 Kernpunkte).\n"
        "- Fachbegriffe: Police, Courtage, BaFin, VVG, Kreditversicherung, Factoring, bAV, Loss Ratio."
    ),
    'pharma': (
        "Branchen-Kontext Pharma / Medizintechnik:\n"
        "- Recherchiere: vfa.de (Branchenstatistiken, Zulassungsinfos), BfArM-Zulassungsdatenbank, "
        "kma-online.de (Krankenhaus-Management), SPECTARIS Jahresbericht (Medizintechnik-Marktdaten).\n"
        "- Klinische Entscheidungsstruktur: Arzt / Chefarzt / Einkaufsleitung Krankenhaus / DRG-Verantwortlicher.\n"
        "- Typischer Einwand: Hauslisten-Problematik (Klinik-Formulary) — Listungs-Antrag im Medizinischen "
        "Sachausschuss, Studiendata + Gesundheitsökonomie-Argumente.\n"
        "- Fachbegriffe: MDR, CE-Klasse I/IIa/IIb/III, DRG, G-BA, AMNOG, IQWiG-Nutzenbewertung, PZN, OTC vs. Rx."
    ),
    'medizintechnik': (
        "Branchen-Kontext Pharma / Medizintechnik:\n"
        "- Recherchiere: vfa.de, BfArM-Zulassungsdatenbank, kma-online.de, SPECTARIS Jahresbericht.\n"
        "- Zulassungsstatus des eigenen Produkts (MDR, CE-Klasse) ist Gesprächsvorbereitung-Pflicht.\n"
        "- Typischer Einwand: Hauslisten-Problematik in Kliniken — Listungs-Antrag + Studiendaten.\n"
        "- Fachbegriffe: MDR, CE-Kennzeichnung, DRG, G-BA, AMNOG, IQWiG, PZN, klinische Studien."
    ),
    'telco': (
        "Branchen-Kontext Telekommunikation / Medien:\n"
        "- Recherchiere: Bundesnetzagentur Jahresbericht, VATM Branchenreport, "
        "Glasfaser-Ausbaukarte der Bundesnetzagentur (Verfügbarkeitsprüfung als PreCall-Recherche).\n"
        "- Wichtigstes: Vertragslaufzeit des aktuellen Providers — bestes Zeitfenster 3-6 Monate vor Ablauf.\n"
        "- Typischer Einwand: Vertraglich gebunden (Gesprächspositionierung: jetzt informieren für Wechselzeitpunkt).\n"
        "- Fachbegriffe: SLA, Uptime-Garantie, Failover, FTTH/FTTB, 5G-B2B, MPLS, SD-WAN, "
        "UC, VoIP, Cloud-PBX, QoS, Peering."
    ),
    'unternehmensberatung': (
        "Branchen-Kontext Unternehmensberatung / Professional Services:\n"
        "- Recherchiere: Lünendonk-Liste (Ranking Top-Beratungen), BDU-Jahresbericht, "
        "Bundesanzeiger + LinkedIn für Vorstands-/Geschäftsführerwechsel "
        "(oft Trigger für externe Beratung), M&A-Datenbanken für Merger-Signale.\n"
        "- Projektzyklus und strategische Situation des Zielkunden sind entscheidend "
        "(Wachstum, Krise, Merger, Digitalisierung).\n"
        "- Typischer Einwand: Intern machen / eigene Kapazitäten "
        "(Komplementär-Positionierung: Spezial-Know-how + Zeitdruck + Objektivität).\n"
        "- Fachbegriffe: Tagessatz, Lünendonk-Liste, SOW, Kickoff, PMI, Operating Model, "
        "RFP, MBB, Interim Management, Proof of Value."
    ),
    'automobil': (
        "Branchen-Kontext Automobil / Mobilität / Fahrzeugtechnik:\n"
        "- Recherchiere: KBA (Kraftfahrtbundesamt — Bestandsstatistiken), VDA Marktstatistiken, "
        "Fuhrpark-Magazin (fuhrpark.de), BVNW (Bundesverband Fuhrparkmanagement).\n"
        "- Flottenstruktur und Erneuerungszyklus des Zielkunden — wann werden Firmenfahrzeuge "
        "turnusmäßig erneuert (oft 3-4 Jahre), Elektrifizierungsplanung.\n"
        "- Typischer Einwand: Rahmenvertrag mit OEM/Leasinggesellschaft "
        "(Prüfen ob ergänzbar, Vertragsablauf-Zeitpunkt, Total Fleet Cost-Analyse).\n"
        "- Fachbegriffe: TCO, Leasingrate, Residualwert, Full-Service-Leasing, CO2-Flottengrenzwert, "
        "WLTP, BEV, PHEV, BAFG-Förderung, Rahmenvertrag, Fleet Card."
    ),
    'automotive': (
        "Branchen-Kontext Automobil / Mobilität / Fahrzeugtechnik:\n"
        "- Recherchiere: KBA, VDA Marktstatistiken, Fuhrpark-Magazin, BVNW.\n"
        "- Flottenstruktur + Erneuerungszyklus (3-4 Jahre), Elektrifizierungsplanung.\n"
        "- Typischer Einwand: Rahmenvertrag (Ergänzbarkeit prüfen, Timing, TCO-Analyse).\n"
        "- Fachbegriffe: TCO, Leasingrate, Residualwert, Full-Service-Leasing, BEV, PHEV, Fleet Card."
    ),
}

_DEFAULT_HINT = (
    "Branchen-Kontext (Standard B2B):\n"
    "- Recherchiere: Northdata.de / Bundesanzeiger für Umsatz + Mitarbeiterzahl + "
    "Gesellschafterstruktur. LinkedIn-Unternehmensseite für aktuelle Updates und Wachstumssignale.\n"
    "- Investitionssignale: Google News '[Firmenname] Investition / Erweiterung', "
    "Stellenausschreibungen als Wachstumssignal, LinkedIn-Posts des Management-Teams.\n"
    "- Typische B2B-Einwände: Kein Budget (ROI-Rechnung, Amortisation), Kein Bedarf "
    "(Problem-Bewusstsein wecken), Bestehender Anbieter (Differenzierung + Pilotprojekt), "
    "Entscheidung im Buying Committee (Stakeholder-Mapping).\n"
    "- Ziel des Briefings: Unternehmens-Snapshot + aktueller Handlungsdruck + "
    "wahrscheinliche Einwände antizipieren."
)

# ── Normalisierungs-Map (Alias → Cluster-Key) ─────────────────────────────────
_BRANCHE_ALIASES: dict[str, str] = {
    'saas': 'it-saas',
    'software': 'it-saas',
    'cloud': 'it-saas',
    'it': 'it-saas',
    'informationstechnologie': 'it-saas',
    'versicherungen': 'versicherung',
    'finanz': 'finanzdienstleistung',
    'bank': 'finanzdienstleistung',
    'banking': 'finanzdienstleistung',
    'industrie': 'maschinenbau',
    'fertigungstechnik': 'maschinenbau',
    'fertigung': 'maschinenbau',
    'manufacturing': 'maschinenbau',
    'auto': 'automobil',
    'kfz': 'automobil',
    'telekommunikation': 'telco',
    'telecom': 'telco',
    'beratung': 'unternehmensberatung',
    'consulting': 'unternehmensberatung',
    'pharmazeutika': 'pharma',
    'medizin': 'medizintechnik',
}


def build_branchen_hint(user_branche: str) -> str:
    """Returns branchen-spezifischen Recherche-Hint-Block fuer PreCall-System-Prompt.

    Args:
        user_branche: basis.branche aus dem User-Profil (was der User verkauft).
                      NICHT die Lead-Firma-Branche.

    Returns:
        Non-empty string — immer. Default-Block wenn keine Cluster-Match.
        Deterministisch: gleicher Input -> gleicher Output (pure function).
    """
    if not user_branche or not isinstance(user_branche, str):
        return _DEFAULT_HINT

    normalized = user_branche.strip().lower()

    # Direct match
    if normalized in _BRANCHEN_HINTS:
        return _BRANCHEN_HINTS[normalized]

    # Alias lookup
    alias_key = _BRANCHE_ALIASES.get(normalized)
    if alias_key and alias_key in _BRANCHEN_HINTS:
        return _BRANCHEN_HINTS[alias_key]

    # Substring match (partial branche string)
    for key in _BRANCHEN_HINTS:
        if key in normalized or normalized in key:
            return _BRANCHEN_HINTS[key]

    return _DEFAULT_HINT
