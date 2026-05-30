// Phase 08.23.2.D.UX.1 — Plan 04 (DC-01 / BLOCKER-2) — zentrale Outcome-Modal-Zustands-Logik.
// Single source of truth: der Browser (pip-launcher.js via window.NerveOutcomeModalState)
// UND die Node-Unit-Tests (tests/test_decide_modal_state.test.js via require) nutzen dieselbe
// _decideModalState. pip-launcher.js selbst greift auf window-Top-Level zu und ist daher nicht
// unter Node ladbar — deshalb diese kleine, DOM-freie UMD-Extraktion.
// ASCII-Enum-Strings (Code-Identifier); nur sichtbarer Text traegt Umlaute (in pip-launcher.js).
(function (root, factory) {
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;                 // Node (node:test)
  } else {
    root.NerveOutcomeModalState = api;    // Browser global
  }
})(typeof self !== 'undefined' ? self : this, function () {
  // 5-Zustand-Decider (DC-02 + F1). Reihenfolge ist load-bearing:
  // 'final' (user_corrected) VOR conf===0 — ein finalisierter Call ist autoritativ,
  // auch wenn die KI ihn nie klassifiziert hat (confidence 0).
  function _decideModalState(data) {
    var conf = +(data && data.confidence) || 0;
    if (data && data.source === 'user_corrected') return 'final';  // F1: bereits finalisiert — read-only
    if (conf === 0) return 'kein_versuch';                         // Zustand 1
    if (data.source === 'ai_auto') return 'sicher';                // Zustand 2
    if (data.source === 'ai_auto_unsicher') return 'unsicher';     // Zustand 3
    if (data.outcome === null && conf > 0) {                       // Zustand 4 (defensiv, DC-03)
      console.warn('[D.UX.1] Inconsistent state', data);
      return 'unsicher';
    }
    return 'unsicher';
  }
  return { _decideModalState: _decideModalState };
});
