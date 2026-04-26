import json
import time
import config
from services.claude_service import claude_client


def generate_crm_export(log_entries, painpoints, einwaende,
                         kb_end, profile_name, dsgvo_modus=True, user_id=None):
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

    _t0 = time.time()
    msg = claude_client.messages.create(
        model=config.MODEL_CRM,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}]
    )
    _latency_ms = int((time.time() - _t0) * 1000)
    try:
        from services.cost_tracker import log_api_cost
        _u = getattr(msg, 'usage', None)
        if _u:
            _in = getattr(_u, 'input_tokens', 0) or 0
            _out = getattr(_u, 'output_tokens', 0) or 0
            log_api_cost('anthropic', 'sonnet-4-5', user_id=user_id,
                         units=_in/1000.0, unit_type='per_1k_input_tokens',
                         context_tag='crm', latency_ms=_latency_ms, call_site='crm')
            log_api_cost('anthropic', 'sonnet-4-5', user_id=user_id,
                         units=_out/1000.0, unit_type='per_1k_output_tokens',
                         context_tag='crm', call_site='crm')
    except Exception as _e:
        print(f"[CostHook] crm skipped: {_e}")
    text  = msg.content[0].text.strip()
    start = text.find('{')
    end   = text.rfind('}') + 1
    return json.loads(text[start:end])
