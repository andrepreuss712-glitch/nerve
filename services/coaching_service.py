"""Coach-Modul: Post-Call Analyse (Sonnet) + Lernkarten Helpers."""
import json
from datetime import datetime, timezone
from config import ANTHROPIC_API_KEY
import anthropic

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

POSTCALL_PROMPT = """Du bist ein erfahrener Sales-Coach. Analysiere dieses Verkaufsgespraech und schlage exakt 3 Lernkarten vor.

Gespraechsdaten:
- Einwaende: {einwaende}
- Kaufsignale: {kaufsignale}
- Painpoints: {painpoints}
- Kaufbereitschaft: Start {kb_start}% -> Ende {kb_end}%
- Redeanteil Berater: {redeanteil_berater}% / Kunde: {redeanteil_kunde}%
- Dauer: {dauer_sek} Sekunden
- Skript-Abdeckung: {skript_abdeckung}%
- Gegenargument-Details: {ga_details}

Priorisierung (per D-03):
1. Fehler der den Abschluss direkt verhindert hat
2. Haeufigster Fehler im Call
3. Kleinste Verbesserung mit groesster Wirkung

WICHTIG: Jeder Vorschlag MUSS ein konkreter Satz sein, den der Vertriebler beim naechsten Call woertlich sagen kann. KEINE generischen Tipps wie "Vertiefen Sie Einwaende".

Beispiel guter Vorschlag:
"Wenn der Kunde sagt 'Das ist zu teuer' - antworte mit: 'Im Vergleich wozu meinen Sie das?' und schweig dann."

Antworte als JSON mit exakt diesem Format:
{{
  "vorschlaege": [
    {{
      "category": "einwand_preis",
      "original_suggestion": "Wenn der Kunde sagt...",
      "alternative_1": "Alternative Formulierung 1...",
      "alternative_2": "Alternative Formulierung 2...",
      "lernziel": "Einwaende vertiefen statt direkt kontern"
    }},
    ...
  ]
}}

Genau 3 Vorschlaege. Jeder mit 2 Alternativen (fuer "Neuer Vorschlag" per D-06, pre-generated to avoid extra Sonnet calls). Categories aus: einwand_preis, einwand_zeit, einwand_wettbewerb, einwand_bedarf, einwand_entscheider, zu_frueh_pitch, redeanteil, kaufsignal_verpasst, abschluss_timing, phasen_sprung."""


def generate_postcall_analysis(conv_id, user_id, einwaende, painpoints,
                                kb_start, kb_end, redeanteil_berater,
                                redeanteil_kunde, dauer_sek,
                                skript_abdeckung, ga_details,
                                kaufsignale=None, profile_data=None):
    """Generate max 3 learning card suggestions via Sonnet (D-01, D-02).

    T-04.11-05: Guard against duplicate analysis — check if suggestions
    already exist for this conv_id before calling Sonnet.
    """
    # T-04.11-05: Duplicate guard — one analysis per conversation
    from database.db import get_session
    from database.models import LearningCard
    db_check = get_session()
    try:
        existing = db_check.query(LearningCard).filter_by(call_id=conv_id).count()
        if existing > 0:
            print(f"[Coach] Suggestions already exist for conv_id={conv_id}, skipping Sonnet call")
            return []
    finally:
        db_check.close()

    prompt_text = POSTCALL_PROMPT.format(
        einwaende=json.dumps(einwaende, ensure_ascii=False)[:2000],
        kaufsignale=json.dumps(kaufsignale or [], ensure_ascii=False)[:1000],
        painpoints=json.dumps(painpoints, ensure_ascii=False)[:1000],
        kb_start=kb_start, kb_end=kb_end,
        redeanteil_berater=redeanteil_berater,
        redeanteil_kunde=redeanteil_kunde,
        dauer_sek=dauer_sek,
        skript_abdeckung=skript_abdeckung,
        ga_details=json.dumps(ga_details, ensure_ascii=False)[:2000],
    )
    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt_text}]
        )
        # Cost tracking (D-02: Sonnet)
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(response, 'usage', None)
            if u:
                log_api_cost('anthropic', 'sonnet-4', user_id=user_id,
                             units=(getattr(u, 'input_tokens', 0) or 0)/1000.0,
                             unit_type='per_1k_input_tokens',
                             context_tag='postcall_coach')
                log_api_cost('anthropic', 'sonnet-4', user_id=user_id,
                             units=(getattr(u, 'output_tokens', 0) or 0)/1000.0,
                             unit_type='per_1k_output_tokens',
                             context_tag='postcall_coach')
        except Exception as _ce:
            print(f"[CostHook] postcall_coach skipped: {_ce}")

        text = response.content[0].text.strip()
        start = text.find('{')
        end = text.rfind('}') + 1
        if start < 0 or end <= start:
            print(f"[Coach] No JSON found in Sonnet response")
            return []
        result = json.loads(text[start:end])
        vorschlaege = result.get('vorschlaege', [])[:3]

        # Persist suggestions linked to conv_id
        db = get_session()
        try:
            for v in vorschlaege:
                card = LearningCard(
                    user_id=user_id,
                    call_id=conv_id,
                    category=v.get('category', 'allgemein'),
                    original_suggestion=v.get('original_suggestion', ''),
                    final_text=v.get('original_suggestion', ''),
                    lernziel=v.get('lernziel', ''),
                    source='ki',
                    status='vorschlag',  # not yet 'aktiv' — user must confirm
                )
                db.add(card)
            db.commit()
        except Exception as _de:
            print(f"[Coach] DB persist failed: {_de}")
        finally:
            db.close()

        return vorschlaege
    except Exception as e:
        print(f"[Coach] Sonnet analysis failed: {e}")
        return []


def validate_user_text(user_text, lernziel):
    """D-06: KI prueft ob user-eingegebener Satz das Lernziel abdeckt (Haiku)."""
    try:
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": f"""Lernziel: {lernziel}
User-Satz: {user_text}

Deckt der Satz das Lernziel ab? Antworte als JSON:
{{"covers_goal": true/false, "feedback": "Kurzes Feedback auf Deutsch"}}"""}]
        )
        text = response.content[0].text.strip()
        start = text.find('{'); end = text.rfind('}') + 1
        return json.loads(text[start:end])
    except Exception as e:
        print(f"[Coach] Validation failed: {e}")
        return {"covers_goal": True, "feedback": ""}


def get_active_cards(user_id):
    """Load user's active learning cards."""
    from database.db import get_session
    from database.models import LearningCard
    db = get_session()
    try:
        cards = db.query(LearningCard).filter_by(
            user_id=user_id, status='aktiv'
        ).order_by(LearningCard.created_at.desc()).all()
        return [{'id': c.id, 'category': c.category,
                 'final_text': c.final_text, 'lernziel': c.lernziel,
                 'applied_count': c.applied_count,
                 'created_at': c.created_at.isoformat() if c.created_at else None}
                for c in cards]
    finally:
        db.close()
