import os
from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_API_KEY  = os.environ.get('DEEPGRAM_API_KEY', '')
# POLISH-49: DSGVO-Pflicht — EU-Endpoint als Default. Wenn .env kein DEEPGRAM_HOST
# setzt, bleibt NERVE trotzdem auf api.eu.deepgram.com (robustness-first).
DEEPGRAM_HOST     = os.environ.get('DEEPGRAM_HOST', 'api.eu.deepgram.com')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY', '')
SECRET_KEY        = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
CORS_ORIGIN       = os.environ.get('CORS_ORIGIN', '*' if os.environ.get('FLASK_DEBUG') else 'https://getnerve.app')

# Stripe
STRIPE_SECRET_KEY      = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET  = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRICE_IDS = {
    'starter':  os.environ.get('STRIPE_PRICE_ID_STARTER', ''),
    'pro':      os.environ.get('STRIPE_PRICE_ID_PRO', ''),
    'business': os.environ.get('STRIPE_PRICE_ID_BUSINESS', ''),
}
# OAuth (Phase 04.6.1)
GOOGLE_CLIENT_ID        = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET    = os.environ.get('GOOGLE_CLIENT_SECRET', '')
MICROSOFT_CLIENT_ID     = os.environ.get('MICROSOFT_CLIENT_ID', '')
MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET', '')

# PreCall Intelligence (Phase 04.13)
BRAVE_SEARCH_API_KEY = os.environ.get('BRAVE_SEARCH_API_KEY', '')

DATABASE_URL      = os.environ.get('DATABASE_URL', 'sqlite:///database/nerve.db')
MAX_SESSION_HOURS = int(os.environ.get('MAX_SESSION_HOURS', 8))

# Phase 08.23.2.STABIL-1 (b), PRE-EXECUTE-AUDIT K1: enger als MAX_SESSION_HOURS.
# Schliesst das Fenster, in dem der DB-Fallback in api_beenden (routes/app_routes.py)
# einen aelteren, aber noch "offenen" Call faelschlich statt des aktuellen schliesst,
# wenn create_call_for_sid fuer den aktuellen Call fehlschlug. Eigene Konstante,
# NICHT MAX_SESSION_HOURS wiederverwenden (die ist fuer Session-Timeout, nicht Fallback-Frische).
STABIL1_FALLBACK_FRESH_HOURS = int(os.environ.get('STABIL1_FALLBACK_FRESH_HOURS', 2))

# ── Phase 08.23.2.STABIL-1: DB-Pool (zieht mit gunicorn --threads 64 mit) ──
# Budget-Beleg 2026-07-23: PG max_connections=100, 3 reserviert => 97 nutzbar.
# nerve-rt importiert DIESELBE database/db.py (nerve_rt/services/session_manager.py:73-77,
# `from database.db import SessionLocal`, gleiche DATABASE_URL) -> KEIN eigener Pool.
# 20+15 = max 35 aus der Haupt-App; worst case gesamt 35 (App) + 35 (nerve-rt) = 70 von 97
# nutzbaren Verbindungen (Pool fuellt lazy, nerve-rt zieht real wenig) -> weiterhin sicher.
DB_POOL_SIZE     = int(os.environ.get('DB_POOL_SIZE', 20))
DB_MAX_OVERFLOW  = int(os.environ.get('DB_MAX_OVERFLOW', 15))
DB_POOL_TIMEOUT  = int(os.environ.get('DB_POOL_TIMEOUT', 10))

SAMPLE_RATE       = 16000
CHUNK_SIZE        = 1024
ANALYSE_INTERVALL = 4  # Phase 06.3: raised from 2s — analyse_loop is intelligence-only now, fewer calls = less 529 risk + lower cost

# ── Phase 08.5: Klassifikator-Confidence-Schwelle (D-03) ─────────────────────
# TAXO1-Welle 4 (K4): Default 0.80 -> 0.55. RESEARCH §3: 0.80 unterdrueckte 13
# legitime frage-Klassifikationen bei conf 0.45-0.75 (Haiku clustert ~0.65).
# Unter diesem Wert: kein lauter Antwort-Cue, aber das intent_event wird mit
# abstained=True festgehalten (Funnel sichtbar, K4 nicht ueberbaut).
# Env-Var erlaubt Justierung ohne Code-Deploy (<30s reversibel, Punkt-12-Marge).
# Im Test-Anruf empirisch nachkalibrieren.
CLASSIFIER_CONFIDENCE_THRESHOLD = float(
    os.environ.get('CLASSIFIER_CONFIDENCE_THRESHOLD', '0.55')
)


# ── Phase 08.23.2.H1 (WEG 1): Merge-Schalter analyse_loop Call 1 + Call 3 ─────
# '1' (Default): analyse_loop fasst Einwand-Analyse (Call 1, analysiere_mit_claude)
# und QA-Klassifikation (Call 3, classify_utterance) zu EINEM Haiku-Call zusammen
# (analysiere_und_klassifiziere). '0': Rollback auf den ALTEN Zwei-Call-Pfad —
# analysiere_mit_claude + classify_utterance bleiben dafuer als lebender Fallback intakt.
#
# ROLLBACK-SEMANTIK (K3, ehrlich): os.getenv wird zur IMPORT-Zeit gelesen (Muster wie
# CACHE_ANTWORT oben). Ein Rollback wirkt NICHT hot/sofort-ohne-Restart. Korrekt ist:
# MERGE_ANALYSE_QA=0 in /etc/nerve/.env eintragen UND den Dienst neu starten
# (systemctl restart nerve). KEIN Deploy noetig — aber ein Restart ist Pflicht.
# (ACHTUNG wie bei CACHE_ANTWORT: /opt/nerve/app/.env existiert auf Prod NICHT —
# deploy.sh schliesst ./.env vom tar-Deploy aus und prueft /etc/nerve/.env.)
MERGE_ANALYSE_QA = os.getenv("MERGE_ANALYSE_QA", "1")


def should_abstain(confidence, threshold=None) -> bool:
    """TAXO1-Welle 4 (K4, Cross-AI Finding #4): reine Funnel-Entscheidung — KEIN
    I/O, KEIN LLM, KEINE DB. low-conf (oder fehlende confidence) -> abstain
    (Aufrufer schreibt das Event mit abstained=True statt es zu droppen).
    Unit-testbar (tests/test_k4_threshold_funnel.py)."""
    t = CLASSIFIER_CONFIDENCE_THRESHOLD if threshold is None else threshold
    return confidence is None or confidence < t


# ── TAXO1-Welle 4: Moment-Fenster (I-4-FOLD + Gemini-R2) ─────────────────────
# NICHT-refreshender Max-Dauer-Deckel ab Fenster-OEFFNUNG (harte Notbremse gegen
# Endlos-Momente, falls das "Berater-antwortet"-Signal mal nicht feuert). KEIN
# refreshender Idle-Timer (der war Teil der Ueber-Verklumpung).
MOMENT_WINDOW_MAX_S = float(os.environ.get('MOMENT_WINDOW_MAX_S', '90.0'))

# Cold-Call-Primaer-Schliesser (FUND A): eine SUBSTANZIELLE Berater-Wendung
# (>= N Woerter, NICHT als Einwand-Echo klassifiziert) = "Berater hat geantwortet"
# -> Moment-Fenster schliessen. Kein Fueller/"aehm ja".
SUBSTANTIAL_TURN_MIN_WORDS = int(os.environ.get('SUBSTANTIAL_TURN_MIN_WORDS', '6'))

# ── Phase 08.13: MODEL-Konstanten (ENV-overridable, per CONTEXT.md D-01) ──────
# Sonnet 4.5 fuer User-sichtbare Outputs — Alias ohne Date-Suffix (robuster gegen Date-Drift,
# siehe Hotfix nach 08.20: 20251022-Suffix existierte nicht → 404 in Production)
MODEL_EWB               = os.getenv("MODEL_EWB",               "claude-sonnet-4-5")
MODEL_QA                = os.getenv("MODEL_QA",                "claude-sonnet-4-5")
MODEL_POSTCALL_INSIGHTS = os.getenv("MODEL_POSTCALL_INSIGHTS",  "claude-sonnet-4-5")
MODEL_POSTCALL_ANALYSIS = os.getenv("MODEL_POSTCALL_ANALYSIS",  "claude-sonnet-4-5")
MODEL_WEEKLY_SUMMARY    = os.getenv("MODEL_WEEKLY_SUMMARY",     "claude-sonnet-4-5")
MODEL_PRECALL           = os.getenv("MODEL_PRECALL",            "claude-sonnet-4-5")
MODEL_CRM               = os.getenv("MODEL_CRM",               "claude-sonnet-4-5")
MODEL_TRAINING_HELP     = os.getenv("MODEL_TRAINING_HELP",      "claude-sonnet-4-5")
MODEL_TRAINING_SCORING  = os.getenv("MODEL_TRAINING_SCORING",   "claude-sonnet-4-5")
# Haiku 4.5 fuer Latenz/Cost-kritisch — UNVERAENDERLICH per CONTEXT.md
MODEL_ANALYSE           = os.getenv("MODEL_ANALYSE",           "claude-haiku-4-5-20251001")
MODEL_TRAINING_DIALOG   = os.getenv("MODEL_TRAINING_DIALOG",   "claude-haiku-4-5-20251001")
MODEL_PERSONALITY_GEN   = os.getenv("MODEL_PERSONALITY_GEN",   "claude-haiku-4-5-20251001")
# Weitere Haiku-Stellen aus RESEARCH.md (grep-verifiziert)
MODEL_PHASE_CLASSIFY    = os.getenv("MODEL_PHASE_CLASSIFY",    "claude-haiku-4-5-20251001")
MODEL_COLDCALL_INFER    = os.getenv("MODEL_COLDCALL_INFER",    "claude-haiku-4-5-20251001")

# ── Phase 08.23.2.STABIL-1: Zeitlimit fuer LLM-Aufrufe im HTTP-Request-Thread ──
# NUR fuer Aufrufe, die aus einer Flask-Route erreichbar sind. Daemon-Threads
# (analyse_loop/coaching_loop/slow_lane) und messages.stream bleiben ohne Limit —
# ein client-weites timeout wuerde die Live-Streams kappen.
# Arithmetik: timeout x (1+retries) muss unter dem nginx-60s-Default bleiben.
# max_retries-Default ist 0 (nicht 1): der SDK-Retry-Mechanismus ehrt einen
# Retry-After-Header bis 60s — mit max_retries=1 koennte ein schnelles 429/529
# mit Retry-After:60 die STANDARD-Stufe auf ~1+60+20 ~= 81s ziehen (> nginx-60s),
# trotz 20s-Timeout. Mit 0 ist STANDARD hart 20s, immun gegen Retry-After.
# ENV-Override bleibt, um ohne Deploy auf 1 zu stellen (Robustheit ist STABIL-2-Kandidat).
HTTP_LLM_TIMEOUT_S      = float(os.getenv("HTTP_LLM_TIMEOUT_S", "20"))
HTTP_LLM_TIMEOUT_LONG_S = float(os.getenv("HTTP_LLM_TIMEOUT_LONG_S", "45"))
HTTP_LLM_MAX_RETRIES    = int(os.getenv("HTTP_LLM_MAX_RETRIES", "0"))

# ── Phase 08.23.2.SOFORT-2 (D-03/D-04) — Zeitlimit auf den LIVE-LLM-Aufrufen ────────────────
# FUENF benannte Festlegungen. Sie stehen HIER und nicht in einer Bedingung, damit sie
# nachpruefbar und aenderbar bleiben (D-04, Andre-Pflicht). Vier sind per ENV ueberschreibbar.
# ⛔ KORRIGIERT 2026-08-05 (F-N7.3): hier stand "ein Wechsel braucht keinen Deploy". FALSCH -
#    config.py liest die Werte beim PROZESS-START. Ohne Neustart des Dienstes aendert sich
#    nichts. Wer die Variable setzt und dann misst, misst den ALTEN Wert.
#
# EIN Mechanismus, ZWEI Zahlen (Punkt 27 — der einfachste tragfaehige Weg):
# `timeout=` wird vom Anthropic-SDK EINS ZU EINS an httpx durchgereicht, und `read` gilt dort
# PRO DATENBLOCK. Fuer eine blockierende Antwort (ein Koerper) wirkt das faktisch wie ein
# Gesamt-Limit; fuer einen Stream (ein Datenblock je Token) wirkt derselbe Parameter als
# TTFT- plus Stillstands-Limit und kappt die Gesamtdauer NICHT. Genau das will D-03.
# ⛔ Deshalb wird KEINE Uhr im Token-Loop gebaut. Es braucht sie nicht.

# F-1 — blockierende Aufrufe (Analyse, Coaching, Phasen-Erkennung, Cold-Call-Ableitung, QA).
# Langsamster gemessener Ø: coaching_haiku 2714 ms (MESSGERAETE-1, 2026-08-04, Headset).
# 12 s = mehr als das Vierfache Luft — es gibt KEINE p95-Messung, also grosszuegig statt knapp.
# Zum Vergleich: die SDK-Vorgabe waere 600 s.
LIVE_LLM_TIMEOUT_S = float(os.getenv("LIVE_LLM_TIMEOUT_S", "12"))

# F-2 — Stream-Pfade (pip_autovar, pip_variante). Gemessener Ø TTFT: 1035 ms.
# ⚠ Bewusst NICHT dicht an 1035 ms: `read` kappt auch eine Pause MITTEN in der Antwort, nicht
# nur bis zum ersten Token. Eine Messung der Token-Abstaende gibt es nicht — nur ttft_ms und
# latency_ms. 8 s ist so gewaehlt, dass eine legitime Pause sie praktisch nie erreicht; wer sie
# erreicht, haengt. Die GESAMTDAUER wird dadurch NICHT begrenzt (lange Antworten sind legitim).
LIVE_LLM_STREAM_TIMEOUT_S = float(os.getenv("LIVE_LLM_STREAM_TIMEOUT_S", "8"))

# F-3 — ab wie vielen Zeitueberschreitungen IN FOLGE der Berater es sieht (D-04 Stufe 2).
# ⚠ "Runde" ist NICHT "Schleifentakt": beide Loops steigen VOR dem LLM-Aufruf aus, wenn nichts
# zu tun ist. Ein Zaehler auf Takte wuerde in einer Gespraechspause ausloesen — genau der
# Alarm, den D-04 vermeiden will. Gezaehlt werden nur LLM-Versuche, die stattfanden UND mit
# einer Zeitueberschreitung endeten. Ein Erfolg setzt auf 0 zurueck ("in Folge").
LIVE_LLM_TIMEOUT_HINWEIS_AB = int(os.getenv("LIVE_LLM_TIMEOUT_HINWEIS_AB", "3"))

# F-4 — der Wortlaut, den der Berater sieht. Ruhig und knapp, kein Alarm (D-04 woertlich).
# User-facing => ECHTE Umlaute. Alle Bezeichner drumherum bleiben ASCII.
# Er beschreibt einen ZUSTAND, keinen Fehler, und sagt ausdruecklich, dass das Gespraech
# weiterlaeuft — denn Stille sieht im Live-Gespraech aus wie "alles in Ordnung, keine
# Einwaende", und das ist die gefaehrlichste Rueckmeldung, die wir geben koennen.
# KEIN ENV-Override: ein Anzeigetext gehoert versioniert, nicht in eine Umgebungsvariable.
LIVE_LLM_TIMEOUT_HINWEIS_TEXT = "Die Live-Erkennung antwortet gerade nicht."
LIVE_LLM_TIMEOUT_HINWEIS_TIP = (
    "Mehrere Anfragen ohne Antwort — die Analyse pausiert, das Gespräch läuft weiter."
)

# F-6 — das VERBINDUNGS-Zeitlimit. NEU 2026-08-05 (Cross-AI-Fund F-N7.1).
# ⚠ Heisst F-6, NICHT F-5: F-5 ist oben schon vergeben (die zwei Buchungs-/Retry-
#   Entscheidungen, dort als F-5a/F-5b referenziert). Zwei Dinge unter einer Nummer waere
#   dieselbe Mehrdeutigkeit, gegen die diese Phase antritt.
# ⚠ Es stand vorher als Literal `connect=5.0` an NEUN Aufruf-Stellen ohne Zentrale - genau die
#   "eine Zahl an N Orten"-Falle, gegen die die Zahlen-Tafel gebaut wurde, nur in Welle 2.
#   Der Wert selbst bleibt 5.0 (unveraendert, Reparatur-Modus) - er bekommt nur EINEN Ort.
#
# ⚠ WORST CASE BLOCKIEREND = LLM_CONNECT_TIMEOUT_S + LIVE_LLM_TIMEOUT_S = 5 + 12 = 17 SEKUNDEN.
#   Diese Zahl stand bis zum Replan NIRGENDS im Plan-Satz - obwohl D-06 gegen sie misst.
#   httpx zaehlt `connect` und `read` NACHEINANDER, nicht als Gesamtbudget: erst bis zu 5 s
#   Verbindungsaufbau, DANN bis zu 12 s auf den Antwort-Koerper.
#   Fuer die Stream-Pfade entsprechend: 5 + 8 = 13 s bis zum ersten Token.
#   Wer das Gesamt-Budget senken will, senkt BEIDE Zahlen - nicht nur die auffaellige.
LLM_CONNECT_TIMEOUT_S = float(os.getenv("LLM_CONNECT_TIMEOUT_S", "5"))

# D-07 (LOCKED 2026-04-29): DACH default = Sonnet for EWB streaming (grammar quality).
# Rollback path (no deploy needed): set ENV MODEL_PIP_AUTOVAR=claude-haiku-4-5-20251001
# MODEL_ANALYSE stays Haiku — CLAUDE.md absolute constraint: never Sonnet in live analyse_loop.
MODEL_PIP_AUTOVAR       = os.getenv("MODEL_PIP_AUTOVAR",       "claude-sonnet-4-5")
MODEL_PIP_VARIANTE      = os.getenv("MODEL_PIP_VARIANTE",      "claude-sonnet-4-5")
MODEL_COACHING          = os.getenv("MODEL_COACHING",          "claude-haiku-4-5-20251001")
MODEL_VALIDATE_USER_TEXT= os.getenv("MODEL_VALIDATE_USER_TEXT","claude-haiku-4-5-20251001")
MODEL_TRAINING_PREVIEW  = os.getenv("MODEL_TRAINING_PREVIEW",  "claude-haiku-4-5-20251001")

# ── TEMPO-1: EIN Cache-Schalter fuer den gemeinsamen Antwort-System-Prompt ────
# Abgeloest: CACHE_EWB / CACHE_QA (hatten null Konsumenten) und CACHE_ANALYSE
# (steuerte einen Zweig, der nie greifen konnte — SYSTEM_PROMPT_BASE ~6.400 Zeichen
# gegen 4.096 TOKENS Mindest-Prefix bei Haiku 4.5).
#
# Warum EIN Schalter und nicht drei: alle drei Antwort-Pfade (Auto/EWB, Knopf, QA)
# ziehen seit TAXO3-P1-02 DENSELBEN Text aus prompt_pipeline.answer_system_content()
# und laufen auf DEMSELBEN Modell (MODEL_EWB/MODEL_QA/MODEL_PIP_AUTOVAR/
# MODEL_PIP_VARIANTE = claude-sonnet-4-5, siehe oben). Gleiches Modell + gleicher
# Prefix = EIN Cache-Eintrag. Getrennte Schalter wuerden vorgaukeln, man koenne die
# Pfade einzeln steuern — schaltet man einen aus, haelt der andere den Speicher
# trotzdem warm.
#
# Wirkt an genau EINER Stelle: services/prompt_pipeline.py, answer_system_content()
# (cache_control auf dem _layer='stable'-Block). Rollback ohne Deploy:
# CACHE_ANTWORT=false in /etc/nerve/.env eintragen und den Dienst neu starten
# (systemctl restart nerve). ACHTUNG: /opt/nerve/app/.env existiert auf Prod NICHT
# (deploy.sh:54 schliesst ./.env vom tar-Deploy aus, :42-45 prueft /etc/nerve/.env).
# Der ANALYSE-Pfad (claude_service.analysiere_mit_claude) ist bewusst uncached und
# wird von diesem Schalter NICHT beruehrt.
CACHE_ANTWORT = os.getenv("CACHE_ANTWORT", "true").lower() == "true"

MERGE_WINDOW_S    = 0.3
SPEAKER_DEBOUNCE_S = 3.0

PLANS = {
    'starter':  {'name': 'Starter',  'preis': 49, 'max_users': 1,
                 'minuten_limit': 1000, 'training_voice_limit': 50},
    'pro':      {'name': 'Pro',      'preis': 59, 'max_users': 1,
                 'minuten_limit': 1000, 'training_voice_limit': 50},
    'business': {'name': 'Business', 'preis': 69, 'max_users': 1,
                 'minuten_limit': 1000, 'training_voice_limit': 50},
}

KATEGORIE_LABEL = {
    'frage':      'Frage fehlt',
    'signal':     'Kaufsignal',
    'redeanteil': 'Redeanteil',
    'uebergang':  'Übergang',
    'lob':        'Lob',
}

# ── Phase 08.20.3: Cap für personalisierte Skripte ────────────────────────
PERSONALIZED_SCRIPTS_CAP = int(os.environ.get('PERSONALIZED_SCRIPTS_CAP', 20))

# ── Phase 08.23.2.TAXO2 Plan 04: Call-Ende-Merge — Audio-Gate (D-09) + Retry (F-07) ──
# Post-launch tunbar ohne Code-Deploy (Punkt 12, <30s reversibel per ENV).
# AUDIO_HEALTH_GATE_THRESHOLD: calls.audio_health_score liegt auf der 0.0-1.0-Skala
#   (NICHT 0-100!). Unter dieser Schwelle ODER NULL -> Call not_gradable (D-09): die Note
#   wuerde auf halluziniertem STT-Muell aufsetzen (False-Confidence-Schutz, T-TAXO2-04-01).
AUDIO_HEALTH_GATE_THRESHOLD = float(os.getenv('AUDIO_HEALTH_GATE_THRESHOLD', '0.5'))
# MIN_HIGH_CONFIDENCE_EVENTS: D-09 "zu wenig hoch-konfidente Events" — weniger als N Events
#   ueber der Tor-1-Konfidenzschwelle -> not_gradable. Die Zaehlung passiert SELBST aus der
#   geladenen intent_event-Liste (confidence >= Tor-1-Gate), NICHT aus einem compute_rubric-
#   Rueckgabefeld (FOLD 26.06.: n_high_confidence_events existiert im Engine-Dict NICHT).
MIN_HIGH_CONFIDENCE_EVENTS = int(os.getenv('MIN_HIGH_CONFIDENCE_EVENTS', '3'))
# SCORE_MAX_RETRIES: Merge-Job-Retry-Cap. Scheitert der rubric_score-Write
#   (RLS/permission-denied/IntegrityError/compute_rubric-Fehler) -> gedeckelter Re-Queue
#   (attempts+1) bis zu diesem Cap, danach Dead-Letter (laut loggen, Job aus der Queue).
#   KEIN Silent-Drop, KEIN Endlos-Block (T-TAXO2-04-13). KEIN SCORE_SWEEP_AFTER_S (H-2 gestrichen).
SCORE_MAX_RETRIES = int(os.getenv('SCORE_MAX_RETRIES', '3'))
