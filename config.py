import os
from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_API_KEY  = os.environ.get('DEEPGRAM_API_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY', '')
SECRET_KEY        = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
DATABASE_URL      = os.environ.get('DATABASE_URL', 'sqlite:///database/nerve.db')
MAX_SESSION_HOURS = int(os.environ.get('MAX_SESSION_HOURS', 8))

SAMPLE_RATE       = 16000
CHUNK_SIZE        = 1024
ANALYSE_INTERVALL = 2
MERGE_WINDOW_S    = 1.0
SPEAKER_DEBOUNCE_S = 3.0

PLANS = {
    'starter':    {'max_users': 5,   'price_per_user': 49},
    'team':       {'max_users': 15,  'price_per_user': 44},
    'business':   {'max_users': 30,  'price_per_user': 39},
    'enterprise': {'max_users': None,'price_per_user': None},
}

KATEGORIE_LABEL = {
    'frage':      'Frage fehlt',
    'signal':     'Kaufsignal',
    'redeanteil': 'Redeanteil',
    'uebergang':  'Übergang',
    'lob':        'Lob',
}
