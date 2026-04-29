# KEY-FINDINGS: Production-Profil-Schema-Analyse
Datum: 2026-04-29 | Profile gesamt: 6

## Top-Level-Keys (alle Profile)
| Key | Vorkommt in N Profilen | Python-Typen |
|-----|------------------------|--------------|
| zielgruppe | 5/6 | dict |
| ki | 5/6 | dict |
| basis | 4/6 | dict |
| einwaende | 3/6 | list |
| kaufsignale | 3/6 | list |
| branche | 3/6 | str |
| produkt | 2/6 | str |
| phasen | 2/6 | list |
| wettbewerber | 2/6 | list |
| techniken | 2/6 | dict, list |
| uebergaenge | 2/6 | list |
| beschreibung | 1/6 | str |
| preismodell | 1/6 | dict |
| usps | 1/6 | list |
| konsequenz | 1/6 | str |
| schmerzpunkte | 1/6 | list |
| emotionale_trigger | 1/6 | dict |
| no_go | 1/6 | list |
| verbotene_phrasen | 1/6 | list |
| firma | 1/6 | str |
| zielkunden | 1/6 | str |
| rolle | 1/6 | str |
| opener | 1/6 | str |
| erlaubnis | 1/6 | str |
| pitch | 1/6 | str |
| schmerzen | 1/6 | dict |
| fragen | 1/6 | list |
| nogos | 1/6 | list |

## basis.*-Keys (alle Profile)
| Key | Vorkommt in N Profilen |
|-----|------------------------|
| produktbeschreibung | 4/6 |
| einwaende | 3/6 |
| phasen | 3/6 |
| unternehmen | 1/6 |
| preismodell | 1/6 |
| usps | 1/6 |
| konsequenz | 1/6 |
| eigene_formulierungen | 1/6 |
| beweise | 1/6 |
| branche_kontext | 1/6 |
| tabu_begriffe | 1/6 |

## Drift-Key-Verteilung (fuer Migration-Entscheidung)
- einwaende top-level: 3/6
- basis.einwaende: 3/6
- phasen top-level: 2/6
- basis.phasen: 3/6
- branche top-level: 3/6
- fragen key (soll entfernt werden): 1/6

## Ungemappte Keys (nicht in ProfileSchema v2)
Keys die im Production-Dump vorhanden sind aber NICHT in ProfileSchema v2 gelistet:
- beschreibung (in 1/6 Profilen)
- emotionale_trigger (in 1/6 Profilen)
- firma (in 1/6 Profilen)
- konsequenz (in 1/6 Profilen)
- no_go (in 1/6 Profilen)
- preismodell (in 1/6 Profilen)
- produkt (in 2/6 Profilen)
- rolle (in 1/6 Profilen)
- schmerzpunkte (in 1/6 Profilen)
- usps (in 1/6 Profilen)
- verbotene_phrasen (in 1/6 Profilen)
- zielkunden (in 1/6 Profilen)
