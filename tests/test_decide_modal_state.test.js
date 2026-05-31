// Phase 08.23.2.D.UX.1 — Plan 04 (DC-04 / BLOCKER-2 / F1)
// Node built-in test runner (node:test + node:assert) — zero dependency, no Jest.
// Function-Call-Return tests against the real _decideModalState (CLAUDE.md test-quality rule).
const { test } = require('node:test');
const assert = require('node:assert');
// pip-launcher.js greift auf window-Top-Level zu -> nicht unter Node ladbar. Daher wird
// die reine Decider-Logik aus dem geteilten UMD-Helper geladen, den der Browser ueber
// window.NerveOutcomeModalState ebenfalls nutzt (DC-01 single source of truth, BLOCKER-2 Fallback).
const { _decideModalState } = require('../static/outcome-modal-state.js');

test('Zustand 1 kein_versuch when confidence 0', () => {
  assert.strictEqual(_decideModalState({confidence: 0, outcome: null, source: null}), 'kein_versuch');
});

test('Zustand 2 sicher when source ai_auto', () => {
  assert.strictEqual(_decideModalState({confidence: 0.95, source: 'ai_auto', outcome: 'meeting_booked'}), 'sicher');
});

test('Zustand 3 unsicher when source ai_auto_unsicher', () => {
  assert.strictEqual(_decideModalState({confidence: 0.6, source: 'ai_auto_unsicher', outcome: 'callback'}), 'unsicher');
});

test('Zustand 4 defensive warns and returns unsicher', () => {
  const orig = console.warn;
  let calls = 0;
  console.warn = () => { calls += 1; };
  try {
    assert.strictEqual(_decideModalState({confidence: 0.5, source: null, outcome: null}), 'unsicher');
    assert.strictEqual(calls, 1);   // DC-03 defensive console.warn fired exactly once
  } finally {
    console.warn = orig;
  }
});

test('Zustand 5 final when source user_corrected', () => {
  // F1: user_corrected ist autoritativ auch bei confidence 0 (beweist Branch-Ordering: final VOR conf===0).
  assert.strictEqual(_decideModalState({confidence: 0, source: 'user_corrected', outcome: 'meeting_booked'}), 'final');
});

test('08.23.2.D.UX.4: conf zero beats source (ai_auto + confidence 0 -> kein_versuch, Reihenfolge load-bearing)', () => {
  // U-01-relevant: ein ai_auto-Vorschlag mit confidence 0 ist KEIN sicherer Outcome —
  // conf===0 muss VOR dem ai_auto->sicher-Zweig greifen, sonst falsche Teal-Vorauswahl.
  assert.strictEqual(_decideModalState({confidence: 0, source: 'ai_auto', outcome: 'meeting_booked'}), 'kein_versuch');
});
