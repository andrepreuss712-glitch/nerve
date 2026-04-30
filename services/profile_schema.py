"""
services/profile_schema.py
────────────────────────────────────────────────────────────────────
Phase 08.19: Pydantic v2 ProfileSchema + idempotente Migration.
Phase 08.19.1: schema_version v2 -> v3. einwaende + phasen top-level in ProfileSchema,
  Dead Fields aus BasisSchema entfernt. extra='forbid' aktiviert in Plan-05.

Exports:
  - ProfileSchema        — Write-Schema (extra='forbid'), fuer wizard_create / bearbeiten
  - ProfileReadSchema    — Read-Schema  (extra='ignore'), fuer bearbeiten GET + alle Reader
  - _migrate_profile_data(daten: dict) -> dict
        Idempotent: v1 -> v2 -> v3 upgrade. Prueft schema_version, entfernt
        eliminierte Felder, setzt neue Defaults, gibt schema_version=3 zurueck.
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

# ── Schema-Version Konstante ────────────────────────────────────────────────
# Kanonische Zielversion fuer alle Migrations-Checks (app.py Batch + wizard_create).
LATEST_SCHEMA_VERSION = 4

# ── Unternehmensgroesse Enum ────────────────────────────────────────────────
# Reviews v2: Diese Literal-Werte sind kanonisch. Plan 04 UI-Chips muessen exakt matchen.
UnternehmensgroesseEnum = Literal['<10', '10-50', '50-250', '250-1000', '1000+']

# ── Zeithorizont Enum ───────────────────────────────────────────────────────
ZeithorizontEnum = Literal['sofort', '3_monate', '6_monate', 'kein_druck']

# ── Einwand-Typ Enum ────────────────────────────────────────────────────────
EinwandTypEnum = Literal['echt', 'vorschiebe', 'unbekannt']


# ── Sub-Schemas (Write-Schemas: extra='forbid' — Schema kalibriert, v3-Migration abgeschlossen) ───

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
    # einwaende + phasen wurden in Phase 08.19.1 nach top-level ProfileSchema verschoben
    # (Editor schreibt seit Phase 08 ausschliesslich top-level — basis.* waren Dead Fields)


class ZielgruppeSchema(BaseModel):
    """Training-relevante Felder (gelesen von _build_coaching_prompt). NICHT eliminieren."""
    model_config = ConfigDict(extra='forbid')
    berufsstatus: str = ''
    beruflicher_hintergrund: Union[str, List[str]] = ''
    vorwissen: str = ''                      # Training-Pfad: claude_service.py Z.229
    entscheidungsverhalten: List[str] = []   # Training-Pfad: claude_service.py Z.230
    # B2C-Felder eliminiert: alter, einkommensniveau, lebenssituation (D-06)
    # position/unternehmen/branche entfernt (F3): Dead Fields per Grep-Analyse — nie in Live-Pfaden gelesen


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
    antwortlaenge: str = ''  # Production-Feld: KI-Antwortlaenge-Konfiguration
    # sensitivitaet entfernt (Phase 08.19.2 Entscheidung — kommt in 08.20 als Lead-Picker zurueck)
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


# ── ProfileSchema (extra='forbid') ──────────────────────────────────────────

class ProfileSchema(BaseModel):
    """Write-Schema: strict (extra='forbid'). Phase 08.19.1: Schema kalibriert,
    alle Profile auf v3 migriert. model_validate() gegen alle Production-Profile
    ohne Fehler verifiziert.
    """
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 3
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
    # produkt entfernt (F4): in _migrate_profile_data() in basis.produktbeschreibung gerettet dann gedroppt
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
    # einwaende und phasen entfernt — nach v3-Migration ausschliesslich top-level in ProfileReadSchema


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
    schema_version: int = 3
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
    # produkt entfernt (F4) — Migration rettet Inhalt in basis.produktbeschreibung


# ── Idempotente Migration v1 → v2 ────────────────────────────────────────────

def _migrate_profile_data(daten: dict) -> dict:
    """Idempotente Migration: schema_version v1 -> v2 -> v3.

    Prueft schema_version. Wenn >= 3: unveraendert zurueck.
    Andernfalls:
      v1->v2: Entfernt eliminierte Felder (D-06), setzt schema_version = 2
      v2->v3: einwaende/phasen upward-merge aus basis.*, fragen+branche entfernen,
              setzt schema_version = 3 (Phase 08.19.1)
      - Kein DB-Zugriff (opener/pitch-Sync in app.py _migrate())

    Modifiziert daten in-place und gibt es zurueck (analog migrate_tabu_begriffe).
    """
    if not isinstance(daten, dict):
        daten = {}

    version = daten.get('schema_version') or 1    # None-safe: None/0 -> 1
    if version >= 4:
        return daten    # bereits migriert — idempotent (v4 ist aktuell)

    # ── v1 → v2: B2C-Feldbereinigung + Basis-Cleanup ─────────────────────────
    # Nur fuer v1/v2-Profile — v3+ ueberspringen (bereits migriert)
    if version < 3:
        # ── zielgruppe: B2C-Felder entfernen ─────────────────────────────────
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

        # ── ki: stil in ton mergen ────────────────────────────────────────────
        ki = daten.get('ki', {})
        if isinstance(ki, dict):
            stil = ki.pop('stil', None)
            if stil and not ki.get('ton'):
                ki['ton'] = stil    # stil-Inhalt in ton uebernehmen wenn ton noch leer
            daten['ki'] = ki

        # ── opener aus daten-JSON entfernen (D-01) ───────────────────────────
        # Sync in ProfileOpener-Tabelle erfolgt in app.py _migrate() (DB-Zugriff dort)
        # erlaubnis und pitch werden dual-written zurueck in daten (transitional bis 08.20)
        daten.pop('opener', None)

        # ── zielkunde anlegen falls fehlend (neue B2B-Felder D-07) ──────────
        if 'zielkunde' not in daten:
            daten['zielkunde'] = {}

        # ── meta anlegen falls fehlend (D-04 consent_text dual-write) ────────
        if not isinstance(daten.get('meta'), dict):
            daten['meta'] = {}

        # ── schema_version setzen ─────────────────────────────────────────────
        daten['schema_version'] = 2

    # ── v2 → v3: Schema-Realitaet-Kalibrierung (Phase 08.19.1) ─────────────────
    version = daten.get('schema_version') or 1
    if version < 3:
        _audit_parts = []
        _profile_id = daten.get('_migration_profile_id', '?')  # wird von Batch-Migration gesetzt

        # Schritt 1: fragen-Key entfernen (war gesetzt auf [] in 08.19.3, jetzt komplett raus)
        if 'fragen' in daten:
            daten.pop('fragen', None)
            _audit_parts.append('dropped fragen')

        # F1: ki.sensitivitaet entfernen (Phase 08.19.2 explizit gestrichen — kommt in 08.20 als Lead-Picker zurueck)
        _ki = daten.get('ki')
        if isinstance(_ki, dict) and 'sensitivitaet' in _ki:
            _ki.pop('sensitivitaet', None)
            daten['ki'] = _ki
            _audit_parts.append('dropped ki.sensitivitaet')

        # F3: zielgruppe Legacy-Felder entfernen (nie in Live-Pfaden gelesen — Dead Fields per Grep-Analyse)
        _zielgruppe = daten.get('zielgruppe')
        if isinstance(_zielgruppe, dict):
            for _zg_key in ('position', 'unternehmen', 'branche'):
                if _zg_key in _zielgruppe:
                    _zielgruppe.pop(_zg_key)
                    _audit_parts.append(f'dropped zielgruppe.{_zg_key}')
            daten['zielgruppe'] = _zielgruppe

        # F4: produkt-Merge — in basis.produktbeschreibung retten wenn dort leer, dann immer droppen
        if 'produkt' in daten:
            _basis_in_migrate = daten.get('basis') if isinstance(daten.get('basis'), dict) else {}
            if not _basis_in_migrate.get('produktbeschreibung'):
                _basis_in_migrate['produktbeschreibung'] = daten['produkt']
                daten['basis'] = _basis_in_migrate
                _audit_parts.append('merged produkt -> basis.produktbeschreibung')
            else:
                _audit_parts.append('dropped produkt (basis.produktbeschreibung already set)')
            daten.pop('produkt', None)

        # Schritt 2: branche top-level entfernen (lebt auf Profile.branche DB-Column)
        if 'branche' in daten:
            daten.pop('branche', None)
            _audit_parts.append('dropped branche top-level')

        # Schritt 3: einwaende upward-merge (D-02 Semantik)
        basis = daten.get('basis') if isinstance(daten.get('basis'), dict) else {}
        _basis_einwaende = basis.get('einwaende')
        _top_einwaende = daten.get('einwaende', '__MISSING__')
        if _top_einwaende == '__MISSING__' or _top_einwaende is None:
            # Key fehlt oder ist null → basis.* hochziehen
            if _basis_einwaende is not None:
                daten['einwaende'] = _basis_einwaende
                _audit_parts.append('upward-merged basis.einwaende->einwaende')
        # Key existiert mit [] → basis.* NICHT hochziehen (User-Intent "alles geloescht")
        basis.pop('einwaende', None)

        # Schritt 4: phasen upward-merge (D-02 Semantik — analog zu einwaende)
        _basis_phasen = basis.get('phasen')
        _top_phasen = daten.get('phasen', '__MISSING__')
        if _top_phasen == '__MISSING__' or _top_phasen is None:
            if _basis_phasen is not None:
                daten['phasen'] = _basis_phasen
                _audit_parts.append('upward-merged basis.phasen->phasen')
        basis.pop('phasen', None)

        # basis-Referenz immer zurueckschreiben — leeres dict ist valid (Sub-Schema-Defaults greifen)
        daten['basis'] = basis

        # Schritt 5: schema_version auf 3 setzen
        daten['schema_version'] = 3

        if _audit_parts:
            print(f"[Schema] Profile {_profile_id}: v2->v3 applied — {', '.join(_audit_parts)}")
        else:
            print(f"[Schema] Profile {_profile_id}: v2->v3 applied — no changes needed")

        # D-03: Pflicht-Audit-Event pro Profil (persist in audit_log, nicht nur print)
        try:
            import json as _json_audit
            from database.db import get_session as _get_audit_session
            from database.models import AuditLog as _AuditLog
            _audit_db = _get_audit_session()
            try:
                _pid_int = int(_profile_id) if str(_profile_id).isdigit() else None
                _audit_entry = _AuditLog(
                    action='profile_schema_v2_to_v3',
                    target_type='profile',
                    target_id=_pid_int,
                    details=_json_audit.dumps({'audit_parts': _audit_parts, 'schema_version': 3}),
                )
                _audit_db.add(_audit_entry)
                _audit_db.commit()
            finally:
                _audit_db.close()
        except Exception as _audit_e:
            print(f"[Schema] Profile {_profile_id}: audit_log write failed (non-fatal): {_audit_e}")

    # ── v3 → v4: einwaende → einwaende_detail (Phase 08.20 D-04) ───────────────
    version = daten.get('schema_version') or 1
    if version < 4:
        _audit_parts = []
        _profile_id = daten.get('_migration_profile_id', '?')

        _einwaende = daten.get('einwaende') or []
        _einwaende_detail = daten.get('einwaende_detail') or []

        if _einwaende and not _einwaende_detail:
            _migrated = []
            for _e in _einwaende:
                if isinstance(_e, dict):
                    _migrated.append({
                        'einwand':       _e.get('einwand') or _e.get('text') or '',
                        'varianten':     _e.get('varianten') or [],
                        'gegenargument': _e.get('gegenargument') or _e.get('gegenargument_1') or '',
                        'technik':       _e.get('technik') or '',
                        'intensitaet':   _e.get('intensitaet') or 3,
                        'kurzlabel':     _e.get('kurzlabel') or '',
                        'kategorie':     _e.get('kategorie') or '',
                        'einwand_typ':   _e.get('einwand_typ') or 'unbekannt',
                    })
                elif isinstance(_e, str):
                    _migrated.append({
                        'einwand': _e, 'varianten': [], 'gegenargument': '',
                        'technik': '', 'intensitaet': 3, 'kurzlabel': '',
                        'kategorie': '', 'einwand_typ': 'unbekannt',
                    })
            daten['einwaende_detail'] = _migrated
            _audit_parts.append(f'migrated einwaende->einwaende_detail ({len(_migrated)} items)')

        daten.pop('einwaende', None)
        _audit_parts.append('dropped einwaende top-level')

        daten['schema_version'] = 4
        print(f"[Schema] Profile {_profile_id}: v3->v4 applied — {', '.join(_audit_parts)}")

        try:
            import json as _json_audit
            from database.db import get_session as _get_audit_session
            from database.models import AuditLog as _AuditLog
            _audit_db = _get_audit_session()
            try:
                _pid_int = int(_profile_id) if str(_profile_id).isdigit() else None
                _audit_entry = _AuditLog(
                    action='profile_schema_v3_to_v4',
                    target_type='profile',
                    target_id=_pid_int,
                    details=_json_audit.dumps({'audit_parts': _audit_parts, 'schema_version': 4}),
                )
                _audit_db.add(_audit_entry)
                _audit_db.commit()
            finally:
                _audit_db.close()
        except Exception as _audit_e:
            print(f"[Schema] Profile {_profile_id}: audit_log write failed (non-fatal): {_audit_e}")

    daten.pop('_migration_profile_id', None)
    return daten
