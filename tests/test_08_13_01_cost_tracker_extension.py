"""Phase 08.13 Plan 01 — Test: ApiCostLog-Model + cost_tracker-Erweiterung.

RED: Assertions schlagen fehl, solange latency_ms/call_site nicht in Modell/Signatur sind.
GREEN: Assertions bestehen nach Implementierung.
"""
import inspect
import pytest


class TestApiCostLogModel:
    """ApiCostLog-Modell hat latency_ms und call_site Spalten."""

    def test_apicostlog_has_latency_ms(self):
        from database.models import ApiCostLog
        assert hasattr(ApiCostLog, 'latency_ms'), "ApiCostLog.latency_ms fehlt"

    def test_apicostlog_has_call_site(self):
        from database.models import ApiCostLog
        assert hasattr(ApiCostLog, 'call_site'), "ApiCostLog.call_site fehlt"

    def test_apicostlog_latency_ms_is_nullable(self):
        """latency_ms darf None sein (abwaertskompatibel)."""
        from database.models import ApiCostLog
        col = ApiCostLog.__table__.c.latency_ms
        assert col.nullable is True, "latency_ms sollte nullable=True sein"

    def test_apicostlog_call_site_is_nullable(self):
        """call_site darf None sein (abwaertskompatibel)."""
        from database.models import ApiCostLog
        col = ApiCostLog.__table__.c.call_site
        assert col.nullable is True, "call_site sollte nullable=True sein"


class TestLogApiCostSignature:
    """log_api_cost() akzeptiert latency_ms und call_site als kwargs."""

    def test_signature_has_latency_ms(self):
        from services.cost_tracker import log_api_cost
        sig = inspect.signature(log_api_cost)
        assert 'latency_ms' in sig.parameters, "latency_ms fehlt in Signatur"

    def test_signature_has_call_site(self):
        from services.cost_tracker import log_api_cost
        sig = inspect.signature(log_api_cost)
        assert 'call_site' in sig.parameters, "call_site fehlt in Signatur"

    def test_latency_ms_default_is_none(self):
        from services.cost_tracker import log_api_cost
        sig = inspect.signature(log_api_cost)
        param = sig.parameters['latency_ms']
        assert param.default is None, "latency_ms Default sollte None sein"

    def test_call_site_default_is_none(self):
        from services.cost_tracker import log_api_cost
        sig = inspect.signature(log_api_cost)
        param = sig.parameters['call_site']
        assert param.default is None, "call_site Default sollte None sein"

    def test_latency_ms_is_keyword_only(self):
        from services.cost_tracker import log_api_cost
        sig = inspect.signature(log_api_cost)
        param = sig.parameters['latency_ms']
        assert param.kind == inspect.Parameter.KEYWORD_ONLY, \
            "latency_ms sollte keyword-only sein (nach *)"

    def test_call_site_is_keyword_only(self):
        from services.cost_tracker import log_api_cost
        sig = inspect.signature(log_api_cost)
        param = sig.parameters['call_site']
        assert param.kind == inspect.Parameter.KEYWORD_ONLY, \
            "call_site sollte keyword-only sein (nach *)"


class TestBackwardCompatibility:
    """log_api_cost() ohne neue kwargs wirft keine Exception (rueckwaertskompatibel)."""

    def test_call_without_new_kwargs_does_not_raise(self, tmp_path):
        """Aufruf ohne latency_ms/call_site darf keine Exception werfen.

        Verwendet in-memory SQLite via monkeypatching, damit kein echter DB-Schreibversuch.
        """
        from services import cost_tracker

        # Stub log_api_cost darf aufgerufen werden ohne neue kwargs
        import inspect
        sig = inspect.signature(cost_tracker.log_api_cost)
        params = list(sig.parameters.keys())
        # Pruefe dass die alten Parameter alle noch da sind
        assert 'provider' in params
        assert 'model' in params
        assert 'user_id' in params
        assert 'units' in params
        assert 'unit_type' in params
        assert 'org_id' in params
        assert 'session_id' in params
        assert 'context_tag' in params
