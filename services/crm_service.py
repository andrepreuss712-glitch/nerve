import json
import anthropic
from config import ANTHROPIC_API_KEY

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def generate_crm_export(log_entries, painpoints, einwaende,
                         kb_end, profile_name, dsgvo_modus=True):
    """
    Generates a CRM note and follow-up email from conversation data.
    Returns dict with keys: crm_notiz, followup_email, naechste_schritte.
    """
    # Build conversation text (last 30 segments, Berater + Kunde only)
    verlauf = []
    for e in log_entries:
        if e['type'] == 'transcript':
            sp = 'Berater' if e.get('speaker') == 0 else 'Kunde'
            verlauf.append(f"[{sp}] {e.get('text', '')}")
    gespraech_text = "\n".join(verlauf[-30:]) or "(kein Transkript)"

    painpoint_text = ", ".join(p.get('text', '') for p in painpoints) if painpoints else "keine"
    einwand_text   = ", ".join(e.get('typ', '') for e in einwaende) if einwaende else "keine"

    if dsgvo_modus:
        dsgvo_regel = (
            "WICHTIG — DSGVO-MODUS AKTIV:\n"
            "- Verwende KEINE wörtlichen Zitate des Kunden\n"
            "- Keine Namen, Firmennamen oder persönliche Details des Kunden\n"
            "- Schreibe alles als zusammengefasste Vertriebsnotiz\n"
            "- Statt \"Kunde sagte: Dafür haben wir kein Budget\" "
            "schreibe \"Kunde äußerte Budgetbedenken\"\n"
            "- Die Notiz soll so klingen als hätte der Berater sie aus dem Gedächtnis geschrieben"
        )
    else:
        dsgvo_regel = "DSGVO-Modus ist deaktiviert. Wörtliche Zitate sind erlaubt wenn sie relevant sind."

    prompt = f"""Erstelle basierend auf diesem Verkaufsgespräch zwei Dinge:

{dsgvo_regel}

GESPRÄCHSVERLAUF:
{gespraech_text}

ERKANNTE PAINPOINTS: {painpoint_text}
ERKANNTE EINWÄNDE: {einwand_text}
KAUFBEREITSCHAFT AM ENDE: {kb_end}%
PROFIL: {profile_name or 'Unbekannt'}

Erstelle als valides JSON:
{{
  "crm_notiz": "Strukturierte CRM-Notiz mit diesen Abschnitten getrennt durch Leerzeilen:\\nGesprächszusammenfassung: (2-3 Sätze)\\nBesprochene Themen:\\n- Punkt 1\\n- Punkt 2\\nErkannte Bedenken:\\n- Bedenken 1\\nNächste Schritte:\\n- Schritt 1\\nAbschlusswahrscheinlichkeit: (hoch/mittel/gering) — (kurze Begründung)",
  "followup_email": "Professionelle Follow-up Email. Erste Zeile ist der Betreff beginnend mit 'Betreff: '. Dann eine Leerzeile. Dann der Email-Text. Duzen. Maximal 8 Sätze. Kein Kundenname — Platzhalter [Name] verwenden.",
  "naechste_schritte": ["Konkreter Schritt 1", "Konkreter Schritt 2", "Konkreter Schritt 3"]
}}

Nutze Stichpunkte mit "- " Prefix. Antworte NUR mit dem JSON."""

    msg = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}]
    )
    text  = msg.content[0].text.strip()
    start = text.find('{')
    end   = text.rfind('}') + 1
    return json.loads(text[start:end])
