"""Deploy-Gate-Waechter fuer scripts/prune_orphans.sh (Phase 08.23.2.DEPLOY-PRUNE, D-07).

Beweist die Prune-Logik DETERMINISTISCH gegen tmp-Fixtures — laeuft im deploy.sh-pytest-Gate
mit (nicht `live`/`perf`). KEIN Zugriff auf echtes /opt/nerve, KEINE DB.

Zwei Stile (Fable MUST-3):
- Subprocess gegen ein tmp-$APP_DIR fuer die aus dem Scan erreichbaren Faelle.
- SOURCE-und-Funktion-direkt fuer den logs/database-Hard-Abort (aus dem Whitelist-Scan
  nicht erreichbar -> Test sourct das Skript und ruft prune_guard_customer_data direkt).
  Anti-Vakuum-Gruen (Fable-Recheck): Positiv-Kontrolle (guter Kandidat -> exit 0) UND
  Assertion auf den [PRUNE][ABORT]-Marker in stderr — sonst wuerde ein defektes Sourcen
  (Top-Level-Crash) returncode!=0 aus dem falschen Grund liefern.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prune_orphans.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    not SCRIPT.exists() or BASH is None,
    reason="scripts/prune_orphans.sh oder bash nicht verfuegbar (lokal/Windows) — laeuft scharf im Linux-Deploy-Gate",
)


def _write_manifest(path: Path, rels):
    """git-ls-files-z-Stil: jeder Pfad NUL-terminiert."""
    path.write_bytes(b"".join(r.encode() + b"\0" for r in rels))


def _make_app(tmp_path, tracked, orphans):
    """Baut ein fake $APP_DIR + Manifest. tracked/orphans = Liste relativer Pfade."""
    app = tmp_path / "app"
    for rel in list(tracked) + list(orphans):
        f = app / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
    manifest = tmp_path / "manifest"
    _write_manifest(manifest, tracked)
    return app, manifest


def _run(app, manifest, tmp_path, apply=False, prune_max=None):
    env = dict(os.environ)
    env["APP_DIR"] = str(app)
    env["MANIFEST"] = str(manifest)
    env["PRUNE_REPORT_DIR"] = str(tmp_path / "reports")
    env["PRUNE_TRASH_BASE"] = str(tmp_path / "trash")
    if apply:
        env["PRUNE_APPLY"] = "1"
    if prune_max is not None:
        env["PRUNE_MAX"] = str(prune_max)
    return subprocess.run(
        [BASH, str(SCRIPT)], env=env, capture_output=True, text=True
    )


# ── Subprocess-Stil (erreichbare Faelle) ─────────────────────────────────────

def test_orphan_listed_dryrun(tmp_path):
    app, manifest = _make_app(
        tmp_path, tracked=["templates/keep.html"], orphans=["templates/orphan.html"]
    )
    r = _run(app, manifest, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "templates/orphan.html" in r.stderr
    assert "templates/keep.html" not in r.stderr  # getrackt -> kein Kandidat
    # Dry-Run bewegt NICHTS:
    assert (app / "templates" / "orphan.html").exists()


def test_empty_manifest_aborts(tmp_path):
    app, manifest = _make_app(tmp_path, tracked=["templates/keep.html"], orphans=[])
    manifest.write_bytes(b"")  # leer
    r = _run(app, manifest, tmp_path)
    assert r.returncode != 0
    assert "[PRUNE][ABORT]" in r.stderr
    assert (app / "templates" / "keep.html").exists()  # nichts bewegt


def test_cap_exceeded_aborts(tmp_path):
    app, manifest = _make_app(
        tmp_path,
        tracked=["templates/keep.html"],
        orphans=["templates/a.html", "templates/b.html"],
    )
    r = _run(app, manifest, tmp_path, prune_max=1)
    assert r.returncode != 0
    assert "[PRUNE][ABORT]" in r.stderr
    assert (app / "templates" / "a.html").exists()  # nichts bewegt


def test_excluded_pycache_not_candidate(tmp_path):
    # __pycache__ + .pyc + tts_samples werden VOR dem Cap ausgefiltert (SHOULD-b/MUST-1a)
    app, manifest = _make_app(
        tmp_path,
        tracked=["templates/keep.html"],
        orphans=[
            "services/__pycache__/x.pyc",
            "tests/tts_samples/voice.mp3",
            "templates/real_orphan.html",
        ],
    )
    r = _run(app, manifest, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "__pycache__" not in r.stderr
    assert "tts_samples" not in r.stderr
    assert "templates/real_orphan.html" in r.stderr  # echte Waise bleibt Kandidat


def test_space_path_orphan(tmp_path):
    # NUL-Schutz (T-PRUNE-06): Leerzeichen im Pfad darf nicht wort-gesplittet werden
    app, manifest = _make_app(
        tmp_path, tracked=["templates/keep.html"], orphans=["templates/a b.html"]
    )
    r = _run(app, manifest, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "templates/a b.html" in r.stderr


def test_apply_moves_to_trash(tmp_path):
    app, manifest = _make_app(
        tmp_path, tracked=["templates/keep.html"], orphans=["templates/orphan.html"]
    )
    r = _run(app, manifest, tmp_path, apply=True)
    assert r.returncode == 0, r.stderr
    assert not (app / "templates" / "orphan.html").exists()  # weg aus App-Dir
    # in Quarantaene (mv, kein Datenverlust):
    trash = tmp_path / "trash"
    moved = list(trash.rglob("templates/orphan.html"))
    assert moved, f"nicht in trash: {list(trash.rglob('*'))}"
    assert (app / "templates" / "keep.html").exists()  # getrackt bleibt


# ── Source-Stil: logs/database-Hard-Abort direkt (Fable MUST-3) ──────────────

def _source_guard(candidate):
    """sourct das Skript und ruft prune_guard_customer_data mit EINEM Kandidaten."""
    return subprocess.run(
        [BASH, "-c", f"source '{SCRIPT}'; prune_guard_customer_data '{candidate}'"],
        capture_output=True, text=True,
    )


def test_logs_candidate_hard_abort(tmp_path):
    r = _source_guard("logs/nerve_log_U1.txt")
    assert r.returncode != 0
    assert "[PRUNE][ABORT]" in r.stderr  # aus dem RICHTIGEN Grund (nicht Sourc-Crash)


def test_database_candidate_hard_abort(tmp_path):
    r = _source_guard("database/salesnerve.db")
    assert r.returncode != 0
    assert "[PRUNE][ABORT]" in r.stderr


def test_guard_passes_clean_candidate(tmp_path):
    # POSITIV-KONTROLLE (Fable-Recheck, Anti-Vakuum-Gruen): ein GUTER Kandidat
    # muss exit 0 liefern — beweist, dass die !=0 der Hard-Abort-Tests vom Guard
    # kommt, nicht von einem defekten Sourcen.
    r = _source_guard("templates/x.html")
    assert r.returncode == 0, r.stderr
    assert "[PRUNE][ABORT]" not in r.stderr
