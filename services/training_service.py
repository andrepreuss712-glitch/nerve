import json
import random
import requests
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY, ELEVENLABS_API_KEY

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Stimmen-Pools (ElevenLabs Voice IDs) ──────────────────────────────────────
VOICE_POOL_MALE = [
    {'id': 'nPczCjzI2devNBz1zQrb', 'name': 'Brian'},
    {'id': 'onwK4e9ZLuTAKqWW03F9', 'name': 'Daniel'},
    {'id': 'N2lVS1w4EtoT3dr4eOWO', 'name': 'Callum'},
    {'id': 'ErXwobaYiN019PkySvjV', 'name': 'Antoni'},
]
VOICE_POOL_FEMALE = [
    {'id': 'EXAVITQu4vr4xnSDxMaL', 'name': 'Bella'},
    {'id': '21m00Tcm4TlvDq8ikWAM', 'name': 'Rachel'},
    {'id': 'AZnzlk1XvdvUeBnXmlld', 'name': 'Domi'},
    {'id': 'LcfcDJNUP1GQjkzn1xUU', 'name': 'Emily'},
]
# backwards compat
VOICE_MALE   = VOICE_POOL_MALE[0]['id']
VOICE_FEMALE = VOICE_POOL_FEMALE[0]['id']

SCHWIERIGKEITEN = {
    'leicht': {
        'label': 'Einsteiger',
        'beschreibung': 'Kunde reagiert milder, mehr Geduld, gibt Hinweise.',
        'sekretaerin': False,
        'prompt_zusatz': """Du reagierst etwas milder als normalerweise. Du gibst dem Berater mehr Zeit, stellst Fragen die ihm helfen, und bringst maximal 1-2 leichte Einwände. Wenn er gut argumentiert, stimmst du zu."""
    },
    'mittel': {
        'label': 'Fortgeschritten',
        'beschreibung': 'Realistisches Verhalten, keine Geschenke.',
        'sekretaerin': False,
        'prompt_zusatz': """Du verhältst dich realistisch und fair. Du bringst 3-4 verschiedene Einwände (Preis, Zeit, Vertrauen, Vergleich). Du lässt dich überzeugen wenn die Argumente gut sind, aber nicht bei Floskeln. Du stellst kritische Rückfragen."""
    },
    'schwer': {
        'label': 'Experte',
        'beschreibung': 'Kunde auf Maximum, kein Fehler wird verziehen.',
        'sekretaerin': False,
        'prompt_zusatz': """Du bist auf Maximum. Du bringst 5+ Einwände, darunter Vorwände ohne echten Grund, versteckte Einwände, und einen Abbruch-Versuch. Du unterbrichst den Berater gelegentlich. Du vergleichst aktiv mit Wettbewerbern. Nur ein wirklich überzeugender Berater kann dich rumdrehen."""
    },
    'sekretaerin': {
        'label': 'Sekretärin + Chef',
        'beschreibung': 'Erst die Sekretärin überwinden, dann den Entscheider überzeugen.',
        'sekretaerin': True,
        'prompt_zusatz': """Du bist ein skeptischer Entscheider. Bevor der Berater
zu dir durchgestellt wurde, musste er erst deine Sekretärin überwinden.
Du weißt dass er kalt anruft. Du bist beschäftigt und gibst ihm
maximal 2 Minuten. Wenn er dich in dieser Zeit nicht fesselt,
beendest du das Gespräch höflich aber bestimmt."""
    }
}

# ── Sekretaerin-Typen (D-06) ─────────────────────────────────────────────────
SEKRETAERIN_TYPES = {
    'blockerin': {
        'label': 'Professionelle Blockerin',
        'beschreibung': 'Höflich aber eisern. Lässt niemanden ohne guten Grund durch.',
        'icon': '\U0001F6E1',
        'prompt_basis': """Du bist {sek_name}, Sekretärin/Assistentin von {chef_name} bei {firma}.
Du bist professionell, höflich, aber absolut eisern. Deine Aufgabe: Deinen Chef vor unerwünschten Anrufen schützen.
VERHALTEN:
- Du fragst sofort: "Um was geht es?" / "Haben Sie einen Termin?"
- Du akzeptierst keine vagen Antworten. Du willst Konkretes hören.
- Typische Blocker: "Herr {chef_name} ist im Meeting", "Schicken Sie eine E-Mail"
- Du lässt dich NUR durchstellen, wenn der Anrufer einen glasklaren geschäftlichen Nutzen für deinen Chef nennt.
- Du bist NIE unhöflich, aber bestimmt.
{geduld}
WICHTIG: Du darfst KEINE eigene Kaufentscheidung treffen. Du stellst nur durch oder blockst ab.
WENN DU DURCHSTELLST: Antworte EXAKT mit: "Einen Moment bitte, ich verbinde Sie. [DURCHGESTELLT]"
WENN DU BLOCKST: Sage "Tut mir leid, Herr {chef_name} ist leider nicht erreichbar. Ich kann ihm etwas ausrichten." und füge [AUFGELEGT] ans Ende an.""",
    },
    'helferin': {
        'label': 'Neugierige Helferin',
        'beschreibung': 'Fragt nach, stellt gerne durch wenn der Nutzen klar ist.',
        'icon': '\U0001F91D',
        'prompt_basis': """Du bist {sek_name}, Sekretärin/Assistentin von {chef_name} bei {firma}.
Du bist hilfsbereit und neugierig. Du hörst gerne zu und interessierst dich aufrichtig für das Anliegen.
VERHALTEN:
- Du fragst freundlich nach: "Oh, erzählen Sie mal, worum geht es?"
- Du stellst Folgefragen: "Das klingt interessant, was genau machen Sie?"
- Du bist grundsätzlich bereit durchzustellen, brauchst aber einen nachvollziehbaren Grund.
- Wenn der Anrufer sympathisch und überzeugend ist, stellst du durch.
- Wenn er vage bleibt oder dich abspeist, wirst du vorsichtiger.
{geduld}
WICHTIG: Du darfst KEINE eigene Kaufentscheidung treffen. Du stellst nur durch oder blockst ab.
WENN DU DURCHSTELLST: Antworte EXAKT mit: "Einen Moment bitte, ich verbinde Sie. [DURCHGESTELLT]"
WENN DU BLOCKST: Sage "Tut mir leid, ich glaube das passt gerade nicht. Soll ich ihm etwas ausrichten?" und füge [AUFGELEGT] ans Ende an.""",
    },
    'abwimmlerin': {
        'label': 'Gestresste Abwimmlerin',
        'beschreibung': 'Hat keine Zeit. Will dich loswerden.',
        'icon': '\u23F0',
        'prompt_basis': """Du bist {sek_name}, Sekretärin/Assistentin von {chef_name} bei {firma}.
Du bist gestresst, hast viel zu tun und keine Lust auf Vertriebler. Du willst das Gespräch so schnell wie möglich beenden.
VERHALTEN:
- Du antwortest kurz und genervt: "Ja? Was gibts?"
- Du unterbrichst: "Kommen Sie zum Punkt" / "Ich hab wenig Zeit"
- Du versuchst sofort abzuwimmeln: "Schicken Sie ne Mail", "Kein Interesse", "Er ist nicht da"
- Nur wenn der Anrufer WIRKLICH überzeugend ist und dich in 1-2 Sätzen fesselt, lässt du ihn durch.
- Sonst legst du auf.
{geduld}
WICHTIG: Du darfst KEINE eigene Kaufentscheidung treffen. Du stellst nur durch oder blockst ab.
WENN DU DURCHSTELLST: Antworte EXAKT mit: "Einen Moment bitte, ich verbinde Sie. [DURCHGESTELLT]"
WENN DU BLOCKST: Sage "Nee, tut mir leid. Tschüss." und füge [AUFGELEGT] ans Ende an.""",
    },
}

# ── Persoenlichkeitstypen (System-Konstante, gespiegelt aus DB-Seed) ──────────
PERSONALITY_TYPES_SEED = [
    {
        'name': 'Beschäftigter Chef',
        'icon': '\U0001F4BC',  # briefcase emoji
        'kurzbeschreibung': 'Hat keine Zeit. Komm zum Punkt oder er legt auf.',
        'startstimmung': -2,
        'geduld': 1,
        'skeptik': 3,
        'zeitdruck': 5,
    },
    {
        'name': 'Skeptiker',
        'icon': '\U0001F914',  # thinking emoji
        'kurzbeschreibung': 'Hinterfragt alles. Braucht harte Fakten, keine Floskeln.',
        'startstimmung': -1,
        'geduld': 3,
        'skeptik': 5,
        'zeitdruck': 2,
    },
    {
        'name': 'Analytiker',
        'icon': '\U0001F4CA',  # bar_chart emoji
        'kurzbeschreibung': 'Will Zahlen, Daten, Fakten. Emotionen prallen ab.',
        'startstimmung': 0,
        'geduld': 4,
        'skeptik': 4,
        'zeitdruck': 2,
    },
    {
        'name': 'Freundlicher Ja-Sager',
        'icon': '\U0001F60A',  # smile emoji
        'kurzbeschreibung': 'Nett, aber kauft nie. Die Herausforderung: echtes Commitment.',
        'startstimmung': 1,
        'geduld': 5,
        'skeptik': 1,
        'zeitdruck': 1,
    },
    {
        'name': 'Aggressiver',
        'icon': '\U0001F4A2',  # anger emoji
        'kurzbeschreibung': 'Laut, direkt, provozierend. Ruhe bewahren ist der Schlüssel.',
        'startstimmung': -3,
        'geduld': 2,
        'skeptik': 3,
        'zeitdruck': 4,
    },
    {
        'name': 'Entscheider',
        'icon': '\U0001F451',  # crown emoji
        'kurzbeschreibung': 'Kein Drama, schnelle Entscheidung. Passt oder passt nicht.',
        'startstimmung': 0,
        'geduld': 3,
        'skeptik': 2,
        'zeitdruck': 3,
    },
]

# ── Sprachen ───────────────────────────────────────────────────────────────────
TRAINING_LANGUAGES = {
    'de': {
        'label': 'Deutsch', 'flag': '🇩🇪',
        'deepgram_code': 'de',
        'elevenlabs_model': 'eleven_multilingual_v2',
        'prompt_sprache': 'Antworte auf Deutsch.',
        'freizeichen': {'hz': 425, 'on': 1.0, 'off': 4.0},
        'audio_freizeichen': '/static/audio/freizeichen_de.mp3',
        'ui': {
            'warte': 'Kunde antwortet…',
            'aufnehmen': 'Aufnahme… loslassen zum Senden',
            'transkribiere': 'Transkribiere…',
            'hilfe_laedt': '💡 Lädt…',
            'hilfe_btn': '💡 Was soll ich sagen?',
            'transkription_fehler': 'Transkription fehlgeschlagen — bitte nochmal',
            'senden': 'Senden →',
            'beenden': '■ Beenden',
            'phase_sek': 'Sekretärin',
            'phase_kunde': 'Entscheider',
            'verbindet': 'Verbinde mit',
            'durchgestellt': '✓ Durchgestellt zu',
        },
    },
    'en': {
        'label': 'English', 'flag': '🇬🇧',
        'deepgram_code': 'en',
        'elevenlabs_model': 'eleven_multilingual_v2',
        'prompt_sprache': 'Respond in English.',
        'freizeichen': {'hz': 440, 'on': 2.0, 'off': 4.0},
        'audio_freizeichen': '/static/audio/freizeichen_en.mp3',
        'ui': {
            'warte': 'Customer responding…',
            'aufnehmen': 'Recording… release to send',
            'transkribiere': 'Transcribing…',
            'hilfe_laedt': '💡 Loading…',
            'hilfe_btn': '💡 What should I say?',
            'transkription_fehler': 'Transcription failed — please try again',
            'senden': 'Send →',
            'beenden': '■ End call',
            'phase_sek': 'Secretary',
            'phase_kunde': 'Decision maker',
            'verbindet': 'Connecting to',
            'durchgestellt': '✓ Connected to',
        },
    },
    'fr': {
        'label': 'Français', 'flag': '🇫🇷',
        'deepgram_code': 'fr',
        'elevenlabs_model': 'eleven_multilingual_v2',
        'prompt_sprache': 'Réponds en français.',
        'freizeichen': {'hz': 440, 'on': 1.5, 'off': 3.5},
        'audio_freizeichen': '/static/audio/freizeichen_fr.mp3',
        'ui': {
            'warte': 'Client répond…',
            'aufnehmen': 'Enregistrement… relâcher pour envoyer',
            'transkribiere': 'Transcription…',
            'hilfe_laedt': '💡 Chargement…',
            'hilfe_btn': '💡 Que dire ?',
            'transkription_fehler': 'Échec de la transcription — réessayez',
            'senden': 'Envoyer →',
            'beenden': '■ Fin appel',
            'phase_sek': 'Secrétaire',
            'phase_kunde': 'Décideur',
            'verbindet': 'Connexion à',
            'durchgestellt': '✓ Connecté à',
        },
    },
    'es': {
        'label': 'Español', 'flag': '🇪🇸',
        'deepgram_code': 'es',
        'elevenlabs_model': 'eleven_multilingual_v2',
        'prompt_sprache': 'Responde en español.',
        'freizeichen': {'hz': 425, 'on': 1.5, 'off': 3.0},
        'audio_freizeichen': '/static/audio/freizeichen_es.mp3',
        'ui': {
            'warte': 'Cliente respondiendo…',
            'aufnehmen': 'Grabando… suelta para enviar',
            'transkribiere': 'Transcribiendo…',
            'hilfe_laedt': '💡 Cargando…',
            'hilfe_btn': '💡 ¿Qué debo decir?',
            'transkription_fehler': 'Error de transcripción — inténtalo de nuevo',
            'senden': 'Enviar →',
            'beenden': '■ Terminar',
            'phase_sek': 'Secretaria',
            'phase_kunde': 'Decisor',
            'verbindet': 'Conectando con',
            'durchgestellt': '✓ Conectado con',
        },
    },
    'it': {
        'label': 'Italiano', 'flag': '🇮🇹',
        'deepgram_code': 'it',
        'elevenlabs_model': 'eleven_multilingual_v2',
        'prompt_sprache': 'Rispondi in italiano.',
        'freizeichen': {'hz': 425, 'on': 1.0, 'off': 4.0},
        'audio_freizeichen': '/static/audio/freizeichen_it.mp3',
        'ui': {
            'warte': 'Cliente risponde…',
            'aufnehmen': 'Registrazione… rilascia per inviare',
            'transkribiere': 'Trascrizione…',
            'hilfe_laedt': '💡 Caricamento…',
            'hilfe_btn': '💡 Cosa devo dire?',
            'transkription_fehler': 'Trascrizione fallita — riprova',
            'senden': 'Invia →',
            'beenden': '■ Termina',
            'phase_sek': 'Segretaria',
            'phase_kunde': 'Decisore',
            'verbindet': 'Collegamento con',
            'durchgestellt': '✓ Collegato con',
        },
    },
    'nl': {
        'label': 'Nederlands', 'flag': '🇳🇱',
        'deepgram_code': 'nl',
        'elevenlabs_model': 'eleven_multilingual_v2',
        'prompt_sprache': 'Antwoord in het Nederlands.',
        'freizeichen': {'hz': 425, 'on': 1.0, 'off': 4.0},
        'audio_freizeichen': '/static/audio/freizeichen_nl.mp3',
        'ui': {
            'warte': 'Klant antwoordt…',
            'aufnehmen': 'Opname… loslaten om te verzenden',
            'transkribiere': 'Transcriberen…',
            'hilfe_laedt': '💡 Laden…',
            'hilfe_btn': '💡 Wat moet ik zeggen?',
            'transkription_fehler': 'Transcriptie mislukt — probeer opnieuw',
            'senden': 'Verzenden →',
            'beenden': '■ Beëindigen',
            'phase_sek': 'Secretaresse',
            'phase_kunde': 'Beslisser',
            'verbindet': 'Verbinden met',
            'durchgestellt': '✓ Verbonden met',
        },
    },
    'pl': {
        'label': 'Polski', 'flag': '🇵🇱',
        'deepgram_code': 'pl',
        'elevenlabs_model': 'eleven_multilingual_v2',
        'prompt_sprache': 'Odpowiedz po polsku.',
        'freizeichen': {'hz': 425, 'on': 1.0, 'off': 4.0},
        'audio_freizeichen': '/static/audio/freizeichen_pl.mp3',
        'ui': {
            'warte': 'Klient odpowiada…',
            'aufnehmen': 'Nagrywanie… puść aby wysłać',
            'transkribiere': 'Transkrypcja…',
            'hilfe_laedt': '💡 Ładowanie…',
            'hilfe_btn': '💡 Co powinienem powiedzieć?',
            'transkription_fehler': 'Transkrypcja nieudana — spróbuj ponownie',
            'senden': 'Wyślij →',
            'beenden': '■ Zakończ',
            'phase_sek': 'Sekretarka',
            'phase_kunde': 'Decydent',
            'verbindet': 'Łączenie z',
            'durchgestellt': '✓ Połączono z',
        },
    },
    'pt': {
        'label': 'Português', 'flag': '🇧🇷',
        'deepgram_code': 'pt',
        'elevenlabs_model': 'eleven_multilingual_v2',
        'prompt_sprache': 'Responda em português.',
        'freizeichen': {'hz': 425, 'on': 1.0, 'off': 4.0},
        'audio_freizeichen': '/static/audio/freizeichen_pt.mp3',
        'ui': {
            'warte': 'Cliente respondendo…',
            'aufnehmen': 'Gravando… solte para enviar',
            'transkribiere': 'Transcrevendo…',
            'hilfe_laedt': '💡 Carregando…',
            'hilfe_btn': '💡 O que devo dizer?',
            'transkription_fehler': 'Transcrição falhou — tente novamente',
            'senden': 'Enviar →',
            'beenden': '■ Encerrar',
            'phase_sek': 'Secretária',
            'phase_kunde': 'Tomador de decisão',
            'verbindet': 'Conectando com',
            'durchgestellt': '✓ Conectado com',
        },
    },
    'tr': {
        'label': 'Türkçe', 'flag': '🇹🇷',
        'deepgram_code': 'tr',
        'elevenlabs_model': 'eleven_multilingual_v2',
        'prompt_sprache': 'Türkçe yanıt ver.',
        'freizeichen': {'hz': 450, 'on': 2.0, 'off': 4.0},
        'audio_freizeichen': '/static/audio/freizeichen_tr.mp3',
        'ui': {
            'warte': 'Müşteri yanıtlıyor…',
            'aufnehmen': 'Kayıt… göndermek için bırakın',
            'transkribiere': 'Transkript…',
            'hilfe_laedt': '💡 Yükleniyor…',
            'hilfe_btn': '💡 Ne demeliyim?',
            'transkription_fehler': 'Transkripsiyon başarısız — tekrar deneyin',
            'senden': 'Gönder →',
            'beenden': '■ Bitir',
            'phase_sek': 'Sekreter',
            'phase_kunde': 'Karar verici',
            'verbindet': 'Bağlanıyor:',
            'durchgestellt': '✓ Bağlandı:',
        },
    },
}

# ── Namen-Pools ────────────────────────────────────────────────────────────────
NAMEN_POOL = {
    'de': {
        'vornamen_m':   ['Thomas', 'Michael', 'Stefan', 'Andreas', 'Markus',
                         'Christian', 'Daniel', 'Martin', 'Frank', 'Jens'],
        'nachnamen':    ['Richter', 'Wagner', 'Becker', 'Hoffmann', 'Schäfer',
                         'Koch', 'Bauer', 'Möller', 'Krause', 'Braun'],
        'sek_vornamen': ['Lisa', 'Julia', 'Anna', 'Sarah', 'Laura',
                         'Katharina', 'Marie', 'Lena', 'Christina', 'Sandra'],
        'firmen':       ['TechVision GmbH', 'Nordstahl AG', 'MediaPlan Solutions',
                         'Grünwald Consulting', 'ProFit Verwaltung GmbH',
                         'InnoWerk Systems', 'Bergmann & Partner', 'DataStream AG',
                         'EcoTrade GmbH', 'Hanseatische Logistik AG'],
        'positionen':   ['Geschäftsführer', 'Vertriebsleiter', 'Head of Sales',
                         'Abteilungsleiter Vertrieb', 'Sales Director',
                         'Leiter Geschäftsentwicklung'],
    },
    'en': {
        'vornamen_m':   ['James', 'John', 'Robert', 'Michael', 'William',
                         'David', 'Richard', 'Thomas', 'Charles', 'Daniel'],
        'nachnamen':    ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones',
                         'Garcia', 'Miller', 'Davis', 'Wilson', 'Taylor'],
        'sek_vornamen': ['Emma', 'Olivia', 'Ava', 'Isabella', 'Sophia',
                         'Mia', 'Charlotte', 'Amelia', 'Harper', 'Evelyn'],
        'firmen':       ['TechCorp Ltd', 'Global Solutions Inc', 'Atlas Consulting',
                         'Meridian Group', 'Apex Systems LLC', 'Nexus Technologies',
                         'Sterling & Partners', 'Horizon Analytics',
                         'Pinnacle Services', 'Summit Logistics'],
        'positionen':   ['CEO', 'VP of Sales', 'Head of Sales', 'Sales Director',
                         'Managing Director', 'Business Development Director'],
    },
    'fr': {
        'vornamen_m':   ['Jean', 'Pierre', 'Michel', 'Philippe', 'Alain',
                         'Laurent', 'Nicolas', 'Christophe', 'François', 'Marc'],
        'nachnamen':    ['Martin', 'Bernard', 'Dubois', 'Thomas', 'Robert',
                         'Richard', 'Petit', 'Durand', 'Leroy', 'Moreau'],
        'sek_vornamen': ['Marie', 'Sophie', 'Isabelle', 'Nathalie', 'Céline',
                         'Émilie', 'Julie', 'Aurélie', 'Camille', 'Laure'],
        'firmen':       ['TechVision SA', 'Groupe Horizon', 'Solutions Atlantique',
                         'Conseil Lumière', 'InnoTech SARL', 'Atlantis Consulting',
                         'Beaumont & Associés', 'DataFlow SA',
                         'EcoCommerce SAS', 'Logistique Nationale'],
        'positionen':   ['Directeur Général', 'Directeur Commercial',
                         'Responsable des Ventes', 'Chef de Département',
                         'Directeur des Ventes', 'Responsable du Développement'],
    },
}
# Fall back to English pool for remaining languages
for _lang in ['es', 'it', 'nl', 'pl', 'pt', 'tr']:
    NAMEN_POOL[_lang] = NAMEN_POOL['en']

# ── Prompts ────────────────────────────────────────────────────────────────────
SEKRETAERIN_PROMPT = """Du bist die Sekretärin/Assistentin von {chef_name} bei der Firma {firma}.
Du heißt {sek_name}.

DEIN VERHALTEN:
- Du bist professionell und freundlich, aber deine Aufgabe ist es
  deinen Chef vor unwichtigen Anrufen zu schützen
- Du fragst IMMER: "Um was geht es denn?" / "Haben Sie einen Termin?" /
  "Worum handelt es sich?"
- Du sagst NICHT einfach "Ich stelle durch" — der Anrufer muss dich überzeugen
- Typische Blocker: "Herr {chef_name} ist gerade in einem Meeting",
  "Können Sie mir eine E-Mail schicken?", "Worum geht es konkret?"
- Wenn der Anrufer überzeugend ist und einen guten Grund nennt,
  stellst du durch mit: "Einen Moment, ich verbinde."
- Wenn der Anrufer schlecht ist, blockst du ab mit:
  "Ich richte ihm das aus" oder "Schicken Sie eine Mail"
- Du brauchst 2-4 Austausche bevor du durchstellst (wenn überhaupt)
- Antworte IMMER kurz, 1-2 Sätze, wie eine echte Sekretärin am Telefon
- Kein Markdown, reiner gesprochener Text

WICHTIG: Wenn du durchstellst, antworte EXAKT mit dem Text:
"Einen Moment bitte, ich verbinde Sie. [DURCHGESTELLT]"
Das [DURCHGESTELLT] ist das Signal für das System.
"""

KUNDEN_PROMPT_TEMPLATE = """Du bist ein potenzieller Kunde in einem Trainings-Verkaufsgespräch.
Der Berater versucht dir folgendes zu verkaufen: {produkt}

DEINE ROLLE:
- Du heißt {name}, bist {alter}, {position} bei {firma}
- Du hast {team_size} Mitarbeiter
- Du hast den Anruf angenommen/wurdest durchgestellt
- Du sprichst natürlich, wie ein echter Mensch —
  kurze Sätze, manchmal "ähm" oder "naja"

SCHWIERIGKEITSGRAD — {schwierigkeit_label}:
{schwierigkeit_prompt}

TYPISCHE EINWÄNDE DIE DU NUTZEN KANNST:
{einwaende}

REGELN:
- Antworte IMMER als der Kunde, nie als KI
- Maximal 2-3 Sätze pro Antwort
- Reagiere natürlich auf das was der Berater sagt
- Kein Markdown, keine Sternchen — reiner gesprochener Text
- Starte mit einer kurzen Begrüßung
"""

TRAINING_PERSONA_PROMPT_BASE = KUNDEN_PROMPT_TEMPLATE


def _random_persona(sprache: str = 'de') -> dict:
    pool = NAMEN_POOL.get(sprache, NAMEN_POOL['en'])
    return {
        'chef_vorname':   random.choice(pool['vornamen_m']),
        'chef_nachname':  random.choice(pool['nachnamen']),
        'chef_alter':     random.randint(38, 55),
        'chef_position':  random.choice(pool['positionen']),
        'chef_team_size': random.randint(5, 40),
        'firma':          random.choice(pool['firmen']),
        'sek_name':       random.choice(pool['sek_vornamen']) + ' ' + random.choice(pool['nachnamen']),
        'voice_male':     random.choice(VOICE_POOL_MALE),
        'voice_female':   random.choice(VOICE_POOL_FEMALE),
    }


def build_sekretaerin_prompt(persona: dict, sprache: str = 'de') -> str:
    lang = TRAINING_LANGUAGES.get(sprache, TRAINING_LANGUAGES['de'])
    base = SEKRETAERIN_PROMPT.format(
        chef_name=persona['chef_nachname'],
        firma=persona['firma'],
        sek_name=persona['sek_name'],
    )
    return base + f"\n\n{lang['prompt_sprache']}"


def build_sekretaerin_type_prompt(persona: dict, sekretaerin_typ: str,
                                   schwierigkeit: str, sprache: str = 'de') -> str:
    """Build typed secretary prompt with difficulty-based patience modifier."""
    lang = TRAINING_LANGUAGES.get(sprache, TRAINING_LANGUAGES['de'])
    typ  = SEKRETAERIN_TYPES.get(sekretaerin_typ, SEKRETAERIN_TYPES['blockerin'])
    geduld_map = {
        'leicht': 'GEDULD: Du bist vergleichsweise geduldig. Der Anrufer hat 3-4 Austausche Zeit dich zu überzeugen.',
        'mittel': 'GEDULD: Du gibst dem Anrufer 2-3 Austausche. Dann entscheidest du.',
        'schwer': 'GEDULD: Du hast wenig Geduld. Nach 1-2 Austauschen ist Schluss wenn nichts Überzeugendes kommt.',
    }
    geduld = geduld_map.get(schwierigkeit, geduld_map['mittel'])
    prompt = typ['prompt_basis'].format(
        chef_name=persona['chef_nachname'],
        firma=persona['firma'],
        sek_name=persona['sek_name'],
        geduld=geduld,
    )
    prompt += f"\n\nAntworte IMMER kurz, 1-2 Sätze, wie eine echte Sekretärin am Telefon.\nKein Markdown, reiner gesprochener Text."
    prompt += f"\n\n{lang['prompt_sprache']}"
    return prompt


def build_customer_prompt(profile_data: dict, schwierigkeit: str, persona: dict,
                          sprache: str = 'de') -> str:
    lang       = TRAINING_LANGUAGES.get(sprache, TRAINING_LANGUAGES['de'])
    diff       = SCHWIERIGKEITEN.get(schwierigkeit, SCHWIERIGKEITEN['mittel'])
    basis      = profile_data.get('basis', {})
    zielgruppe = profile_data.get('zielgruppe', {})
    schmerzen  = profile_data.get('schmerzen', {})
    einwaende  = profile_data.get('einwaende', [])
    wettbew    = profile_data.get('wettbewerber', [])
    ki         = profile_data.get('ki', {})
    produkt    = basis.get('produktbeschreibung') or profile_data.get('produkt', 'ein Produkt')
    einw_liste = "\n".join(
        f"- '{e.get('einwand','')}'" +
        (f" (auch: {', '.join(e['varianten'][:2])})" if e.get('varianten') else '')
        for e in einwaende[:6] if e.get('einwand')
    )
    if not einw_liste:
        einw_liste = "- Das ist mir zu teuer\n- Ich muss das erstmal intern besprechen\n- Wir haben sowas schon"
    zusatz = []
    if zielgruppe.get('vorwissen') == 'hoch':
        zusatz.append('Du hast hohes Fachwissen — stelle technische Detailfragen.')
    elif zielgruppe.get('vorwissen') == 'gering':
        zusatz.append('Du hast wenig Vorwissen — stelle einfache Grundfragen.')
    if zielgruppe.get('entscheidungsverhalten'):
        zusatz.append(f'Dein Entscheidungsverhalten: {", ".join(zielgruppe["entscheidungsverhalten"])}')
    schmerzpunkte = schmerzen.get('schmerzpunkte', [])
    if schmerzpunkte and isinstance(schmerzpunkte[0], dict) and schmerzpunkte[0].get('situation'):
        zusatz.append(f'Dein Hauptproblem: {schmerzpunkte[0]["situation"]}')
    wettb_namen = [w.get('name','') for w in wettbew if w.get('name')]
    if wettb_namen:
        zusatz.append(f'Du kennst die Konkurrenz ({", ".join(wettb_namen[:3])}) — vergleiche gelegentlich.')
    ansprache = ki.get('ansprache', 'Du')
    zusatz.append(f'Sprich den Berater mit "{ansprache}" an.')
    base = KUNDEN_PROMPT_TEMPLATE.format(
        produkt=produkt,
        name=f"{persona['chef_vorname']} {persona['chef_nachname']}",
        alter=persona['chef_alter'],
        position=persona['chef_position'],
        firma=persona['firma'],
        team_size=persona['chef_team_size'],
        schwierigkeit_label=diff['label'],
        schwierigkeit_prompt=diff['prompt_zusatz'],
        einwaende=einw_liste,
    )
    if zusatz:
        base += '\n\nZUSATZ-KONTEXT:\n' + '\n'.join(zusatz)
    return base + f"\n\n{lang['prompt_sprache']}"


# ── Personality-Driven Training (Phase 04.9) ──────────────────────────────────

AUFLEGE_REGELN = {
    'leicht': """Einsteiger-Modus:
- Setze letzte_chance=true wenn Stimmung auf -4 faellt (IMMER warnen vor Auflegen)
- Setze aufgelegt=true NUR wenn Stimmung auf -5 faellt UND du schon letzte_chance gegeben hast
- Gib dem Berater immer eine zweite Chance""",
    'mittel': """Fortgeschritten-Modus:
- Setze letzte_chance=true bei weichen Triggern (z.B. zu viel reden, generisch) wenn Stimmung <= -3
- Setze aufgelegt=true bei harten Triggern OHNE Warnung
- Setze aufgelegt=true wenn Stimmung auf -5 faellt""",
    'schwer': """Experte-Modus:
- KEINE letzte_chance Warnung — setze letzte_chance IMMER auf false
- Setze aufgelegt=true SOFORT bei harten Triggern
- Setze aufgelegt=true wenn Stimmung auf -4 faellt (strenger als andere Modi)""",
}

PERSONALITY_MOOD_PROMPT_SUFFIX = """
STIMMUNGS-TRACKING:
Deine aktuelle Stimmung: {current_mood} (Skala: -5 = kurz vor Auflegen, +5 = kaufbereit)

Berechne nach jeder Antwort des Beraters deine neue Stimmung.
Regeln fuer Stimmungsaenderungen:
- Konkreter Nutzen ohne Umschweife: +1
- Ehrliche Antwort auf kritische Frage: +1
- Gute Frage statt Pitch: +1
- Verstaendnis fuer meine Situation: +2
- Ruhig unter Druck: +1
- Generischer Opener: -2
- Zu frueh pitchen: -1
- Ausweichen bei direkter Frage: -2
- Uebertriebene Versprechen: -1
- Zu viel reden: -1
- Preis vor Bedarfsanalyse: -2

AUFLEGE-LOGIK ({schwierigkeit}):
{auflege_regeln}

HARTE AUFLEGE-TRIGGER (persoenlichkeitsabhaengig):
{hart_trigger}

Antworte IMMER als valides JSON (kein Text davor oder danach):
{{
  "text": "Deine gesprochene Antwort als Kunde (1-3 Saetze, kein Markdown)",
  "neue_stimmung": <int zwischen -5 und +5>,
  "aufgelegt": false,
  "letzte_chance": false
}}
"""


def build_personality_prompt(profile_data: dict, personality_data: dict,
                             schwierigkeit: str, current_mood: int,
                             sprache: str = 'de', szenario: dict = None) -> str:
    """Build system prompt for personality-driven training with mood tracking."""
    lang = TRAINING_LANGUAGES.get(sprache, TRAINING_LANGUAGES['de'])

    # Base profile context (reuse existing pattern from build_customer_prompt)
    produkt = profile_data.get('produkt', 'ein Produkt')
    branche = profile_data.get('branche', 'B2B')
    einwaende = profile_data.get('einwaende', [])

    # Personality-specific behavior
    name = personality_data.get('name', 'Kunde')
    verhaltensregeln = personality_data.get('verhaltensregeln', '')
    position = personality_data.get('position_profil', 'Geschaeftskontakt')
    vorgeschichte = personality_data.get('vorgeschichte', '')
    beispiel_reaktionen = personality_data.get('beispiel_reaktionen', [])

    # Scenario context
    szenario_ctx = ''
    if szenario:
        szenario_ctx = f"""
SZENARIO:
Situation: {szenario.get('kunde_situation', '')}
Dein Verhalten: {szenario.get('kunde_verhalten', '')}
Spezielle Einwaende die du bringen sollst: {szenario.get('spezial_einwaende', '[]')}
"""

    # Hard triggers from personality
    hart_trigger_list = personality_data.get('auflege_trigger_hart', [])
    hart_trigger = '\n'.join(f'- {t}' for t in hart_trigger_list) if hart_trigger_list else '- Keine speziellen harten Trigger'

    # Auflege rules per difficulty
    auflege_regeln = AUFLEGE_REGELN.get(schwierigkeit, AUFLEGE_REGELN['mittel'])

    prompt = f"""Du bist {name}, {position}. Du fuehrst ein Telefonat mit einem Vertriebler.

DEINE PERSOENLICHKEIT:
{verhaltensregeln}
{'Vorgeschichte: ' + vorgeschichte if vorgeschichte else ''}
Beispiel-Reaktionen: {json.dumps(beispiel_reaktionen, ensure_ascii=False)}

DER BERATER VERKAUFT:
Produkt: {produkt}
Branche: {branche}
Bekannte Einwaende: {json.dumps([e.get('name', e) if isinstance(e, dict) else e for e in einwaende], ensure_ascii=False)}

{szenario_ctx}

{lang.get('prompt_sprache', 'Antworte auf Deutsch.')}
"""

    # Append mood tracking suffix
    mood_suffix = PERSONALITY_MOOD_PROMPT_SUFFIX.format(
        current_mood=current_mood,
        schwierigkeit=schwierigkeit,
        auflege_regeln=auflege_regeln,
        hart_trigger=hart_trigger
    )

    return prompt + mood_suffix


def generate_response(conversation_history: list, system_prompt: str) -> str:
    messages = []
    for msg in conversation_history:
        role = "assistant" if msg['speaker'] == 'kunde' else "user"
        messages.append({"role": role, "content": msg['text']})

    if not messages:
        messages = [{"role": "user", "content": "(Telefon klingelt. Geh ran.)"}]

    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        system=system_prompt,
        messages=messages
    )
    return response.content[0].text.strip()


def generate_response_with_mood(
    conversation_history: list,
    system_prompt: str,
    current_mood: int,
    schwierigkeit: str = 'mittel',
) -> dict:
    """Returns dict with keys: text, neue_stimmung, aufgelegt, letzte_chance.

    Falls back gracefully on JSON parse failure: returns plain text with unchanged mood.
    Used for personality-driven training (Phase 04.9). The original generate_response()
    remains for sekretaerin mode which does not need mood tracking.
    """
    messages = []
    for msg in conversation_history:
        role = "assistant" if msg['speaker'] == 'kunde' else "user"
        messages.append({"role": role, "content": msg['text']})
    if not messages:
        messages = [{"role": "user", "content": "(Telefon klingelt. Geh ran.)"}]

    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=system_prompt,
        messages=messages
    )
    text = response.content[0].text.strip()

    # Parse JSON from response (same pattern as generate_scoring)
    start = text.find('{')
    end   = text.rfind('}') + 1
    if start == -1 or end <= start:
        # Fallback: no JSON found, treat as plain text
        print(f"[Training] Mood JSON parse: no braces found, falling back to plain text")
        return {
            'text': text,
            'neue_stimmung': current_mood,
            'aufgelegt': False,
            'letzte_chance': False
        }
    try:
        parsed = json.loads(text[start:end])
        # Validate required keys exist
        result = {
            'text': parsed.get('text', text),
            'neue_stimmung': int(parsed.get('neue_stimmung', current_mood)),
            'aufgelegt': bool(parsed.get('aufgelegt', False)),
            'letzte_chance': bool(parsed.get('letzte_chance', False)),
        }
        # Clamp mood to valid range
        result['neue_stimmung'] = max(-5, min(5, result['neue_stimmung']))
        return result
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"[Training] Mood JSON parse error: {e}, falling back to plain text")
        return {
            'text': text,
            'neue_stimmung': current_mood,
            'aufgelegt': False,
            'letzte_chance': False
        }


def generate_help_suggestion(conversation_history: list, profile_data: dict,
                             sprache: str = 'de') -> str:
    lang     = TRAINING_LANGUAGES.get(sprache, TRAINING_LANGUAGES['de'])
    gespraech = "\n".join(
        f"[{'Berater' if m['speaker'] == 'berater' else 'Kunde'}] {m['text']}"
        for m in conversation_history[-6:]
    )
    basis    = profile_data.get('basis', {})
    ki       = profile_data.get('ki', {})
    einwaende= profile_data.get('einwaende', [])
    produkt  = basis.get('produktbeschreibung') or profile_data.get('produkt', '')
    usps     = basis.get('usps') or profile_data.get('usps', [])
    ansprache= ki.get('ansprache', 'Du')
    einw_str = ''
    if einwaende:
        einw_str = '\nBekannte Gegenargumente:\n' + '\n'.join(
            f"- {e.get('einwand','')}: {e.get('gegenargument','')}"
            for e in einwaende[:4] if e.get('gegenargument')
        )

    prompt = f"""Du bist ein Vertriebscoach. Der Berater steckt in einem
Trainingsgespräch und braucht Hilfe. Was sollte er als nächstes sagen?

Produkt: {produkt}
USPs: {", ".join(usps)}{einw_str}

Letzte Gesprächszeilen:
{gespraech}

Gib EINEN konkreten Antwortvorschlag (2-3 Sätze) den der Berater
jetzt sagen könnte. Sprich den Kunden mit "{ansprache}" an.
Kein Markdown, reiner Text. Ende mit einer offenen Frage.

{lang['prompt_sprache']}"""

    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def generate_scoring(conversation_history: list, profile_data: dict,
                     schwierigkeit: str, sekretaerin_ueberwunden: bool,
                     sprache: str = 'de', modus: str = 'guided',
                     hilfe_count: int = 0,
                     stimmung_history: list = None) -> dict:
    lang      = TRAINING_LANGUAGES.get(sprache, TRAINING_LANGUAGES['de'])
    gespraech = "\n".join(
        f"[{'Berater' if m['speaker'] == 'berater' else m.get('rolle', 'Kunde')}] {m['text']}"
        for m in conversation_history
    )

    sek_bonus = ""
    if sekretaerin_ueberwunden:
        sek_bonus = "\n6. Sekretärin überwunden — Hat er die Sekretärin professionell überzeugt? (1-10)"

    sek_json = ', {"name": "Sekretärin", "score": 7, "feedback": "1 Satz"}' if sekretaerin_ueberwunden else ''

    # ── 6. Beziehungsaufbau category (D-14) — only when stimmung_history is present ──
    beziehung_kategorie = ""
    beziehung_json = ""
    stimmung_kontext = ""
    wendepunkte_prompt = ""
    wendepunkte_json_example = ""
    if stimmung_history:
        stimmung_kontext = f"""
Stimmungsverlauf des Kunden waehrend des Gespraechs:
{json.dumps(stimmung_history, ensure_ascii=False)}
"""
        beziehung_kategorie = "\n6. Beziehungsaufbau — Hat der Berater die Stimmung des Kunden positiv beeinflusst? Hat er Rapport aufgebaut? (1-10)"
        beziehung_json = ', {{"name": "Beziehungsaufbau", "score": 6, "feedback": "1 Satz"}}'
        wendepunkte_prompt = "\nIdentifiziere die 1-3 kritischen Wendepunkte im Gespraech wo die Stimmung signifikant gefallen ist. Fuer jeden Wendepunkt: was hat der Berater gesagt, was war das Problem, und was haette er stattdessen sagen sollen."
        wendepunkte_json_example = """,
  "wendepunkte_detail": [
    {{"turn": 3, "berater_sagt": "Was der Berater gesagt hat", "was_schief": "Was schiefging", "alternativ": "Was er haette sagen sollen"}}
  ]"""

    if modus == 'free':
        modus_info = "Der Berater hat im FREIEN Modus trainiert — ohne jede Hilfestellung. Bewerte entsprechend strenger."
    else:
        modus_info = f"Der Berater hat im GEFÜHRTEN Modus trainiert und {hilfe_count}x den Hilfe-Button genutzt."

    prompt = f"""Analysiere dieses Trainings-Verkaufsgespräch und bewerte den Berater.
Schwierigkeitsgrad: {schwierigkeit}
{'Sekretärin-Modus war aktiv.' if sekretaerin_ueberwunden else ''}
{modus_info}

Gespräch:
{gespraech}
{stimmung_kontext}
Bewerte in diesen Kategorien (jeweils 1-10):
1. Gesprächseröffnung — Guter Einstieg?
2. Bedarfsanalyse — Richtige Fragen gestellt?
3. Einwandbehandlung — Einwände gut entkräftet?
4. Gesprächsführung — Gespräch kontrolliert, offene Fragen?
5. Abschluss — Klaren nächsten Schritt vereinbart?{beziehung_kategorie}{sek_bonus}
{wendepunkte_prompt}
Extrahiere ausserdem die 1-3 besten Saetze des Beraters, die einen Einwand erfolgreich entkraeftet haben (Wendepunkt-Saetze). Wenn keine erkennbar sind, gib ein leeres Array zurueck.

Antworte NUR als valides JSON:
{{
  "gesamt_score": 0,
  "kategorien": [
    {{"name": "Gesprächseröffnung", "score": 7, "feedback": "1 Satz"}},
    {{"name": "Bedarfsanalyse", "score": 5, "feedback": "1 Satz"}},
    {{"name": "Einwandbehandlung", "score": 8, "feedback": "1 Satz"}},
    {{"name": "Gesprächsführung", "score": 6, "feedback": "1 Satz"}},
    {{"name": "Abschluss", "score": 4, "feedback": "1 Satz"}}{beziehung_json}{sek_json}
  ],
  "staerken": ["Stärke 1", "Stärke 2"],
  "verbesserungen": ["Verbesserung 1", "Verbesserung 2", "Verbesserung 3"],
  "zusammenfassung": "2-3 Sätze Gesamtbewertung",
  "wendepunkt_saetze": [
    {{"text": "Konkreter Satz des Beraters der den Einwand erfolgreich behandelt hat", "einwand_typ": "Name des Einwands"}}
  ]{wendepunkte_json_example}
}}

{lang['prompt_sprache']}"""

    response = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    text   = response.content[0].text.strip()
    start  = text.find('{')
    end    = text.rfind('}') + 1
    if start == -1 or end <= start:
        raise ValueError(f"No JSON braces in Claude response: {text[:100]}")
    try:
        result = json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Scoring JSON parse failed: {e}") from e

    # ── Basis-Punkte (D-16) ────────────────────────────────────────────────────
    gesamt = result.get('gesamt_score', 0)
    bonus  = max(0, gesamt - 50)  # bonus for scores above 50
    result['punkte'] = 10 + bonus  # 10 base points + score bonus

    return result


def _generate_live_preview(conversation_history: list, profile_data: dict) -> dict:
    """Zeigt was der Live-Assistent im echten Call angezeigt hätte."""
    gespraech = "\n".join(
        f"[{'Berater' if m['speaker'] == 'berater' else 'Kunde'}] {m['text']}"
        for m in conversation_history
    )

    prompt = f"""Analysiere dieses Verkaufsgespräch als wärst du ein Live-Vertriebsassistent der in Echtzeit mithört.

Gespräch:
{gespraech}

Gib für die wichtigsten Momente im Gespräch an was du dem Berater LIVE angezeigt hättest. Antworte als JSON:

{{
    "momente": [
        {{
            "nach_zeile": 3,
            "kunde_sagte": "Das ist mir zu teuer",
            "einwand_typ": "Kosten/Preis",
            "gegenargument": "Konkreter Vorschlag was der Berater hätte sagen sollen",
            "coaching_tipp": "Konkreter Tipp für diesen Moment",
            "painpoint": "Erkannter Schmerzpunkt oder leer lassen"
        }}
    ],
    "zusammenfassung": "In diesem Gespräch hätte NERVE dir an X Stellen geholfen. Besonders bei [konkretem Moment] hättest du eine bessere Antwort bekommen."
}}

Finde 2-4 der wichtigsten Momente. Sei konkret — keine generischen Phrasen."""

    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    text  = response.content[0].text.strip()
    start = text.find('{')
    end   = text.rfind('}') + 1
    if start == -1 or end <= start:
        return {'momente': [], 'zusammenfassung': ''}
    try:
        return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        return {'momente': [], 'zusammenfassung': ''}


def text_to_speech(text: str, voice_id: str = None,
                   model: str = 'eleven_multilingual_v2') -> bytes:
    if not ELEVENLABS_API_KEY:
        return None

    if not voice_id:
        voice_id = VOICE_POOL_MALE[0]['id']

    url     = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        if response.status_code == 200:
            # ── Phase 04.7.2 Cost-Hook: TTS-Zeichen ────────────────────────────
            try:
                from services.cost_tracker import log_api_cost
                char_units = len(text or '') / 1000.0
                if char_units > 0:
                    uid = None
                    try:
                        from flask import g
                        uid = getattr(getattr(g, 'user', None), 'id', None)
                    except Exception:
                        uid = None
                    log_api_cost('elevenlabs', 'multilingual-v2', user_id=uid,
                                 units=char_units, unit_type='per_1k_chars',
                                 context_tag='training_tts')
            except Exception as _e:
                print(f"[CostHook] elevenlabs tts skipped: {_e}")
            # ────────────────────────────────────────────────────────────────────
            return response.content
        print(f"[ElevenLabs] Fehler {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[ElevenLabs] Exception: {e}")
    return None
