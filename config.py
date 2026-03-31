import os
from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_API_KEY  = os.environ.get('DEEPGRAM_API_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY', '')
SECRET_KEY        = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
CORS_ORIGIN       = os.environ.get('CORS_ORIGIN', '*' if os.environ.get('FLASK_DEBUG') else 'https://nerve.app')
DATABASE_URL      = os.environ.get('DATABASE_URL', 'sqlite:///database/nerve.db')
MAX_SESSION_HOURS = int(os.environ.get('MAX_SESSION_HOURS', 8))

SAMPLE_RATE       = 16000
CHUNK_SIZE        = 1024
ANALYSE_INTERVALL = 2
MERGE_WINDOW_S    = 1.0
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
