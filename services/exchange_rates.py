"""Phase 04.7.2 — Wechselkurs-Service (D-05).

Frankfurter API als EZB-Quelle. Kostenlos, kein Key, kein Quota.
Daily-Cron via APScheduler BackgroundScheduler (06:00 UTC).
Multi-Worker-Safety via env-Flag NERVE_SCHEDULER_WORKER oder File-Lock.
Frankfurter-Down → skip (kein Crash, letzter bekannter Kurs bleibt gültig).
"""
from __future__ import annotations
import os
import tempfile
import requests
from datetime import date
from decimal import Decimal

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
SCHEDULER_LOCK_FILE = os.path.join(tempfile.gettempdir(), "nerve_fx_scheduler.lock")
_scheduler_instance = None


# ── Frankfurter Client ──────────────────────────────────────────────────────
def fetch_usd_eur() -> float | None:
    """Holt aktuellen USD→EUR Kurs von Frankfurter. None bei API-Fehler."""
    try:
        r = requests.get(
            FRANKFURTER_URL,
            params={'base': 'USD', 'symbols': 'EUR'},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        return float(data['rates']['EUR'])
    except Exception as e:
        print(f"[FX] Frankfurter fetch failed: {e}")
        return None


# ── Daily Update (Cron-Entrypoint) ──────────────────────────────────────────
def update_daily_rate():
    """Cron-Entrypoint. Schreibt Tagesrate wenn noch nicht vorhanden.
    Bei API-Down: kein Write → letzter bekannter Kurs bleibt aktiv.
    Idempotent: mehrfache Aufrufe am selben Tag = 1 Row.
    """
    rate = fetch_usd_eur()
    if rate is None:
        print("[FX] update_daily_rate skipped (api down)")
        return
    from database.db import get_session
    from database.models import ExchangeRate
    db = get_session()
    try:
        existing = (
            db.query(ExchangeRate)
              .filter_by(date=date.today(), currency_pair='USD_EUR')
              .first()
        )
        if existing:
            # Overwrite only if from a weaker source (seed/fallback)
            if existing.source == 'frankfurter':
                print(f"[FX] already have frankfurter rate for {date.today()}: {existing.rate}")
                return
            existing.rate = Decimal(str(rate))
            existing.source = 'frankfurter'
            db.commit()
            print(f"[FX] upgraded {date.today()} rate to frankfurter={rate}")
            return
        db.add(ExchangeRate(
            date=date.today(),
            currency_pair='USD_EUR',
            rate=Decimal(str(rate)),
            source='frankfurter',
        ))
        db.commit()
        print(f"[FX] updated USD_EUR={rate} for {date.today()}")
    except Exception as e:
        print(f"[FX] update_daily_rate DB error: {e}")
        db.rollback()
    finally:
        db.close()


# ── Current Rate Lookup ─────────────────────────────────────────────────────
def get_current_rate(currency_pair: str = 'USD_EUR') -> float:
    """Liefert neuesten Kurs für das Paar. Fallback 0.92 bei leerer Tabelle."""
    from database.db import get_session
    from database.models import ExchangeRate
    db = get_session()
    try:
        row = (
            db.query(ExchangeRate)
              .filter_by(currency_pair=currency_pair)
              .order_by(ExchangeRate.date.desc())
              .first()
        )
        return float(row.rate) if row else 0.92
    finally:
        db.close()


# ── Multi-Worker Lock ───────────────────────────────────────────────────────
def _acquire_worker_lock() -> bool:
    """Multi-Worker-Safety: nur 1 Worker darf Scheduler starten.
    - NERVE_SCHEDULER_WORKER=1 → force yes
    - NERVE_SCHEDULER_WORKER=0 → force no
    - sonst File-Lock (O_CREAT|O_EXCL) mit PID-Check als Fallback.
    """
    env_flag = os.environ.get('NERVE_SCHEDULER_WORKER')
    if env_flag == '0':
        return False
    if env_flag == '1':
        return True
    try:
        fd = os.open(SCHEDULER_LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{os.getpid()}".encode())
        os.close(fd)
        return True
    except FileExistsError:
        # Lock-File exists — check if owning PID still alive.
        try:
            with open(SCHEDULER_LOCK_FILE) as f:
                pid = int((f.read().strip() or '0'))
            if pid > 0:
                try:
                    os.kill(pid, 0)
                    return False  # owner alive
                except (ProcessLookupError, PermissionError, OSError):
                    # stale lock — remove and retry once
                    try:
                        os.remove(SCHEDULER_LOCK_FILE)
                    except Exception:
                        return False
                    return _acquire_worker_lock()
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"[FX] worker lock error: {e}")
        return False


# ── Scheduler Start ─────────────────────────────────────────────────────────
def start_scheduler():
    """Initialisiert BackgroundScheduler falls dieser Worker den Lock hält.
    Idempotent: mehrfacher Aufruf startet nicht doppelt.
    """
    global _scheduler_instance
    if _scheduler_instance is not None:
        return
    if not _acquire_worker_lock():
        print("[FX] scheduler lock held by other worker — skipping")
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        print("[FX] APScheduler not installed — scheduler disabled (pip install apscheduler)")
        return
    sched = BackgroundScheduler(timezone='UTC')
    sched.add_job(
        update_daily_rate,
        'cron',
        hour=6,
        minute=0,
        id='fx_daily',
        replace_existing=True,
        misfire_grace_time=3600,
    )
    sched.start()
    _scheduler_instance = sched
    print("[FX] BackgroundScheduler started (daily 06:00 UTC)")
    # Run once at startup to populate today's rate if missing
    try:
        update_daily_rate()
    except Exception as e:
        print(f"[FX] initial update skipped: {e}")
