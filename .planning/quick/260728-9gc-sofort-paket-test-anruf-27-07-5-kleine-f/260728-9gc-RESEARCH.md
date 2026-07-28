# 260728-9gc — Recherche (nur FIX 3: Deepgram Keepalive)

**Erhoben:** 2026-07-28
**Methode:** context7 (`/lukeocodes/deepgram-python-sdk`, Migration-Docs v3→v5) + Verifikation
gegen den **tatsächlich installierten SDK-Quellcode** + Versionsabgleich auf Prod via ssh.

## Installierte Version

| Ort | Version | Beleg |
|---|---|---|
| Prod (178.104.82.166) | **deepgram-sdk 3.10.0** | `ssh -i ~/.ssh/nerve_vps root@178.104.82.166 "/opt/nerve/venv/bin/pip show deepgram-sdk"` |
| Lokal | **v3.10.0** | `python -c "import deepgram; print(deepgram.__version__)"` |
| Pin | `deepgram-sdk>=3.7.0` | `requirements.txt:6` |

→ Lokal == Prod. Die v3-Syntax gilt.

## Ergebnis: Keepalive ist in 3.x eine **Client-Option**, KEINE manuelle Nachricht

context7 (Migrating-v3-to-v5.md) sagt eindeutig:

- **v3.0.0 – v4.8.1:** „Keep alive was passed as a config option."
  ```python
  config = DeepgramClientOptions(options={"keepalive": "true"})
  deepgram = DeepgramClient(API_KEY, config)
  ```
- **Erst ab v5.0.0:** manuell via `connection.send_control(ListenV1ControlMessage(type="KeepAlive"))`.

**→ Für uns (3.10.0) gilt ausschließlich die Client-Options-Variante.**
Die v5-Variante (`send_control`) existiert in 3.10.0 nicht — nicht verwenden.

### Gegenprobe am installierten Code (nicht nur Doku)

`site-packages/deepgram/options.py:98-104`
```python
def is_keep_alive_enabled(self) -> bool:
    return self.options.get("keepalive", False) or self.options.get("keep_alive", False)
```

`site-packages/deepgram/clients/listen/v1/websocket/client.py:168-174`
```python
# keepalive thread
if self._config.is_keep_alive_enabled():
    self._logger.notice("keepalive is enabled")
    self._keep_alive_thread = self._thread_cls(target=self._keep_alive)
    self._keep_alive_thread.start()
else:
    self._logger.notice("keepalive is disabled")
```

Das SDK startet also bei gesetzter Option **selbst einen Hintergrund-Thread**, der periodisch
die KeepAlive-Nachricht schickt. Wir müssen nichts selbst takten.

Akzeptierte Schlüssel: `"keepalive"` **oder** `"keep_alive"`. Truthy-Prüfung via `.get(...)`,
d.h. der String `"true"` (wie in der offiziellen Doku) wirkt. Wir nehmen die Doku-Schreibweise.

## Konkrete Fundstelle im Projekt

`services/deepgram_service.py:431-434` — der Client wird **ohne** `options` gebaut:
```python
client = DeepgramClient(
    ...,
    config=DeepgramClientOptions(url=f"https://{DEEPGRAM_HOST}"),
)
```

**Änderung:** `options={"keepalive": "true"}` ergänzen. Ein Argument, ein Ort.

## Fallstricke

1. **Nicht in `LiveOptions` packen.** Keepalive gehört an `DeepgramClientOptions`
   (Client-Ebene), nicht an die Transkriptions-Optionen. `LiveOptions` (Zeile 468/474)
   nicht anfassen.
2. **`url=` darf nicht verloren gehen** — der bestehende `url`-Parameter muss erhalten
   bleiben, sonst zeigt der Client nicht mehr auf `DEEPGRAM_HOST`.
3. Der Keepalive-Thread wird erst in `connection.start()` gestartet — die Option muss
   also vor dem Verbindungsaufbau am Client hängen (ist bei :431 der Fall).
4. Keepalive verhindert den 1011-Abbruch bei Ton-Stau, **ersetzt aber keinen
   Wiederaufbau** — der bleibt bewusst außen vor (spätere Phase, siehe FIX 4).

## Waechter (Test)

Prüfbar ohne Netz: die erzeugte Verbindungs-Konfiguration bewerten, z.B.
`DeepgramClientOptions(...).is_keep_alive_enabled() is True` bzw. den an
`DeepgramClientOptions` übergebenen `options`-Dict abfangen und auf den Keepalive-Schlüssel
prüfen. Kein echter Deepgram-Call nötig.
