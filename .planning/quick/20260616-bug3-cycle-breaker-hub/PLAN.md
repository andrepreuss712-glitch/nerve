---
slug: bug3-cycle-breaker-hub
created: 2026-06-16
phase_ref: 08.23.2.PGTEST.GREEN
type: quick
gemini_review: _green_bug3_gemini_OUT.md (Punkt-24-Beleg, 3. Sicht)
---

# Quick: Bug 3 Cycle-Breaker — Hub statt Blatt brechen (Gemini-verifiziert)

## Root-Cause (Gemini 3.1 Pro, am Code verifiziert)

Der Zyklus-Brecher in `tests/_schema_introspect.py` (eingeführt im Bug-3-Fix db2d4be) wählte das
Opfer per `min(stuck, key=reverse_in_degree)` = Knoten mit den WENIGSTEN FK-Eltern = ein **Blatt**
(z.B. `crm.accounts`, tie-break alphabetisch). Per `in_degree=0` wurde es zur Kahn-**Root** ->
früh in `topo_order` -> nach `reversed()` SPÄT in der Löschorder -> `crm.accounts` landete HINTER
`public.tenant_orgs` (Index 35 statt vor 20). Damit invertierte der Brecher eine **legitime
Nicht-Zyklus-Kante** (`accounts->tenant_orgs`) -> test_06 rot + FK-Violation-Risiko.

## Fix (Gemini)

NICHT das Blatt brechen, sondern den echten Zyklus-**HUB**: den Rest-Knoten mit den MEISTEN noch
blockierten Kindern im Rest-Graph. `tests/_schema_introspect.py`:

    # vorher
    victim = min(stuck, key=lambda n: (reverse_in_degree[n], n))
    # nachher
    victim = max(stuck, key=lambda n: (sum(1 for child in reverse_adj[n] if child in stuck_set), n))

Damit wird `public.organisations` (viele Kinder) zur Root = spät gelöscht (korrekt für einen
vielreferenzierten Parent); gebrochen wird nur eine **INTRA-SCC-Kante** (`organisations->users`).
Blätter wie `crm.accounts` (0 Rest-Kinder) bleiben früh -> crm-vor-public erhalten -> test_06 grün.
Der Retry-Loop-Airbag (`_fk_safe_delete_rows`) zündet nur noch für die echte Mutual-FK-Brücke.

## Entscheidungen

- **test_06 NICHT lockern** (Gemini: das wäre Maskieren des echten Ordering-Bugs).
- `stuck_set = set(stuck)` aus dem `if not diagnosed`-Block hochgezogen (wird jetzt pro Iteration
  für die Victim-Wahl gebraucht). Kommentar + Log-Message an Hub-Semantik angepasst.

## Validierung

KEIN lokaler pytest (HART). Statisch: `python -m py_compile` grün; grep bestätigt `max(stuck...)`-Hub.
Empirisch: Claudian fährt `scripts/triage.sh` test_06 (Server) -> grün (crm.accounts vor tenant_orgs),
keine FK-Violation. Gemini-3.-Sicht-Beleg: `_green_bug3_gemini_OUT.md` im Phasen-Verzeichnis (Punkt 24).
