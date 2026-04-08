import json
import sys


def test_ft_objection_insert_and_export(db_session, monkeypatch, tmp_path):
    from database.models import (
        Organisation, User, FtCallSession, FtObjectionEvent, FtAssistantEvent,
    )

    org = Organisation(name="Test Org")
    db_session.add(org)
    db_session.flush()

    u = User(org_id=org.id, email="t@t.de", passwort_hash="x",
             market="dach", language="de")
    db_session.add(u)
    db_session.flush()

    sess = FtCallSession(
        user_id=u.id, mode="cold_call", market="dach", language="de"
    )
    db_session.add(sess)
    db_session.flush()

    db_session.add(FtAssistantEvent(
        ft_session_id=sess.id, user_id=u.id, market="dach", language="de",
        timestamp_ms=1, conversation_phase="unknown",
        hint_type="objection", hint_text="test hint",
        model_used="claude-haiku-4-5-20251001", prompt_version="v1.0.0",
    ))
    db_session.add(FtObjectionEvent(
        ft_session_id=sess.id, user_id=u.id, market="dach", language="de",
        timestamp_ms=1, objection_type="kein_bedarf",
        recommended_response="Antwort",
        model_used="claude-haiku-4-5-20251001", prompt_version="v1.0.0",
    ))
    db_session.commit()

    assert db_session.query(FtObjectionEvent).count() == 1
    assert db_session.query(FtAssistantEvent).count() == 1

    # Export via script (mock SessionLocal to reuse the in-memory db_session)
    from database import db as dbmod

    class _Fake:
        def __init__(self, real):
            self._real = real

        def query(self, m):
            return self._real.query(m)

        def close(self):
            pass

    monkeypatch.setattr(dbmod, "SessionLocal", lambda: _Fake(db_session))

    # Assistant table export
    out_file = tmp_path / "out_assistant.jsonl"
    sys.argv = [
        "export_ft_jsonl.py", "--market", "dach",
        "--out", str(out_file), "--table", "assistant",
    ]
    from scripts.export_ft_jsonl import main
    rc = main()
    assert rc == 0
    assert out_file.exists()
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["market"] == "dach"
    assert rec["hint_type"] == "objection"

    # Objection table export
    out_file2 = tmp_path / "out_obj.jsonl"
    sys.argv = [
        "export_ft_jsonl.py", "--market", "dach",
        "--out", str(out_file2), "--table", "objection",
    ]
    rc2 = main()
    assert rc2 == 0
    lines2 = out_file2.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines2) == 1
    rec2 = json.loads(lines2[0])
    assert rec2["objection_type"] == "kein_bedarf"
