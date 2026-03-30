# Technology Stack

**Analysis Date:** 2026-03-30

## Languages

**Primary:**
- Python 3.x - Core application backend

## Runtime

**Environment:**
- Python (Flask-based runtime)

**Package Manager:**
- pip - Dependency management
- Lockfile: `requirements.txt` present

## Frameworks

**Core:**
- Flask 3.0.0+ - Web framework
- Flask-SocketIO 5.3.6+ - Real-time WebSocket support for live session communication

**Testing:**
- Not detected

**Build/Dev:**
- Werkzeug 3.0.0+ - WSGI utilities for Flask

## Key Dependencies

**Critical:**
- `anthropic` 0.40.0+ - Claude API integration for conversation analysis and coaching
- `deepgram-sdk` 3.7.0+ - Real-time speech-to-text transcription service
- `elevenlabs-api` (configured via `ELEVENLABS_API_KEY`) - Text-to-speech voice synthesis for training
- `sqlalchemy` 2.0.0+ - ORM for database models and queries
- `pyaudio` 0.2.14+ - Audio input/capture for live recording during calls
- `requests` 2.31.0+ - HTTP client for external API calls (ElevenLabs text-to-speech)

**Infrastructure:**
- `python-dotenv` 1.0.0+ - Environment variable configuration loading

## Configuration

**Environment:**
- Loaded via `python-dotenv` from `.env` file
- See `.env.example` for required variables

**Key configs required:**
- `DEEPGRAM_API_KEY` - Deepgram speech recognition API credentials
- `ANTHROPIC_API_KEY` - Claude API credentials for analysis and coaching
- `ELEVENLABS_API_KEY` - ElevenLabs text-to-speech API credentials
- `SECRET_KEY` - Flask session encryption key (must be generated for production)
- `DATABASE_URL` - SQLite database path (default: `sqlite:///database/salesnerve.db`)
- `MAX_SESSION_HOURS` - Session timeout duration (default: 8 hours)

**Audio Configuration:**
- `SAMPLE_RATE` - 16000 Hz (configured in `config.py`)
- `CHUNK_SIZE` - 1024 bytes per audio chunk
- `ANALYSE_INTERVALL` - 2 seconds between analysis runs
- `MERGE_WINDOW_S` - 1.0 second window for transcript merging
- `SPEAKER_DEBOUNCE_S` - 3.0 second debounce for speaker detection

## Platform Requirements

**Development:**
- Python 3.8+
- PyAudio library (requires system audio libraries)
- Git for version control

**Production:**
- Python 3.8+ runtime
- SQLite database (default) or PostgreSQL (via DATABASE_URL)
- System audio support for microphone input
- CORS enabled on Flask-SocketIO for real-time communication
- Port 5000 accessible (default; configurable via environment)

## Build & Run

**Start Application:**
```bash
python app.py
```

Starts Flask + SocketIO server on `http://localhost:5000`

---

*Stack analysis: 2026-03-30*
