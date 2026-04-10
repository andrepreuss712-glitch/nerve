"""
NERVE Real-Time Engine — Configuration

Reads from the same .env file as the Flask app.
Uses plain os.environ.get + load_dotenv() to stay consistent
with the Flask config.py pattern.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # Same .env as Flask


class Settings:
    """Engine configuration from environment variables."""

    # API keys (shared with Flask)
    deepgram_api_key: str = os.environ.get('DEEPGRAM_API_KEY', '')
    anthropic_api_key: str = os.environ.get('ANTHROPIC_API_KEY', '')

    # Redis
    redis_url: str = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')

    # CORS (same logic as Flask config.py)
    cors_origin: str = os.environ.get(
        'CORS_ORIGIN',
        '*' if os.environ.get('FLASK_DEBUG') else 'https://nerve.app'
    )

    # Server
    host: str = os.environ.get('RT_HOST', '127.0.0.1')
    port: int = int(os.environ.get('RT_PORT', '8001'))

    # Audio constants (must match Flask config.py)
    sample_rate: int = 16000
    analyse_intervall: int = 2


settings = Settings()
