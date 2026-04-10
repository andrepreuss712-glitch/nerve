#!/usr/bin/env python3
"""
Generate telephone audio files for NERVE training simulation.

Creates 13 MP3 audio files in static/audio/:
  - 9 language-specific freizeichen (dial tones)
  - 4 universal signals (klingeln, besetztzeichen, verbindungston, wartemusik)

Uses numpy for waveform generation, wave module for WAV output,
and ffmpeg for WAV->MP3 conversion (falls back to .wav-in-.mp3 if ffmpeg unavailable).

Re-runnable: `python tools/generate_audio.py`
"""

import os
import wave
import struct
import subprocess
import shutil
import tempfile
import numpy as np

SAMPLE_RATE = 44100
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'audio')

# Check ffmpeg availability once
FFMPEG = shutil.which('ffmpeg')


def _write_wav(filepath, samples):
    """Write float32 numpy array (-1..1) as 16-bit mono WAV."""
    pcm = np.clip(samples, -1.0, 1.0)
    pcm16 = (pcm * 32767).astype(np.int16)
    with wave.open(filepath, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())


def _save_mp3(name, samples):
    """Save samples as MP3 (via ffmpeg) or WAV-in-MP3-extension fallback."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    mp3_path = os.path.join(OUTPUT_DIR, name)

    if FFMPEG:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_wav = tmp.name
        try:
            _write_wav(tmp_wav, samples)
            subprocess.run([
                FFMPEG, '-y', '-i', tmp_wav,
                '-codec:a', 'libmp3lame', '-b:a', '128k', '-ar', '44100',
                mp3_path
            ], capture_output=True, check=True)
        finally:
            if os.path.exists(tmp_wav):
                os.unlink(tmp_wav)
    else:
        # Fallback: save as WAV with .mp3 extension (browsers handle this)
        print(f'  [WARN] No ffmpeg — saving {name} as WAV-in-MP3-extension')
        _write_wav(mp3_path, samples)


def _tone(freq, duration, volume=0.15):
    """Generate a sine wave tone."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    return volume * np.sin(2 * np.pi * freq * t)


def _silence(duration):
    """Generate silence."""
    return np.zeros(int(SAMPLE_RATE * duration))


def _dual_tone(freq1, freq2, duration, volume=0.15):
    """Generate dual-frequency tone (e.g., US dial tone)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    return volume * (np.sin(2 * np.pi * freq1 * t) + np.sin(2 * np.pi * freq2 * t)) / 2


def _fade_in_out(samples, fade_ms=10):
    """Apply short fade in/out to avoid clicks."""
    fade_len = int(SAMPLE_RATE * fade_ms / 1000)
    if len(samples) < fade_len * 2:
        return samples
    samples = samples.copy()
    samples[:fade_len] *= np.linspace(0, 1, fade_len)
    samples[-fade_len:] *= np.linspace(1, 0, fade_len)
    return samples


# ── Freizeichen generators ──────────────────────────────────────────────────────

def gen_freizeichen_de():
    """Germany: 425 Hz, 1s on / 4s off, ~8s total, loopable."""
    parts = []
    for _ in range(2):  # 2 cycles = ~10s
        parts.append(_fade_in_out(_tone(425, 1.0)))
        parts.append(_silence(4.0))
    return np.concatenate(parts)


def gen_freizeichen_en():
    """US/UK: 440+480 Hz dual tone, 2s on / 4s off."""
    parts = []
    for _ in range(2):
        parts.append(_fade_in_out(_dual_tone(440, 480, 2.0)))
        parts.append(_silence(4.0))
    return np.concatenate(parts)


def gen_freizeichen_fr():
    """France: 440 Hz, 1.5s on / 3.5s off."""
    parts = []
    for _ in range(2):
        parts.append(_fade_in_out(_tone(440, 1.5)))
        parts.append(_silence(3.5))
    return np.concatenate(parts)


def gen_freizeichen_es():
    """Spain: 425 Hz, 1.5s on / 3.0s off."""
    parts = []
    for _ in range(2):
        parts.append(_fade_in_out(_tone(425, 1.5)))
        parts.append(_silence(3.0))
    return np.concatenate(parts)


def gen_freizeichen_it():
    """Italy: 425 Hz, 1.0s on / 4.0s off."""
    parts = []
    for _ in range(2):
        parts.append(_fade_in_out(_tone(425, 1.0)))
        parts.append(_silence(4.0))
    return np.concatenate(parts)


def gen_freizeichen_nl():
    """Netherlands: 425 Hz, 1.0s on / 4.0s off."""
    parts = []
    for _ in range(2):
        parts.append(_fade_in_out(_tone(425, 1.0)))
        parts.append(_silence(4.0))
    return np.concatenate(parts)


def gen_freizeichen_pl():
    """Poland: 425 Hz, 1.0s on / 4.0s off."""
    parts = []
    for _ in range(2):
        parts.append(_fade_in_out(_tone(425, 1.0)))
        parts.append(_silence(4.0))
    return np.concatenate(parts)


def gen_freizeichen_pt():
    """Portugal: 425 Hz, 1.0s on / 5.0s off."""
    parts = []
    for _ in range(2):
        parts.append(_fade_in_out(_tone(425, 1.0)))
        parts.append(_silence(5.0))
    return np.concatenate(parts)


def gen_freizeichen_tr():
    """Turkey: 450 Hz, 1.0s on / 4.0s off."""
    parts = []
    for _ in range(2):
        parts.append(_fade_in_out(_tone(450, 1.0)))
        parts.append(_silence(4.0))
    return np.concatenate(parts)


# ── Universal signals ──────────────────────────────────────────────────────────

def gen_klingeln():
    """Classic phone ring: 440+480 Hz alternating burst, ~4s loopable.
    Pattern: 0.4s on / 0.2s off / 0.4s on / 2s pause."""
    parts = []
    for _ in range(2):
        parts.append(_fade_in_out(_dual_tone(440, 480, 0.4, volume=0.2)))
        parts.append(_silence(0.2))
        parts.append(_fade_in_out(_dual_tone(440, 480, 0.4, volume=0.2)))
        parts.append(_silence(2.0))
    return np.concatenate(parts)


def gen_besetztzeichen():
    """Busy signal: 425 Hz, 0.5s on / 0.5s off, ~4s loopable."""
    parts = []
    for _ in range(4):
        parts.append(_fade_in_out(_tone(425, 0.5, volume=0.2)))
        parts.append(_silence(0.5))
    return np.concatenate(parts)


def gen_verbindungston():
    """Connection click: short low-pass filtered white noise burst, ~0.1s."""
    n_samples = int(SAMPLE_RATE * 0.1)
    noise = np.random.randn(n_samples) * 0.15
    # Simple low-pass via moving average
    kernel_size = 20
    kernel = np.ones(kernel_size) / kernel_size
    filtered = np.convolve(noise, kernel, mode='same')
    # Envelope: quick attack, quick decay
    envelope = np.exp(-np.linspace(0, 8, n_samples))
    return _fade_in_out(filtered * envelope)


def gen_wartemusik():
    """Gentle hold music loop: ascending/descending major scale, ~8s.
    Uses sine waves at soft volume with gentle envelope."""
    # C major scale notes (Hz) starting from A3=220Hz
    # A3, B3, C4, D4, E4, F4, G4, A4
    notes = [220, 246.94, 261.63, 293.66, 329.63, 349.23, 392.00, 440.00]
    # Ascending then descending
    melody = notes + list(reversed(notes[:-1]))

    note_dur = 0.5  # seconds per note
    parts = []
    for freq in melody:
        t = np.linspace(0, note_dur, int(SAMPLE_RATE * note_dur), endpoint=False)
        # Sine with soft envelope
        envelope = np.sin(np.pi * t / note_dur)  # smooth bell curve
        note = 0.08 * np.sin(2 * np.pi * freq * t) * envelope
        parts.append(note)

    return np.concatenate(parts)


# ── Main ────────────────────────────────────────────────────────────────────────

FILES = {
    'freizeichen_de.mp3': gen_freizeichen_de,
    'freizeichen_en.mp3': gen_freizeichen_en,
    'freizeichen_fr.mp3': gen_freizeichen_fr,
    'freizeichen_es.mp3': gen_freizeichen_es,
    'freizeichen_it.mp3': gen_freizeichen_it,
    'freizeichen_nl.mp3': gen_freizeichen_nl,
    'freizeichen_pl.mp3': gen_freizeichen_pl,
    'freizeichen_pt.mp3': gen_freizeichen_pt,
    'freizeichen_tr.mp3': gen_freizeichen_tr,
    'klingeln.mp3': gen_klingeln,
    'besetztzeichen.mp3': gen_besetztzeichen,
    'verbindungston.mp3': gen_verbindungston,
    'wartemusik.mp3': gen_wartemusik,
}

if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f'[Audio] Generating {len(FILES)} files in {OUTPUT_DIR}')
    if FFMPEG:
        print(f'[Audio] Using ffmpeg: {FFMPEG}')
    else:
        print('[Audio] WARNING: ffmpeg not found, using WAV-in-MP3 fallback')

    for name, gen_fn in FILES.items():
        print(f'  Generating {name}...', end=' ')
        samples = gen_fn()
        _save_mp3(name, samples)
        size = os.path.getsize(os.path.join(OUTPUT_DIR, name))
        print(f'OK ({size:,} bytes)')

    print(f'[Audio] Done. {len(FILES)} files generated.')
