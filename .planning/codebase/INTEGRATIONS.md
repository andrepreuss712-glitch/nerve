# External Integrations

**Analysis Date:** 2026-03-30

## APIs & External Services

**Speech & Audio Processing:**
- Deepgram - Real-time speech-to-text transcription
  - SDK/Client: `deepgram-sdk` 3.7.0+
  - Auth: `DEEPGRAM_API_KEY` environment variable
  - Usage: `services/deepgram_service.py` - Captures live audio input and transcribes to text during calls
  - Integration: Live WebSocket transcription in `deepgram_starten()` function
  - Features: Multi-speaker detection with speaker diarization (Speaker 0 = salesperson, Speaker 1+ = customer)

- ElevenLabs - Text-to-speech voice synthesis
  - API Endpoint: `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
  - Auth: `ELEVENLABS_API_KEY` environment variable (header `xi-api-key`)
  - Client: HTTP via `requests` library in `services/training_service.py`
  - Usage: `text_to_speech()` function generates audio for training scenarios
  - Features:
    - Multilingual model `eleven_multilingual_v2`
    - Voice stability: 0.5, similarity_boost: 0.75
    - Pre-configured voice pools: 4 male voices (Brian, Daniel, Callum, Antoni), 4 female voices (Bella, Rachel, Domi, Emily)
    - Supports multiple languages: German (de), English (en), French (fr), Spanish (es)

**AI & Analysis:**
- Anthropic Claude - Conversation analysis and coaching
  - SDK/Client: `anthropic` 0.40.0+ Python client
  - Auth: `ANTHROPIC_API_KEY` environment variable
  - Model: `claude-haiku-4-5-20251001` for CRM export generation
  - Usage locations:
    - `services/claude_service.py` - Real-time objection detection and counterargument generation
    - `services/crm_service.py` - Post-call CRM note and follow-up email generation
    - `routes/training.py` - Training scenario customer response generation
  - Features:
    - Real-time JSON-based objection analysis with speaker sentiment
    - Coaching tip generation during live calls
    - Multi-language support (German, English, French, Spanish)
    - DSGVO-compliant CRM export (no direct customer quotes)

## Data Storage

**Databases:**
- SQLite (primary)
  - Connection: `DATABASE_URL` (default: `sqlite:///database/salesnerve.db`)
  - Location: `database/database/salesnerve.db` (relative to project root)
  - Client: SQLAlchemy 2.0.0+ ORM
  - Migration: Automatic schema migration on startup (`app.py` `_migrate()` function)

**Alternative:**
- PostgreSQL supported via `DATABASE_URL` environment variable (e.g., `postgresql://user:pass@host/db`)

**File Storage:**
- Local filesystem only
  - Conversation logs: `logs/` directory (created at runtime)
  - Log format: Text files with conversation transcripts and analysis results

**Caching:**
- None detected - all state stored in SQLite or memory during active sessions

## Authentication & Identity

**Auth Provider:**
- Custom in-house authentication
  - Implementation: Email + password with Werkzeug `generate_password_hash()` / `check_password_hash()`
  - Session management: Flask session (cookie-based with SECRET_KEY encryption)
  - Session timeout: `MAX_SESSION_HOURS` (default 8 hours)
  - Routes: `routes/auth.py` - Login, signup, session validation
  - Database: User credentials stored in `users` table (email unique, password hashed)
  - Decorator: `@login_required` enforces authentication on protected routes

**Session Model:**
- Flask session cookies (server-side state tracked in memory/SQLite)
- User role-based access: owner/admin/member/coach roles in `users.role`

## Monitoring & Observability

**Error Tracking:**
- Not detected

**Logs:**
- File-based logging
  - Location: `logs/` directory in project root
  - Format: Text-based conversation transcripts with timestamps
  - Content: Conversation segments, speaker identification, analysis results, coaching notes
  - Suppression: Werkzeug polling routes (`/api/ergebnis`, `/api/status`) filtered to reduce noise

**Debugging:**
- Flask debug mode disabled in production (set in `app.run()` call)
- Standard Python logging with custom filters

## CI/CD & Deployment

**Hosting:**
- Self-hosted / On-premise deployment
- Default: Local development on `http://localhost:5000`
- Production: Run `python app.py` with `socketio.run(app, host='0.0.0.0', port=5000)`

**CI Pipeline:**
- Not detected

## Environment Configuration

**Required env vars:**
- `DEEPGRAM_API_KEY` - Deepgram API key for speech transcription
- `ANTHROPIC_API_KEY` - Claude API key for analysis
- `ELEVENLABS_API_KEY` - ElevenLabs API key for TTS (optional for training module)
- `SECRET_KEY` - Flask secret key (generate: `secrets.token_hex(32)`)
- `DATABASE_URL` - Database connection string (default: SQLite)
- `MAX_SESSION_HOURS` - Session lifetime in hours (default: 8)

**Secrets location:**
- `.env` file (Git-ignored, see `.gitignore`)
- Example template: `.env.example`

**Note:** Never commit `.env` to version control; always use `.env.example` as template.

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- None detected (integrations are API pull/push only, no webhook subscriptions)

## Real-Time Communication

**WebSocket (SocketIO):**
- Protocol: Flask-SocketIO with threading async mode
- CORS: Enabled for all origins (`cors_allowed_origins="*"`)
- Events (inferred from code):
  - `transcript` - Live transcription updates from Deepgram
  - `analysis` - Real-time objection analysis from Claude
  - `coaching_tip` - Live coaching suggestions
  - `status` - Session state updates
  - `ergebnis` - Analysis result polling (suppressed in logs)

---

*Integration audit: 2026-03-30*
