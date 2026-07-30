"""
services/mode_strategy.py
────────────────────────────────────────────────────────────────────
TAXO1-07 (REQ 6): Modus als First-Class-Dimension ueber ein Strategy-Pattern.

ZWECK
  Eine deklarative Registry (MODE_REGISTRY) bildet die Hoerbarkeits-/Routing-
  Achse ab: jeder Modus ist eine ModeStrategy-Klasse. Ein neuer Modus = neue
  Klasse registrieren; der Kern-Code (claude_service / einwand_keyword_matcher /
  deepgram_service) aendert sich NICHT — er liest nur MODE_REGISTRY[mode].

WOHER KOMMT DER MODE-WERT
  Der cold_call/meeting-Modus lebt per-SID in `_session_state[sid]['mode']`
  (live_session.py). Er wird AUSSCHLIESSLICH bei Call-Start gesetzt (kein
  Live-Toggle cold_call<->meeting). Die Aufrufer lesen ihn per-SID und schlagen
  hier nach: `MODE_REGISTRY.get(mode) or MODE_REGISTRY['cold_call']`.

WAS DIESE STRATEGY REGIERT — UND WAS NICHT
  - extract_intent(): liefert speaker_role / speaker_id / inference_basis /
    confidence fuer emit_intent_event (services/intent_event_writer.py).
  - setup_audio_routes(): dokumentierter Audibility-Contract (welche Sprecher
    hoerbar sind). In TAXO1 NUR Vertrag — NICHT verdrahtet.
  - KEINE Klassifikations-Prompt-Methode (Decision 1): Die Klassifikation laeuft
    zentral ueber SYSTEM_PROMPT_BASE (claude_service.py:32, MEDFIX 2026-06-18).
    Ein per-Modus-Prompt wuerde den MEDFIX re-brechen (intent_event wieder leer).
    Die Strategy regiert NUR Sprecher-Zuordnung + Audibility, NICHT den Prompt.

CAVEAT — ZWEI ACHSEN (seit Phase 08.23.2.COUNTERPART wortgetrennt)
  - _session_state[sid]['mode']    (Anruf-Art/Hoerbarkeit: cold_call vs meeting)  <- DIESE Registry
  - state['counterpart']           (Gespraechspartner: gatekeeper vs decision_maker) <- toggle_counterpart
  Die beiden Achsen teilen KEIN Wort mehr. Diese Registry regiert NUR die
  Hoerbarkeits-Achse. NICHT mit der Gespraechspartner-Achse vermischen.

KEIN AIR-GAP-BUS: kein In-Prozess-Nachrichten-Geruest, keine Sim-internen
Namespaces, keine Audio-Routing-Kanaele in TAXO1.
"""

from abc import ABC, abstractmethod

# cold_call ist haerter gecapped als meeting: jede transkribierte Aeusserung im
# cold_call ist der Berater (NERVE hoert nur den Berater) -> die Einwand-Erkennung
# ist eine Berater-PARAPHRASE (Inferenz), keine direkte Kunden-Aussage. Deshalb
# wird die confidence gedeckelt. meeting ist eine direkte Aussage -> kein Cap.
COLD_CALL_CONF_CAP = 0.85


class ModeStrategy(ABC):
    """Audibility-/Sprecher-Contract eines Modus. ZUSTANDSLOS (kein per-Call-State
    auf der Instanz — alles via Argumente; die Instanzen sind prozess-global shared
    und werden parallel aus mehreren Lanes/Threads aufgerufen, T-TAXO1-22)."""

    @abstractmethod
    def setup_audio_routes(self) -> dict:
        """Deklarativer Audibility-Contract: welche Sprecher hoerbar sind.
        In TAXO1 NUR Vertrag (Doku) — NICHT verdrahtet."""
        raise NotImplementedError

    @abstractmethod
    def extract_intent(self, *, speaker=None, ergebnis=None, **ctx) -> dict:
        """Liefert {'speaker_role', 'speaker_id', 'inference_basis', 'confidence'}
        fuer emit_intent_event. ZUSTANDSLOS — alles via Argumente."""
        raise NotImplementedError

    # KEINE Klassifikations-Prompt-Methode (Decision 1): SYSTEM_PROMPT_BASE
    # (claude_service.py:32, MEDFIX 2026-06-18) ist der EINE Klassifikations-Prompt.
    # Eine per-Modus-Prompt-Methode hier wuerde den MEDFIX re-brechen.


MODE_REGISTRY: dict[str, "ModeStrategy"] = {}


def register(mode_key):
    """Decorator: registriert eine Strategy-INSTANZ unter mode_key (Instanz, da
    zustandslos/shared). Neuer Modus = neue Klasse mit @register — der Kern-Code
    bleibt unberuehrt."""
    def deco(cls):
        MODE_REGISTRY[mode_key] = cls()
        return cls
    return deco


@register('cold_call')
class ColdCallStrategy(ModeStrategy):
    """Cold-Call: NERVE hoert NUR den Berater (diarize=False). Jede transkribierte
    Aeusserung ist der Berater -> advisor-abgeleitete Erkennung wird als BERATER
    attribuiert, NIE als Kunde (Decision 2 — Sprecher-Bug-Fix).

    ACHTUNG: 'cold_call' hier = Anruf-Art/Hoerbarkeit (vs meeting). Der
    Gespraechspartner liegt getrennt in state['counterpart'] (gatekeeper vs
    decision_maker, toggle_counterpart). Diese Strategy regiert die
    Hoerbarkeits-Achse."""

    def setup_audio_routes(self) -> dict:
        # NERVE hoert nur den Berater. Vertrag — in TAXO1 nicht verdrahtet.
        return {'diarize': False, 'audible': ['berater']}

    def extract_intent(self, *, speaker=None, ergebnis=None, **ctx) -> dict:
        _inc = ctx.get('confidence')
        try:
            _conf = float(_inc) if _inc is not None else 0.7
        except (TypeError, ValueError):
            _conf = 0.7
        return {
            'speaker_role': 'berater',
            'speaker_id': 'local',
            'inference_basis': 'advisor_paraphrase',
            'confidence': min(_conf, COLD_CALL_CONF_CAP),
        }


@register('meeting')
class MeetingStrategy(ModeStrategy):
    """Meeting (consented): beide Sprecher hoerbar (diarize=True). speaker_role
    folgt der Sprecher-Trennung (Diarization): speaker==0 -> Berater,
    speaker==1 -> Kunde."""

    def setup_audio_routes(self) -> dict:
        return {'diarize': True, 'audible': ['berater', 'kunde']}

    def extract_intent(self, *, speaker=None, ergebnis=None, **ctx) -> dict:
        if speaker == 0:
            _role, _basis = 'berater', 'advisor_paraphrase'
        elif speaker == 1:
            _role, _basis = 'kunde', 'direct_customer_utterance'
        elif speaker is None:
            # Medium-Lane hat keinen pro-Sprecher-Wert -> Default Kunde (wie heute
            # fuer meeting korrekt: der erkannte Einwand ist eine Kunden-Aussage).
            _role, _basis = 'kunde', 'direct_customer_utterance'
        else:
            # unbekannter Sprecher-Index -> system (dokumentiert)
            _role, _basis = 'system', 'direct_customer_utterance'
        _inc = ctx.get('confidence')
        try:
            _conf = float(_inc) if _inc is not None else None
        except (TypeError, ValueError):
            _conf = None
        return {
            'speaker_role': _role,
            'speaker_id': 'local',
            'inference_basis': _basis,
            'confidence': _conf,  # meeting = direkte Aussage -> KEIN Cap
        }


# ── Zukunftssichere Registry-Steckplaetze (Geruest §2) ──────────────────────
# KEIN Training-Air-Gap-Event-Bus (Geruest §6) — nur das Interface ist
# aufnahmefaehig. Beide Methoden werfen NotImplementedError bis zum Ausbau in
# einer spaeteren Phase.

@register('meeting_ext')
class MeetingExtStrategy(ModeStrategy):
    def setup_audio_routes(self) -> dict:
        raise NotImplementedError("Steckplatz: Ausbau spaetere Phase (Geruest §2). KEIN Air-Gap-Bus in TAXO1.")

    def extract_intent(self, *, speaker=None, ergebnis=None, **ctx) -> dict:
        raise NotImplementedError("Steckplatz: Ausbau spaetere Phase (Geruest §2). KEIN Air-Gap-Bus in TAXO1.")


@register('training_cold')
class TrainingColdStrategy(ModeStrategy):
    def setup_audio_routes(self) -> dict:
        raise NotImplementedError("Steckplatz: Ausbau spaetere Phase (Geruest §2). KEIN Air-Gap-Bus in TAXO1.")

    def extract_intent(self, *, speaker=None, ergebnis=None, **ctx) -> dict:
        raise NotImplementedError("Steckplatz: Ausbau spaetere Phase (Geruest §2). KEIN Air-Gap-Bus in TAXO1.")


@register('training_meeting')
class TrainingMeetingStrategy(ModeStrategy):
    def setup_audio_routes(self) -> dict:
        raise NotImplementedError("Steckplatz: Ausbau spaetere Phase (Geruest §2). KEIN Air-Gap-Bus in TAXO1.")

    def extract_intent(self, *, speaker=None, ergebnis=None, **ctx) -> dict:
        raise NotImplementedError("Steckplatz: Ausbau spaetere Phase (Geruest §2). KEIN Air-Gap-Bus in TAXO1.")
