# NERVE Staging Server — Ersteinrichtungs-Runbook

**Ziel:** staging.getnerve.app auf Hetzner CX32 aufsetzen.
**Einmaliger Aufwand:** ~60-90 Minuten

## Voraussetzungen (lokal)

- [ ] Hetzner-Account mit CX32-Budget
- [ ] jq installiert in Git Bash: `which jq` → Pfad vorhanden
- [ ] Lokales Repository auf `main` Branch, alle Changes gepusht

---

## Schritt 1: Hetzner CX32 erstellen

1. Hetzner Cloud Console → New Server
2. Location: **Nuremberg** (NBG1) — gleiche Region wie Production
3. Image: **Ubuntu 22.04 LTS**
4. Type: **CX32** (4 vCPU, 8 GB RAM)
5. SSH Key: Neuen Key hinzufuegen (Schritt 2 zuerst)
6. Hostname: `nerve-staging`
7. **Notiere die zugewiesene IPv4-Adresse** → wird als `<STAGING_IP>` verwendet

---

## Schritt 2: SSH-Key generieren

```bash
# Lokal in Git Bash ausfuehren:
ssh-keygen -t ed25519 -f ~/.ssh/nerve_staging -C "nerve-staging-deploy"
# Public Key fuer Hetzner-Console:
cat ~/.ssh/nerve_staging.pub
```

Public Key in Hetzner-Console bei Schritt 1 eintragen.

---

## Schritt 3: DNS-Eintrag setzen

In deinem DNS-Provider (z.B. Namecheap/Cloudflare):
- Typ: **A**
- Name: `staging`
- Wert: `<STAGING_IP>` (aus Schritt 1)
- TTL: 300

Warte auf DNS-Propagation: `nslookup staging.getnerve.app` muss `<STAGING_IP>` zurueckgeben.

---

## Schritt 4: setup_staging.sh ausfuehren

```bash
# Skript auf Server kopieren und ausfuehren:
scp -i ~/.ssh/nerve_staging scripts/setup_staging.sh root@<STAGING_IP>:/tmp/
ssh -i ~/.ssh/nerve_staging root@<STAGING_IP> "bash /tmp/setup_staging.sh"
```

---

## Schritt 5: /etc/nerve/.env anlegen

```bash
ssh -i ~/.ssh/nerve_staging root@<STAGING_IP>
# Auf dem Server:
mkdir -p /etc/nerve
# Vorlage aus .env.staging.example verwenden:
nano /etc/nerve/.env
# Alle Variablen aus .env.staging.example eintragen (echte Werte!)
```

Pflicht-Variablen (aus .env.staging.example):
- `ANTHROPIC_API_KEY` — Staging-Sandbox-Key (separater Key von Production)
- `DEEPGRAM_API_KEY` — Staging-Key
- `STRIPE_SECRET_KEY=sk_test_...` — Stripe Test-Mode
- `STAGING_BASIC_AUTH_USER=staging`
- `STAGING_BASIC_AUTH_PASS` — Wert aus Schritt 6

---

## Schritt 6: htpasswd-Datei erstellen

```bash
ssh -i ~/.ssh/nerve_staging root@<STAGING_IP>
# Basic-Auth-Passwort generieren:
openssl rand -hex 12
# htpasswd-Datei erstellen (Passwort wird interaktiv abgefragt):
htpasswd -c /etc/htpasswd.nerve-staging staging
# Tipp: Passwort aus openssl-Output verwenden und in .env STAGING_BASIC_AUTH_PASS eintragen
```

---

## Schritt 7: nginx-Staging-Config deployen (vorlaeufig ohne SSL)

```bash
scp -i ~/.ssh/nerve_staging deploy/nginx-staging.conf root@<STAGING_IP>:/etc/nginx/sites-available/nerve-staging
ssh -i ~/.ssh/nerve_staging root@<STAGING_IP> "ln -sf /etc/nginx/sites-available/nerve-staging /etc/nginx/sites-enabled/nerve-staging && nginx -t && systemctl reload nginx"
```

---

## Schritt 8: SSL-Zertifikat via Certbot

```bash
ssh -i ~/.ssh/nerve_staging root@<STAGING_IP>
certbot --nginx -d staging.getnerve.app
# Folge den Anweisungen; Certbot aktualisiert nginx-Config automatisch
```

---

## Schritt 9: Ersten Deploy ausfuehren

```bash
# deploy.sh kennt Staging-IP nach Refactor (Plan 02) — dann:
./deploy.sh staging
```

---

## Verifikation

```bash
# Health-Check OHNE Basic-Auth (location /api/health hat auth_basic off)
curl -fsS https://staging.getnerve.app/api/health
# Erwartete Antwort: {"status": "ok", "git_head": "...", "deployed_at": "..."}

# Auth-Check: / braucht Credentials — ohne muss 401 kommen
curl -o /dev/null -w "%{http_code}" https://staging.getnerve.app/

# Robots-Check (erbt auth_basic vom Server — 401 ohne Credentials ist korrekt fuer Crawler)
curl -u staging:<PASS> -fsS https://staging.getnerve.app/robots.txt
```

---

## Troubleshooting

- **Certbot schlaegt fehl:** DNS noch nicht propagiert — `nslookup staging.getnerve.app` pruefen
- **nginx -t schlaegt fehl:** SSL-Cert-Pfade noch nicht vorhanden — Certbot zuerst (Schritt 8)
- **gunicorn startet nicht:** `journalctl -u nerve-staging -n 50` → .env-Variablen pruefen
