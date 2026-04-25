from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# H-20: Brute-Force-Schutz — Singleton-Instanz, wird in app.py mit init_limiter(app) gebunden.
# ACHTUNG: ProxyFix muss in app.py VOR init_limiter(app) gesetzt sein.
# Ohne ProxyFix gibt get_remote_address 127.0.0.1 fuer alle Requests hinter Nginx —
# Rate-Limit wird zum globalen Bucket statt per-IP.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],       # Kein globales Limit — nur spezifische Decorators
    storage_uri="memory://",
    # Future Multi-Worker (Block M): storage_uri="redis://localhost:6379" setzen.
)


def init_limiter(app):
    """H-20: Bindet limiter an Flask-App. Aufzurufen in app.py nach ProxyFix-Setup."""
    limiter.init_app(app)
