"""DSGVO build-blocking render-assertions for the Meeting-Merk-Fenster (Phase 08.23.2.G-MEET Plan 05).

GRENZFALL-RATIONALE (CLAUDE.md Test-Qualitaets-Regel):
  These are source/markup assertions on static/pip-launcher.js, NOT runtime DOM assertions. They are
  allowed under the documented Grenzfall clause because each one guards a LEGAL runtime constraint
  (DSGVO Art. 25 Abs. 2 default-off checkbox; Art. 6 Abs. 1 f privacy-note) for which there is no
  function-mock alternative: pip-launcher.js is vanilla browser JS inside an IIFE that touches
  `window` at top level, so it cannot be imported/rendered under pytest (no DOM). The rendered HTML
  is built by string concatenation in renderMeetingForm(); asserting on that exact markup is the only
  mechanical guard available. D-2/D-4 (auto_save_meeting DEFAULT false, server-honored) ARE true
  real-PG runtime assertions and live in tests/test_meeting_save_rls.py (Plan 04) — not duplicated here.

  The backend Firma-Pflicht 400 guard (routes/crm_export.py save_meeting) is a defensive early-return
  verified end-to-end by the live browser/route test on Production (Plan 05 <verification>), since a
  route-level pytest would require the in-memory-SQLite `client` fixture whose create_all cannot build
  the crm/training schema tables without an explicit ATTACH (Wave-3 SUMMARY §(g) deviation 4).
"""
import os

import pytest

_PIP_JS_PATH = os.path.join(os.path.dirname(__file__), '..', 'static', 'pip-launcher.js')


def _pip_js():
    with open(_PIP_JS_PATH, encoding='utf-8') as fh:
        return fh.read()


def test_meeting_checkbox_never_prechecked():
    """D-1 (Art. 25 Abs. 2): the auto_save_meeting checkbox is NEVER pre-checked by default.

    Grenzfall (legal constraint, no DOM in pytest): assert the rendered checkbox markup defaults to
    aria-checked="false" and that the ONLY place it is turned on is the guarded reflection of a
    previously, explicitly user-chosen opt-in (GET /crm/preferences -> auto_save_meeting === true),
    i.e. there is no unconditional default-on.
    """
    src = _pip_js()
    # Default render is OFF.
    assert 'role="checkbox" aria-checked="false"' in src
    # No HTML `checked` attribute on the meeting checkbox/input markup.
    assert 'id="meeting-autosave"' in src
    assert ' checked' not in src.split('id="meeting-autosave"')[1].split('</div>')[0]
    # The only default-on call is guarded by the explicit prior user opt-in (user will, not a default).
    assert 'if (d && d.auto_save_meeting === true) _setCb(true)' in src
    assert src.count('_setCb(true)') == 1


def test_privacy_note_present_verbatim():
    """D-3 (Art. 6 Abs. 1 f): the privacy note renders verbatim (echte Umlaute, UTF-8)."""
    src = _pip_js()
    expected = ('Kontaktdaten werden als B2B-Geschäftskontakt gespeichert (berechtigtes Interesse, '
                'Art. 6 Abs. 1 f DSGVO), um dir beim nächsten Anruf ein Briefing zu zeigen.')
    assert expected in src


def test_meeting_hint_copy_is_honest_mm02():
    """MM-02 (Andre Option b): the honest hint copy is present and the old 'ohne Nachfrage'-promise is gone."""
    src = _pip_js()
    assert 'Merkt sich deine Auswahl für später. Jederzeit abschaltbar.' in src
    assert 'ohne Nachfrage an' not in src


def test_firma_is_required_field():
    """André-Direktive 2026-06-02: Firma is a Pflichtfeld in the form (frontend enforcement).

    Grenzfall (UX/data-integrity constraint, no DOM in pytest): assert the Firma input carries the
    `required` attribute + a visible required marker, AND the save handler blocks an empty Firma
    (returns without POSTing) while keeping the field values (no clear). Ansprechpartner/Datum/Thema
    stay optional (no `required` on them).
    """
    src = _pip_js()
    # Firma input is marked required + has a visible marker.
    assert 'id="meeting-firma" type="text" required aria-required="true"' in src
    assert 'n-meeting-required-mark' in src
    # The save handler blocks empty Firma with an inline error and an early return (no POST).
    assert "if (!firma) {" in src
    assert "Firma ist Pflicht." in src
    # Optional fields are NOT required (negative check: no `required` on person/datetime/notes inputs).
    assert 'id="meeting-person" type="text" required' not in src
    assert 'id="meeting-datetime" type="datetime-local" required' not in src
    assert 'id="meeting-notes" type="text" required' not in src
