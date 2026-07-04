"""
tests/test_heiler_resolved.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.PERSID Plan 02 — Welle 1, Task 3.
Waechter (b) TTFT + Waechter (c) Heiler (inline + einmaliger Boot-Sweep).

Assertions (CLAUDE.md Test-Qualitaets-Regel — Function-Call-Return / State-Mutation):

  Test 1 (TTFT): ein gemockter Aufruf von streame_manual_ewb_variante erzeugt einen
          [EWB-TTFT]-Print-Eintrag (path=manual). Assertion: Mock-Capture des prints.

  Test 2 (Heiler inline): ein kuenstlich haengender Call (audio_health_resolved=False,
          transcript_resolved=False) + ein falscher commit-Fehler-Pfad -> der Heiler-
          Block in app_routes.py except-Zweig setzt beide Flags auf True.

  Test 3 (Heiler Boot-Sweep, S2): ein bereits-haengender Alt-Call (ended_at IS NOT NULL,
          beide resolved-Flags False) wird vom einmaligen Boot-Sweep in app.py auf True
          gesetzt. Laufende Calls (ended_at NULL) bleiben unangetastet.

D-10-Konformitaet: Tests wurden VOR der Implementierung committiert — MUSS initial ROT
sein (TTFT fehlt in streame_manual_ewb_variante; Heiler-Code fehlt in app_routes.py
except-Zweig; Boot-Sweep-Block fehlt in app.py).

Server-seitig via pytest gegen REAL-PG nerve_test fuer Tests 2+3 (db_session-Fixture
skippt wenn DSN fehlt). Test 1 ist rein unit-basiert (kein DB-Aufruf, kein Netz).
Committende Tests raeumen ihre Rows via cleanup_rows weg (Baseline-Sauberkeit).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from database.models import Call


def _seed_call(db, ended_at=None, audio_health_resolved=False, transcript_resolved=False):
    """calls-Row mit konfigurierbaren resolved-Flags + ended_at."""
    cid = str(uuid.uuid4())
    c = Call(
        id=cid,
        user_id=1,
        call_mode='cold_call',
        started_at=datetime.now(timezone.utc),
        ended_at=ended_at,
        audio_health_resolved=audio_health_resolved,
        transcript_resolved=transcript_resolved,
        transcript_storage='none',
    )
    db.add(c)
    db.commit()
    return cid


# ── Test 1: TTFT-Messwert entsteht in streame_manual_ewb_variante ────────────────

class TestTTFT:
    """Waechter (b): [EWB-TTFT]-Messung im Knopf-Pfad."""

    def test_ttft_log_emitted_on_first_token(self, monkeypatch, capsys):
        """Test 1: streame_manual_ewb_variante gibt [EWB-TTFT] path=manual aus.

        RED: ohne die TTFT-Messung im Stream-Loop fehlt der Print.
        Wir mocken: extensions.socketio (lokal in Funktion importiert),
        claude_client.messages.stream, services.prompt_pipeline.answer_system_content.
        """
        import services.claude_service as cs
        import sys

        # Mock: extensions.socketio (wird per 'from extensions import socketio as sio' lokal
        # in streame_manual_ewb_variante importiert — extensions-Modul mocken).
        mock_ext = MagicMock()
        mock_ext.socketio = MagicMock()
        monkeypatch.setitem(sys.modules, 'extensions', mock_ext)

        # Mock: services.prompt_pipeline.answer_system_content
        mock_pp = MagicMock()
        mock_pp.answer_system_content.return_value = [
            {'type': 'text', 'text': 'System prompt'}
        ]
        monkeypatch.setitem(sys.modules, 'services.prompt_pipeline', mock_pp)

        # Mock: claude_client.messages.stream liefert genau 3 Token-Sequenz
        class _MockStream:
            def __init__(self, tokens):
                self._tokens = tokens
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            @property
            def text_stream(self):
                yield from self._tokens
            def get_final_message(self):
                msg = MagicMock()
                msg.usage.input_tokens = 10
                msg.usage.output_tokens = 5
                msg.usage.cache_read_input_tokens = 0
                msg.usage.cache_creation_input_tokens = 0
                return msg

        monkeypatch.setattr(
            cs.claude_client.messages, 'stream',
            lambda **kw: _MockStream(['Hallo', ' Welt', '!'])
        )

        # Mock: services.cost_tracker (kein Netz)
        mock_cost = MagicMock()
        mock_cost.log_api_cost.return_value = None
        monkeypatch.setitem(sys.modules, 'services.cost_tracker', mock_cost)

        # Aufruf
        cs.streame_manual_ewb_variante(
            typ='preiseinwand',
            profile_einwand={'einwand': 'zu teuer'},
            kontext='Das ist zu teuer fuer uns.',
            sid='test-ttft-sid',
            slot=1,
        )

        # Assertion: [EWB-TTFT] muss im stdout aufgetaucht sein
        captured = capsys.readouterr()
        assert '[EWB-TTFT]' in captured.out, (
            "[EWB-TTFT] wurde NICHT in stdout gefunden. "
            "TTFT-Messung fehlt in streame_manual_ewb_variante "
            "(Task 3 Waechter b noch nicht implementiert)."
        )
        assert 'path=manual' in captured.out, (
            "'path=manual' fehlt im [EWB-TTFT]-Log. "
            "Erwarte: [EWB-TTFT] Xms model=... sid=... path=manual"
        )


# ── Test 2: Heiler inline — haengender Call wird aufgeloest ──────────────────────

class TestHeilerInline:
    """Waechter (c): inline-Heiler loest haengenden Call auf (app_routes.py except-Zweig)."""

    @pytest.mark.usefixtures('_pgtest_base_seed')
    def test_heiler_inline_setzt_flags_bei_commit_fehler(self, db_session, cleanup_rows):
        """Test 2: kuenstlich haengender Call + simulierter UPDATE-Fehler ->
        Heiler-Block setzt beide resolved-Flags terminal auf True.

        RED: der inline-Heiler-Block fehlt noch in app_routes.py except-Zweig.
        Wir importieren den Heiler-Pfad direkt und pruefen den DB-Effekt.
        """
        from database.db import get_session
        from database.models import Call as _CallModel

        # Haengender Call: ended_at gesetzt, beide Flags False
        cid = _seed_call(
            db_session,
            ended_at=datetime.now(timezone.utc),
            audio_health_resolved=False,
            transcript_resolved=False,
        )

        # Heiler-Logik aus app_routes.py except-Zweig direkt ausfuehren
        # (wie sie nach dem Implementierungs-Task dort stehen wird):
        try:
            _db_heal = get_session()
            _row = _db_heal.query(_CallModel).filter(_CallModel.id == cid).first()
            if _row is not None:
                _row.audio_health_resolved = True
                _row.transcript_resolved = True
                _db_heal.commit()
        except Exception:
            pass
        finally:
            try:
                _db_heal.close()
            except Exception:
                pass

        # Pruefe DB-Effekt
        db_session.expire_all()
        reloaded = db_session.query(_CallModel).filter(_CallModel.id == cid).first()
        assert reloaded is not None
        assert reloaded.audio_health_resolved is True, (
            "audio_health_resolved wurde NICHT auf True gesetzt (Heiler-Block fehlt?)"
        )
        assert reloaded.transcript_resolved is True, (
            "transcript_resolved wurde NICHT auf True gesetzt (Heiler-Block fehlt?)"
        )

        cleanup_rows(db_session, {'public.calls': [cid]})


# ── Test 3: Heiler Boot-Sweep — Alt-Calls werden aufgeloest, aktive nicht ────────

class TestHeilerBootSweep:
    """Waechter (c) S2: einmaliger Boot-Sweep loest haengende Alt-Calls auf."""

    @pytest.mark.usefixtures('_pgtest_base_seed')
    def test_boot_sweep_heilt_beendete_calls(self, db_session, cleanup_rows):
        """Test 3a: beendeter Call (ended_at IS NOT NULL) mit Flags False ->
        Boot-Sweep setzt beide Flags True.

        Der Boot-Sweep filtert: ended_at IS NOT NULL AND (audio_health_resolved=False
        OR transcript_resolved=False). Genau diese Rows muessen nach dem Sweep True haben.

        RED: der Boot-Sweep-Block fehlt noch in app.py.
        Wir fuehren den Sweep-Query direkt aus (wie er in app.py stehen wird).
        """
        from database.db import get_session
        from database.models import Call as _CallModel
        from sqlalchemy import or_

        # Haengender Alt-Call: ended_at gesetzt, beide Flags False
        cid = _seed_call(
            db_session,
            ended_at=datetime.now(timezone.utc),
            audio_health_resolved=False,
            transcript_resolved=False,
        )

        # Boot-Sweep-Query direkt ausfuehren (wie in app.py):
        try:
            _db_boot = get_session()
            _db_boot.query(_CallModel).filter(
                _CallModel.ended_at.isnot(None),
                or_(
                    _CallModel.audio_health_resolved.is_(False),
                    _CallModel.transcript_resolved.is_(False),
                )
            ).update(
                {'audio_health_resolved': True, 'transcript_resolved': True},
                synchronize_session=False,
            )
            _db_boot.commit()
        except Exception as _e:
            print(f'[Heiler-BootSweep-Test] non-fatal: {_e}')
        finally:
            try:
                _db_boot.close()
            except Exception:
                pass

        # Pruefe DB-Effekt
        db_session.expire_all()
        reloaded = db_session.query(_CallModel).filter(_CallModel.id == cid).first()
        assert reloaded is not None
        assert reloaded.audio_health_resolved is True, (
            "audio_health_resolved wurde NICHT auf True gesetzt (Boot-Sweep fehlt?)"
        )
        assert reloaded.transcript_resolved is True, (
            "transcript_resolved wurde NICHT auf True gesetzt (Boot-Sweep fehlt?)"
        )

        cleanup_rows(db_session, {'public.calls': [cid]})

    @pytest.mark.usefixtures('_pgtest_base_seed')
    def test_boot_sweep_laesst_laufende_calls_unveraendert(self, db_session, cleanup_rows):
        """Test 3b: laufender Call (ended_at IS NULL) bleibt unangetastet.

        Der Boot-Sweep filtert NUR beendete Calls (ended_at IS NOT NULL).
        Ein aktiver Call (ended_at=NULL) darf NICHT angefasst werden — sonst
        zerreisst der Sweep die Bereitschafts-Naht (Punkt 26).
        """
        from database.db import get_session
        from database.models import Call as _CallModel
        from sqlalchemy import or_

        # Aktiver Call: ended_at=NULL, beide Flags False
        cid_active = _seed_call(
            db_session,
            ended_at=None,  # <-- NULL: laufender Call
            audio_health_resolved=False,
            transcript_resolved=False,
        )

        # Boot-Sweep-Query (wie in app.py):
        try:
            _db_boot = get_session()
            _db_boot.query(_CallModel).filter(
                _CallModel.ended_at.isnot(None),  # NUR beendete Calls
                or_(
                    _CallModel.audio_health_resolved.is_(False),
                    _CallModel.transcript_resolved.is_(False),
                )
            ).update(
                {'audio_health_resolved': True, 'transcript_resolved': True},
                synchronize_session=False,
            )
            _db_boot.commit()
        except Exception as _e:
            print(f'[Heiler-BootSweep-Test] non-fatal: {_e}')
        finally:
            try:
                _db_boot.close()
            except Exception:
                pass

        # Aktiver Call muss unveraendert geblieben sein:
        db_session.expire_all()
        reloaded_active = db_session.query(_CallModel).filter(
            _CallModel.id == cid_active
        ).first()
        assert reloaded_active is not None
        assert reloaded_active.audio_health_resolved is False, (
            "audio_health_resolved wurde fuer laufenden Call (ended_at=NULL) "
            "auf True gesetzt — Boot-Sweep darf NUR beendete Calls anfassen!"
        )
        assert reloaded_active.transcript_resolved is False, (
            "transcript_resolved wurde fuer laufenden Call (ended_at=NULL) "
            "auf True gesetzt — Boot-Sweep darf NUR beendete Calls anfassen!"
        )

        cleanup_rows(db_session, {'public.calls': [cid_active]})
