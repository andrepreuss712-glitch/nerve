# Phase 06: PiP Komplett-Rebuild — Research

**Researched:** 2026-04-14
**Domain:** Document Picture-in-Picture API, Claude Streaming, Socket.IO token relay, CSS layered transparency, Teleprompter UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Fester Split ~55/45 im Live-Zustand: Obere Hälfte = KI-Hinweise + EWB-Buttons, untere Hälfte = Skript-Teleprompter. Kein Resizing, keine Tabs.
**D-02:** KI-Bereich zeigt proaktive Tipps — nie leer. Zwischen Einwänden: kontextbezogene Frage-Vorschläge, Phase-Wechsel-Hinweise, Kaufbereitschafts-Trend.
**D-03:** Dual-Slot-System für KI-Antworten. Slot 1 läuft zu Ende, Slot 2 beantwortet neue Frage. KI entscheidet: gleicher Kontext = Alternativen, neuer Kontext = separate Antworten, Themenwechsel = beide ersetzen.
**D-04:** Setup-Flow bleibt unverändert: Modus → Kundendaten → Profil/Skript → Start.
**D-05:** Consent-Schritt verschoben aus Setup IN Live-Zustand (nur Meeting-Modus). Consent-Vollbild-Screen → [Stattgegeben] = voller Meeting-Modus, [Abgelehnt] = Fallback Cold-Call.
**D-06:** Consent-Text natürlich formuliert, im Profil editierbar. Default: "Herr/Frau [Name], kurzer Hinweis — ich mache mir während unseres Gesprächs digitale Notizen. Ist das für Sie in Ordnung?"
**D-07:** Cold-Call-Modus: kein Consent-Schritt — direkt zum Opener.
**D-08:** Wort-für-Wort Streaming wie ChatGPT, Token für Token mit blinkendem Cursor. WebSocket-Push (Socket.IO Event).
**D-09:** Streaming NUR im PiP. Haupt-Tab `/live` bleibt auf bestehendem Polling.
**D-10:** Dual-Slot Ersetzungslogik steuert Interaktion zwischen laufenden Streams.
**D-11:** Teleprompter zeigt vollen Skript-Text — nicht Phasen-Übersicht.
**D-12:** Datenquelle: ProfileSkript-Tabelle (bereits vorhanden in DB). Skript-Dropdown im Setup-Step 3.
**D-13:** Semantische Position-Erkennung per KI (`skript_position` im Claude-Response). Manuelles Scrollen überschreibt, KI passt sich an neue Position an.
**D-14:** Aktiver Skript-Block in voller Helligkeit + Teal-Akzent links. Vorherige und kommende Blöcke bei ~40% Opacity. Sanftes Auto-Scroll.
**D-15:** Opacity-Slider im PiP-Header, nur im Live-Zustand sichtbar.
**D-16:** Slider steuert NUR den Background-Layer. Schrift, Buttons bleiben IMMER bei 100% Opacity.
**D-17:** Transparenz-Wert in localStorage gespeichert.

### Claude's Discretion

- Exact CSS-Implementierung der Background-Transparenz (welche Layer, rgba vs. backdrop)
- Slider-Design und Interaktion (Range-Input, Custom-Slider, Min/Max-Werte)
- Streaming-Token-Batching (wie viele Tokens pro WebSocket-Event)
- Auto-Scroll-Verhalten und Timing (Easing, Debounce)
- Dual-Slot Layout-Details (Spacing, Trenner, Animation bei Slot-Wechsel)
- Consent-Text Profil-Feld Name und Platzierung im Profil-Editor

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

---

## Summary

This phase replaces the PiP live section (tabs + polling) with a split-layout streaming UI. The technical foundations are all present and compatible: the Anthropic SDK 0.86.0 provides `client.messages.stream()` with a `text_stream` iterator, Flask-SocketIO 5.6.1 supports per-room emit (used already by Deepgram's `room=sid` pattern), and the Document PiP window is established and stable. The `ProfileSkript` table already exists in `database/models.py`. No new dependencies are required for any part of this phase.

The highest-complexity work is: (1) the streaming relay pattern — a background thread runs `client.messages.stream()` and emits per-token Socket.IO events to the correct `sid` room; (2) the dual-slot state machine on the frontend, which must track two independent streaming responses and apply the replace/keep/overwrite logic per D-03; (3) the CSS layered transparency, which requires two stacked `position: absolute` elements — a background layer with rgba and a content layer that always stays at full opacity.

**Primary recommendation:** Build the streaming relay as a new function `analysiere_mit_claude_streaming(neuer_text, kontext, sid, slot_id)` that emits `pip_token`, `pip_token_done`, and `pip_stream_start` events. Keep `analysiere_mit_claude()` intact for the main-tab polling path. The dual-slot frontend can be a pure JS state machine without any backend changes beyond the new streaming emitter.

---

## Project Constraints (from CLAUDE.md)

- Flask + Vanilla JS — no React, no framework changes
- Haiku for ALL live operations — Sonnet only post-call. This applies to streaming too: `model='claude-haiku-4-5-20251001'`
- Cost-Hook pattern must be preserved: `log_api_cost()` calls after each Anthropic call
- Naming: lowercase_with_underscores for functions, German domain variables (`einwand`, `gegenargument`, etc.)
- No PyAudio on server — all audio via browser + Socket.IO
- FT logging (`_write_ft_assistant_event`) should wrap new streaming calls too

---

## Standard Stack

### Core (already installed, no new deps)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| anthropic | 0.86.0 | Streaming API via `messages.stream()` | VERIFIED: `pip show anthropic` |
| flask-socketio | 5.6.1 | Per-room token emit from background thread | VERIFIED: `pip show flask-socketio` |
| SQLAlchemy | (existing) | ProfileSkript table queries | VERIFIED: table exists in models.py |

### No New Dependencies Required
The entire phase can be implemented with the existing stack. `client.messages.stream()` has been available since anthropic SDK 0.20+. [VERIFIED: anthropic 0.86.0 installed]

---

## Architecture Patterns

### Pattern 1: Anthropic Streaming Relay via Socket.IO

The Python SDK provides a context manager pattern for streaming. The key is that this runs in a background thread (same as `analyse_loop`/`coaching_loop`), and emits per-token events to the user's specific `sid` room.

```python
# Source: platform.claude.com/docs/en/api/messages-streaming + verified anthropic 0.86.0
def analysiere_mit_claude_streaming(neuer_text: str, kontext: str, sid: str, slot_id: int):
    """PiP-only streaming variant. Emits pip_token events to specific sid room."""
    from extensions import socketio as sio

    # Signal stream start to frontend (so it can set up the cursor)
    sio.emit('pip_stream_start', {'slot': slot_id}, room=sid)

    full_text = ''
    try:
        with claude_client.messages.stream(
            model='claude-haiku-4-5-20251001',   # MUST stay Haiku per CLAUDE.md
            max_tokens=400,
            system=_build_system_prompt(),
            messages=[{'role': 'user', 'content': f'...'  }]
        ) as stream:
            for token in stream.text_stream:
                full_text += token
                sio.emit('pip_token', {'slot': slot_id, 'token': token}, room=sid)
        # Stream complete — send final parsed result
        parsed = _parse_json(full_text)
        sio.emit('pip_token_done', {'slot': slot_id, 'result': parsed}, room=sid)
        return parsed
    except Exception as e:
        sio.emit('pip_stream_error', {'slot': slot_id, 'error': str(e)}, room=sid)
        return {}
```

**Thread safety note:** Flask-SocketIO's `emit()` is thread-safe when called from background threads. This is already proven by `coaching_loop` calling `sio.emit('coaching', ...)` from a background thread. [VERIFIED: existing pattern in claude_service.py line 1031]

### Pattern 2: sid Routing for PiP-Only Streaming

The streaming must go to the right user's PiP window. The `sid` is already tracked per Deepgram session (`_deepgram_sessions = {sid: connection}`). The same `sid` from `request.sid` in the Socket.IO handler is the room identifier.

The `analyse_loop` currently writes to `ls.state` (shared global) — the streaming path needs to know the `sid` to target. Two options:

**Option A (recommended):** Store the active `sid` in `ls.state` at session start:
```python
# In handle_start_live_session:
ls.state['active_sid'] = request.sid
```
Then the streaming function reads `ls.state.get('active_sid')` to target the correct room.

**Option B:** Pass `sid` as parameter from the `analyse_loop` (requires refactor of loop signature).

Option A is lower-risk — the existing loop structure stays intact.

### Pattern 3: Dual-Slot Frontend State Machine

Two independent JS objects manage slot state. The decision logic runs when a new Claude analysis arrives:

```javascript
// Source: derived from D-03 decisions
var _pipSlots = {
  0: { streaming: false, text: '', result: null, context_key: null },
  1: { streaming: false, text: '', result: null, context_key: null }
};

function handlePipStreamStart(data) {
  var slot = data.slot;
  var el = getPipElement('pip-slot-' + slot);
  if (el) {
    el.textContent = '';
    el.classList.add('pip-streaming');
  }
  _pipSlots[slot].streaming = true;
  _pipSlots[slot].text = '';
}

function handlePipToken(data) {
  var slot = data.slot;
  var el = getPipElement('pip-slot-' + slot);
  if (el) {
    _pipSlots[slot].text += data.token;
    el.textContent = _pipSlots[slot].text;
    // Ensure cursor blink visible
  }
}

function handlePipTokenDone(data) {
  var slot = data.slot;
  _pipSlots[slot].streaming = false;
  _pipSlots[slot].result = data.result;
  var el = getPipElement('pip-slot-' + slot);
  if (el) el.classList.remove('pip-streaming');
}
```

### Pattern 4: CSS Background-Only Transparency (D-16)

The requirement is background transparent, text at 100% opacity. This cannot be achieved with a single `opacity` property (it cascades to children). The correct approach uses two stacked layers:

```css
/* Source: [ASSUMED] CSS specification — opacity vs rgba behavior */
#pip-section-live {
  position: relative;
}

/* Background layer — controlled by slider */
#pip-section-live::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--page-bg, #06060a);
  opacity: var(--pip-bg-opacity, 1);  /* JS sets this CSS variable */
  z-index: 0;
  pointer-events: none;
}

/* Content layer — always full opacity */
#pip-section-live > * {
  position: relative;
  z-index: 1;
}
```

**Alternative approach** (simpler, avoids z-index stacking):
```css
/* Use rgba directly on background — no opacity inheritance */
#pip-section-live {
  background: rgba(6, 6, 10, var(--pip-bg-alpha, 1));
}
```

The `rgba` approach is simpler and recommended. JS updates `--pip-bg-alpha` via `document.documentElement.style.setProperty()` or inline style on `#pip-section-live`. Since the PiP content is moved via `appendChild` into `pipWindow.document.body`, the variable must be set on the PiP document's root, not the main tab's root.

```javascript
// Correct: set on PiP window document
function setPipBgOpacity(value) {  // value 0.0–1.0
  var doc = window._pipWindow ? window._pipWindow.document : document;
  var liveSection = getPipElement('pip-section-live');
  if (liveSection) {
    liveSection.style.background = 'rgba(6,6,10,' + value + ')';
  }
  try { localStorage.setItem('nerve_pip_opacity', value); } catch(e) {}
}
```

### Pattern 5: Teleprompter — ProfileSkript Data Model

The `ProfileSkript` table already exists. [VERIFIED: database/models.py line 133]

```python
class ProfileSkript(Base):
    __tablename__ = 'profile_skripte'
    id          = Column(Integer, primary_key=True)
    profile_id  = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    name        = Column(String(200), nullable=False)
    inhalt      = Column(Text)       # Full script text
    sortierung  = Column(Integer, default=0)
    created_at  = Column(DateTime, default=utcnow)
```

The `inhalt` field stores the full script text. For the Teleprompter, the text needs to be divided into "blocks" (by paragraph or by structured section markers). Two parsing approaches:

**Option A (recommended):** Parse by double-newline into blocks — no schema change needed.
**Option B:** Define structured block markers in the text (e.g., `## Phase Name`).

For `skript_position`, Claude returns a 0-based block index or a block title. The frontend highlights that block.

### Pattern 6: Consent Flow State Machine (D-05)

The consent screen is a new `pip-section-consent` state, inserted between `setup` and `live`. State machine becomes:

```
setup → consent (meeting only) → live
setup → live (cold_call direct)
consent → live (stattgegeben: full meeting mode)
consent → live (abgelehnt: falls back to cold_call)
```

`setPipState()` gains `'consent'` as a valid state. The consent text is loaded from the active profile's new `consent_text` field (or default if null).

**Profile model change:** Add `consent_text` column to `Profile`. Migration via `ALTER TABLE` in `app.py`'s migration block (existing pattern: app.py lines 78-83).

### Pattern 7: Proactive KI Fill (D-02) — "Never Empty"

Between objections, the KI-Bereich must show contextual content. This is new logic in the backend that triggers on:
- Phase change detected → emit a phase hint
- Coaching tipp available → show in Slot 0
- KB trend → show in Slot 1

The simplest implementation: the existing `coaching_loop` already emits `sio.emit('coaching', {...})`. For PiP streaming, add a parallel path in `coaching_loop` that, instead of just emitting the tipp as text, streams it token-by-token to the PiP.

### Pattern 8: skript_position in Claude Response

The `analysiere_mit_claude` response JSON gains an optional `skript_position` field:

```python
# In SYSTEM_PROMPT_BASE addition:
# "Wenn ein aktives Skript vorhanden ist: Ergänze 'skript_position': <int> mit dem 0-basierten Index des aktuellen Skript-Abschnitts"
```

Backend adds `skript_position` to the response if a script is active. Frontend uses it to auto-scroll.

### Recommended Project Structure (additions only)

```
services/
├── claude_service.py     # Add analysiere_mit_claude_streaming()
routes/
├── app_routes.py         # Add /api/skripte endpoint for Setup dropdown
templates/
├── app.html              # Replace pip-section-live HTML entirely
                          # Add pip-section-consent HTML
                          # Add new CSS for split layout, slots, teleprompter
static/
├── app.js                # Replace tab functions with split-layout functions
                          # Add pip_token/pip_stream_start handlers
                          # Add teleprompter block renderer
database/
├── models.py             # Add Profile.consent_text column (migration only)
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Streaming token delivery | Custom SSE endpoint | `client.messages.stream()` + Socket.IO emit | SDK handles reconnect, timeout, chunking |
| CSS opacity inheritance | JS opacity walker | `rgba()` on background or `::before` pseudo-element | Single property, no z-index complexity |
| Cursor blink animation | JS setInterval cursor | CSS `@keyframes` on `::after` pseudo-element | Pure CSS, no JS overhead |
| Smooth scroll | Manual scroll calculation | `scrollIntoView({ behavior: 'smooth' })` | Native browser API, works in PiP window |
| localStorage JSON | Custom serialization | `JSON.stringify/parse` with try-catch (pattern already in codebase) | Existing pattern in app.js |

---

## Common Pitfalls

### Pitfall 1: CSS Variables Don't Cross Document Boundary

**What goes wrong:** Setting `--pip-bg-alpha` on `document.documentElement` has no effect in the PiP window because the PiP window is a separate `Document`.

**Why it happens:** `window.documentPictureInPicture.requestWindow()` returns a new window with a separate DOM. CSS variables set on the main tab's `:root` do not propagate.

**How to avoid:** Always target `pipWindow.document.documentElement` for CSS variable updates. Use `getPipElement()` (which already searches the PiP window first) for DOM queries.

**Warning signs:** Slider moves but background doesn't change.

### Pitfall 2: Socket.IO emit from Background Thread Needs Correct Room

**What goes wrong:** Streaming tokens arrive at all connected users, not just the one whose PiP is active.

**Why it happens:** `sio.emit('pip_token', data)` without `room=sid` broadcasts globally. The existing `analyse_loop` stores results in `ls.state` (global), which works because there's one active session at a time. But `room=sid` targeting is required for streaming to avoid token leakage between users.

**How to avoid:** Always include `room=sid` in streaming emits. Store `sid` in `ls.state['active_sid']` at `start_live_session` time.

**Warning signs:** A second browser tab sees token flashes from another user's session.

### Pitfall 3: Streaming Response is not Valid JSON Until Complete

**What goes wrong:** Attempting to `_parse_json()` on partial token accumulations triggers JSONDecodeError mid-stream.

**Why it happens:** The `analysiere_mit_claude` response is a JSON object. During streaming, the text builds character by character — `{"einwand": tr` is not valid JSON.

**How to avoid:** Only call `_parse_json()` in `pip_token_done` after the stream completes. During streaming, the frontend shows raw token text (which happens to be JSON). After `pip_token_done`, replace the raw text with the parsed/formatted response.

**Warning signs:** Console errors about JSON parse failures during stream.

### Pitfall 4: Dual-Slot Conflict — Both Slots Streaming Simultaneously

**What goes wrong:** EWB button press while Slot 1 is mid-stream attempts to start Slot 2, but Slot 1 was supposed to finish. Thread collision or doubled content.

**Why it happens:** The backend streaming function runs in a thread. If a new trigger arrives before the first thread exits, two concurrent stream threads both try to emit to the same `sid`.

**How to avoid:** Track streaming state with a slot-level lock or use `threading.Event` per slot. If Slot 1 is streaming and a new objection arrives, let Slot 1 finish and start Slot 2. Only if it's a topic switch (D-03 "Themenwechsel") should Slot 1 be interrupted — which means cancelling the stream iterator.

**Warning signs:** Interleaved tokens between slots, garbled text.

### Pitfall 5: Teleprompter Auto-Scroll Fighting Manual Scroll

**What goes wrong:** User manually scrolls to a different block. Next `skript_position` update from KI forces scroll back to the KI's position, overriding the user's manual scroll.

**Why it happens:** Auto-scroll runs on every `pip_token_done` or analysis cycle.

**How to avoid:** Set a `_teleprompterManualOverride = true` flag on `scroll` event. Clear it after N seconds of no new analysis. KI's `skript_position` updates the flag only if override is not active.

**Warning signs:** Teleprompter jumps back after user scroll.

### Pitfall 6: PiP Window CSS Copy — Inline Styles Override Variables

**What goes wrong:** The `openPipWindow()` function copies stylesheets via `cssRules`. However, CSS custom properties set via `style.setProperty()` on the main tab's root are NOT copied — only stylesheet rules are.

**Why it happens:** `element.style` (inline styles) are separate from stylesheet rules.

**How to avoid:** Set initial PiP background color in the `openPipWindow()` function via `pipWindow.document.body.style.background = ...` (already done for body). For the live section, initialize opacity from localStorage in `initPipContent()`.

### Pitfall 7: `profileSkript.inhalt` is NULL for Profiles Without a Script

**What goes wrong:** Teleprompter renders nothing, no fallback, confused user.

**Why it happens:** `ProfileSkript` may not exist for a given `profile_id`. If no script is selected in Step 3 or profile has none, `inhalt` is null.

**How to avoid:** Always show a fallback message in the teleprompter section: "Kein Skript hinterlegt — Profil bearbeiten". Treat null/empty `inhalt` gracefully in block parser.

---

## Code Examples

### Streaming Relay — Background Thread Pattern

```python
# Source: existing pattern in claude_service.py coaching_loop + anthropic 0.86.0 SDK
def analysiere_mit_claude_streaming(neuer_text: str, kontext: str, sid: str, slot_id: int) -> dict:
    """PiP-only streaming variant. Emits pip_token events to specific sid room.
    Returns final parsed result dict (same shape as analysiere_mit_claude)."""
    from extensions import socketio as sio
    import services.live_session as ls

    sio.emit('pip_stream_start', {'slot': slot_id}, room=sid)
    full_text = ''
    try:
        with claude_client.messages.stream(
            model='claude-haiku-4-5-20251001',
            max_tokens=400,
            system=_build_system_prompt(),
            messages=[{'role': 'user', 'content': (
                f'Bisheriger Gesprächskontext:\n{kontext or "(Kein vorheriger Kontext)"}\n\n'
                f'Neues Gesprächssegment (analysiere NUR dieses auf Einwände):\n{neuer_text}'
            )}]
        ) as stream:
            for token in stream.text_stream:
                full_text += token
                sio.emit('pip_token', {'slot': slot_id, 'token': token}, room=sid)
        parsed = _parse_json(full_text)
        sio.emit('pip_token_done', {'slot': slot_id, 'result': parsed}, room=sid)
        # Cost tracking (same pattern as analysiere_mit_claude)
        try:
            from services.cost_tracker import log_api_cost
            final_msg = stream.get_final_message()
            u = getattr(final_msg, 'usage', None)
            if u:
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=getattr(u, 'input_tokens', 0)/1000.0,
                             unit_type='per_1k_input_tokens', context_tag='pip_stream')
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=getattr(u, 'output_tokens', 0)/1000.0,
                             unit_type='per_1k_output_tokens', context_tag='pip_stream')
        except Exception as _e:
            print(f'[CostHook] pip_stream skipped: {_e}')
        return parsed
    except Exception as e:
        print(f'[PiP-Stream] Fehler slot={slot_id}: {e}')
        sio.emit('pip_stream_error', {'slot': slot_id, 'error': str(e)}, room=sid)
        return {}
```

### Frontend Socket.IO Event Handlers

```javascript
// Source: [ASSUMED] derived from existing socket.on('coaching') pattern in app.js
socket.on('pip_stream_start', function(data) {
  var el = getPipElement('pip-slot-' + data.slot);
  if (!el) return;
  el.textContent = '';
  el.classList.add('pip-streaming');  // triggers cursor blink CSS
  _pipSlots[data.slot].streaming = true;
  _pipSlots[data.slot].text = '';
});

socket.on('pip_token', function(data) {
  var el = getPipElement('pip-slot-' + data.slot);
  if (!el) return;
  _pipSlots[data.slot].text += data.token;
  el.textContent = _pipSlots[data.slot].text;
});

socket.on('pip_token_done', function(data) {
  _pipSlots[data.slot].streaming = false;
  _pipSlots[data.slot].result = data.result;
  var el = getPipElement('pip-slot-' + data.slot);
  if (el) el.classList.remove('pip-streaming');
  // If einwand: format nicely with typ + gegenargument text
  renderPipSlotResult(data.slot, data.result);
});
```

### CSS Cursor Blink for Streaming State

```css
/* Source: [ASSUMED] CSS animation — standard teleprompter cursor pattern */
.pip-streaming::after {
  content: '▌';
  animation: pip-cursor-blink 0.7s step-end infinite;
  color: #00D4AA;
  margin-left: 2px;
}

@keyframes pip-cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
```

### Teleprompter Block Renderer

```javascript
// Source: [ASSUMED] DOM manipulation pattern matching existing PiP JS style
function renderTeleprompterBlocks(inhalt, activeBlockIdx) {
  var container = getPipElement('pip-teleprompter');
  if (!container) return;
  if (!inhalt) {
    container.innerHTML = '<div class="tp-empty">Kein Skript hinterlegt</div>';
    return;
  }
  var blocks = inhalt.split(/\n\n+/).filter(function(b) { return b.trim(); });
  var doc = container.ownerDocument || document;
  container.innerHTML = '';
  blocks.forEach(function(block, idx) {
    var div = doc.createElement('div');
    div.className = 'tp-block' + (idx === activeBlockIdx ? ' tp-block-active' : '');
    div.dataset.blockIdx = idx;
    div.textContent = block.trim();
    container.appendChild(div);
  });
  // Scroll active block into view
  var activeEl = container.querySelector('.tp-block-active');
  if (activeEl) {
    activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}
```

### Opacity Slider Initialization

```javascript
// Source: [ASSUMED] localStorage + CSS inline style pattern from existing codebase
function initPipOpacitySlider() {
  var slider = getPipElement('pip-opacity-slider');
  if (!slider) return;
  var saved = 1.0;
  try { saved = parseFloat(localStorage.getItem('nerve_pip_opacity') || '1'); } catch(e) {}
  if (isNaN(saved) || saved < 0.1) saved = 0.1;
  if (saved > 1) saved = 1;
  slider.value = Math.round(saved * 100);
  setPipBgOpacity(saved);
}

function setPipBgOpacity(value) {
  var liveEl = getPipElement('pip-section-live');
  if (liveEl) {
    liveEl.style.setProperty('--pip-bg-alpha', value);
  }
  try { localStorage.setItem('nerve_pip_opacity', String(value)); } catch(e) {}
}
```

---

## Existing Code: What Gets Replaced vs. Kept

### Kept (no changes)
- `openPipWindow()` (app.js:1843) — Document PiP API wrapper, CSS loading, pagehide cleanup
- `getPipElement(id)` — PiP-window-first lookup helper
- `window._pipWindow` / `window._pipState` state management
- `pipStartSetup()`, `pipPopulateProfiles()`, `pipPopulateKundendatenHistory()` — Setup-Flow
- `pipSubmitKundendaten()`, `pipStartPrecall()` — Setup steps 2+3
- `pipBeendenCall()`, `showPipPostcall()` — End-of-call flow
- `nerveApp` shared reference pattern for socket/profile access from PiP window
- Polling endpoint `/api/ergebnis` — still used by main-tab `/live`

### Replaced
| Old | New | Why |
|-----|-----|-----|
| Tab state machine (handlePipTabClick, setPipTabFromKI, activatePipTab) | Split layout, no tabs | D-01 |
| `updatePipFromErgebnis()` | `handlePipTokenDone()` + `renderPipSlotResult()` | D-08 streaming |
| `updatePipFromCoaching()` | Streaming coaching slot | D-08 streaming |
| `#pip-section-live` HTML (tabs + panels) | Split HTML: upper KI+EWB, lower Teleprompter | D-01 |
| PiP CSS in app.html (`.pip-tabs`, `.pip-panel`) | New split-layout CSS | D-01 |
| Consent in setup step 1 (`pipSelectMode` shows inline consent) | New `pip-section-consent` state | D-05 |

### Added to Backend
| What | Where | Why |
|------|-------|-----|
| `analysiere_mit_claude_streaming()` | claude_service.py | Streaming relay (D-08) |
| `ls.state['active_sid']` storage | deepgram_service.py `handle_start_live_session` | Route tokens to correct room |
| `skript_position` field in Claude response | SYSTEM_PROMPT_BASE addition | D-13 |
| `/api/skripte` endpoint | app_routes.py | Dropdown data for Setup-Step 3 |
| `Profile.consent_text` column | models.py + migration | D-06 |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Polling `/api/ergebnis` every 500ms | Socket.IO push per token | This phase | Real-time streaming, no polling overhead for PiP |
| Tab-based navigation (4 tabs) | Split layout (no tabs) | This phase | Always-visible teleprompter |
| `opacity` CSS property for transparency | `rgba()` background color | This phase | Text/buttons unaffected by slider |
| Consent in setup step 1 | Consent as live-state screen | This phase | DSGVO consent at decision moment |

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies beyond existing stack — anthropic streaming is part of already-installed SDK 0.86.0)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `client.messages.stream()` is available in anthropic 0.86.0 | Streaming Pattern | LOW: SDK 0.86.0 confirmed; `stream()` was introduced ~0.20; `text_stream` is the documented iterator |
| A2 | Flask-SocketIO 5.6.1 `emit(room=sid)` from background threads is thread-safe | Streaming Relay | LOW: Already used by `coaching_loop` (claude_service.py:1031) without room= for global, and deepgram_service.py:66 uses room=sid |
| A3 | `::after` pseudo-element cursor blink works inside Document PiP window | CSS Cursor | LOW: PiP window is a real browser window, CSS animations work normally |
| A4 | Setting CSS variable on `#pip-section-live` element (inline style) instead of `:root` works for rgba approach | Opacity Slider | LOW: `element.style.setProperty()` for inline CSS property is standard DOM |
| A5 | `scrollIntoView({ behavior: 'smooth' })` works inside the PiP document | Teleprompter scroll | LOW: Standard DOM API, works in all Chromium windows including PiP |
| A6 | `stream.get_final_message()` is available after stream iteration for cost tracking | Cost Hook | MEDIUM: Documented in SDK; verify that iterating `text_stream` still allows `get_final_message()` — or use `stream.usage` directly |

---

## Open Questions

1. **Slot assignment logic for D-03 — who decides which slot gets which stream?**
   - What we know: KI entscheidet (gleicher Kontext = Alternativen, neuer Kontext = separate Antworten, Themenwechsel = beide ersetzen)
   - What's unclear: This decision must be made BEFORE streaming starts (to assign `slot_id`). The backend needs to classify incoming trigger as "same context", "new context", or "topic switch" before dispatching the stream.
   - Recommendation: Add a lightweight pre-classification step (one Haiku call or heuristic based on `typ` field from last result vs. new trigger) before dispatching to `analysiere_mit_claude_streaming()`. Or: always stream to Slot 0 first, only stream to Slot 1 when Slot 0 is still streaming.

2. **Streaming interrupt on topic switch (D-03 "Themenwechsel")**
   - What we know: "Themenwechsel = alles ersetzen" — both slots cleared
   - What's unclear: Python `for token in stream.text_stream` runs on a thread. To interrupt mid-stream requires either a threading.Event checked in the loop, or just letting the thread finish but discarding the emitted tokens on the frontend.
   - Recommendation: Frontend approach — when a topic switch is signaled, the frontend clears both slot elements immediately and ignores incoming `pip_token` events for the cancelled slots. Cleaner than thread interruption.

3. **Profile.consent_text field: where in the profile editor UI?**
   - What we know: From D-06, it must be per-profile editable
   - What's unclear: The profile editor (`routes/profiles.py`) is a separate screen. Whether this phase includes the editor UI change, or just the backend field + default fallback.
   - Recommendation: Backend: add the column, store default text. PiP loads it. Profile editor gets a simple textarea in a separate wave or task. The PiP can work with just the default if `consent_text` is null.

---

## Validation Architecture

Step 2.4: The phase is primarily UI/streaming work. No automated test framework is detected for frontend JS. Backend streaming function can be manually verified via a test script.

Manual verification steps:
- Start a live session → PiP shows Setup correctly (Setup unchanged)
- Start a meeting-mode call → Consent screen appears after clicking Start
- Consent Stattgegeben → Live split layout visible with empty slots
- Speak a sentence with an objection → Tokens appear in Slot 0 character by character
- Slot 0 completes → Formatted result shown (einwand-typ + gegenargument)
- Background slider → Only background opacity changes, text stays readable
- Teleprompter → Blocks render, active block highlighted in teal, auto-scrolls
- Manual teleprompter scroll → Overrides KI position for next cycle

---

## Sources

### Primary (HIGH confidence)
- `services/claude_service.py` — Full source read, verified streaming is not yet implemented, verified Haiku model name `claude-haiku-4-5-20251001`, verified cost-hook pattern
- `static/app.js` — PiP state machine read (lines 1416–2124), verified `openPipWindow()` at 1843, tab functions at 1955–2124
- `templates/app.html` — PiP HTML structure read (lines 982–1049), verified tab/panel structure being replaced
- `database/models.py` — Verified `ProfileSkript` table at line 133, `Profile` at 121
- `services/deepgram_service.py` — Verified `room=sid` emit pattern, `active_sid` storage approach
- `pip show anthropic` — Version 0.86.0 confirmed
- `pip show flask-socketio` — Version 5.6.1 confirmed

### Secondary (MEDIUM confidence)
- platform.claude.com/docs/en/api/messages-streaming — Fetched, verified `client.messages.stream()` + `stream.text_stream` iterator + `stream.get_final_message()` pattern

### Tertiary (LOW confidence)
- CSS `::after` cursor animation — [ASSUMED] standard pattern, not verified against PiP window specifically

---

## Metadata

**Confidence breakdown:**
- Streaming relay pattern: HIGH — SDK verified, existing thread pattern proven in codebase
- Dual-slot state machine: MEDIUM — logic derived from decisions, no prior implementation to reference
- CSS transparency: HIGH — rgba approach is simple and deterministic
- Teleprompter: HIGH — ProfileSkript table exists, block parsing is trivial
- Consent state machine: HIGH — setPipState() pattern well-understood from existing code

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable stack)
