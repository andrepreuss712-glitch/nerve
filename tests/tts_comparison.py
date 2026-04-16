"""
TTS-Vergleich: ElevenLabs vs Azure Neural TTS
===============================================
Generiert dieselben Saetze in 4 Emotionen ueber beide Services.
Ausgabe: MP3-Dateien in tests/tts_samples/

Setup:
  1. pip install requests azure-cognitiveservices-speech
  2. Azure Speech Key holen: https://portal.azure.com -> Speech Services (Free F0 = 500K chars/mo gratis)
  3. AZURE_SPEECH_KEY und AZURE_SPEECH_REGION in .env eintragen

Usage:
  cd salesnerve
  python tests/tts_comparison.py
"""

import os
import sys
import json
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

ELEVENLABS_KEY = os.environ.get('ELEVENLABS_API_KEY', '')
AZURE_KEY      = os.environ.get('AZURE_SPEECH_KEY', '')
AZURE_REGION   = os.environ.get('AZURE_SPEECH_REGION', 'germanywestcentral')

OUTPUT_DIR = Path(__file__).parent / 'tts_samples'
OUTPUT_DIR.mkdir(exist_ok=True)

# ElevenLabs Voice: Conrad-aehnlich (maennlich, deutsch)
EL_VOICE_ID = 'N2lVS1w4EtoT3dr4eOWO'  # Callum
EL_MODEL_V2    = 'eleven_multilingual_v2'
EL_MODEL_FLASH = 'eleven_flash_v2_5'

# Azure Voice: Conrad Neural (deutsch, Emotion-Support)
AZ_VOICE = 'de-DE-ConradNeural'

# ── Testsaetze mit Emotionen ──────────────────────────────────────────────────

TEST_CASES = [
    {
        'emotion': 'neutral',
        'text': 'Ja, ich verstehe. Schicken Sie mir gerne weitere Informationen per Mail.',
        'azure_style': 'friendly',
        'azure_degree': '0.5',
        'el_stability': 0.5,
        'el_style': 0.0,
    },
    {
        'emotion': 'freundlich',
        'text': 'Das klingt wirklich interessant! Erzaehlen Sie mir mehr darueber, das wuerde uns sicher weiterhelfen.',
        'azure_style': 'friendly',
        'azure_degree': '2',
        'el_stability': 0.6,
        'el_style': 0.3,
    },
    {
        'emotion': 'gereizt',
        'text': 'Hoeren Sie, ich habe Ihnen doch gesagt, dass wir dafuer kein Budget haben. Warum rufen Sie nochmal an?',
        'azure_style': 'angry',
        'azure_degree': '1',
        'el_stability': 0.35,
        'el_style': 0.5,
    },
    {
        'emotion': 'wuetend',
        'text': 'Das ist jetzt wirklich das letzte Mal! Ich habe keine Zeit fuer sowas, streichen Sie meine Nummer!',
        'azure_style': 'angry',
        'azure_degree': '2',
        'el_stability': 0.2,
        'el_style': 0.8,
    },
]

# ── ElevenLabs ────────────────────────────────────────────────────────────────

def generate_elevenlabs(text: str, stability: float, style: float, filename: str, model: str = None) -> bool:
    if not ELEVENLABS_KEY:
        print(f'  [ElevenLabs] SKIP - Kein API Key')
        return False

    if model is None:
        model = EL_MODEL_V2

    label = 'v2' if 'v2' in model and 'flash' not in model else 'Flash'

    url = f'https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE_ID}'
    headers = {
        'Accept': 'audio/mpeg',
        'Content-Type': 'application/json',
        'xi-api-key': ELEVENLABS_KEY,
    }
    data = {
        'text': text,
        'model_id': model,
        'voice_settings': {
            'stability': stability,
            'similarity_boost': 0.75,
            'style': style,
            'use_speaker_boost': True,
        }
    }

    start = time.time()
    try:
        resp = requests.post(url, json=data, headers=headers, timeout=15)
        elapsed = time.time() - start
        if resp.status_code == 200:
            path = OUTPUT_DIR / filename
            path.write_bytes(resp.content)
            print(f'  [EL {label:5s}]  OK  {elapsed:.1f}s  -> {filename}')
            return True
        else:
            print(f'  [EL {label:5s}]  FEHLER {resp.status_code}: {resp.text[:100]}')
            return False
    except Exception as e:
        print(f'  [EL {label:5s}]  FEHLER: {e}')
        return False

# ── Azure Neural TTS ──────────────────────────────────────────────────────────

def generate_azure(text: str, style: str, degree: str, filename: str) -> bool:
    if not AZURE_KEY:
        print(f'  [Azure]      SKIP - Kein API Key (AZURE_SPEECH_KEY)')
        return False

    url = f'https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1'
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': 'audio-16khz-128kbitrate-mono-mp3',
    }

    ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
       xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="de-DE">
  <voice name="{AZ_VOICE}">
    <mstts:express-as style="{style}" styledegree="{degree}">
      {text}
    </mstts:express-as>
  </voice>
</speak>'''

    start = time.time()
    try:
        resp = requests.post(url, headers=headers, data=ssml.encode('utf-8'), timeout=15)
        elapsed = time.time() - start
        if resp.status_code == 200:
            path = OUTPUT_DIR / filename
            path.write_bytes(resp.content)
            print(f'  [Azure]      OK  {elapsed:.1f}s  -> {filename}')
            return True
        else:
            print(f'  [Azure]      FEHLER {resp.status_code}: {resp.text[:200]}')
            return False
    except Exception as e:
        print(f'  [Azure]      FEHLER: {e}')
        return False

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('=' * 60)
    print('TTS-Vergleich: ElevenLabs vs Azure Neural TTS')
    print('=' * 60)
    print(f'Output: {OUTPUT_DIR}/')
    print(f'ElevenLabs Key: {"Ja" if ELEVENLABS_KEY else "FEHLT"}')
    print(f'Azure Key:      {"Ja" if AZURE_KEY else "FEHLT"}')
    print()

    if not ELEVENLABS_KEY and not AZURE_KEY:
        print('Mindestens ein API Key muss gesetzt sein!')
        print('  ELEVENLABS_API_KEY=... in .env')
        print('  AZURE_SPEECH_KEY=... in .env')
        sys.exit(1)

    for i, tc in enumerate(TEST_CASES, 1):
        print(f'\n[{i}/4] Emotion: {tc["emotion"].upper()}')
        print(f'  Text: "{tc["text"][:60]}..."')

        generate_elevenlabs(
            tc['text'],
            tc['el_stability'],
            tc['el_style'],
            f'{i}_{tc["emotion"]}_elevenlabs_v2.mp3',
            model=EL_MODEL_V2,
        )

        generate_elevenlabs(
            tc['text'],
            tc['el_stability'],
            tc['el_style'],
            f'{i}_{tc["emotion"]}_elevenlabs_flash.mp3',
            model=EL_MODEL_FLASH,
        )

        generate_azure(
            tc['text'],
            tc['azure_style'],
            tc['azure_degree'],
            f'{i}_{tc["emotion"]}_azure.mp3',
        )

    print('\n' + '=' * 60)
    print(f'Fertig! Dateien in: {OUTPUT_DIR}/')
    print()
    print('Hoer dir die Vergleiche an:')
    for i, tc in enumerate(TEST_CASES, 1):
        print(f'  {tc["emotion"]:12s}  EL v2:    {i}_{tc["emotion"]}_elevenlabs_v2.mp3')
        print(f'  {" ":12s}  EL Flash: {i}_{tc["emotion"]}_elevenlabs_flash.mp3')
        print(f'  {" ":12s}  Azure:    {i}_{tc["emotion"]}_azure.mp3')
    print()
    print('Preise pro 1K Zeichen:  v2 = $0.30  |  Flash = $0.05  |  Azure = $0.016')


if __name__ == '__main__':
    main()
