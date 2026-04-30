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
# Default 0.80. Unter diesem Wert: keine Antwort-Generation, Soft-Hint statt Antwort.
# Env-Var erlaubt Justierung ohne Code-Deploy (Admin-Panel-UI post-Launch).
CLASSIFIER_CONFIDENCE_THRESHOLD = float(
    os.environ.get('CLASSIFIER_CONFIDENCE_THRESHOLD', '0.80')
)

# ── Phase 08.13: MODEL-Konstanten (ENV-overridable, per CONTEXT.md D-01) ──────
# Sonnet 4.5 fuer User-sichtbare Outputs (20251022)
MODEL_EWB               = os.getenv("MODEL_EWB",               "claude-sonnet-4-5-20251022")
MODEL_QA                = os.getenv("MODEL_QA",                "claude-sonnet-4-5-20251022")
MODEL_POSTCALL_INSIGHTS = os.getenv("MODEL_POSTCALL_INSIGHTS",  "claude-sonnet-4-5-20251022")
MODEL_POSTCALL_ANALYSIS = os.getenv("MODEL_POSTCALL_ANALYSIS",  "claude-sonnet-4-5-20251022")
MODEL_WEEKLY_SUMMARY    = os.getenv("MODEL_WEEKLY_SUMMARY",     "claude-sonnet-4-5-20251022")
MODEL_PRECALL           = os.getenv("MODEL_PRECALL",            "claude-sonnet-4-5-20251022")
MODEL_CRM               = os.getenv("MODEL_CRM",               "claude-sonnet-4-5-20251022")
MODEL_TRAINING_HELP     = os.getenv("MODEL_TRAINING_HELP",      "claude-sonnet-4-5-20251022")
MODEL_TRAINING_SCORING  = os.getenv("MODEL_TRAINING_SCORING",   "claude-sonnet-4-5-20251022")
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
MODEL_PIP_AUTOVAR       = os.getenv("MODEL_PIP_AUTOVAR",       "claude-sonnet-4-5-20251022")
MODEL_PIP_VARIANTE      = os.getenv("MODEL_PIP_VARIANTE",      "claude-sonnet-4-5-20251022")
MODEL_COACHING          = os.getenv("MODEL_COACHING",          "claude-haiku-4-5-20251001")
MODEL_VALIDATE_USER_TEXT= os.getenv("MODEL_VALIDATE_USER_TEXT","claude-haiku-4-5-20251001")
MODEL_TRAINING_PREVIEW  = os.getenv("MODEL_TRAINING_PREVIEW",  "claude-haiku-4-5-20251001")

# ── Phase 08.13: CACHE-Toggles (ENV-overridable, per Decision 3) ───────────────
# CACHE_EWB: EWB-Generation cachen (System-Prompt gross genug — default an)
# CACHE_QA: QA-Response cachen (System-Prompt gross genug — default an)
# CACHE_ANALYSE: Analyse-Loop cachen (System-Prompt kuerzer — default AUS)
CACHE_EWB     = os.getenv("CACHE_EWB",     "true").lower()  == "true"
CACHE_QA      = os.getenv("CACHE_QA",      "true").lower()  == "true"
CACHE_ANALYSE = os.getenv("CACHE_ANALYSE", "false").lower() == "true"

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
