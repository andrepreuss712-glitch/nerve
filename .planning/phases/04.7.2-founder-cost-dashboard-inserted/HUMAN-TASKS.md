# Phase 04.7.2 — Human Pre-Execution Tasks

**Status:** MUST be completed before Phase 04.7.2 execution hits deploy / first revenue-log webhook / first EÜR-export.

Diese Tasks kann Claude NICHT automatisieren. André führt sie manuell durch.

## Blocking before Wave 2 (Stripe revenue tracking goes live)

### HT-01: Stripe Tax Registration für Deutschland aktivieren
- **Wo:** Stripe Dashboard → Tax → Registrations → Add registration
- **Was:** Germany / Umsatzsteuer / gültig ab aktuellem Monatsanfang
- **Warum:** Ohne aktive Tax Registration liefert Stripe `invoice.lines.data[].tax_amounts` leer zurück. `automatic_tax: { enabled: true }` im Code allein reicht nicht — Stripe ignoriert die Flag ohne Registration.
- **Verifikation:** In Stripe-Dashboard → Tax → Registrations zeigt `Germany — Active` mit Gültigkeitsdatum.
- **Reference:** CONTEXT.md D-03, RESEARCH.md Pitfall 1.

### HT-02: Webhook-Subscription um `invoice.payment_succeeded` erweitern
- **Wo:** Stripe Dashboard → Developers → Webhooks → (bestehender Endpoint `https://getnerve.app/api/webhooks/stripe`) → Select events to listen to
- **Was:** Event `invoice.payment_succeeded` zur bestehenden Subscription hinzufügen (bestehend: `checkout.session.completed`, `invoice.paid`).
- **Warum:** Ohne diesen Event wird `_record_revenue()` nie gefeuert, RevenueLog bleibt leer.
- **Verifikation:** In Stripe-Dashboard → Webhook-Endpoint-Detail zeigt `invoice.payment_succeeded` in der Event-Liste. Test-Webhook fires erfolgreich → 200 von Server.
- **Reference:** CONTEXT.md D-03.

## Blocking before Wave 5 (PDF-Export)

### HT-03: VPS System-Pakete + pip install
- **Wo:** SSH Hetzner VPS (`ssh root@178.104.82.166`)
- **Befehle:**
  ```bash
  apt-get update
  apt-get install -y libpango-1.0-0 libpangoft2-1.0-0
  cd /opt/nerve
  source venv/bin/activate
  pip install WeasyPrint APScheduler
  pip freeze > requirements.txt  # aktualisieren
  ```
- **Warum:** WeasyPrint braucht native Pango/Cairo-Libs. APScheduler wird für den Frankfurter-Wechselkurs-Cron gebraucht.
- **Verifikation:**
  ```bash
  python -c "import weasyprint; print(weasyprint.__version__)"
  python -c "from apscheduler.schedulers.background import BackgroundScheduler; print('ok')"
  ```
- **Reference:** CONTEXT.md D-04, RESEARCH.md Pitfall 5.

## Blocking before erster produktiver EÜR/USt-VA Export

### HT-04: count.tax Sign-Off auf §13b-Behandlung der US-Drittland-API-Anbieter
- **Wo:** Email / Telefonat / Erstgespräch count.tax
- **Was:** Sign-off dass folgende Interpretation steuerlich korrekt ist:
  > API-Zahlungen an Anthropic (US), Deepgram (US), ElevenLabs (US) sind B2B sonstige Leistungen am Empfängerort (§3a (2) UStG). Damit greift § 13b UStG Reverse Charge. Meldung in USt-VA:
  > - KZ 84 (Bemessungsgrundlage) = netto-EUR-Betrag
  > - KZ 85 (darauf entfallende USt) = 19% von KZ 84
  > - KZ 67 (Vorsteuer Reverse Charge) = identisch zu KZ 85 (voller Vorsteuerabzug)
  > - Netto-Effekt 0 €, Meldepflicht trotzdem.
- **Warum:** Das ist der einzige Teil des EÜR-Calculators bei dem ein Rechenfehler echte steuerliche Konsequenzen hat (Finanzamt-Rückfragen). Phase 04.7.2 implementiert die Logik basierend auf dem Briefing-Beispiel (Seite 192), aber das ist nicht count.tax-validated.
- **Verifikation:** Schriftliche Bestätigung (Email / Chat-Export) in `06 Archiv/`.
- **Reference:** CONTEXT.md D-12, RESEARCH.md Pitfall 3, Assumption A1.

## Non-blocking (optional, dokumentiert für später)

### HT-05: Windows-Dev WeasyPrint (optional)
Nur relevant falls André PDF-Generierung lokal auf Windows testen möchte. Fallback HTML-Preview-Endpoint im Dev reicht aus.
- MSYS2 installieren + `pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-cairo mingw-w64-x86_64-gdk-pixbuf2`
- PATH setzen.
- Siehe https://github.com/Kozea/WeasyPrint/issues/2105

### HT-06: Stripe-Backfill historischer Invoices
Deferred auf spätere Quick-Task. Phase 04.7.2 startet bei 0 ab Deploy. Wenn später historische Zahlen nötig: einmalig `stripe.Invoice.list` + `_record_revenue()` aufrufen.
