"""
Phase 08.23.2.TEMPO-1 Welle 0: Waechter fuer die Stabilitaet des Antwort-Cache-Prefix.

Der als 'stabil' gecachte Block (build_answer_context, _layer='stable') traegt den
Profil-Stabilteil (Sek. 1-7 inkl. ## FAQ). Drei Bestands-Defekte machten ihn bei Profilen
OHNE Opener instabil: None-Sentinel (DB-Fallback bei JEDEM Call), FAQ-Liste als Referenz
statt Kopie (Prompt-Bloat pro Call), FAQ-Query ohne order_by (stille Reihenfolge-Wechsel).

Warum der Defekt so lange unsichtbar blieb: der Bestands-Test
tests/test_build_answer_context.py:138 baut den Cache seit jeher mit
    'In-Memory statt DB: Cache mit opener_content='' verhindert den DB-Fallback.'
— Produktion schrieb an derselben Stelle aber None. Genau diese Diskrepanz zwischen
Test-Welt und Produktion loest Welle 0 auf.

Alle Tests sind Runtime-Tests (Funktionsaufruf + Assertion auf Rueckgabe/State) — kein
Source-Presence (CLAUDE.md Test-Qualitaets-Regel).

Test-Cleanup (CLAUDE.md Test-Cleanup-Regel / Phase 08.23.2.PGTEST): die beiden real-PG-Tests
machen ausschliesslich db_session.flush() (KEIN eigener commit) -> der function-scoped
db_session-Rollback raeumt die Rows weg -> baseline-sauber, KEIN cleanup_rows noetig.
Der per-SID In-Memory-State wird in finally via pop_session_state entfernt.
"""
from __future__ import annotations

import threading


# ── Gemeinsame Helfer ────────────────────────────────────────────────────────

def _stabil(blocks: list) -> str:
    """Zieht den Stabil-Block ueber den _layer-WERT (nicht ueber den Listen-Index)."""
    for _b in blocks:
        if _b.get('_layer') == 'stable':
            return _b.get('text', '')
    raise AssertionError(
        f"Kein Block mit _layer=='stable' in build_answer_context-Rueckgabe: {blocks!r}")


class _NoCloseProxy:
    """Delegiert an die Fixture-Session, neutralisiert close().

    _load_profile_cache und der DB-Fallback rufen im finally _db.close(). Auf der
    Fixture-Session wuerde das die uncommitteten flush()-Rows verwerfen und den
    Fixture-Teardown stoeren. Das Bestands-Muster (test_per_sid_migration.py:74,
    'lambda: db_session') kommt ohne Proxy durch, weil es nur Schluessel-Existenz
    prueft — die Waechter hier lesen echte Zeilen.
    """

    def __init__(self, s):
        self._s = s

    def query(self, *a, **k):
        return self._s.query(*a, **k)

    def close(self):
        pass          # die Fixture besitzt den Lebenszyklus


def _counting_session_factory(db_session):
    """(factory, opened) — factory zaehlt jede geoeffnete DB-Session in opened['n']."""
    opened = {'n': 0}

    def _factory():
        opened['n'] += 1
        return _NoCloseProxy(db_session)

    return _factory, opened


class _Row:
    """Schlichte Zeile fuer die Fake-DB (id / frage_muster / antwort / inhalt / ...)."""

    def __init__(self, **kw):
        for _k, _v in kw.items():
            setattr(self, _k, _v)


class _FakeQuery:
    """Minimal-Nachbau der genutzten SQLAlchemy-Kette: filter_by/order_by/limit/first/all.

    Modelliert die Postgres-Realitaet: OHNE order_by ist die Reihenfolge nicht garantiert.
    limit() schneidet bewusst VOR einem spaeteren order_by ab — genau deshalb gehoert das
    order_by VOR das limit.
    """

    def __init__(self, rows, recorder, kind):
        self._rows, self._rec, self._kind, self._ordered = list(rows), recorder, kind, False

    def filter_by(self, **kw):
        return self

    def order_by(self, *a):
        self._ordered = True
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        if self._ordered:
            return sorted(self._rows, key=lambda r: r.id)
        self._rec['unordered'] += 1
        # PG darf ohne ORDER BY jede Reihenfolge liefern — hier deterministisch wechselnd.
        return list(reversed(self._rows)) if self._rec['unordered'] % 2 == 0 else list(self._rows)


class _FakeSession:
    """query(model) bildet ueber die Modell-KLASSE auf die passende Zeilenliste ab."""

    def __init__(self, tables, recorder):
        self._tables, self._rec = tables, recorder

    def query(self, model):
        return _FakeQuery(self._tables.get(model, []), self._rec, model)

    def close(self):
        pass


def _fake_tables(faq_rows, opener_rows=()):
    from database.models import User, Profile, ProfileOpener, ProfileFaq
    return {
        User:          [_Row(id=1, active_profile_id=7)],
        Profile:       [_Row(id=7, branche='Software')],
        ProfileOpener: list(opener_rows),
        ProfileFaq:    list(faq_rows),
    }


# ── Test 1 (real-PG): Kern-Waechter — ohne Opener, mit FAQs ──────────────────

def test_ohne_opener_mit_faqs_prefix_byte_gleich_und_kein_db_im_hotpath(db_session, monkeypatch):
    """Welle-0-Kernwaechter. ROT gegen den ungefixten Stand aus DREI Gruenden gleichzeitig:
    opener_content=None -> DB-Fallback bei JEDEM Call (Latenz), _faqs als Referenz -> die
    FAQ-Liste im Session-Cache waechst pro Call (Prefix-Bytes aendern sich), FAQ-Query ohne
    order_by. Genau die Kombination, die beim EA-Launch entsteht: FAQs gepflegt, Opener leer."""
    import database.db as _db_mod
    import services.live_session as ls
    import services.prompt_pipeline as pp
    from database.models import User, Profile, ProfileFaq

    u = User(vorname='W0', nachname='Tester', email='w0-ohne-opener@nerve.de',
             passwort_hash='x', rolle='member', org_id=1)
    db_session.add(u)
    db_session.flush()

    p = Profile(name='W0Profil', org_id=1, daten='{}')
    db_session.add(p)
    db_session.flush()

    u.active_profile_id = p.id          # der Fallback loest ueber active_profile_id auf
    db_session.flush()

    # mode='literal' ist Pflicht: _load_profile_cache filtert darauf (live_session.py:795-797).
    # Mit 'ki_generated' waere die gecachte FAQ-Liste leer und der Test pruefte nichts.
    for _q, _a in (('Was kostet es?',      'Es kostet X.'),
                   ('Wie lange dauert es?', 'Zwei Wochen.'),
                   ('Gibt es Referenzen?',  'Ja, drei.')):
        db_session.add(ProfileFaq(profile_id=p.id, frage_muster=_q, antwort=_a, mode='literal'))
    db_session.flush()
    # KEIN ProfileOpener — das ist der Kern des Falls.

    sid = 'w0-sid-ohne-opener'
    _factory, _opened = _counting_session_factory(db_session)
    try:
        ls.init_session_state(sid, user_id=u.id, org_id=1, profile_id=p.id)
        # Ohne set_profile_for_sid waere pdata leer -> build_profile_context faellt in den
        # pdata-Fallback (:152-175) und oeffnet aus einem UNBETEILIGTEN Grund eine DB-Session.
        ls.set_profile_for_sid(sid, 'W0Profil',
                               {'basis': {'unternehmen': 'ACME'}, 'ki': {'ansprache': 'Sie'}})

        monkeypatch.setattr(_db_mod, 'SessionLocal', _factory)

        ls._load_profile_cache(sid=sid, user_id=u.id, profile_id=p.id)
        with ls._session_state_lock:
            _cache = ls._session_state.get(sid, {}).get('_profile_cache', {})

        assert _cache['opener_content'] == '', (
            "Sentinel-Bruch: _load_profile_cache schreibt bei fehlendem Opener nicht '' sondern "
            f"{_cache['opener_content']!r} -> prompt_pipeline.py:193 kann 'nicht geladen' nicht von "
            "'kein Opener' unterscheiden und faellt bei JEDEM Antwort-Call in den DB-Pfad.")
        assert len(_cache['faqs']) == 3

        _opened['n'] = 0        # ab hier zaehlt ausschliesslich der Hot-Path
        stabil_1 = _stabil(pp.build_answer_context(
            user_id=u.id, sid=sid, primary_intent='preis_einwand'))
        stabil_2 = _stabil(pp.build_answer_context(
            user_id=u.id, sid=sid, primary_intent='preis_einwand'))

        assert stabil_1 == stabil_2, (
            'Stabil-Block NICHT byte-gleich ueber zwei Aufrufe — der Cache-Prefix wackelt, '
            'cache_control (Welle 2) laeuft dann in Cache-WRITES statt Cache-READS.')
        assert _opened['n'] == 0, (
            f'{_opened["n"]} DB-Session(s) im Antwort-Hot-Path — die Zusage in '
            'prompt_pipeline.py:126 ("HOT PATH: 0 DB queries, < 5ms") ist verletzt '
            '(CLAUDE.md Punkt 25).')
        assert len(_cache['faqs']) == 3, (
            'FAQ-Liste im Session-Cache ist gewachsen -> Referenz statt Kopie '
            '(prompt_pipeline.py:186), Prompt-Bloat pro Antwort-Call.')
        assert stabil_1.count('F: Was kostet es?') == 1     # jede FAQ genau EINMAL im Prefix
        assert '## FAQ' in stabil_1                         # kein leerer False-Green
    finally:
        ls.pop_session_state(sid)


# ── Test 2 (real-PG): der NULL-inhalt-Pfad zum None ──────────────────────────

def test_opener_zeile_mit_null_inhalt_liefert_leerstring_sentinel(db_session, monkeypatch):
    """Zweiter Pfad zum None: eine Opener-ZEILE existiert, aber inhalt ist NULL
    (profile_opener.inhalt ist nullable — inspect.sh-Beleg im Plan, Abschnitt 5).
    getattr(_opener, 'inhalt', None) liefert dann None, obwohl _opener wahr ist. Ein Fix,
    der nur den else-Zweig anfasst, laesst genau diesen Fall weiter in den DB-Fallback
    laufen — und ein Waechter, der nur 'gar keine Opener-Zeile' testet, bleibt gruen."""
    import database.db as _db_mod
    import services.live_session as ls
    import services.prompt_pipeline as pp
    from database.models import User, Profile, ProfileOpener

    u = User(vorname='W0', nachname='Nulltester', email='w0-null-inhalt@nerve.de',
             passwort_hash='x', rolle='member', org_id=1)
    db_session.add(u)
    db_session.flush()

    p = Profile(name='W0Profil', org_id=1, daten='{}')
    db_session.add(p)
    db_session.flush()

    u.active_profile_id = p.id
    db_session.flush()

    db_session.add(ProfileOpener(profile_id=p.id, name='Leer-Opener', inhalt=None))
    db_session.flush()

    sid = 'w0-sid-null-inhalt'
    _factory, _opened = _counting_session_factory(db_session)
    try:
        ls.init_session_state(sid, user_id=u.id, org_id=1, profile_id=p.id)
        # identisch zu Test 1: ohne set_profile_for_sid greift der pdata-Fallback und
        # oeffnet aus einem UNBETEILIGTEN Grund eine DB-Session (falsches Rot).
        ls.set_profile_for_sid(sid, 'W0Profil',
                               {'basis': {'unternehmen': 'ACME'}, 'ki': {'ansprache': 'Sie'}})

        monkeypatch.setattr(_db_mod, 'SessionLocal', _factory)

        ls._load_profile_cache(sid=sid, user_id=u.id, profile_id=p.id)
        with ls._session_state_lock:
            _cache = ls._session_state.get(sid, {}).get('_profile_cache', {})

        assert _cache['opener_content'] == '', (
            "NULL-inhalt-Pfad: Opener-Zeile vorhanden, inhalt NULL -> muss '' ergeben (geladen, kein "
            f"nutzbarer Opener), ist aber {_cache['opener_content']!r} -> DB-Fallback bei jedem Call.")
        assert _cache['opener_content'] is not None

        # ZUSATZ (Claudian-Pre-Execute 2026-07-21, Gemini-Befund): der Sentinel-WERT ist ein
        # Umsetzungs-Detail — hier zusaetzlich das ZIEL, 0 DB im Hot-Path (:126-Zusage).
        _opened['n'] = 0                      # ab hier zaehlt ausschliesslich der Hot-Path
        _b1 = pp.build_answer_context(user_id=u.id, sid=sid, primary_intent='preis_einwand')
        _b2 = pp.build_answer_context(user_id=u.id, sid=sid, primary_intent='preis_einwand')
        _st1 = _stabil(_b1)
        _st2 = _stabil(_b2)
        assert _opened['n'] == 0, (
            f"NULL-inhalt-Pfad oeffnet {_opened['n']} DB-Session(s) im Antwort-Hot-Path — der Sentinel "
            "greift fuer diesen zweiten Weg zum None nicht; die 0-DB-Zusage (prompt_pipeline.py:126) "
            'ist verletzt (CLAUDE.md Punkt 25).')
        assert _st1 == _st2, 'Stabil-Block nicht byte-gleich — Cache-Prefix wackelt im NULL-inhalt-Fall.'
    finally:
        ls.pop_session_state(sid)


# ── Test 3 (In-Memory): der Fallback darf den Session-Cache nicht mutieren ───

def test_faq_liste_im_session_cache_waechst_nicht(monkeypatch):
    """Der DB-Fallback laeuft hier LEGITIM: das Cache-Dict hat gar keinen 'opener_content'-
    Schluessel (halb befuellter/aelterer Cache) -> .get() -> None -> Fallback. Auch dann darf
    er die Liste im Session-Cache nicht mutieren. ROT ohne die Kopie in prompt_pipeline.py:186."""
    import database.db as _db_mod
    import services.live_session as ls
    import services.prompt_pipeline as pp

    sid = 'w0-sid-faq-kopie'
    pdata = {'basis': {'unternehmen': 'ACME'}, 'ki': {'ansprache': 'Sie'}}
    _cache_dict = {'faqs': [{'q': 'A', 'a': '1'}]}          # KEIN 'opener_content'-Schluessel
    _state = {sid: {'_profile_cache': _cache_dict}}
    monkeypatch.setattr(ls, '_session_state', _state, raising=False)
    monkeypatch.setattr(ls, '_session_state_lock', threading.Lock(), raising=False)
    monkeypatch.setattr(ls, 'get_profile_for_sid', lambda s: ('W0Profil', pdata), raising=False)
    monkeypatch.setattr(ls, 'get_briefing_for_sid', lambda s: None, raising=False)

    _rec = {'unordered': 0}
    _tables = _fake_tables([_Row(id=1, frage_muster='F1', antwort='A1'),
                            _Row(id=2, frage_muster='F2', antwort='A2')])
    monkeypatch.setattr(_db_mod, 'SessionLocal', lambda: _FakeSession(_tables, _rec))

    stabil_1 = _stabil(pp.build_answer_context(user_id=1, sid=sid, primary_intent='preis_einwand'))
    stabil_2 = _stabil(pp.build_answer_context(user_id=1, sid=sid, primary_intent='preis_einwand'))

    assert len(_cache_dict['faqs']) == 1, (
        f"Session-Cache mutiert: {len(_cache_dict['faqs'])} statt 1 FAQ -> _faqs ist eine Referenz "
        'auf den Cache, der Fallback appendet hinein (prompt_pipeline.py:186/:218).')
    assert stabil_1 == stabil_2


# ── Test 4 (In-Memory): FAQ-Reihenfolge ueber zwei Aufrufe ───────────────────

def test_faq_reihenfolge_ueber_zwei_aufrufe_stabil(monkeypatch):
    """Postgres garantiert OHNE ORDER BY keine Reihenfolge. Die Fake-DB modelliert genau das:
    eine Query ohne .order_by(...) liefert bei jedem zweiten Aufruf die umgekehrte Reihenfolge;
    eine Query MIT .order_by(...) liefert immer nach id sortiert. ROT ohne das order_by in
    prompt_pipeline.py:211-213 — und zwar STILL: kein Fehler, nur ein anderer Prefix."""
    import database.db as _db_mod
    import services.live_session as ls
    import services.prompt_pipeline as pp

    sid = 'w0-sid-faq-reihenfolge'
    pdata = {'basis': {'unternehmen': 'ACME'}, 'ki': {'ansprache': 'Sie'}}
    # Leeres Cache-Dict: _faqs ist dann ohnehin eine frische Liste -> dieser Test isoliert
    # AUSSCHLIESSLICH die Reihenfolge.
    _state = {sid: {'_profile_cache': {}}}
    monkeypatch.setattr(ls, '_session_state', _state, raising=False)
    monkeypatch.setattr(ls, '_session_state_lock', threading.Lock(), raising=False)
    monkeypatch.setattr(ls, 'get_profile_for_sid', lambda s: ('W0Profil', pdata), raising=False)
    monkeypatch.setattr(ls, 'get_briefing_for_sid', lambda s: None, raising=False)

    _rec = {'unordered': 0}
    _tables = _fake_tables([_Row(id=1, frage_muster='F1', antwort='A1'),
                            _Row(id=2, frage_muster='F2', antwort='A2')])
    monkeypatch.setattr(_db_mod, 'SessionLocal', lambda: _FakeSession(_tables, _rec))

    stabil_1 = _stabil(pp.build_answer_context(user_id=1, sid=sid, primary_intent='preis_einwand'))
    stabil_2 = _stabil(pp.build_answer_context(user_id=1, sid=sid, primary_intent='preis_einwand'))

    assert stabil_1 == stabil_2, (
        'FAQ-Reihenfolge wechselt zwischen zwei Aufrufen -> die FAQ-Fallback-Query braucht ein '
        'order_by VOR dem limit (prompt_pipeline.py:211-213); ohne ORDER BY garantiert Postgres '
        'keine Reihenfolge und der Cache-Prefix aendert sich STILL.')
