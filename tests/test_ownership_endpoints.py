"""Phase 08.23.2.SOFORT-2 Plan 01 — Verhaltens-Waechter: Konto A gegen Konto B (ERST-ROT).

WOFUER: Der AST-Sweep (tests/test_ownership_state_guard.py) sieht, DASS geprueft wird — nicht,
ob das Ergebnis beachtet wird, und den DB-Fall B-01 sieht er strukturell gar nicht. Dieser Test
ist die TRAGENDE Schicht: er faehrt jeden der ACHT gefundenen Eingaenge mit zwei echten Konten
in ZWEI VERSCHIEDENEN Organisationen an und prueft das VERHALTEN (HTTP-Antwort, DB-Zeile,
Emit-Raum) — nie den Quelltext (CLAUDE.md Test-Qualitaets-Regel).

WARUM ECHTES POSTGRES, KEIN SQLITE-ZWEIG: die crm.*-Faelle (R-7) haengen an
Row-Level-Security, `public.calls` traegt einen UUID-Primaerschluessel und die Zeilen werden
committet. Ein SQLite-Zweig waere ein Source-Presence-FALSE-GREEN. Harness: die `client`- und
`db_from_client`-Fixtures aus tests/conftest.py (SKIP ohne TEST_DATABASE_URL, kein Fallback).

RESTLUECKEN
-----------
1. ABGEDECKT: dass Konto A ueber die ACHT bekannten Eingaenge weder Daten von Konto B liest
   noch dessen Zustand, DB-Zeilen oder Fremdreferenzen veraendert — geprueft am VERHALTEN
   (HTTP-Antwort, DB-Zeile, Emit-Raum), nicht am Quelltext.

2. STRUKTURELL UNSICHTBAR: dieser Test kennt genau die acht Eingaenge, die der Sweep vom
   2026-08-04/05 gefunden hat. Ein NEUNTER Eingang, der spaeter entsteht, taucht hier NIE auf.
   Genau dagegen steht der abgeleitete Sweep tests/test_ownership_state_guard.py — die beiden
   Waechter decken bewusst zwei verschiedene Fehlerarten ab und ersetzen einander NICHT.

3. HEURISTIK, zweischneidig: die Lecks werden ueber MARKIERTE Zeichenketten (GEHEIM-*) gesucht.
   Ein Leck, das die Daten umformt (zusammenfasst, uebersetzt, in einen Vektor kippt), rutscht
   lautlos durch (Durchrutscher). Umgekehrt wuerde ein legitimer Antworttext, der zufaellig
   'GEHEIM-B' enthaelt, faelschlich rot melden (Falschtreffer) — deshalb sind die Marker
   bewusst unnatuerliche Zeichenketten.

4. UNKLAR: ob die Fixture den Live-Zustand strukturgleich nachbaut. Der Aufbau von
   _session_state[sid] ist per grep aus services/live_session.py::init_session_state
   uebernommen; weicht die echte Struktur ab, koennte ein Fall gruen sein, obwohl der Endpunkt
   in Produktion anders laeuft. Dagegen steht die Gegenprobe mit zwei Konten im Browser (D-06).
   EBENFALLS UNKLAR: ob der Test-Login denselben tenant_id-Weg nimmt wie der echte Login. Die
   Fixture setzt tenant_id explizit in die Sitzung; weicht der Produktionsweg ab, prueft der
   R-7-Fall eine andere Konstellation als die Wirklichkeit.

5. GEPRUEFT UND GESCHLOSSEN:
   - Der DB-Fall B-01, den der AST-Sweep strukturell NICHT sehen kann: hier abgedeckt durch
     test_b01_fremder_call_wird_nicht_beendet (Zeile frisch aus der DB nachgelesen).
   - Der R-8-Durchrutscher, den die Server-Identitaets-Regel des AST-Sweeps NICHT sieht: hier
     abgedeckt durch test_r8_fremdes_profil_nicht_uebertragbar.
   - Die Fremdreferenz R-7, die keine fremde ZEILE anfasst und deshalb von RLS nicht gedeckt
     ist: hier abgedeckt durch test_r7_fremde_call_id_wird_nicht_an_termin_gehaengt, samt
     Gegenprobe ohne call_id (sonst waere eine 403 aus fehlendem Mandanten ein Falsch-Beweis).
   - Blindheit der Fixture: geschlossen durch test_fixture_baut_wirklich_eine_fremde_sitzung.
   - Ueberschiessender Fix ("verweigere einfach alles"): geschlossen durch
     test_eigener_zugriff_funktioniert_weiter.

6. ZWEITE SCHICHT DARUNTER: die Gegenprobe mit zwei Konten im Browser (D-06, Plan 04 Task 3).
   ⚠ Eine DRITTE Schicht gibt es NICHT: public.calls hat auf Production KEINE RLS. Fuer crm.*
   gibt es sie (force=true) — sie schuetzt aber die ZEILE, nicht die FREMDREFERENZ darin (R-7).
"""
import logging
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from tests.conftest import cleanup_rows
from database.models import (User, Organisation, Call, ConversationLog,
                             Profile, CoachAssignment)
import services.live_session as ls
import routes.learning as learning_routes


# ── Die vier (+1) Pflicht-Seams ──────────────────────────────────────────────────────────────
# ⚠ Ohne sie loest JEDER Ausrollvorgang echte, bezahlte Modell-Aufrufe aus (deploy.sh faehrt die
# ganze Suite) — und schlimmer: fliegt in einem dieser Pfade eine Ausnahme VOR dem calls-UPDATE,
# findet der UPDATE gar nicht statt und test_b01 waere GRUEN, OHNE den Fix zu pruefen.

class _FakeMessages:
    """Jeder Modell-Aufruf im Test ist ein Fehler, kein Ergebnis — deshalb laut statt still."""

    def create(self, *a, **kw):
        raise RuntimeError('[SEAM] echter Modell-Aufruf im Test unterbunden (messages.create)')

    def stream(self, *a, **kw):
        raise RuntimeError('[SEAM] echter Modell-Aufruf im Test unterbunden (messages.stream)')


class _FakeClaudeClient:
    def __init__(self):
        self.messages = _FakeMessages()

    def with_options(self, *a, **kw):
        return self


class _EmitRecorder:
    """Faengt die SocketIO-Emits von routes/learning.py ab — der Raum ist hier der Beweis."""

    def __init__(self):
        self.emits = []

    def emit(self, event, payload=None, **kw):
        self.emits.append({'event': event, 'payload': payload, 'room': kw.get('room')})

    def raeume(self, event):
        return [e['room'] for e in self.emits if e['event'] == event]


def _fake_generate_crm_export(*a, **kw):
    return {'crm_notiz': '', 'followup_email': '', 'naechste_schritte': []}


def _fake_generate_postcall_analysis(*a, **kw):
    return []


def _fake_classify(conv_data):
    return {'outcome': None, 'confidence': 0.0}


# ── Fixture: zwei Konten in ZWEI Organisationen ─────────────────────────────────────────────

@pytest.fixture
def zwei_konten(client, db_from_client, monkeypatch):
    """Konto A (Coach, mit Mandant) und Konto B (Opfer) in VERSCHIEDENEN Organisationen."""
    db = db_from_client

    org_a = Organisation(name='[SOFORT2] Firma A', plan='starter')
    org_b = Organisation(name='[SOFORT2] Firma B', plan='starter')
    db.add_all([org_a, org_b])
    db.flush()

    user_a = User(email=f'sofort2_a_{uuid.uuid4().hex[:8]}@nerve.local',
                  passwort_hash=generate_password_hash('pw'), rolle='owner',
                  org_id=org_a.id, aktiv=True, is_coach=True, is_test_user=True)
    user_b = User(email=f'sofort2_b_{uuid.uuid4().hex[:8]}@nerve.local',
                  passwort_hash=generate_password_hash('pw'), rolle='owner',
                  org_id=org_b.id, aktiv=True, is_test_user=True)
    db.add_all([user_a, user_b])
    db.flush()

    # Fuer R-8: A ist seiner EIGENEN Org zugewiesen (die ZIEL-Pruefung besteht damit) — nur so
    # testet der Fall wirklich die QUELL-Pruefung und nicht ein 403 aus fehlender Zuweisung.
    zuweisung = CoachAssignment(coach_id=user_a.id, org_id=org_a.id, aktiv=True)
    # Das fremde Profil, das A NICHT kopieren darf.
    profil_von_b = Profile(org_id=org_b.id, name=f'[SOFORT2] Methodik B {uuid.uuid4().hex[:6]}',
                           branche='GEHEIM-B', daten='{"einwaende": ["GEHEIM-EINWAND-B"]}',
                           erstellt_von=user_b.id)
    db.add_all([zuweisung, profil_von_b])

    # Der offene Anruf von B — die DB-Zeile, die A weder beenden noch referenzieren darf.
    call_id_von_B = uuid.uuid4()
    call_von_b = Call(id=call_id_von_B, user_id=user_b.id, call_mode='cold_call',
                      started_at=datetime.now(timezone.utc), ended_at=None)
    db.add(call_von_b)

    # ★ F-B3: Konto A braucht eine EIGENE ConversationLog. routes/learning.py:23-27 / :209-213
    # antworten OHNE eigene conv_id mit 400 bzw. 404 — VOR jedem Emit. Ohne diese Zeile
    # erreichen test_n02/test_n03 den Emit-Block NIE und sind trivial gruen.
    conv_von_a = ConversationLog(user_id=user_a.id, org_id=org_a.id,
                                 started_at=datetime.now(), typ='live')
    db.add(conv_von_a)
    db.commit()

    conv_id_von_A = conv_von_a.id
    org_a_id, org_b_id = org_a.id, org_b.id
    user_a_id, user_b_id = user_a.id, user_b.id
    profil_b_id, profil_b_name = profil_von_b.id, profil_von_b.name

    # Der Trigger trg_mk_tenant_org hat die tenant_orgs-Zeilen erzeugt — zurueckLESEN, nie raten
    # (Muster: tests/test_meeting_save_rls.py::_new_tenant).
    def _tenant_von(org_id):
        row = db.execute(text('SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = :o'),
                         {'o': org_id}).first()
        return row[0] if row else None

    tenant_a = _tenant_von(org_a_id)
    tenant_b = _tenant_von(org_b_id)

    # Die laufende Sitzung von B. Aufbau aus services/live_session.py::init_session_state
    # uebernommen (D-01 gilt auch fuer Datenstrukturen) — 'active_profile_data' liest
    # api_gatekeeper_phrases aus dem 'state'-Unterdict.
    sid_von_B = f'sofort2-sid-B-{uuid.uuid4().hex[:10]}'
    ls._session_state[sid_von_B] = {
        'user_id': user_b_id,
        'org_id': org_b_id,
        'active_profile_id': profil_b_id,
        'active_sid': sid_von_B,
        'mode': 'cold_call',
        'session_start_time': 1.0,
        '_briefing': 'GEHEIM-BRIEFING-B',
        'conversation_log': [
            {'type': 'transcript', 'speaker': 'kunde', 'ts': 0,
             'text': 'GEHEIM-TRANSKRIPT-B'},
        ],
        'painpoints': [],
        'kaufbereitschaft_verlauf': [],
        'word_confidences': [],
        'state': {
            'call_id': call_id_von_B,
            'active_profile_data': {'branche': 'GEHEIM-B', 'detail': 'GEHEIM-DETAIL-B'},
            'precall_briefing': 'GEHEIM-BRIEFING-B',
            'ewb_clicks': [],
            'suggestion_offers': [],
        },
    }

    # ── Seams scharfschalten ────────────────────────────────────────────────────────────────
    emit_recorder = _EmitRecorder()
    monkeypatch.setattr(learning_routes, '_sio_phase_d', emit_recorder)
    monkeypatch.setattr('services.claude_service.claude_client', _FakeClaudeClient())
    monkeypatch.setattr('services.crm_service.generate_crm_export', _fake_generate_crm_export)
    monkeypatch.setattr('services.coaching_service.generate_postcall_analysis',
                        _fake_generate_postcall_analysis)
    monkeypatch.setattr('services.outcome_service.classify', _fake_classify)

    def _fake_recherche_firma(firmenname, ansprechpartner=None, branche=None, profil_daten=None,
                              user_id=None, profile_id=None, sid=None, account_id=None,
                              anonymizer_cache=None):
        # ★ R2-3: GARANTIERT schreiben. Ohne diesen Seam braeche recherche_firma mangels
        # BRAVE_SEARCH_API_KEY ab, BEVOR es schreibt — die Assertion "unveraendert" waere dann
        # trivial erfuellt und bewiese ueber den Schreibschutz nichts.
        if sid:
            ls.set_briefing_for_sid(sid, 'INJEKTION-DURCH-A')
        return ({'text': 'Test-Briefing', 'fields': {}, 'firmenname': firmenname}, None)

    monkeypatch.setattr('services.precall_service.recherche_firma', _fake_recherche_firma)

    def _login(user_id, tenant=None, als_coach=False):
        with client.session_transaction() as s:
            s.clear()
            s['user_id'] = user_id
            s['rolle'] = 'owner'
            if tenant:
                s['tenant_id'] = tenant
            if als_coach:
                s['is_coach'] = True

    def _call_row_frisch():
        db.rollback()
        db.expire_all()
        return db.get(Call, call_id_von_B)

    def _crm_zaehle(sql, params):
        """crm.* liest nur unter gesetzter Tenant-GUC — sonst ist die 0 ein Falsch-Negativ."""
        db.rollback()
        db.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {'t': str(tenant_a)})
        wert = db.execute(text(sql), params).scalar()
        db.rollback()
        return wert

    ctx = {
        'db': db, 'emits': emit_recorder,
        'org_a_id': org_a_id, 'org_b_id': org_b_id,
        'user_a_id': user_a_id, 'user_b_id': user_b_id,
        'tenant_a': tenant_a, 'tenant_b': tenant_b,
        'call_id_von_B': call_id_von_B, 'sid_von_B': sid_von_B,
        'conv_id_von_A': conv_id_von_A,
        'profil_b_id': profil_b_id, 'profil_b_name': profil_b_name,
        'login': _login, 'call_row_frisch': _call_row_frisch, 'crm_zaehle': _crm_zaehle,
    }

    yield ctx

    # ── Teardown ────────────────────────────────────────────────────────────────────────────
    ls._session_state.pop(sid_von_B, None)
    db.rollback()
    user_ids = [user_a_id, user_b_id]
    org_ids = [org_a_id, org_b_id]

    def _ids(sql, params):
        try:
            return [r[0] for r in db.execute(text(sql), params).fetchall()]
        except Exception:
            db.rollback()
            return []

    conv_ids = _ids('SELECT id FROM public.conversation_logs WHERE user_id = ANY(:u)',
                    {'u': user_ids})
    call_ids = [str(x) for x in _ids('SELECT id FROM public.calls WHERE user_id = ANY(:u)',
                                     {'u': user_ids})]
    profil_ids = _ids('SELECT id FROM public.profiles WHERE org_id = ANY(:o)', {'o': org_ids})
    ca_ids = _ids('SELECT id FROM public.coach_assignments WHERE coach_id = ANY(:u)',
                  {'u': user_ids})
    seg_ids = _ids('SELECT id FROM public.transcript_segments WHERE conversation_log_id = ANY(:c)',
                   {'c': conv_ids or [-1]})
    obj_ids = _ids('SELECT id FROM public.objection_events WHERE user_id = ANY(:u)',
                   {'u': user_ids})
    kosten_ids = _ids('SELECT id FROM public.api_cost_log WHERE user_id = ANY(:u)',
                      {'u': user_ids})
    tenant_ids = _ids('SELECT id FROM public.tenant_orgs WHERE legacy_org_id = ANY(:o)',
                      {'o': org_ids})

    # crm.* NUR unter gesetzter Tenant-GUC lesen (FORCE-RLS: ohne GUC sind 0 Zeilen KEIN
    # Abwesenheitsbeweis). deploy.sh verlangt danach 0 Zeilen je crm.*-Tabelle.
    # ⚠ CAST(:t AS uuid), NICHT :t::uuid — SQLAlchemy ersetzt einen Platzhalter NICHT, wenn
    #   direkt ein `::`-Cast folgt (das Doppel-Kolon ist dort die Cast-Schreibweise, nicht der
    #   Beginn eines zweiten Platzhalters). `:t::uuid` ging deshalb WOERTLICH an Postgres und
    #   starb mit `syntax error at or near ":"`. Der `except` darunter verschluckte den Fehler,
    #   crm_ids blieb leer — und weil damit die crm-Kinder nie geloescht wurden, stallte
    #   anschliessend auch public.tenant_orgs/organisations am FK. Sichtbar wurde es erst am
    #   POST-SUITE-Check in deploy.sh ("crm.* nicht leer, 2 Leak-Rows"), nicht am gruenen Test.
    crm_ids = {'crm.meetings': [], 'crm.contacts': [], 'crm.accounts': []}
    for tenant in [t for t in (tenant_a, tenant_b) if t]:
        try:
            db.rollback()
            db.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {'t': str(tenant)})
            for tabelle in crm_ids:
                crm_ids[tabelle] += [
                    str(r[0]) for r in db.execute(
                        text(f'SELECT id FROM {tabelle} WHERE tenant_id = CAST(:t AS uuid)'),
                        {'t': str(tenant)}).fetchall()
                ]
        except Exception as fehler:
            # LAUT, nicht still: ein verschluckter Fehler hier sieht aus wie "keine crm-Zeilen
            # da" und ist von einem echten Abwesenheitsbeweis nicht zu unterscheiden. Der
            # rollback bleibt Pflicht (CLAUDE.md: nie stiller except auf einer PG-Session).
            db.rollback()
            logging.getLogger(__name__).warning(
                '[SOFORT-2-TEARDOWN] crm-Einsammeln fuer tenant=%s fehlgeschlagen: %r — '
                'die crm-Zeilen dieses Tests bleiben liegen und der POST-SUITE-Check in '
                'deploy.sh wird sie melden.', tenant, fehler,
            )

    spec = {
        'crm.meetings': crm_ids['crm.meetings'],
        'crm.contacts': crm_ids['crm.contacts'],
        'crm.accounts': crm_ids['crm.accounts'],
        'public.objection_events': obj_ids,
        'public.transcript_segments': seg_ids,
        'public.api_cost_log': kosten_ids,
        'public.calls': call_ids,
        'public.conversation_logs': conv_ids,
        'public.coach_assignments': ca_ids,
        'public.profiles': profil_ids,
        'public.users': user_ids,
        'public.tenant_orgs': tenant_ids,
        'public.organisations': org_ids,
    }
    cleanup_rows(db, spec, tenant=tenant_a)


# ── Die ACHT Eingaenge ──────────────────────────────────────────────────────────────────────

@pytest.mark.rot_vor_fix
def test_b01_fremder_call_wird_nicht_beendet(client, zwei_konten):
    """Markierung: rot_vor_fix — reisst B-01 auf (calls-UPDATE ohne user_id-Filter)."""
    k = zwei_konten
    k['login'](k['user_a_id'], tenant=k['tenant_a'])
    client.post('/api/beenden',
                json={'call_id': str(k['call_id_von_B']), 'session_mode': 'cold_call'})

    zeile = k['call_row_frisch']()
    assert zeile is not None, 'Die calls-Zeile von B ist verschwunden — Fixture pruefen.'
    assert zeile.ended_at is None, (
        'Konto A hat den Anruf von Konto B BEENDET. Der calls-UPDATE filtert nur auf die '
        'gepostete call_id, nicht auf den Besitzer — und unter public.calls gibt es KEINE RLS.'
    )
    assert zeile.conversation_log_id is None, (
        'Konto A hat sein eigenes Transkript an den fremden Anruf von B gehaengt.'
    )

    # ★ Positiv-Gegenprobe im SELBEN Test (R2-7): mit Bs eigenem Login greift derselbe Aufruf
    # sehr wohl. Ohne sie waere "die Zeile ist unveraendert" nicht von "der Endpunkt ist
    # abgestuerzt" unterscheidbar.
    k['login'](k['user_b_id'], tenant=k['tenant_b'])
    client.post('/api/beenden',
                json={'call_id': str(k['call_id_von_B']), 'session_mode': 'cold_call'})
    zeile_b = k['call_row_frisch']()
    assert zeile_b.ended_at is not None, (
        'Der Endpunkt beendet den Anruf auch mit Bs eigenem Login nicht — dann beweist die '
        'Assertion oben nichts ueber die Besitzpruefung, sondern nur, dass der Pfad tot ist.'
    )


@pytest.mark.rot_vor_fix
def test_b02_fremde_call_daten_nicht_in_der_antwort(client, zwei_konten):
    """Markierung: rot_vor_fix — reisst B-02 auf (Stufe-1-SID-Aufloesung ueber fremde call_id).

    ★ Der ROT-Traeger ist `call_id` in der Antwort: routes/app_routes.py:275-276 uebernimmt die
    GEPOSTETE Kennung ungeprueft, :950 gibt sie zurueck. `conv_id` traegt NICHT (Konto A legt
    legitim eine eigene, leere ConversationLog an — kein Leck).
    """
    k = zwei_konten
    k['login'](k['user_a_id'], tenant=k['tenant_a'])
    antwort = client.post('/api/beenden',
                          json={'call_id': str(k['call_id_von_B']), 'session_mode': 'cold_call'})

    daten = antwort.get_json() or {}
    assert daten.get('call_id') is None, (
        'Die Antwort an Konto A traegt die call_id von Konto B zurueck — die gepostete Kennung '
        'wurde ungeprueft uebernommen und hat die Sitzung von B aufgeloest.'
    )
    zeile = k['call_row_frisch']()
    assert zeile.conversation_log_id is None, (
        'Der fremde Anruf von B zeigt jetzt auf ein Transkript von A.'
    )
    # Zusaetzliche Absicherung, NICHT der ROT-Traeger: bei gefakten Diensten ist das in beiden
    # Laeufen trivial erfuellt.
    assert 'GEHEIM-TRANSKRIPT-B' not in antwort.get_data(as_text=True)


@pytest.mark.rot_vor_fix
def test_b03_gatekeeper_liefert_keine_fremden_variablen(client, zwei_konten):
    """Markierung: rot_vor_fix — reisst B-03 auf (request.args.get('sid') ohne Besitzpruefung)."""
    k = zwei_konten
    k['login'](k['user_a_id'], tenant=k['tenant_a'])
    antwort = client.get(f"/api/gatekeeper/phrases?sid={k['sid_von_B']}")

    assert antwort.status_code == 200
    variablen = (antwort.get_json() or {}).get('variables', {})
    assert variablen.get('branche') == '', (
        'Konto A liest die Branche aus dem LAUFENDEN Gespraech von Konto B.'
    )
    assert variablen.get('detail') == '', (
        'Konto A liest das Detail aus dem laufenden Gespraech von Konto B.'
    )
    assert 'GEHEIM-B' not in antwort.get_data(as_text=True)


@pytest.mark.rot_vor_fix
def test_n01_fremde_sitzung_wird_abgelehnt(client, zwei_konten):
    """Markierung: rot_vor_fix — reisst N-01 auf (Prompt-Injektion in ein fremdes Gespraech)."""
    k = zwei_konten
    k['login'](k['user_a_id'], tenant=k['tenant_a'])
    antwort = client.post('/api/precall/research',
                          json={'firmenname': 'Testfirma GmbH', 'sid': k['sid_von_B']})

    assert antwort.status_code == 404, (
        'Eine fremde sid muss wirken, als gaebe es sie nicht (404) — sonst schreibt Konto A in '
        'das laufende Verkaufsgespraech von Konto B.'
    )
    assert ls._session_state[k['sid_von_B']].get('_briefing') == 'GEHEIM-BRIEFING-B', (
        'Das Briefing der fremden Sitzung wurde UEBERSCHRIEBEN — der Schreib-Pfad ist die '
        'eigentliche Gefahr: _briefing geht in Abschnitt 8 jedes Live-Prompts.'
    )


@pytest.mark.rot_vor_fix
def test_n02_kein_outcome_emit_in_fremden_raum(client, zwei_konten):
    """Markierung: rot_vor_fix — reisst N-02 auf (outcome_ready in den PiP eines Fremden).

    Eigene conv_id + FREMDE call_id ist die einzige Kombination, die bis zum Emit-Block kommt
    (routes/learning.py:23-27 gaten davor mit 400/404).
    """
    k = zwei_konten
    k['login'](k['user_a_id'], tenant=k['tenant_a'])
    client.post('/api/postcall_analysis',
                json={'conv_id': k['conv_id_von_A'], 'call_id': str(k['call_id_von_B'])})

    assert k['sid_von_B'] not in k['emits'].raeume('outcome_ready'), (
        'outcome_ready ging in den SocketIO-Raum von Konto B — mitten in dessen laufendem '
        'Gespraech. Der Raum wird aus der Anfrage abgeleitet statt aus dem eigenen Kontext.'
    )


@pytest.mark.rot_vor_fix
def test_n03_kein_outcome_emit_in_fremden_raum_outcome(client, zwei_konten):
    """Markierung: rot_vor_fix — reisst N-03 auf (derselbe Emit in /api/postcall_outcome)."""
    k = zwei_konten
    k['login'](k['user_a_id'], tenant=k['tenant_a'])
    client.post('/api/postcall_outcome',
                json={'conv_id': k['conv_id_von_A'], 'call_id': str(k['call_id_von_B'])})

    assert k['sid_von_B'] not in k['emits'].raeume('outcome_ready'), (
        'outcome_ready ging in den SocketIO-Raum von Konto B (routes/learning.py:317).'
    )


@pytest.mark.rot_vor_fix
def test_r7_fremde_call_id_wird_nicht_an_termin_gehaengt(client, zwei_konten):
    """Markierung: rot_vor_fix — reisst R-7 auf (Fremdreferenz in eine EIGENE Zeile).

    Die RLS auf crm.* schuetzt die ZEILE mandantenweise — nicht die Fremdreferenz darin.
    """
    k = zwei_konten
    k['login'](k['user_a_id'], tenant=k['tenant_a'])
    antwort = client.post('/crm/meetings',
                          json={'firma': 'Testfirma GmbH', 'call_id': str(k['call_id_von_B'])})

    assert antwort.status_code == 403, (
        'Konto A durfte einen FREMDEN Anruf an seinen eigenen Termin haengen.'
    )
    anzahl = k['crm_zaehle'](
        'SELECT count(*) FROM crm.meetings WHERE call_id::text = :c',
        {'c': str(k['call_id_von_B'])},
    )
    assert anzahl == 0, (
        f'In crm.meetings stehen {anzahl} Zeilen mit der fremden call_id — die Antwort allein '
        'ist kein Beweis, der Schreibvorgang ist es.'
    )

    # Pflicht-Gegenprobe: derselbe Aufruf ohne call_id muss weiterhin durchgehen. Nur damit ist
    # belegt, dass die 403 aus der Besitzpruefung kam und nicht aus einem fehlenden Mandanten.
    ok_antwort = client.post('/crm/meetings', json={'firma': 'Testfirma GmbH'})
    assert (ok_antwort.get_json() or {}).get('ok') is True, (
        'Der Normalfall (ohne call_id) ist mit gebrochen — dann sagt die 403 oben nichts ueber '
        'die Besitzpruefung, sondern nur, dass der Endpunkt gar nicht funktioniert.'
    )


@pytest.mark.rot_vor_fix
def test_r8_fremdes_profil_nicht_uebertragbar(client, zwei_konten):
    """Markierung: rot_vor_fix — reisst R-8 auf (Quell-Org wird nicht geprueft).

    Die vorhandene Pruefung deckt nur die ZIEL-Org (CoachAssignment). Deshalb ist A seiner
    eigenen Org zugewiesen: sonst waere der Test gruen aus dem falschen Grund (403 statt 404).
    """
    k = zwei_konten
    k['login'](k['user_a_id'], tenant=k['tenant_a'], als_coach=True)
    antwort = client.post('/coach/methodik/uebertragen',
                          json={'profile_id': k['profil_b_id'], 'ziel_org_id': k['org_a_id']})

    assert antwort.status_code == 404, (
        'Ein Coach konnte ein FREMDES Profil (Methodik, Einwaende, Skripte) in seine eigene '
        'Organisation kopieren — das Quell-Profil wird nicht gegen seine Org geprueft.'
    )
    db = k['db']
    db.rollback()
    kopien = db.execute(
        text('SELECT count(*) FROM public.profiles WHERE org_id = :o AND name = :n'),
        {'o': k['org_a_id'], 'n': k['profil_b_name']},
    ).scalar()
    db.rollback()
    assert kopien == 0, (
        f'{kopien} Kopie(n) des fremden Profils liegen jetzt in der Organisation von A — der '
        'Inhalt ist tatsaechlich abgeflossen, nicht nur die Antwort.'
    )


# ── Zwei Pflicht-Zusatztests gegen den stillen Ausfall (Punkt 31) ───────────────────────────

def test_fixture_baut_wirklich_eine_fremde_sitzung(zwei_konten):
    """Markierung: keine — schon gruen, prueft aber das Fundament aller acht Faelle.

    ⚠ Ohne diesen Test sind alle acht oben wertlos: legt die Fixture die Sitzung von B nicht an,
    sind alle Assertions trivial erfuellt und der Waechter ist BLIND statt rot — sieht dabei
    aber gruen aus.
    """
    k = zwei_konten
    sid = k['sid_von_B']
    assert sid in ls._session_state, 'Die fremde Sitzung existiert gar nicht.'
    assert ls._session_state[sid]['user_id'] == k['user_b_id']
    assert ls._session_state[sid]['_briefing'] == 'GEHEIM-BRIEFING-B'

    zeile = k['call_row_frisch']()
    assert zeile is not None and zeile.user_id == k['user_b_id']
    assert zeile.ended_at is None, 'Der Anruf von B muss zu Testbeginn OFFEN sein.'

    db = k['db']
    db.rollback()
    profil = db.get(Profile, k['profil_b_id'])
    assert profil is not None and profil.org_id == k['org_b_id'], (
        'Das Profil von B fehlt oder liegt in der falschen Organisation — dann beweist der '
        'R-8-Fall nichts.'
    )
    assert k['org_a_id'] != k['org_b_id'], (
        'A und B sitzen in DERSELBEN Organisation — dann ist keiner der Faelle ein '
        'Fremdzugriff und alle acht sind bedeutungslos.'
    )


def test_eigener_zugriff_funktioniert_weiter(client, zwei_konten):
    """Markierung: keine — die Gegenprobe gegen den ueberschiessenden Fix.

    Ohne sie wuerde ein Fix, der einfach ALLE Zugriffe verweigert, gruen durchgehen — und das
    Produkt waere kaputt.
    """
    k = zwei_konten
    k['login'](k['user_b_id'], tenant=k['tenant_b'])
    antwort = client.get(f"/api/gatekeeper/phrases?sid={k['sid_von_B']}")

    assert antwort.status_code == 200
    variablen = (antwort.get_json() or {}).get('variables', {})
    assert variablen.get('branche') == 'GEHEIM-B', (
        'Konto B kommt an die eigene Sitzung nicht mehr heran — der Fix schiesst ueber und '
        'macht das Produkt kaputt.'
    )
