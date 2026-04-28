---
quick_id: 260428-pua
slug: polish-08-19-2-post-uat
date: 2026-04-28
status: complete
commit: 778825e
---

# Summary: Polish-Round 08.19.2 Post-UAT

Alle 14 Items umgesetzt. Commit 778825e.

## Umgesetzt
- Painpoints (Accordion + Chevron, default-collapsed)
- vorwissen, ki.ansprache, ki.sensitivitaet entfernt
- CRUD-Cards: Accordion-Layout (name oben, body collapsed, Löschen-Button)
- "Opener-Sammlung" → "Opener"
- Chevron ▸/▾ in allen Cards: Einwände, Fragen, Painpoints, FAQ, CRUD
- Default-collapsed für alle Listen
- 8 Umlaut-Fixes (inkl. Consent-Placeholder)
- sec-hint: 13px, 600, var(--page-text-color)
- field-desc: var(--page-text-color)
- tip-icon: permanent teal, 12px

## Offen (Plant-Seeds)
- vorwissen → Live-Workflow PreCall
- ki.ansprache → Smart-Switch Live-Assistent
- ki.sensitivitaet → Live-Workflow Skript/Opener

## Deploy
`git push origin main` + Live-UAT durch André.
