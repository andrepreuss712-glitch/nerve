"""
services/profile_schema.py
────────────────────────────────────────────────────────────────────
Phase 08.19: Pydantic v2 ProfileSchema + idempotente Migration.
Phase 08.19.1: schema_version v2 -> v3. einwaende + phasen top-level in ProfileSchema,
  Dead Fields aus BasisSchema entfernt. extra='forbid' wird in Plan-05 aktiviert.

Exports:
  - ProfileSchema        — Write-Schema (extra='ignore'), fuer wizard_create / bearbeiten
  - ProfileReadSchema    — Read-Schema  (extra='ignore'), fuer bearbeiten GET + alle Reader
  - _migrate_profile_data(daten: dict) -> dict
        Idempotent: v1 -> v2 upgrade. Prueft schema_version, entfernt
        eliminierte Felder, setzt neue Defaults, gibt schema_version=2 zurueck.
        v2 -> v3: einwaende/phasen upward-merge aus basis.*, fragen-Key entfernen.

Namespace-Entscheidung (Claude's Discretion per 08.19-CONTEXT.md):
  - zielgruppe.vorwissen + zielgruppe.entscheidungsverhalten bleiben in zielgruppe.*
    (claude_service._build_coaching_prompt liest explizit pdata.get('zielgruppe', {}))
  - Neue B2B-Felder kommen in zielkunde.*
  - branche bleibt als String in basis.branche (DB-Column-Konsolidierung spaeter in 08.20)

Reviews v2 — Enum-Sync-Pflicht:
  UnternehmensgroesseEnum Literal-Werte sind kanonische Quelle der Wahrheit.
  Plan 04 HTML-Chips MUESSEN onclick-Werte exakt matchen:
    '<10', '10-50', '50-250', '250-1000', '1000+'
  Jede Abweichung erzeugt silent HTTP-400 beim wizard_create() POST.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict

# ── Unternehmensgroesse Enum ────────────────────────────────────────────────
# Reviews v2: Diese Literal-Werte sind kanonisch. Plan 04 UI-Chips muessen exakt matchen.
UnternehmensgroesseEnum = Literal['<10', '10-50', '50-250', '250-1000', '1000+']

# ── Zeithorizont Enum ───────────────────────────────────────────────────────
ZeithorizontEnum = Literal['sofort', '3_monate', '6_monate', 'kein_druck']

# ── Einwand-Typ Enum ────────────────────────────────────────────────────────
EinwandTypEnum = Literal['echt', 'vorschiebe', 'unbekannt']


# ── Sub-Schemas (extra='ignore' — real data contains unlisted fields) ───────

class BasisSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')
    unternehmen: str = ''
    produktbeschreibung: str = ''
    branche: str = ''                        # Enum-Whitelist via routes/profiles.py _normalize_branche()
    branche_kontext: str = ''
    usps: List[str] = []
    preismodell: str = ''
    konsequenz: str = ''
    eigene_formulierungen: List[str] = []
    beweise: List[str] = []
    tabu_begriffe: List[dict] = []           # [{text: str, alternativ: str}]
    # Wizard-Feld (Phase 08.9)
    zielkunden: str = ''
    # einwaende + phasen wurden in Phase 08.19.1 nach top-level ProfileSchema verschoben
    # (Editor schreibt seit Phase 08 ausschliesslich top-level — basis.* waren Dead Fields)


class ZielgruppeSchema(BaseModel):
    """Training-relevante Felder (gelesen von _build_coaching_prompt). NICHT eliminieren."""
    model_config = ConfigDict(extra='ignore')
    berufsstatus: str = ''
    beruflicher_hintergrund: Union[str, List[str]] = ''
    vorwissen: str = ''                      # Training-Pfad: claude_service.py Z.229
    entscheidungsverhalten: List[str] = []   # Training-Pfad: claude_service.py Z.230
    # B2C-Felder eliminiert: alter, einkommensniveau, lebenssituation (D-06)


class ZielkundeSchema(BaseModel):
    """Neue B2B-Felder aus 08.18-Literatur-Synthese (D-07)."""
    model_config = ConfigDict(extra='ignore')
    unternehmensgroesse: Optional[UnternehmensgroesseEnum] = None   # Pflicht-Wizard-Feld
    buying_committee: str = ''                                        # Detail-Editor
    statusquo: str = ''                                              # Detail-Editor (loest schmerzen.trigger ab)
    zeithorizont: Optional[ZeithorizontEnum] = None                  # Detail-Editor


class ValueSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')
    roi_argumente: List[str] = []    # Detail-Editor (D-07)


class EinwandDetailSchema(BaseModel):
    """Erweitertes Einwand-Objekt im Detail-Editor (einwaende[] als Liste von Dicts)."""
    model_config = ConfigDict(extra='ignore')
    einwand: str = ''
    varianten: List[str] = []
    gegenargument: str = ''
    technik: str = ''
    intensitaet: int = 3
    kurzlabel: str = ''
    kategorie: str = ''
    einwand_typ: EinwandTypEnum = 'unbekannt'    # NEU D-07


class KiSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')
    anrede: str = 'Sie'
    ansprache: str = ''
    ton: str = ''           # ki.stil eliminiert — Inhalt geht in ki.ton (D-06)
    zusatz: str = ''
    # ki.stil wird in _migrate_profile_data() in ki.ton gemergt


class SchmerzenSchema(BaseModel):
    """schmerzen.trigger eliminiert (D-06). Inhalte wandern in zielkunde.statusquo."""
    model_config = ConfigDict(extra='ignore')
    schmerzpunkte: List[dict] = []
    # trigger eliminiert


class MetaSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')
    firma: str = ''
    rolle: str = ''
    consent_text: str = ''    # D-04 dual-write (liest auch aus profiles.consent_text als Fallback)


# ── ProfileSchema (extra='ignore') ──────────────────────────────────────────

class ProfileSchema(BaseModel):
    """Write-Schema: permissive (extra='ignore'). Wird bei wizard_create() und bearbeiten() POST validiert.
    Realdata-Kalibrierung 2026-04-27: strict='forbid' ist nicht anwendbar solange Schema die
    realen Profile-Felder nicht vollstaendig abbildet. Strict-Mode kommt in Phase 08.19.1.
    """
    model_config = ConfigDict(extra='ignore')
    schema_version: int = 2
    basis: BasisSchema = BasisSchema()
    zielgruppe: ZielgruppeSchema = ZielgruppeSchema()
    zielkunde: ZielkundeSchema = ZielkundeSchema()
    value: ValueSchema = ValueSchema()
    ki: KiSchema = KiSchema()
    schmerzen: SchmerzenSchema = SchmerzenSchema()
    meta: MetaSchema = MetaSchema()
    kaufsignale: List[dict] = []
    nogos: Union[List[str], List[Dict[str, Any]]] = []
    wettbewerber: List[dict] = []
    uebergaenge: List[dict] = []
    techniken: dict = {}
    einwaende_detail: List[EinwandDetailSchema] = []    # Erweitertes Einwand-Format (Detail-Editor)
    # Phase 08.19.1 D-01: Editor schreibt einwaende + phasen top-level (nie in basis.*)
    einwaende: List[dict] = []   # war faelschlicherweise in BasisSchema (Dead Field dort)
    phasen: List[dict] = []      # war faelschlicherweise in BasisSchema (Dead Field dort)
    # Phase 08.19.1: produkt in 2/6 Production-Profilen — KEY-FINDINGS.md; in v4-Migration pruefen ob entfernen oder behalten
    produkt: Any = None          # Production-Key aus KEY-FINDINGS.md — Phase 08.19.1; in v4-Migration pruefen ob entfernen oder behalten
    # opener und pitch werden NICHT modelliert (D-01) — canonical: ProfileOpener-Tabelle
    # erlaubnis eliminiert (D-06)


# ── Read-Sub-Schemas (extra='ignore' + Any-Typen fuer Drift-Toleranz) ────────
# Echte Profil-Daten koennen Typ-Drift enthalten (z.B. List statt str, dict statt str).
# Read-Sub-Schemas sind permissiv: extra='ignore' + Any fuer drift-anfaellige Felder.

class _ZielgruppeReadSchema(BaseModel):
    """Permissive Read-Variante: beruflicher_hintergrund kann str oder List sein (Drift)."""
    model_config = ConfigDict(extra='ignore')
    berufsstatus: str = ''
    beruflicher_hintergrund: Any = ''    # Drift: war List[str] in alten Profilen
    vorwissen: str = ''
    entscheidungsverhalten: Any = []     # Drift: war str in einigen alten Profilen


class _KiReadSchema(BaseModel):
    """Permissive Read-Variante: extra='ignore' fuer antwortlaenge/sensitivitaet etc."""
    model_config = ConfigDict(extra='ignore')
    anrede: str = 'Sie'
    ansprache: str = ''
    ton: str = ''
    zusatz: str = ''


class _ZielkundeReadSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')
    unternehmensgroesse: Any = None
    buying_committee: str = ''
    statusquo: str = ''
    zeithorizont: Any = None


class _BasisReadSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')
    unternehmen: str = ''
    produktbeschreibung: str = ''
    branche: str = ''
    branche_kontext: str = ''
    usps: Any = []
    preismodell: str = ''
    konsequenz: str = ''
    eigene_formulierungen: Any = []
    beweise: Any = []
    tabu_begriffe: Any = []
    zielkunden: str = ''
    einwaende: Any = []
    phasen: Any = []


class _SchmerzenReadSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')
    schmerzpunkte: Any = []


class _MetaReadSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')
    firma: str = ''
    rolle: str = ''
    consent_text: str = ''


class _ValueReadSchema(BaseModel):
    model_config = ConfigDict(extra='ignore')
    roi_argumente: Any = []


# ── ProfileReadSchema (Read — extra='ignore') ────────────────────────────────

class ProfileReadSchema(BaseModel):
    """Read-Schema: permissive. Ignoriert unbekannte Felder (alte Drift-Felder).
    Verwendet permissive Sub-Schemas mit extra='ignore' und Any-Typen fuer
    drift-anfaellige Felder (z.B. nogos: List[dict] statt List[str] in alten Profilen).
    Nur nach _migrate_profile_data() verwenden — Migration bereinigt Felder zuerst.
    """
    model_config = ConfigDict(extra='ignore')
    schema_version: int = 2
    basis: _BasisReadSchema = _BasisReadSchema()
    zielgruppe: _ZielgruppeReadSchema = _ZielgruppeReadSchema()
    zielkunde: _ZielkundeReadSchema = _ZielkundeReadSchema()
    value: _ValueReadSchema = _ValueReadSchema()
    ki: _KiReadSchema = _KiReadSchema()
    schmerzen: _SchmerzenReadSchema = _SchmerzenReadSchema()
    meta: _MetaReadSchema = _MetaReadSchema()
    kaufsignale: Any = []
    nogos: Any = []              # Drift: war List[dict] in alten Profilen, jetzt List[str]
    wettbewerber: Any = []
    uebergaenge: Any = []
    techniken: Any = {}
    einwaende_detail: Any = []
    # Phase 08.19.1 D-01: top-level einwaende + phasen (kanonisch nach v3-Migration)
    einwaende: Any = []
    phasen: Any = []
    produkt: Any = None          # Production-Key aus KEY-FINDINGS.md — Phase 08.19.1


# ── Idempotente Migration v1 → v2 ────────────────────────────────────────────

def _migrate_profile_data(daten: dict) -> dict:
    """Idempotente Migration: schema_version v1 -> v2.

    Prueft schema_version. Wenn >= 2: unveraendert zurueck.
    Andernfalls:
      - Entfernt eliminierte Felder (D-06)
      - Setzt schema_version = 2
      - Kein DB-Zugriff (opener/pitch-Sync in app.py _migrate())

    Modifiziert daten in-place und gibt es zurueck (analog migrate_tabu_begriffe).
    """
    if not isinstance(daten, dict):
        daten = {}

    version = daten.get('schema_version') or 1    # None-safe: None/0 -> 1
    if version >= 2:
        return daten    # bereits migriert — idempotent

    # ── zielgruppe: B2C-Felder entfernen ─────────────────────────────────────
    zg = daten.get('zielgruppe', {})
    if isinstance(zg, dict):
        for b2c_key in ('alter', 'einkommensniveau', 'lebenssituation'):
            zg.pop(b2c_key, None)
        daten['zielgruppe'] = zg

    # ── schmerzen: trigger entfernen (geht in zielkunde.statusquo — Benutzer traegt manuell nach) ─
    schmerzen = daten.get('schmerzen', {})
    if isinstance(schmerzen, dict):
        schmerzen.pop('trigger', None)
        daten['schmerzen'] = schmerzen

    # ── ki: stil in ton mergen ────────────────────────────────────────────────
    ki = daten.get('ki', {})
    if isinstance(ki, dict):
        stil = ki.pop('stil', None)
        if stil and not ki.get('ton'):
            ki['ton'] = stil    # stil-Inhalt in ton uebernehmen wenn ton noch leer
        daten['ki'] = ki

    # ── opener aus daten-JSON entfernen (D-01) ───────────────────────────────
    # Sync in ProfileOpener-Tabelle erfolgt in app.py _migrate() (DB-Zugriff dort)
    # erlaubnis und pitch werden dual-written zurueck in daten (transitional bis 08.20)
    daten.pop('opener', None)

    # ── zielkunde anlegen falls fehlend (neue B2B-Felder D-07) ──────────────
    if 'zielkunde' not in daten:
        daten['zielkunde'] = {}

    # ── meta anlegen falls fehlend (D-04 consent_text dual-write) ────────────
    if not isinstance(daten.get('meta'), dict):
        daten['meta'] = {}

    # ── schema_version setzen ─────────────────────────────────────────────────
    daten['schema_version'] = 2

    return daten
