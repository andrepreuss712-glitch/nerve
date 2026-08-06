"""Phase 08.23.2.MEHRNUTZER-REST-1 — Riegel PRO conv_id statt EIN globaler Riegel.

Der Befund (Roadmap + RESEARCH §1): services/coaching_service.py:8 haelt einen
modul-globalen threading.Lock(), und :59 umschliesst mit ihm den GANZEN Rumpf von
generate_postcall_analysis — inklusive des Sonnet-Aufrufs auf :84, dessen Zeitlimit
config.HTTP_LLM_TIMEOUT_LONG_S = 45.0 s betraegt (config.py:134). Zwei gleichzeitige
Anruf-Enden laufen damit hintereinander statt nebeneinander.

Was diese Datei prueft — und was NICHT:
  (a) test_verschiedene_conv_ids_blockieren_sich_nicht
      ROT-BELEG. Marker rot_vor_fix. Gegen den ungefixten Stand MUSS er failen.
  (b) test_gleiche_conv_id_erzeugt_nur_einen_satz_karten
      KEIN ROT-BELEG (RESEARCH §3.5 / Falle 6). Der heutige globale Riegel schuetzt
      exakt genauso. Dieser Test ist der GEGENPOL gegen den FALSCHEN Fix
      ("Riegel ersatzlos raus, die DB-Pruefung dahinter schuetzt schon") — der ist am
      Code widerlegt: learning_cards hat KEINEN Unique-Constraint auf call_id
      (database/models.py:629-631) und kann auch keinen bekommen (bis zu 3 Karten
      pro Call by design, coaching_service.py:113).
  (c) test_riegellose_variante_erzeugt_doppelte_karten
      FALSIFIZIERBARKEIT. Dieselbe Apparatur gegen eine hier im Testmodul definierte,
      absichtlich riegellose Mini-Funktion -> 6 statt 3 Karten. Ohne diesen Test
      waere (b) eine Behauptung: er beweist, dass die Apparatur Duplikate SEHEN kann.
      Muster "synthetischer Quelltext statt verunreinigter Produktiv-Datei", wie
      tests/test_session_lock_blocking_calls_guard.py:432-441.

KEINE Wanduhr-Messung. "Keine Serialisierung" wird ueber ein threading.Event-Rendezvous
bewiesen ("sind beide gleichzeitig im kritischen Abschnitt?"), nicht ueber
"parallel < 2x seriell" — das wuerde auf dem geteilten VPS unter Deploy-Last die
Maschine messen statt den Code. Deshalb auch KEIN perf-Marker: der wuerde den Test aus
dem Deploy-Tor werfen (-m "not live and not perf") und die Ratsche entwerten.

Jedes wait()/join() traegt ein EIGENES timeout: deploy.sh:221 hat KEINEN pytest-Timeout,
ein haengender Test haengt den gesamten Deploy (tests/test_session_lock_deadlock_guard.py:118-119).

Kein Netz, kein echter Anthropic-Call, keine committenden DB-Writes -> kein cleanup_rows
noetig, keine db_session/client-Fixture, kein TEST_DATABASE_URL. usage=None auf der
Fake-Antwort haelt die Cost-Hooks inaktiv (coaching_service.py:93 "if u:").
"""
import json
import threading
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

import services.claude_service as claude_service_module
from services.coaching_service import generate_postcall_analysis

# ── Zeitgrenzen ───────────────────────────────────────────────────────────────
# (a): wird nur im ROT-Lauf voll ausgeschoepft. Im gefixten Stand kehren beide wait()
#      in Millisekunden zurueck. 5.0 s ist lang genug gegen jeden Scheduler-Ruckler
#      auf dem geteilten VPS und kurz genug fuers Tor (RESEARCH §3.4).
_RENDEZVOUS_S = 5.0
# (b)/(c): wird im KORREKTEN Stand JEDES MAL voll ausgeschoepft (der zweite Faden steht
#      dann am conv_id-Riegel und meldet sich nie). Das ist die dauerhafte Tor-Kosten
#      dieses Gegenpols.
#      SIZING-BELEG (nicht geraten): die Konstante muss NUR die Faden-Startzeit im
#      RIEGELLOSEN Fall ueberbieten — und genau die misst Test (c) empirisch. Dort
#      kommen beide Faden in Millisekunden am Rendezvous an und (c) sieht seine 6 Karten.
#      0.5 s ist damit durch (c) belegt und spart 1,5 s pro Deploy-Tor gegenueber 2.0.
#      Sollte (c) je flattern, ist DAS der Beleg zum Nachziehen — kein Bauchgefuehl.
_GEGENPOL_S = 0.5
# Notbremse fuer das Einsammeln der Faden.
_JOIN_S = 20.0

_DREI_VORSCHLAEGE = json.dumps({'vorschlaege': [
    {'category': 'einwand_preis', 'original_suggestion': f'Satz {i}',
     'alternative_1': 'a1', 'alternative_2': 'a2', 'lernziel': 'Lernziel'}
    for i in range(3)
]})


def _fake_response(text='{"vorschlaege": []}'):
    """Stand-in fuer ein anthropic.types.Message. usage=None haelt die Cost-Hooks
    inaktiv (coaching_service.py:93 "if u:") -> keine echte DB-Session noetig."""
    return SimpleNamespace(content=[SimpleNamespace(text=text)], usage=None)


def _zweig():
    """'A' oder 'B' — abgeleitet aus dem Faden-Namen (Muster
    tests/test_session_lock_deadlock_guard.py:172 'LOCK1-pruefling-A')."""
    return threading.current_thread().name[-1]


# ── Gefaelschte DB-Session mit ECHTEM Zustand ────────────────────────────────
class _FakeQuery:
    def __init__(self, db):
        self._db = db
        self._kw = {}

    def filter_by(self, **kw):
        self._kw = kw
        return self

    def count(self):
        cid = self._kw.get('call_id')
        with self._db.sperre:
            return sum(1 for k in self._db.karten if k == cid)


class _FakeDB:
    """MagicMock reicht hier NICHT: (b)/(c) muessen zaehlen, wie viele Karten wirklich
    entstanden sind. add() legt fadeneigen ab, commit() uebernimmt in die geteilte
    Liste — sonst vermischten zwei Faden ihre ungeschriebenen Karten.

    Committet nichts in eine echte DB -> kein cleanup_rows (tests/conftest.py:263)."""

    def __init__(self):
        self.karten = []              # committete call_id-Werte
        self.sperre = threading.Lock()
        self._offen = {}              # faden-name -> [call_id, ...]

    def query(self, *_a, **_kw):
        return _FakeQuery(self)

    def add(self, card):
        self._offen.setdefault(threading.current_thread().name, []).append(card.call_id)

    def commit(self):
        n = threading.current_thread().name
        with self.sperre:
            self.karten.extend(self._offen.pop(n, []))

    def rollback(self):
        self._offen.pop(threading.current_thread().name, None)

    def close(self):
        pass


def _starte_paar(ziel, argumente):
    """Zwei Daemon-Faden 'MEHRNUTZER-A'/'MEHRNUTZER-B', gestartet und zurueckgegeben.
    daemon=True + join(timeout=) sind Pflicht (deploy.sh:221 ohne pytest-Timeout)."""
    faeden = []
    for name, arg in zip(('MEHRNUTZER-A', 'MEHRNUTZER-B'), argumente):
        t = threading.Thread(target=ziel, args=(arg,), daemon=True, name=name)
        faeden.append(t)
    for t in faeden:
        t.start()
    return faeden


def _sammle_ein(faeden):
    for t in faeden:
        t.join(timeout=_JOIN_S)
    for t in faeden:
        assert not t.is_alive(), (
            f'Faden {t.name} kehrte nicht innerhalb {_JOIN_S}s zurueck — '
            f'ein haengender Faden haengt den Deploy (deploy.sh:221 ohne pytest-Timeout).')


def _rufe_analyse(conv_id):
    generate_postcall_analysis(
        conv_id=conv_id, user_id=1, einwaende=[], painpoints=[],
        kb_start=0, kb_end=30, redeanteil_berater=50, redeanteil_kunde=50,
        dauer_sek=60, skript_abdeckung=0, ga_details=[],
    )


# ══ (a) ROT-BELEG ═════════════════════════════════════════════════════════════

@pytest.mark.rot_vor_fix
def test_verschiedene_conv_ids_blockieren_sich_nicht():
    """Zwei VERSCHIEDENE conv_id muessen GLEICHZEITIG im kritischen Abschnitt sein koennen.

    Gegen den ungefixten Stand (services/coaching_service.py:59 "with _analysis_lock:")
    ist das unmoeglich: Faden A haelt den prozessweiten Riegel und steht im gefaelschten
    LLM-Aufruf, Faden B kommt nie ueber :59 hinaus. A's wait() laeuft in den Timeout,
    erfolg['A'] ist False -> ROT. Das ist eine BLOCKADE, kein Rennen; der Test flattert
    also nicht.

    Nach dem Fix nehmen beide ihren eigenen conv_id-Riegel, beide Events sind gesetzt,
    beide wait() kehren mit True zurueck — typischerweise in Millisekunden.

    Bewusst KEINE Zeitmessung: "parallel < 2x seriell" wuerde auf dem geteilten VPS die
    Maschine messen statt den Code (RESEARCH §3.4 / Falle 4).
    """
    drin = {'A': threading.Event(), 'B': threading.Event()}
    erfolg = {}

    def _fake_create(**_kwargs):
        wer = _zweig()
        anderer = 'B' if wer == 'A' else 'A'
        drin[wer].set()
        erfolg[wer] = drin[anderer].wait(timeout=_RENDEZVOUS_S)
        return _fake_response()

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = _fake_create

    fake_db = MagicMock()
    fake_db.query.return_value.filter_by.return_value.count.return_value = 0

    with patch.object(claude_service_module.claude_client, 'with_options',
                      return_value=fake_client), \
         patch('database.db.get_session', return_value=fake_db):
        faeden = _starte_paar(_rufe_analyse, (4711, 4712))
        _sammle_ein(faeden)

    assert erfolg.get('A') is True and erfolg.get('B') is True, (
        f"Zwei verschiedene conv_id (4711/4712) waren NICHT gleichzeitig im kritischen "
        f"Abschnitt: {erfolg!r}. Der Riegel in services/coaching_service.py:59 ist "
        f"prozessweit — ein zweiter Nutzer wartet im Worst Case "
        f"config.HTTP_LLM_TIMEOUT_LONG_S = 45 s (config.py:134) und belegt dabei einen "
        f"der 64 gthread-Threads (deploy/nerve.service:35-36). Der Fix ist ein Riegel "
        f"PRO conv_id, NICHT das ersatzlose Entfernen des Riegels.")


# ══ (b) GEGENPOL — KEIN ROT-BELEG ═════════════════════════════════════════════

def test_gleiche_conv_id_erzeugt_nur_einen_satz_karten():
    """Zwei parallele Requests DERSELBEN conv_id erzeugen weiterhin EINEN Satz Karten.

    ⚠ EHRLICHKEIT (RESEARCH §3.5 / Falle 6): Dieser Test ist gegen den HEUTIGEN Stand
    GRUEN. Er ist KEIN ROT-Beleg und darf im SUMMARY nicht als solcher gefuehrt werden —
    der globale Riegel schuetzt exakt genauso. Er ist der GEGENPOL gegen den FALSCHEN
    Fix ("Riegel ersatzlos raus"): learning_cards hat KEINEN Unique-Constraint auf
    call_id (database/models.py:629-631) und kann auch keinen bekommen (bis zu 3 Karten
    pro Call by design, coaching_service.py:113). Ohne Riegel lesen beide Faden die 0
    und schreiben beide.

    Warum das deterministisch beisst: das Rendezvous sitzt IM gefaelschten LLM-Aufruf —
    also NACH der count-Abfrage (:65) und VOR dem Schreiben (:129-130). Faden A schreibt
    erst, nachdem B sich gemeldet hat; B meldet sich erst, nachdem B gezaehlt hat. Im
    riegellosen Fall zaehlen also beide zwingend 0 (-> Test (c) belegt genau das).
    Im korrekten Fall steht B am conv_id-Riegel, A laeuft nach _GEGENPOL_S weiter,
    schreibt 3, gibt frei; B zaehlt dann 3 und ueberspringt den Sonnet-Aufruf.
    Die _GEGENPOL_S sind die dauerhaften Tor-Kosten dieses Gegenpols.
    """
    fake_db = _FakeDB()
    drin = {'A': threading.Event(), 'B': threading.Event()}
    aufrufe = []
    aufrufe_sperre = threading.Lock()

    def _fake_create(**_kwargs):
        with aufrufe_sperre:
            aufrufe.append(_zweig())
        wer = _zweig()
        anderer = 'B' if wer == 'A' else 'A'
        drin[wer].set()
        drin[anderer].wait(timeout=_GEGENPOL_S)
        return _fake_response(_DREI_VORSCHLAEGE)

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = _fake_create

    with patch.object(claude_service_module.claude_client, 'with_options',
                      return_value=fake_client), \
         patch('database.db.get_session', return_value=fake_db):
        faeden = _starte_paar(_rufe_analyse, (4711, 4711))
        _sammle_ein(faeden)

    assert len(fake_db.karten) == 3, (
        f"Duplikatschutz gebrochen: {len(fake_db.karten)} Karten fuer conv_id=4711 statt 3. "
        f"Der Riegel darf NICHT ersatzlos entfallen — die count()-Pruefung in "
        f"services/coaching_service.py:65 ist die EINZIGE Duplikat-Sperre im Prozess.")
    assert len(aufrufe) == 1, (
        f"Der Sonnet-Aufruf lief {len(aufrufe)}x statt 1x ({aufrufe!r}). Das ist die "
        f"schaerfere der beiden Aussagen: sie faellt auch dann, wenn die Karten zufaellig "
        f"ueberschrieben statt verdoppelt wuerden.")


# ══ (c) FALSIFIZIERBARKEIT ════════════════════════════════════════════════════

def _riegellos_erzeuge_karten(conv_id, db, drin):
    """Absichtlich RIEGELLOSE Mini-Fassung derselben count-dann-schreib-Logik.

    Steht bewusst IM TESTMODUL (Muster "synthetischer Quelltext",
    tests/test_session_lock_blocking_calls_guard.py:432-441): so laesst sich beweisen,
    dass die Apparatur Duplikate ueberhaupt SEHEN kann, OHNE Produktiv-Code anzufassen
    und ohne Rueckbau-Risiko. Sie bildet coaching_service.py:65 / :129-130 nach.
    """
    class _Karte:
        def __init__(self, call_id):
            self.call_id = call_id

    if db.query(None).filter_by(call_id=conv_id).count() > 0:
        return
    wer = _zweig()
    anderer = 'B' if wer == 'A' else 'A'
    drin[wer].set()
    drin[anderer].wait(timeout=_GEGENPOL_S)
    for _ in range(3):
        db.add(_Karte(conv_id))
    db.commit()


def test_riegellose_variante_erzeugt_doppelte_karten():
    """Anti-Stub: OHNE Riegel entstehen 6 Karten. Damit ist bewiesen, dass Test (b)
    Duplikate sehen KANN und nicht bloss immer gruen ist."""
    fake_db = _FakeDB()
    drin = {'A': threading.Event(), 'B': threading.Event()}

    faeden = _starte_paar(lambda cid: _riegellos_erzeuge_karten(cid, fake_db, drin),
                          (4711, 4711))
    _sammle_ein(faeden)

    assert len(fake_db.karten) == 6, (
        f"Die Apparatur sieht Duplikate NICHT: riegellos entstanden {len(fake_db.karten)} "
        f"statt 6 Karten. Solange das so ist, beweist Test (b) nichts.")
