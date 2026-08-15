"""Phase 08.23.2.SOFORT-2 Plan 01 — Waechter: Besitzpruefung an den Eingaengen (ERST-ROT).

WOFUER: Ein Endpunkt, der eine `sid`/`call_id`/`profile_id` aus der Anfrage entgegennimmt und
damit einen Zustand oder eine DB-Zeile aufloest, beweist mit `@login_required` nur „irgendein
Konto" — nicht „dieses Objekt gehoert dir". Genau diese Fehlerklasse steckt an sechs Eingaengen
in routes/ (Sweep 2026-08-04/05, gemeldet in 08.23.2.SOFORT-2-FUNDE.md).

WAS ER TUT: reiner statischer AST-Sweep ueber routes/*.py. Er leitet die Pruefpunkte SELBST aus
dem Code ab (D-05) — ein Waechter, der die Fundliste aus der RESEARCH.md abschreibt, beweist nur
seinen eigenen Pruefkatalog (CLAUDE.md Punkt 31, wortwoertlich der LOCK-2-Fall). Keine Datenbank,
kein Netz, kein Laden der Anwendung: die Datei laesst sich gegen jeden ausgecheckten oder
ausgerollten Stand fahren — das ist die Voraussetzung fuer den ROT-Lauf in Plan 02.

RESTLUECKEN
-----------
1. ABGEDECKT: FUENF Mengen aus routes/*.py, ALLE Regeln HELFER-BEWUSST.
   - Mengen 1-3 (loest _session_state auf / liest 'sid' bzw. 'call_id' aus der Anfrage):
     einen der DREI benannten Live-Besitz-Helfer ODER einen anerkannten Besitz-Helfer rufen.
   - Menge 4 ('profile_id' aus der Anfrage): org_id muss GEGEN EINE SERVER-IDENTITAET GEBUNDEN
     sein (Vergleich <zeile>.org_id gegen g.* ODER Schluesselwort org_id=g.* in einem Filter)
     ODER ein anerkannter Besitz-Helfer wird gerufen. Die blosse ERWAEHNUNG von org_id genuegt
     NICHT - sie kann an einem Anfrage-Wert haengen (belegt: methodik_uebertragen).
   - Menge 5 (sid|call_id|profile_id als URL-Routen-Parameter): eine Server-Identitaet im
     eigenen Rumpf ODER ein anerkannter Besitz-Helfer.
   ANERKANNT heisst ABGELEITET, nicht behauptet: der Helfer existiert als FunctionDef in seiner
   Quelldatei UND traegt selbst eine Server-Identitaet in SEINEM Rumpf. Ein Helfer, der nichts
   prueft, macht seine Aufrufer weiterhin rot. Belegt: _rolle() (routes/profiles.py:35) traegt
   KEINE Server-Identitaet und ist deshalb kein Besitz-Helfer.

2. ⚠ DIE ZENTRALE LUECKE: der Waechter sieht, DASS geprueft wird — NICHT, DASS SEIN ERGEBNIS
   BEACHTET WIRD. `if sid_belongs_to(sid, uid): pass` waere gruen. Ebenso sieht er nicht, ob die
   Pruefung VOR oder NACH der Verwendung der Kennung steht (AST-Nachbarschaft ist kein Beweis
   fuer Ausfuehrungs-Reihenfolge). Dagegen schuetzt allein der Verhaltens-Waechter
   tests/test_ownership_endpoints.py.

3. ⚠ DER DB-FALL IST STRUKTURELL UNSICHTBAR: B-01 ist ein fehlender `user_id`-Filter in einem
   SQLAlchemy-Query. Ein AST-Sweep kann „hat einen Besitz-Filter" nicht zuverlaessig
   entscheiden — genau daran scheiterte der Sweep dieser Phase (8 von 84 Verdachtsfaellen waren
   Fehlalarme, weil die Bedingung ueber eine Variable oder einen Helfer lief). Fuer B-01 ist der
   Zwei-Konten-Verhaltenstest die TRAGENDE Schicht, dieser Sweep hoechstens eine zweite.

4. STRUKTURELL UNSICHTBAR, weiteres: geparst wird NUR routes/*.py. Ein Endpunkt, der ausserhalb
   dieses Ordners registriert wird, taucht hier nie auf. Ebenso: dynamischer Dispatch via
   getattr, Callbacks, Registry-Hooks, alles was erst zur Laufzeit entsteht. Und: die Mengen 2-4
   erkennen `.get('sid')` nur mit LITERALEM Schluessel — ein `.get(_KEY)` rutscht lautlos durch.
   INDEX-ZUGRIFF (data['call_id'], request.get_json()['sid']) wird ebenfalls NICHT gesehen;
   gemessen 2026-08-05: HEUTE 0 Fundorte in routes/, also aktuell kein Loch — aber eine offene
   Kante fuer neuen Code.

   ⚠ DIE NAMENS-KANTE (R2-4): Dieser Waechter kennt DREI Kennungs-NAMEN - 'sid', 'call_id',
   'profile_id'. Eine Kennung, die ANDERS heisst, ist fuer ihn STRUKTURELL UNSICHTBAR.
   Belegte Beispiele im selben Repo: routes/app_routes.py:1420 @route('/api/launcher/profile/
   <int:pid>') -> def api_launcher_profile(pid) ist eine Profil-Id aus der URL, nur anders
   benannt; routes/profiles.py:266/:292 <int:pid>/skripte/<int:sid>; routes/app_routes.py:1582
   <int:event_id>; routes/coach.py:165 ziel_org = data.get('ziel_org_id').
   KEIN LOCH, SONDERN EINE KATALOG-GRENZE: ein unabhaengiger Gegen-Sweep ueber ALLE
   URL-Parameter-Namen (Cross-AI Fable, 2026-08-05) fand KEINEN ungeschuetzten Fall; einziger
   Treffer ohne Guard war routes/waitlist.py::check_status, bewusst oeffentlich. Der BESTAND
   ist also sauber - aber das Gruen dieses Waechters darf NICHT als "alle Kennungen geprueft"
   gelesen werden. Deshalb steht es hier.

   ⚠ SOCKET.IO IST AUSSERHALB (R-9 / C-2): der Sweep parst NUR routes/*.py. Die Live-Strecke
   laeuft ueber Socket.IO-Handler in services/deepgram_service.py. Zwei davon nehmen eine SID
   als zweites Positions-Argument entgegen: handle_mute_mic (:963) und handle_manual_ewb (:978),
   je '_sid = request.sid if sid is None else sid'. Die Datei liegt nicht in routes/, die
   Kennung kommt nicht aus .get(), und _sid ist kein URL-Parameter - sie faellt durch ALLE FUENF
   Mengen. Gemeldet als R-9 in 08.23.2.SOFORT-2-FUNDE.md Abschnitt 2, in dieser Phase bewusst
   NICHT gefixt (Reparatur-Modus).

5. HEURISTIK, zweischneidig — in BEIDE Richtungen:
   - `.get('sid')` trifft JEDES `get` mit diesem Schluessel, auch auf einem Dict, das nichts mit
     der Anfrage zu tun hat (Falschtreffer; Beispiel: routes/training.py::training_end liest
     session.get('profile_id') aus dem Trainings-Zustand, nicht aus der Anfrage).
   - Der URL-Platzhalter `<int:sid>` heisst in routes/dashboard.py eine ConversationLog-Id und in
     routes/profiles.py eine Skript-Id — NAMENSGLEICH, aber kein Sitzungs-Bezug (Falschtreffer;
     beide sind trotzdem korrekt besitzgeprueft und fallen deshalb nicht auf).
   - ⚠ GESCHLOSSENER FALSCHTREFFER (F-B1), als Warnung fuer den naechsten Regel-Bauer:
     Die ERSTE Fassung der Regel fuer Mengen 4/5 forderte eine Server-Identitaet im EIGENEN
     Rumpf. Sie haette routes/profiles.py::api_faqs_list (:621), ::api_faqs_create (:647) und
     ::api_tabu_update (:745) als Verstoss gemeldet - DREI KORREKT GESCHUETZTE Funktionen, deren
     Pruefung im Helfer _require_own_profile sitzt. Geschlossen durch die Helfer-Bewusstheit,
     NICHT durch einen Allowlist-Eintrag (der waere eine stille Ausnahme fuer korrekten Code
     gewesen). Regressions-Sperre: Gegenprobe 2 in test_regeln_fangen_ein_kuenstliches_leck.
   - ⚠ DURCHRUTSCHER der Server-Identitaets-Regel, belegt und TEILWEISE geschlossen:
     routes/coach.py::methodik_uebertragen ENTHAELT `coach_id=g.user.id` — aber der Vergleich
     gilt der ZIEL-Organisation, nicht dem QUELL-Profil. Eine Regel, die nur "irgendeine
     Identitaets-Erwaehnung" sucht, haelt die Funktion faelschlich fuer geprueft.
     GESCHLOSSEN fuer Menge 4 durch die geschaerfte org_id-BINDUNGS-Regel: sie verlangt org_id
     gegen eine Server-Identitaet gebunden, und methodik_uebertragen bindet org_id nur an einen
     Anfrage-Wert -> der Waechter faengt R-8 jetzt SELBST (er ist am Bestand rot). OFFEN BLEIBT
     die allgemeine Klasse "Vergleich gegen das FALSCHE Objekt" fuer die Mengen 1-3 und 5: dort
     prueft der Waechter Anwesenheit eines Helfers bzw. einer Identitaet, nicht die Richtigkeit
     des verglichenen Objekts. Wer sich auf sein Gruen verlaesst, verlaesst sich auf zu wenig.
   - ⚠ FOUNDER-ONLY-KLASSE (neu 2026-08-15, METRIK-1): Fuer eine Route, die AUSSCHLIESSLICH
     der Founder-Sicht dient, stellt Menge 5 die FALSCHE Frage. Ihre Regel fragt "gehoert
     dieses Objekt dem Anfragenden?" — beim mandanten-UEBERGREIFENDEN Nachpruefen gibt es dazu
     nichts zu pruefen, das Uebergreifen IST der Zweck. Belegter Fall:
     routes/admin_dashboard.py::beleg_check_fall (METRIK-1 Plan 01). Ein g.user.id-Vergleich
     waere dort kein Fix, sondern ein Feature-Bruch. Getragen wird die Route von
     @superadmin_required (services/auth_decorators.py:5-11, abort(403) VOR dem Rumpf) — fuer
     DIESE Route strenger als eine org_id-Bindung, nicht schwaecher.
     ⛔ BEWUSST NICHT als allgemeine Regel gebaut: haette der Waechter jeden
     @superadmin_required-Endpunkt pauschal anerkannt, waere der Dekorator zum Freibrief
     geworden — jede kuenftige Route, die Founder-Sicht mit NUTZER-EIGENEN Daten mischt, waere
     stillschweigend mit ausgenommen. Stattdessen: ein begruendeter Allowlist-Eintrag PRO
     ROUTE, und die Weiche selbst wird am AST nachgeprueft
     (test_founder_ausnahmen_tragen_ihre_founder_weiche_noch) — faellt der Dekorator weg,
     faellt der Eintrag auf.
     OFFENE REST-KANTE, ausdruecklich: fuer diese eine Route sagt der Sweep jetzt NICHTS mehr.
     Tragende Schicht ist der Verhaltens-Test
     tests/test_beleg_check_founder.py::test_einzelfall_seite_ist_nicht_fuer_jeden.
   - ⚠ DURCHRUTSCHER der org_id-BINDUNGS-Regel selbst: Zweig (b) kann einen FILTER nicht
     zuverlaessig von einem SCHREIBVORGANG unterscheiden. Deshalb ist (b) bewusst ENG gefasst
     (nur filter_by/filter/get/query-Ketten). Belegt: routes/training.py::training_end (:714)
     traegt CLog(org_id=g.org.id, ...) -- die eigene org_id wird dort nur HINGESCHRIEBEN, die
     Funktion prueft profile_id ueberhaupt nicht. Unter einer weiten Fassung ("irgendein
     ast.Call") waere sie faelschlich GRUEN gewesen. Hier ist der Fall harmlos, weil
     profile_id aus dem Server-Zustand kommt (session.get, :715) und deshalb als
     FALSCH-TREFFER in der Allowlist steht -- aber die Kante bleibt fuer NEUEN Code offen:
     ein Konstruktor-Schreibvorgang sieht einem Filter strukturell aehnlich. Das ist dieselbe
     Wurzel wie F-B1 und R-8: ANWESENHEIT STATT BINDUNG.

6. GEPRUEFT UND GESCHLOSSEN:
   - Die direkteste Form der Fehlerklasse — eine _session_state-Aufloesung in routes/ ganz ohne
     Besitz-Vergleich — ist abgedeckt durch test_zustands_aufloesungen_gehen_durch_den_besitz_helfer.
     Rest-Kante: siehe Punkt 2 (Ergebnis wird nicht beachtet).
   - Die Weitergabe einer fremden sid an einen SERVICE (N-01, recherche_firma) ist abgedeckt
     durch die zweite Menge SID_AUS_ANFRAGE — obwohl in routes/ dort gar keine
     _session_state-Zeile steht.
   - Die Fremdreferenz in eine EIGENE Zeile (R-7, crm.meetings.call_id) ist abgedeckt durch die
     dritte Menge plus den dritten Helfer call_belongs_to.
   - Kennungen aus dem URL-Pfad sind abgedeckt durch die fuenfte Menge (vorher: strukturell
     unsichtbar).
   - Stiller Ausfall der Ableitung: geschlossen durch FUENF getrennte Mindest-Soll-Zahlen.
   - Umbenennung der Helfer: geschlossen durch test_helfer_existieren_und_pruefen_user_id.
   - Dass Menge 5 ueberhaupt beisst: geschlossen durch test_regeln_fangen_ein_kuenstliches_leck
     (sie ist am Bestand gruen, ihr ROT-Beleg ist das kuenstliche Leck).
   - Dass Menge 4 beisst: geschlossen AM BESTAND - die geschaerfte org_id-Bindungs-Regel meldet
     methodik_uebertragen (R-8) rot, ohne kuenstliches Leck. Sie ist damit die einzige der fuenf
     Mengen mit einem echten ROT-Beleg aus dem Produktionscode.
   - Der Falschtreffer gegen helfer-geschuetzten Code (F-B1): geschlossen durch die
     Helfer-Bewusstheit aller drei Regeln plus Gegenprobe 2 im Selbsttest.
   - Dass ein wertloser Helfer zum Freibrief wird: geschlossen durch Teil (b) der Anerkennung
     (test_helfer_existieren_und_pruefen_user_id) plus Gegenprobe 3 im Selbsttest.
   - Dass ein Allowlist-Eintrag seine Begruendung ueberlebt, waehrend der Code sie verliert:
     geschlossen fuer die Founder-Klasse durch die AST-Nachpruefung der Weiche
     (test_founder_ausnahmen_tragen_ihre_founder_weiche_noch, mit eigener Gegenprobe).
     ⚠ NICHT geschlossen fuer die UEBRIGEN Allowlist-Eintraege: deren Begruendungen
     (verschachtelter Helfer, korrekter user_id-Filter, Server-Zustand statt Anfrage) haengen
     an Code-Formen, die dieser Waechter nicht nachprueft. Sie bleiben Prosa.
   - NICHT geschlossen: der DB-Fall (Punkt 3), die Namens-Kante und die Socket.IO-Flaeche
     (Punkt 4), sowie die allgemeine Klasse "Vergleich gegen das falsche Objekt" fuer die
     Mengen 1-3 und 5 (Punkt 5).

ZWEITE SCHICHT DARUNTER
-----------------------
tests/test_ownership_endpoints.py (Verhalten, Konto A gegen Konto B) und die Gegenprobe mit zwei
Konten im Browser (D-06, Plan 04). ⚠ Eine DRITTE Schicht gibt es NICHT: public.calls,
public.conversation_logs und public.profiles haben auf Production KEINE RLS (belegt per psql als
postgres: pg_class.relrowsecurity = f, 2026-08-05). Der Filter im Code ist die einzige Kontrolle.

WAS NICHT ERLAUBT IST, wenn dieser Waechter anschlaegt: die Allowlist fuellen, das Muster
aufweichen oder ein Mindest-Soll senken. Einzige zulaessige Ausnahme ist der nachweisliche
Falsch-Treffer, mit `# FALSCH-TREFFER:`-Kommentar, Datei:Zeile und Begruendung.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Der Sweep-Bereich. Bewusst der ganze Ordner statt einer Datei-Liste: eine handverlesene
# Datei-Grenze ist genau die Handpflege, die D-05 verbietet.
SWEEP_ORDNER = 'routes'

# Die drei benannten Live-Besitz-Helfer (services/live_session.py, gebaut in Plan 02 Task 2).
HELFER = ('sid_belongs_to', 'resolve_own_sid_by_call_id', 'call_belongs_to')

# Was als Identitaet des ANFRAGENDEN gilt — vom Server gesetzt, nicht vom Client waehlbar.
SERVER_IDENTITAET = ('g.user.id', 'g.org.id', 'g.tenant_id', 'g.user.org_id')

# Anerkannte Besitz-Helfer: Name -> Quelldatei. Die Anerkennung wird ABGELEITET
# (Existenz als FunctionDef + eigene Server-Identitaet im Rumpf), nicht hier behauptet.
BESITZ_HELFER_QUELLEN = {
    'sid_belongs_to':             'services/live_session.py',
    'resolve_own_sid_by_call_id': 'services/live_session.py',
    'call_belongs_to':            'services/live_session.py',
    '_require_own_profile':       'routes/profiles.py',
}

# Die drei live_session-Helfer arbeiten auf dem RAM-Zustand und vergleichen dort user_id
# statt g.* — deshalb gilt fuer sie zusaetzlich dieser Bezeichner als Identitaets-Beleg.
LIVE_HELFER_IDENTITAET = 'user_id'

# Kennungs-Namen, die dieser Waechter kennt. Die Katalog-Grenze steht im Modul-Docstring
# Punkt 4 (Namens-Kante) ausdruecklich benannt.
URL_KENNUNGEN = frozenset({'sid', 'call_id', 'profile_id'})

# Die Founder-Weiche. Sie ist KEIN allgemeiner Freibrief (siehe Modul-Docstring Punkt 5,
# Bullet FOUNDER-ONLY-KLASSE) — sie wird nur dort anerkannt, wo ein Allowlist-Eintrag sie
# ausdruecklich benennt, und dieser Eintrag wird gegen den echten Dekorator nachgeprueft.
FOUNDER_WEICHE = 'superadmin_required'

# Lese-/Filter-Aufrufe fuer Zweig (b) der org_id-Bindung. BEWUSST ENG: ein Konstruktor ist
# ein SCHREIBVORGANG und beweist keine Pruefung (Checker-B-3).
FILTER_METHODEN = frozenset({'filter_by', 'filter', 'get', 'query'})

MENGEN_NAMEN = (
    'ZUSTANDS_FUNKTIONEN',
    'SID_AUS_ANFRAGE',
    'CALLID_AUS_ANFRAGE',
    'PROFILEID_AUS_ANFRAGE',
    'KENNUNG_AUS_URL',
)

PRAEFIX_FALSCH_TREFFER = 'FALSCH-TREFFER:'
PRAEFIX_GEMELDET = 'GEMELDET-NICHT-GEFIXT:'

# ── Mindest-Soll je Menge — Sperre gegen den stillen Ausfall (CLAUDE.md Punkt 31) ────────────
# Werte: Zahlen-Tafel ZT-2 / ZT-3 / ZT-4 / ZT-5 / ZT-6 im Plan 01.
# Am Code abgeleitet 2026-08-05 (ast.parse ueber routes/*.py), NICHT geschaetzt.
# Zaehlung VOR Allowlist-Abzug.
#
# ⚠ DIE ZAHLEN MUESSEN DEN EIGENEN FIX UEBERLEBEN. Ein Mindest-Soll auf einer Menge, die
# der Fix VERKLEINERT, macht sich selbst dauerhaft rot und zwingt den naechsten Leser zu genau
# der stillschweigenden Senkung, die die Fehlermeldung verbietet. Deshalb steht hier jeweils
# der Wert NACH dem Fix; im ROT-Lauf (vor dem Fix) sind die Mengen groesser und die Pruefung
# ist wegen >= trotzdem PASSED.
MINDEST_ZUSTANDS_FUNKTIONEN   = 3   # ZT-2. NACH dem Fix: api_beenden (der Stufe-2-Scan bleibt),
                                    # _load_beenden_state (verschachtelt!), api_gatekeeper_phrases.
                                    # api_postcall_analysis und api_postcall_outcome loesen
                                    # _session_state nach Plan 03 Task 2 NICHT MEHR SELBST auf.
                                    # Vor dem Fix: 5 (ZT-1).
MINDEST_SID_AUS_ANFRAGE       = 2   # ZT-3. api_gatekeeper_phrases, api_precall_research
MINDEST_CALLID_AUS_ANFRAGE    = 5   # ZT-4. api_beenden, api_calls_latest_outcome, save_meeting,
                                    # api_postcall_analysis, api_postcall_outcome
MINDEST_PROFILEID_AUS_ANFRAGE = 6   # ZT-5. api_set_profile, methodik_uebertragen,
                                    # api_profile_preview_context, training_start, training_end,
                                    # api_training_personality_generate
MINDEST_KENNUNG_AUS_URL       = 8   # ZT-6. api_calls_correct_outcome, session_detail,
                                    # api_faqs_list, api_faqs_create, api_tabu_update,
                                    # skript_bearbeiten, skript_loeschen,
                                    # training_scenarios_delete

SOLL_JE_MENGE = {
    'ZUSTANDS_FUNKTIONEN':   MINDEST_ZUSTANDS_FUNKTIONEN,
    'SID_AUS_ANFRAGE':       MINDEST_SID_AUS_ANFRAGE,
    'CALLID_AUS_ANFRAGE':    MINDEST_CALLID_AUS_ANFRAGE,
    'PROFILEID_AUS_ANFRAGE': MINDEST_PROFILEID_AUS_ANFRAGE,
    'KENNUNG_AUS_URL':       MINDEST_KENNUNG_AUS_URL,
}

# ── Allowlist — Datei::Funktion -> GRUND. Ohne Grund kein Eintrag. ───────────────────────────
# Jeder Eintrag beginnt mit GENAU EINEM der zwei Praefixe. Die Unterscheidung ist der ganze
# Punkt: „Allowlist fuellen" ist die verbotene Abkuerzung, ein benannter, begruendeter
# Ausnahmefall ist es nicht (Punkt 31).
ALLOWLIST: dict[str, str] = {
    'routes/app_routes.py::_load_beenden_state':
        'FALSCH-TREFFER: verschachtelte Helfer-Funktion in api_beenden '
        '(routes/app_routes.py:211). Sie liest ls._session_state.get(_sid) in :216, bekommt '
        '_sid aber als ARGUMENT aus dem Aufruf-Kontext — und der ist nach dem Fix (Plan 03 '
        'Task 1a) bereits besitzgeprueft: _beenden_sid stammt aus resolve_own_sid_by_call_id '
        'im eigenen Rumpf von api_beenden. Ein Helfer-Aufruf hier waere die zweite Pruefung '
        'derselben Sache. ACHTUNG: der Eintrag faellt weg, sobald _load_beenden_state einen '
        'zweiten Aufrufer bekaeme — der Hygiene-Test meldet ihn dann nicht, deshalb steht es '
        'hier im Klartext.',
    'routes/app_routes.py::api_calls_latest_outcome':
        'FALSCH-TREFFER: nimmt call_id aus dem Query-String (routes/app_routes.py:2116), '
        'filtert den Query aber bereits korrekt auf den Besitzer — :2126 '
        '"q = db_lo.query(Call).filter(Call.user_id == g.user.id)", die call_id verengt nur '
        'zusaetzlich (:2128). Eine fremde call_id liefert 0 Zeilen. Ein Helfer-Aufruf waere '
        'eine zweite Pruefung derselben Sache.',
    'routes/admin_dashboard.py::beleg_check_fall':
        'FALSCH-TREFFER: FOUNDER-ONLY-KLASSE. Die Regel von Menge 5 fragt "gehoert dieses '
        'Objekt dem Anfragenden?" — bei dieser Route gibt es dazu NICHTS zu pruefen, weil das '
        'mandanten-UEBERGREIFENDE Lesen der ZWECK ist (METRIK-1 Plan 01, D-23 Auflage 3: der '
        'Founder muss JEDEN Anruf nachpruefen koennen, sonst ist der Satz "wird von einem '
        'NERVE-Mitarbeiter geprueft" ein Versprechen ohne Deckung). Ein g.user.id-Vergleich '
        'waere hier kein Fix, sondern ein Feature-Bruch — der Founder besitzt die Anrufe nicht. '
        'GETRAGEN WIRD DIE ROUTE VON @superadmin_required (services/auth_decorators.py:5-11): '
        'ohne g.user.is_superadmin bricht der Dekorator mit 403 ab, BEVOR der Rumpf laeuft — '
        'ein fremder Nutzer erreicht die call_id-Aufloesung also gar nicht. Das ist fuer DIESE '
        'Route strenger als eine org_id-Bindung, nicht schwaecher. BELEGT ZUR LAUFZEIT, NICHT '
        'IN PROSA: tests/test_beleg_check_founder.py::test_einzelfall_seite_ist_nicht_fuer_jeden '
        '(nicht-superadmin bekommt 302/401/403, nie 200). '
        '⛔ KEIN FREIBRIEF FUER DEN DEKORATOR: die Ausnahme gilt, weil hier NUR '
        'Founder-Sicht-Daten aufgeloest werden. Eine Route, die eine Founder-Weiche mit '
        'nutzer-eigenen Daten MISCHT, braucht die Besitzpruefung weiterhin — deshalb ist dies '
        'ein Eintrag pro Route und keine Regel-Aufweichung. Die Weiche selbst wird von '
        'test_founder_ausnahmen_tragen_ihre_founder_weiche_noch am AST nachgeprueft: faellt '
        '@superadmin_required weg, faellt dieser Eintrag auf.',
    'routes/training.py::training_end':
        'FALSCH-TREFFER: profile_id stammt aus session.get("profile_id") '
        '(Server-Zustand, training.py:715), NICHT aus der Anfrage — die Funktion hat '
        'nichts zu pruefen. Ihr einziges org_id=g.org.id steht in training.py:714 im '
        'CLog-Konstruktor: ein SCHREIBVORGANG, kein Besitznachweis; die enge Fassung '
        'von Regel (b) erkennt ihn deshalb bewusst nicht an.',
}


# ── AST-Hilfen (Muster: tests/test_live_latency_coverage.py) ─────────────────────────────────

def _own_nodes(func: ast.AST):
    """Alle Nachfahren-Knoten von `func`, OHNE in verschachtelte Funktionen abzusteigen."""
    for child in ast.iter_child_nodes(func):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield child
        yield from _own_nodes(child)


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - defensiv
        return ''


def _erstes_arg_konstante(call: ast.Call):
    if not call.args:
        return None
    erstes = call.args[0]
    if isinstance(erstes, ast.Constant) and isinstance(erstes.value, str):
        return erstes.value
    return None


def _liest_session_state(eigene: list) -> bool:
    """Menge 1: `_session_state` als Attribut oder Name im EIGENEN Rumpf.

    Kommentare zaehlen nicht — das ist der ganze Grund fuer AST statt grep
    (routes/app_routes.py enthaelt reine Kommentar-Erwaehnungen).
    """
    for n in eigene:
        if isinstance(n, ast.Attribute) and n.attr == '_session_state':
            return True
        if isinstance(n, ast.Name) and n.id == '_session_state':
            return True
    return False


def _get_mit_schluessel(eigene: list, schluessel: str) -> bool:
    """Mengen 2-4: `<irgendwas>.get('<schluessel>')` mit LITERALEM Schluessel."""
    for n in eigene:
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute) and f.attr == 'get':
            if _erstes_arg_konstante(n) == schluessel:
                return True
    return False


def _url_kennungen(fn: ast.AST) -> frozenset:
    """Menge 5: Kennung als URL-Routen-Parameter — sie landet als FUNKTIONS-ARGUMENT im Rumpf.

    Genau das war die Blindstelle: es gibt kein `.get()`, das die Mengen 2-4 sehen koennten.
    """
    arg_namen = {a.arg for a in getattr(fn, 'args').args}
    if not arg_namen:
        return frozenset()
    treffer = set()
    for dek in getattr(fn, 'decorator_list', []):
        if not isinstance(dek, ast.Call):
            continue
        strings = [a.value for a in dek.args
                   if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        for kw in dek.keywords:
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                strings.append(kw.value.value)
        for s in strings:
            for name in re.findall(r'<(?:[^:<>]+:)?([A-Za-z_][A-Za-z0-9_]*)>', s):
                if name in URL_KENNUNGEN and name in arg_namen:
                    treffer.add(name)
    return frozenset(treffer)


def _gerufene_namen(eigene: list) -> frozenset:
    """Alle im eigenen Rumpf gerufenen Funktions-/Methoden-Namen.

    Deckt `sid_belongs_to(...)`, `ls.sid_belongs_to(...)` und `_require_own_profile(...)`.
    """
    namen = set()
    for n in eigene:
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name):
            namen.add(f.id)
        elif isinstance(f, ast.Attribute):
            namen.add(f.attr)
    return frozenset(namen)


def _hat_server_identitaet(eigene: list) -> bool:
    for n in eigene:
        if isinstance(n, ast.Attribute) and _unparse(n) in SERVER_IDENTITAET:
            return True
    return False


def _ist_server_identitaet(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and _unparse(node) in SERVER_IDENTITAET


def _hat_org_id_bindung(eigene: list) -> bool:
    """Zweig (a) Vergleich gegen g.*, Zweig (b) org_id=g.* in einem LESE-/FILTER-Aufruf.

    Entscheidend ist, dass org_id GEGEN EINE SERVER-IDENTITAET GEBUNDEN wird — nicht, dass der
    Bezeichner irgendwo vorkommt (belegt: methodik_uebertragen traegt zweimal org_id=ziel_org,
    einen reinen Anfrage-Wert).
    """
    for n in eigene:
        # (a) <zeile>.org_id != g.user.org_id
        if isinstance(n, ast.Compare):
            seiten = [n.left] + list(n.comparators)
            hat_org_id = any(isinstance(s, ast.Attribute) and s.attr == 'org_id' for s in seiten)
            hat_ident = any(_ist_server_identitaet(s) for s in seiten)
            if hat_org_id and hat_ident:
                return True
        # (b) filter_by(id=pid, org_id=g.org.id) — NUR Lese-/Filter-Aufrufe, NIE Konstruktoren
        if isinstance(n, ast.Call):
            f = n.func
            methode = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else '')
            if methode not in FILTER_METHODEN:
                continue
            for kw in n.keywords:
                if kw.arg == 'org_id' and _ist_server_identitaet(kw.value):
                    return True
    return False


class Fund(NamedTuple):
    datei: str
    funktion: str
    zeile: int
    gerufene: frozenset
    server_identitaet: bool
    org_id_bindung: bool

    @property
    def schluessel(self) -> str:
        return f'{self.datei}::{self.funktion}'

    def etikett(self) -> str:
        return f'{self.datei}::{self.funktion} (Zeile {self.zeile})'


# ── DIE EINE REGEL — zweigeteilt, damit der Selbsttest DIESELBE Funktion prueft (R2-5) ───────

def _mengen_aus_quelltext(quelltext: str, rel: str) -> dict[str, set]:
    """DIE EINE REGEL. Nimmt Quelltext + relativen Pfad, gibt die fuenf Mengen zurueck."""
    ergebnis: dict[str, set] = {name: set() for name in MENGEN_NAMEN}
    try:
        baum = ast.parse(quelltext)
    except SyntaxError:  # pragma: no cover - defensiv
        return ergebnis
    for knoten in ast.walk(baum):
        # ⚠ ast.walk (nicht baum.body): verschachtelte FunctionDef wie _load_beenden_state
        # muessen SICHTBAR bleiben. _own_nodes begrenzt danach nur den Rumpf-Umfang.
        if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        eigene = list(_own_nodes(knoten))
        fund = Fund(
            datei=rel,
            funktion=knoten.name,
            zeile=knoten.lineno,
            gerufene=_gerufene_namen(eigene),
            server_identitaet=_hat_server_identitaet(eigene),
            org_id_bindung=_hat_org_id_bindung(eigene),
        )
        if _liest_session_state(eigene):
            ergebnis['ZUSTANDS_FUNKTIONEN'].add(fund)
        if _get_mit_schluessel(eigene, 'sid'):
            ergebnis['SID_AUS_ANFRAGE'].add(fund)
        if _get_mit_schluessel(eigene, 'call_id'):
            ergebnis['CALLID_AUS_ANFRAGE'].add(fund)
        if _get_mit_schluessel(eigene, 'profile_id'):
            ergebnis['PROFILEID_AUS_ANFRAGE'].add(fund)
        if _url_kennungen(knoten):
            ergebnis['KENNUNG_AUS_URL'].add(fund)
    return ergebnis


def _mengen_aus_routes() -> dict[str, set]:
    """Duenner Datei-Wrapper: liest routes/*.py und ruft _mengen_aus_quelltext je Datei."""
    gesamt: dict[str, set] = {name: set() for name in MENGEN_NAMEN}
    ordner = REPO_ROOT / SWEEP_ORDNER
    for pfad in sorted(ordner.glob('*.py')):
        rel = f'{SWEEP_ORDNER}/{pfad.name}'
        try:
            quelltext = pfad.read_text(encoding='utf-8')
        except OSError:  # pragma: no cover - defensiv
            continue
        for name, menge in _mengen_aus_quelltext(quelltext, rel).items():
            gesamt[name] |= menge
    return gesamt


# ── Die Anerkennung eines Besitz-Helfers — ABGELEITET, nicht behauptet ───────────────────────

def _anerkannte_aus_quelltext(quelltext: str, kandidaten) -> set:
    """Teil (a) Existenz als FunctionDef + Teil (b) eigene Server-Identitaet im Rumpf.

    ⚠ Ohne Teil (b) waere jeder Helfer-Aufruf ein Freibrief und der Regel-Umbau kippte in eine
    Allowlist um. Ein Helfer, der nichts prueft, faellt hier durch.
    """
    anerkannt = set()
    try:
        baum = ast.parse(quelltext)
    except SyntaxError:  # pragma: no cover - defensiv
        return anerkannt
    for knoten in ast.walk(baum):
        if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if knoten.name not in kandidaten:
            continue
        eigene = list(_own_nodes(knoten))
        if _hat_server_identitaet(eigene):
            anerkannt.add(knoten.name)
            continue
        # Die drei live_session-Helfer arbeiten auf dem RAM-Zustand: dort ist user_id der
        # Vergleichs-Anker, nicht g.*.
        for n in eigene:
            if isinstance(n, ast.Name) and n.id == LIVE_HELFER_IDENTITAET:
                anerkannt.add(knoten.name)
                break
            if isinstance(n, ast.Attribute) and n.attr == LIVE_HELFER_IDENTITAET:
                anerkannt.add(knoten.name)
                break
            if isinstance(n, ast.Constant) and n.value == LIVE_HELFER_IDENTITAET:
                anerkannt.add(knoten.name)
                break
    return anerkannt


def _anerkannte_besitz_helfer() -> set:
    """Leitet die Anerkennung je Quelldatei ab. Fehlt der Helfer, ist er NICHT anerkannt."""
    anerkannt = set()
    nach_datei: dict[str, set] = {}
    for name, quelle in BESITZ_HELFER_QUELLEN.items():
        nach_datei.setdefault(quelle, set()).add(name)
    for quelle, kandidaten in nach_datei.items():
        pfad = REPO_ROOT / quelle
        if not pfad.exists():
            continue
        try:
            quelltext = pfad.read_text(encoding='utf-8')
        except OSError:  # pragma: no cover - defensiv
            continue
        anerkannt |= _anerkannte_aus_quelltext(quelltext, kandidaten)
    return anerkannt


def _erfuellt(fund: Fund, menge: str, anerkannt) -> bool:
    """Die Forderung je Menge — ALLE DREI Fassungen sind HELFER-BEWUSST."""
    if fund.gerufene & set(anerkannt):
        return True
    if menge in ('ZUSTANDS_FUNKTIONEN', 'SID_AUS_ANFRAGE', 'CALLID_AUS_ANFRAGE'):
        return bool(fund.gerufene & set(HELFER))
    if menge == 'PROFILEID_AUS_ANFRAGE':
        return fund.org_id_bindung
    if menge == 'KENNUNG_AUS_URL':
        return fund.server_identitaet
    raise KeyError(menge)  # pragma: no cover - defensiv


def _verstoesse(menge: str) -> list:
    anerkannt = _anerkannte_besitz_helfer()
    offen = []
    for fund in sorted(_mengen_aus_routes()[menge], key=lambda f: (f.datei, f.zeile)):
        if fund.schluessel in ALLOWLIST:
            continue
        if not _erfuellt(fund, menge, anerkannt):
            offen.append(fund)
    return offen


def _funktion_existiert(rel: str, name: str) -> bool:
    pfad = REPO_ROOT / rel
    if not pfad.exists():
        return False
    try:
        baum = ast.parse(pfad.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):  # pragma: no cover - defensiv
        return False
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
               for n in ast.walk(baum))


def _dekoratoren_aus_quelltext(quelltext: str, name: str) -> frozenset:
    """Die Dekorator-NAMEN einer Funktion — ABGELEITET aus dem AST, nicht behauptet.

    Deckt `@superadmin_required` (Name) und `@bp.route(...)` (Attribut/Aufruf). Der Sinn ist
    derselbe wie bei der Helfer-Anerkennung: ein Allowlist-Eintrag, der sich auf eine Weiche
    beruft, darf nicht gruen bleiben, wenn die Weiche entfernt wird.
    """
    try:
        baum = ast.parse(quelltext)
    except SyntaxError:  # pragma: no cover - defensiv
        return frozenset()
    for n in ast.walk(baum):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) or n.name != name:
            continue
        namen = set()
        for dek in n.decorator_list:
            ziel = dek.func if isinstance(dek, ast.Call) else dek
            if isinstance(ziel, ast.Name):
                namen.add(ziel.id)
            elif isinstance(ziel, ast.Attribute):
                namen.add(ziel.attr)
        return frozenset(namen)
    return frozenset()


# ── Die Pruefungen ──────────────────────────────────────────────────────────────────────────

def test_mindestens_erwartete_pruefpunkte_gefunden():
    """Markierung: keine — die Ableitung muss VOR wie NACH dem Fix funktionieren.

    Ist sie hier rot, ist der SWEEP kaputt, nicht der Code. Fuenf getrennte Zahlen auf fuenf
    Mengen: eine Sammelzahl liesse eine wachsende Menge den Ausfall einer anderen zudecken.
    Gezaehlt wird VOR dem Allowlist-Abzug, damit ein wachsender Allowlist-Bestand das
    Schrumpfen einer Menge nicht verstecken kann.
    """
    mengen = _mengen_aus_routes()
    zu_klein = []
    for name, soll in SOLL_JE_MENGE.items():
        ist = len(mengen[name])
        if ist < soll:
            gefunden = ', '.join(f.etikett() for f in
                                 sorted(mengen[name], key=lambda f: (f.datei, f.zeile)))
            zu_klein.append(f'{name}: {ist} gefunden, erwartet mindestens {soll}. '
                            f'Gefunden: {gefunden or "(nichts)"}')
    assert not zu_klein, (
        'Die Ableitung liefert zu wenig Pruefpunkte. Das ist KEIN Erfolg: ohne Ableitung ist '
        'dieser Waechter blind statt rot und sieht dabei gruen aus. '
        'Die Zahl NIE stillschweigend senken — Ursache klaeren und mit Begruendung nachziehen.\n'
        + '\n'.join(zu_klein)
    )


@pytest.mark.rot_vor_fix
def test_zustands_aufloesungen_gehen_durch_den_besitz_helfer():
    """Markierung: rot_vor_fix — reisst B-02/B-03/N-02/N-03 auf.

    Vier Funktionen loesen _session_state ohne Besitz-Helfer auf.
    """
    offen = _verstoesse('ZUSTANDS_FUNKTIONEN')
    assert not offen, (
        'Diese Funktionen loesen _session_state auf, ohne die Eigentuemerschaft ueber einen '
        'Besitz-Helfer zu pruefen. Ein Ghost-SID-Guard prueft LEBENDIGKEIT, nicht '
        'Eigentuemerschaft — das ist die Fehlerklasse dieser Phase.\n  '
        + '\n  '.join(f.etikett() for f in offen)
    )


@pytest.mark.rot_vor_fix
def test_sid_aus_der_anfrage_wird_besitzgeprueft():
    """Markierung: rot_vor_fix — reisst N-01 auf.

    api_precall_research reicht eine fremde sid an recherche_firma weiter; in routes/ steht
    dort gar keine _session_state-Zeile. Ohne diese zweite Menge waere N-01 unsichtbar.
    """
    offen = _verstoesse('SID_AUS_ANFRAGE')
    assert not offen, (
        'Diese Funktionen nehmen eine sid aus der Anfrage entgegen, ohne sie besitzzupruefen. '
        'Ein Ghost-SID-Guard prueft LEBENDIGKEIT, nicht Eigentuemerschaft.\n  '
        + '\n  '.join(f.etikett() for f in offen)
    )


@pytest.mark.rot_vor_fix
def test_call_id_aus_der_anfrage_wird_besitzgeprueft():
    """Markierung: rot_vor_fix — reisst B-01 und R-7 auf.

    save_meeting steht hier, seit sein Allowlist-Eintrag weggefallen ist (R-7 wird gebaut).
    """
    offen = _verstoesse('CALLID_AUS_ANFRAGE')
    assert not offen, (
        'Diese Funktionen loesen eine call_id aus der Anfrage auf, ohne den Besitz-Helfer zu '
        'rufen. Eine fremde call_id darf weder eine Zeile aendern noch als Fremdreferenz in '
        'eine eigene Zeile wandern.\n  '
        + '\n  '.join(f.etikett() for f in offen)
    )


@pytest.mark.rot_vor_fix
def test_profile_id_aus_der_anfrage_wird_besitzgeprueft():
    """Markierung: rot_vor_fix — reisst R-8 auf.

    routes/coach.py::methodik_uebertragen laedt ein Profil ueber die Anfrage-Kennung, ohne
    org_id gegen eine Server-Identitaet zu binden. Diese Pruefung ist AM BESTAND ROT — das ist
    der eigene ROT-Beleg von Menge 4, ohne kuenstliches Leck.
    """
    offen = _verstoesse('PROFILEID_AUS_ANFRAGE')
    assert not offen, (
        'Eine profile_id aus der Anfrage loest eine DB-Zeile auf, ohne dass org_id im Rumpf an '
        'eine Server-Identitaet gebunden wird — die blosse Erwaehnung von org_id genuegt nicht, '
        'sie kann an einem Anfrage-Wert haengen.\n  '
        + '\n  '.join(f.etikett() for f in offen)
    )


def test_kennung_aus_url_wird_besitzgeprueft():
    """Markierung: keine — am Bestand gruen (alle acht Funktionen tragen eine Server-Identitaet
    oder laufen ueber _require_own_profile).

    Sie prueft trotzdem etwas: sie ist das Netz fuer NEUEN Code, der eine URL-Kennung ganz ohne
    Pruefung aufloest. Ihr ROT-Beleg ist der Selbsttest, nicht ein kaputter Produktionspfad.
    """
    offen = _verstoesse('KENNUNG_AUS_URL')
    assert not offen, (
        'Die Kennung kommt hier als URL-Routen-Parameter an, nicht ueber .get() — genau deshalb '
        'war sie fuer die Mengen 2-4 unsichtbar.\n  '
        + '\n  '.join(f.etikett() for f in offen)
    )


def test_regeln_fangen_ein_kuenstliches_leck():
    """Markierung: keine — er prueft die REGEL, nicht den Produktionscode.

    Er muss in BEIDEN Laeufen gruen sein. Ist er rot, beissen die Regeln nicht und alle ihre
    gruenen Ergebnisse sind wertlos (Punkt 31: ein Waechter, der nie rot war, ist wertlos).
    Er ruft _mengen_aus_quelltext DIREKT — dieselbe Funktion, die den Produktivcode prueft;
    eine im Test duplizierte Regel bewiese nichts (R2-5).
    """
    LECK = '''
@app.route('/api/profile/<int:profile_id>/leak', methods=['POST'])
@login_required
def leck_url(profile_id):
    row = db.query(Profile).filter_by(id=profile_id).first()
    return jsonify(row.daten)

@app.route('/api/leak2', methods=['POST'])
@login_required
def leck_body():
    pid = request.get_json().get('profile_id')
    row = db.query(Profile).filter_by(id=pid).first()
    return jsonify(row.daten)
'''
    anerkannt = _anerkannte_besitz_helfer()
    mengen = _mengen_aus_quelltext(LECK, 'routes/kuenstlich.py')

    url_namen = {f.funktion for f in mengen['KENNUNG_AUS_URL']}
    body_namen = {f.funktion for f in mengen['PROFILEID_AUS_ANFRAGE']}
    assert 'leck_url' in url_namen, (
        'Menge 5 sieht die URL-Kennung nicht — die Ableitung ist kaputt, nicht der Code. '
        f'Gefunden: {sorted(url_namen)}'
    )
    assert 'leck_body' in body_namen, (
        'Menge 4 sieht die profile_id aus dem Anfrage-Koerper nicht. '
        f'Gefunden: {sorted(body_namen)}'
    )
    for fund in mengen['KENNUNG_AUS_URL']:
        assert not _erfuellt(fund, 'KENNUNG_AUS_URL', anerkannt), (
            f'{fund.etikett()} hat KEINEN Besitz-Vergleich, wird aber als geprueft durchgewinkt '
            '— die Regel beisst nicht.'
        )
    for fund in mengen['PROFILEID_AUS_ANFRAGE']:
        assert not _erfuellt(fund, 'PROFILEID_AUS_ANFRAGE', anerkannt), (
            f'{fund.etikett()} bindet org_id an nichts, wird aber durchgewinkt.'
        )

    # Gegenprobe 1: derselbe Code MIT org_id-Bindung im Filter wird NICHT geflaggt — sonst
    # waere die Regel ein Dauer-Alarm und wuerde weggeklickt.
    SAUBER = '''
@app.route('/api/profile/<int:profile_id>/ok', methods=['POST'])
@login_required
def ok_url(profile_id):
    row = db.query(Profile).filter_by(id=profile_id, org_id=g.org.id).first()
    return jsonify(row.daten)
'''
    g1 = _mengen_aus_quelltext(SAUBER, 'routes/kuenstlich.py')
    for fund in g1['KENNUNG_AUS_URL'] | g1['PROFILEID_AUS_ANFRAGE']:
        assert _erfuellt(fund, 'KENNUNG_AUS_URL', anerkannt), (
            'Gegenprobe 1 gescheitert: korrekt gebundener Code wird faelschlich geflaggt.'
        )

    # Gegenprobe 2 — die REGRESSIONS-SPERRE gegen F-B1: ein Rumpf, der NUR
    # _require_own_profile(profile_id) ruft und KEIN g. enthaelt, darf NICHT geflaggt werden.
    # Ohne sie faellt der Waechter in den Falschtreffer zurueck, der drei korrekt geschuetzte
    # Funktionen (api_faqs_list/-create, api_tabu_update) rot gemacht haette.
    HELFER_GESCHUETZT = '''
@app.route('/api/profile/<int:profile_id>/faqs', methods=['GET'])
@login_required
def helfer_url(profile_id):
    p = _require_own_profile(profile_id)
    if not p:
        return jsonify({'error': 'nicht gefunden'}), 404
    return jsonify(p.daten)
'''
    g2 = _mengen_aus_quelltext(HELFER_GESCHUETZT, 'routes/kuenstlich.py')
    assert g2['KENNUNG_AUS_URL'], 'Gegenprobe 2 leer — die Ableitung hat gar nichts gesehen.'
    for fund in g2['KENNUNG_AUS_URL']:
        assert not fund.server_identitaet, (
            'Gegenprobe 2 ist entwertet: der Rumpf enthaelt doch ein g.* und beweist die '
            'Helfer-Bewusstheit deshalb nicht.'
        )
        assert _erfuellt(fund, 'KENNUNG_AUS_URL', anerkannt), (
            'Gegenprobe 2 gescheitert (F-B1): helfer-geschuetzter Code wird faelschlich '
            'geflaggt. Die Regel ist nicht helfer-bewusst.'
        )

    # Gegenprobe 3: ein NICHT anerkannter Helfer (er traegt selbst keine Server-Identitaet)
    # ist KEIN Freibrief — sein Aufrufer bleibt rot.
    WERTLOSER_HELFER = '''
def _prueft_nichts(profile_id):
    return True
'''
    nicht_anerkannt = _anerkannte_aus_quelltext(WERTLOSER_HELFER, {'_prueft_nichts'})
    assert not nicht_anerkannt, (
        'Gegenprobe 3 gescheitert: ein Helfer ohne Server-Identitaet in seinem eigenen Rumpf '
        'wurde anerkannt — damit waere jeder Helfer-Aufruf ein Freibrief.'
    )
    SCHEIN_GESCHUETZT = '''
@app.route('/api/profile/<int:profile_id>/schein', methods=['GET'])
@login_required
def schein_url(profile_id):
    p = _prueft_nichts(profile_id)
    return jsonify(p)
'''
    g3 = _mengen_aus_quelltext(SCHEIN_GESCHUETZT, 'routes/kuenstlich.py')
    assert g3['KENNUNG_AUS_URL'], 'Gegenprobe 3 leer — die Ableitung hat gar nichts gesehen.'
    for fund in g3['KENNUNG_AUS_URL']:
        assert not _erfuellt(fund, 'KENNUNG_AUS_URL', anerkannt | nicht_anerkannt), (
            'Gegenprobe 3 gescheitert: ein wertloser Helfer wirkt als Freibrief.'
        )


@pytest.mark.rot_vor_fix
def test_helfer_existieren_und_pruefen_user_id():
    """Markierung: rot_vor_fix — die drei live_session-Helfer gibt es vor Plan 02 Task 2 nicht.

    Der Waechter darf nicht gegen Namen pruefen, die es nicht gibt (sonst waere er nach einer
    Umbenennung still gruen, weil die Mengen leer laufen). Das ist Teil (b) der Anerkennung und
    hier das tragende Stueck: faellt er weg, wird jeder Helfer-Aufruf zum Freibrief.
    """
    fehlend = []
    ohne_pruefung = []
    anerkannt = _anerkannte_besitz_helfer()
    for name, quelle in sorted(BESITZ_HELFER_QUELLEN.items()):
        if not _funktion_existiert(quelle, name):
            fehlend.append(f'{quelle}::{name}')
        elif name not in anerkannt:
            ohne_pruefung.append(f'{quelle}::{name}')
    assert not fehlend, (
        'Diese Besitz-Helfer gibt es nicht als FunctionDef in ihrer Quelldatei. Die drei '
        'live_session-Helfer baut Plan 02 Task 2; fehlt ein anderer, ist er umbenannt oder '
        'geloescht worden:\n  ' + '\n  '.join(fehlend)
    )
    assert not ohne_pruefung, (
        'Diese Helfer existieren, tragen in IHREM eigenen Rumpf aber keine Server-Identitaet '
        'bzw. keinen user_id-Vergleich. Ein Helfer, der nichts prueft, darf seine Aufrufer '
        'nicht gruen machen:\n  ' + '\n  '.join(ohne_pruefung)
    )


def test_allowlist_ist_begruendet_und_lebt():
    """Markierung: keine — Allowlist-Hygiene ist von Fix und Nicht-Fix unabhaengig.

    Rot heisst hier: ein Eintrag zeigt ins Leere oder ist eine stille Ausnahme.
    """
    unbegruendet = [k for k, grund in ALLOWLIST.items() if len((grund or '').strip()) < 20]
    assert not unbegruendet, (
        'Allowlist-Eintraege ohne belastbare Begruendung — genau so wird die Allowlist die '
        'Hintertuer, die den Waechter aushoehlt: ' + ', '.join(unbegruendet)
    )

    tot = []
    for schluessel in ALLOWLIST:
        datei, _, funktion = schluessel.partition('::')
        if not _funktion_existiert(datei, funktion):
            tot.append(schluessel)
    assert not tot, (
        'Diese Allowlist-Eintraege zeigen ins Leere (Funktion umbenannt oder geloescht). Das ist '
        'KEIN Erfolg: der Eintrag weitet den Sweep still auf und sieht dabei gruen aus. '
        'Nachziehen oder streichen:\n  ' + '\n  '.join(tot)
    )

    ohne_praefix = [
        k for k, grund in ALLOWLIST.items()
        if not (grund.startswith(PRAEFIX_FALSCH_TREFFER) or grund.startswith(PRAEFIX_GEMELDET))
    ]
    assert not ohne_praefix, (
        'Ein Eintrag ohne Praefix ist eine stille Ausnahme — entweder ist es ein Falsch-Treffer '
        '(dann belegen) oder ein Loch (dann als R-Nummer melden).\n  '
        + '\n  '.join(ohne_praefix)
    )

    ohne_fundstelle = [
        k for k, grund in ALLOWLIST.items()
        if grund.startswith(PRAEFIX_GEMELDET)
        and not (re.search(r'R-\d', grund) and 'FUNDE.md' in grund)
    ]
    assert not ohne_fundstelle, (
        'Ein gemeldetes, nicht gefixtes Loch braucht seine R-Nummer UND den Verweis auf '
        'FUNDE.md — sonst ist es nirgends nachlesbar:\n  ' + '\n  '.join(ohne_fundstelle)
    )


def test_founder_ausnahmen_tragen_ihre_founder_weiche_noch():
    """Markierung: keine — Allowlist-Hygiene, unabhaengig von Fix und Nicht-Fix.

    METRIK-1 (2026-08-15). Ein Allowlist-Eintrag, der sich auf die Founder-Weiche beruft, ist
    nur so viel wert wie die Weiche selbst. Faellt @superadmin_required irgendwann weg — beim
    Umbau, beim Kopieren der Route, aus Versehen — bliebe der Eintrag stehen und wuerde eine
    dann WIRKLICH ungeschuetzte URL-Kennung still durchwinken. Genau die Hintertuer, vor der
    der Modul-Docstring warnt.

    Er prueft ZWEI Dinge, und die Reihenfolge ist Absicht:
      Teil 1 (Gegenprobe): die Ableitung beisst ueberhaupt. Ohne sie waere ein Ausfall von
        _dekoratoren_aus_quelltext blind statt rot — und saehe dabei gruen aus (Punkt 31).
      Teil 2: jeder Founder-Eintrag der ALLOWLIST traegt die Weiche im echten Quelltext.
    """
    # ── Teil 1: Gegenprobe an einer kuenstlichen Route (dieselbe Funktion wie in Teil 2) ────
    OHNE_WEICHE = '''
@admin_dashboard_bp.route('/x/<call_id>')
@login_required
def kuenstliche_route(call_id):
    return call_id
'''
    MIT_WEICHE = OHNE_WEICHE.replace('@login_required',
                                     '@login_required\n@superadmin_required')
    assert FOUNDER_WEICHE not in _dekoratoren_aus_quelltext(OHNE_WEICHE, 'kuenstliche_route'), (
        'Die Dekorator-Ableitung meldet eine Founder-Weiche, wo keine steht — sie beisst nicht '
        'und jedes gruene Ergebnis von Teil 2 waere wertlos.'
    )
    assert FOUNDER_WEICHE in _dekoratoren_aus_quelltext(MIT_WEICHE, 'kuenstliche_route'), (
        'Die Dekorator-Ableitung sieht eine vorhandene Founder-Weiche NICHT — sie ist blind, '
        'und Teil 2 wuerde jede Route faelschlich als ungeschuetzt melden.'
    )

    # ── Teil 2: der Produktivcode ───────────────────────────────────────────────────────────
    fehlend = []
    for schluessel, grund in ALLOWLIST.items():
        if FOUNDER_WEICHE not in grund:
            continue
        datei, _, funktion = schluessel.partition('::')
        pfad = REPO_ROOT / datei
        quelle = pfad.read_text(encoding='utf-8') if pfad.exists() else ''
        if FOUNDER_WEICHE not in _dekoratoren_aus_quelltext(quelle, funktion):
            fehlend.append(schluessel)
    assert not fehlend, (
        'Diese Allowlist-Eintraege berufen sich auf die Founder-Weiche, die Funktion traegt sie '
        'aber nicht mehr. Der Eintrag deckt damit eine URL-Kennung, die jetzt WIRKLICH '
        'ungeschuetzt ist. Weiche wiederherstellen ODER den Eintrag streichen und die '
        'Besitzpruefung bauen:\n  ' + '\n  '.join(fehlend)
    )
