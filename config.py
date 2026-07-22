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
