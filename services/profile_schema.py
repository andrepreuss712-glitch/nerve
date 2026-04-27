"""
services/profile_schema.py
────────────────────────────────────────────────────────────────────
Phase 08.19: Pydantic v2 ProfileSchema + idempotente Migration.

Exports:
  - ProfileSchema        — Write-Schema (extra='forbid'), fuer wizard_create / bearbeiten
  - ProfileReadSchema    — Read-Schema  (extra='ignore'), fuer bearbeiten GET + alle Reader
  - _migrate_profile_data(daten: dict) -> dict
        Idempotent: v1 -> v2 upgrade. Prueft schema_version, entfernt
        eliminierte Felder, setzt neue Defaults, gibt schema_version=2 zurueck.

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

from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict

# ── Unternehmensgroesse Enum ────────────────────────────────────────────────
# Reviews v2: Diese Literal-Werte sind kanonisch. Plan 04 UI-Chips muessen exakt matchen.
UnternehmensgroesseEnum = Literal['<10', '10-50', '50-250', '250-1000', '1000+']

# ── Zeithorizont Enum ───────────────────────────────────────────────────────
ZeithorizontEnum = Literal['sofort', '3_monate', '6_monate', 'kein_druck']

# ── Einwand-Typ Enum ────────────────────────────────────────────────────────
EinwandTypEnum = Literal['echt', 'vorschiebe', 'unbekannt']


# ── Sub-Schemas (Write — extra='forbid') ────────────────────────────────────

class BasisSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')
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
    einwaende: List[str] = []
    phasen: List[dict] = []


class ZielgruppeSchema(BaseModel):
    """Training-relevante Felder (gelesen von _build_coaching_prompt). NICHT eliminieren."""
    model_config = ConfigDict(extra='forbid')
    berufsstatus: str = ''
    beruflicher_hintergrund: str = ''
    vorwissen: str = ''                      # Training-Pfad: claude_service.py Z.229
    entscheidungsverhalten: List[str] = []   # Training-Pfad: claude_service.py Z.230
    # B2C-Felder eliminiert: alter, einkommensniveau, lebenssituation (D-06)


class ZielkundeSchema(BaseModel):
    """Neue B2B-Felder aus 08.18-Literatur-Synthese (D-07)."""
    model_config = ConfigDict(extra='forbid')
    unternehmensgroesse: Optional[UnternehmensgroesseEnum] = None   # Pflicht-Wizard-Feld
    buying_committee: str = ''                                        # Detail-Editor
    statusquo: str = ''                                              # Detail-Editor (loest schmerzen.trigger ab)
    zeithorizont: Optional[ZeithorizontEnum] = None                  # Detail-Editor


class ValueSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')
    roi_argumente: List[str] = []    # Detail-Editor (D-07)


class EinwandDetailSchema(BaseModel):
    """Erweitertes Einwand-Objekt im Detail-Editor (einwaende[] als Liste von Dicts)."""
    model_config = ConfigDict(extra='forbid')
    einwand: str = ''
    varianten: List[str] = []
    gegenargument: str = ''
    technik: str = ''
    intensitaet: int = 3
    kurzlabel: str = ''
    kategorie: str = ''
    einwand_typ: EinwandTypEnum = 'unbekannt'    # NEU D-07


class KiSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')
    anrede: str = 'Sie'
    ansprache: str = ''
    ton: str = ''           # ki.stil eliminiert — Inhalt geht in ki.ton (D-06)
    zusatz: str = ''
    # ki.stil wird in _migrate_profile_data() in ki.ton gemergt


class SchmerzenSchema(BaseModel):
    """schmerzen.trigger eliminiert (D-06). Inhalte wandern in zielkunde.statusquo."""
    model_config = ConfigDict(extra='forbid')
    schmerzpunkte: List[dict] = []
    # trigger eliminiert


class MetaSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')
    firma: str = ''
    rolle: str = ''
    consent_text: str = ''    # D-04 dual-write (liest auch aus profiles.consent_text als Fallback)


# ── ProfileSchema (Write — extra='forbid') ──────────────────────────────────

class ProfileSchema(BaseModel):
    """Write-Schema: strict. Wird bei wizard_create() und bearbeiten() POST validiert.
    extra='forbid' wirft ValidationError bei unbekannten Feldern.
    """
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 2
    basis: BasisSchema = BasisSchema()
    zielgruppe: ZielgruppeSchema = ZielgruppeSchema()
    zielkunde: ZielkundeSchema = ZielkundeSchema()
    value: ValueSchema = ValueSchema()
    ki: KiSchema = KiSchema()
    schmerzen: SchmerzenSchema = SchmerzenSchema()
    meta: MetaSchema = MetaSchema()
    kaufsignale: List[dict] = []
    nogos: List[str] = []
    wettbewerber: List[dict] = []
    uebergaenge: List[dict] = []
    techniken: dict = {}
    einwaende_detail: List[EinwandDetailSchema] = []    # Erweitertes Einwand-Format (Detail-Editor)
    # opener und pitch werden NICHT modelliert (D-01) — canonical: ProfileOpener-Tabelle
    # erlaubnis eliminiert (D-06)


# ── ProfileReadSchema (Read — extra='ignore') ────────────────────────────────

class ProfileReadSchema(ProfileSchema):
    """Read-Schema: permissive. Ignoriert unbekannte Felder (alte Drift-Felder).
    Nur nach _migrate_profile_data() verwenden — Migration bereinigt Felder zuerst.
    """
    model_config = ConfigDict(extra='ignore')


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

    version = daten.get('schema_version', 1)
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

    # ── erlaubnis entfernen ───────────────────────────────────────────────────
    daten.pop('erlaubnis', None)

    # ── opener/pitch aus daten-JSON entfernen (D-01) ──────────────────────────
    # Sync in ProfileOpener-Tabelle erfolgt in app.py _migrate() (DB-Zugriff dort)
    daten.pop('opener', None)
    daten.pop('pitch', None)

    # ── schema_version setzen ─────────────────────────────────────────────────
    daten['schema_version'] = 2

    return daten
