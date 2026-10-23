# sfx.py
"""
Procedural chiptune sound effects - no audio files needed.

Every sound is *synthesized at startup* from a tiny "recipe" (waveform,
frequency sweep, envelope), exactly like the sound chips of 80s arcade
cabinets did. The samples are generated in pure Python with the ``array``
module (no numpy), turned into ``pygame.mixer.Sound`` objects and cached.

If the audio device is missing (servers, some VMs, remote desktops) every
call silently becomes a no-op, so games never crash because of audio.

Usage:
    import sfx
    sfx.play("eat")
    sfx.set_enabled(False)   # mute
"""
from __future__ import annotations

import math
import random
from array import array
from dataclasses import dataclass

import pygame

# Ask for a small, low-latency mono mixer. This only has effect if it runs
# before pygame.init(); every game imports this module first, so it does.
try:
    pygame.mixer.pre_init(22050, -16, 1, 512)
except Exception:  # pragma: no cover - extremely old pygame builds
    pass

MASTER_VOLUME = 0.35


@dataclass(frozen=True)
class Tone:
    """One synthesized note.

    Attributes:
        freq: Start frequency in Hz.
        dur: Duration in seconds.
        wave: "square", "triangle", "saw" or "noise".
        end_freq: Frequency at the end (linear sweep). ``None`` = constant.
        vol: Relative volume 0..1.
        duty: Duty cycle for square waves (0.5 = classic, 0.125 = thin/nasal).
        attack: Attack time in seconds.
        vibrato: Vibrato depth in Hz (0 = none).
    """

    freq: float
    dur: float
    wave: str = "square"
    end_freq: float | None = None
    vol: float = 1.0
    duty: float = 0.5
    attack: float = 0.004
    vibrato: float = 0.0


def _note(name: str) -> float:
    """Convert a note name like ``"C5"`` or ``"F#4"`` into a frequency in Hz."""
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4,
             "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    pitch, octave = name[:-1], int(name[-1])
    semitones = names[pitch] + (octave - 4) * 12
    return 440.0 * (2.0 ** (semitones / 12.0))


def _arp(notes: str, step: float, wave: str = "square", vol: float = 0.8,
         duty: float = 0.5) -> list[Tone]:
    """Build an arpeggio/jingle from a space-separated list of note names."""
    return [Tone(_note(n), step, wave, vol=vol, duty=duty) for n in notes.split()]


# Recipes: name -> list of tones played one after the other.
RECIPES: dict[str, list[Tone]] = {
    # --- UI ---
    "select": [Tone(660, 0.04, duty=0.25, vol=0.6), Tone(990, 0.05, duty=0.25, vol=0.6)],
    "move": [Tone(520, 0.025, duty=0.25, vol=0.35)],
    "back": [Tone(500, 0.04, duty=0.25, vol=0.5), Tone(330, 0.06, duty=0.25, vol=0.5)],
    "launch": _arp("C5 E5 G5 C6", 0.055, duty=0.25),
    "pause": [Tone(880, 0.05, "triangle"), Tone(660, 0.07, "triangle")],
    # --- generic game events ---
    "blip": [Tone(880, 0.03, duty=0.25, vol=0.5)],
    "hit": [Tone(520, 0.045, duty=0.5, vol=0.7)],
    "wall": [Tone(260, 0.04, duty=0.5, vol=0.55)],
    "score": [Tone(660, 0.07, end_freq=1320, duty=0.25, vol=0.7)],
    "bonus": _arp("E5 G5 B5 E6", 0.05, duty=0.125, vol=0.7),
    "powerup": [Tone(400, 0.25, end_freq=1600, duty=0.25, vol=0.6, vibrato=25)],
    "hurt": [Tone(420, 0.28, end_freq=90, duty=0.5, vol=0.8)],
    "explosion": [Tone(1800, 0.35, "noise", end_freq=120, vol=0.9)],
    "small_explosion": [Tone(2400, 0.12, "noise", end_freq=500, vol=0.6)],
    "shoot": [Tone(1400, 0.11, end_freq=350, duty=0.25, vol=0.45)],
    "enemy_shoot": [Tone(700, 0.09, end_freq=250, duty=0.125, vol=0.3)],
    "ufo": [Tone(900, 0.4, "triangle", vol=0.45, vibrato=120)],
    "win": _arp("C5 E5 G5 C6 G5 C6", 0.09, duty=0.25),
    "lose": _arp("G4 E4 C4", 0.14, duty=0.5) + [Tone(_note("C3"), 0.3, "triangle")],
    "record": _arp("G5 C6 E6 G6 E6 G6", 0.07, duty=0.125),
    "error": [Tone(150, 0.12, duty=0.5, vol=0.6), Tone(120, 0.12, duty=0.5, vol=0.6)],
    # --- game specific ---
    "eat": [Tone(600, 0.06, end_freq=1100, duty=0.25, vol=0.6)],
    "rotate": [Tone(700, 0.03, "triangle", vol=0.5)],
    "drop": [Tone(3000, 0.06, "noise", end_freq=800, vol=0.5)],
    "line": _arp("C5 G5 C6", 0.05, duty=0.25),
    "tetris": _arp("C5 E5 G5 C6 E6 G6", 0.05, duty=0.125),
    "levelup": _arp("G4 C5 E5 G5", 0.07, duty=0.25),
    "flip": [Tone(480, 0.04, "triangle", end_freq=620, vol=0.5)],
    "match": _arp("E5 B5", 0.07, "triangle"),
    "brick": [Tone(780, 0.04, duty=0.25, vol=0.5)],
    "slide": [Tone(300, 0.04, "triangle", end_freq=200, vol=0.5)],
    "step": [Tone(_note("A2"), 0.07, "triangle", vol=0.8)],
    "step2": [Tone(_note("G2"), 0.07, "triangle", vol=0.8)],
    "step3": [Tone(_note("F2"), 0.07, "triangle", vol=0.8)],
    "step4": [Tone(_note("E2"), 0.07, "triangle", vol=0.8)],
    "place_x": [Tone(500, 0.05, duty=0.25, vol=0.6)],
    "place_o": [Tone(380, 0.05, "triangle", vol=0.7)],
}


def synthesize(tones: list[Tone], rate: int, seed: int = 1234) -> array:
    """
    Turn a list of tones into signed 16-bit mono samples.

    This is a pure function (no pygame needed), which makes it easy to test.

    Args:
        tones: The notes to render, played sequentially.
        rate: Sample rate in Hz.
        seed: Seed for the noise generator (deterministic output).

    Returns:
        ``array('h')`` of mono samples.
    """
    rng = random.Random(seed)
    out = array("h")
    peak = 32767 * MASTER_VOLUME
    for tone in tones:
        n = max(1, int(tone.dur * rate))
        attack_n = max(1, int(tone.attack * rate))
        phase = 0.0
        noise_val = 0.0
        noise_counter = 0.0
        end = tone.end_freq if tone.end_freq is not None else tone.freq
        for i in range(n):
            t = i / n
            freq = tone.freq + (end - tone.freq) * t
            if tone.vibrato:
                freq += tone.vibrato * math.sin(2 * math.pi * 7 * i / rate)
            phase = (phase + freq / rate) % 1.0
            if tone.wave == "square":
                s = 1.0 if phase < tone.duty else -1.0
            elif tone.wave == "triangle":
                s = 4.0 * abs(phase - 0.5) - 1.0
            elif tone.wave == "saw":
                s = 2.0 * phase - 1.0
            else:  # noise: sample-and-hold, the hold rate follows the frequency
                noise_counter += freq / rate
                if noise_counter >= 1.0:
                    noise_counter -= 1.0
                    noise_val = rng.uniform(-1.0, 1.0)
                s = noise_val
            # Envelope: short linear attack, then linear decay to zero.
            env = i / attack_n if i < attack_n else 1.0 - (i - attack_n) / max(1, n - attack_n)
            out.append(int(s * env * tone.vol * peak))
    return out


class _SoundBank:
    """Lazily builds and caches pygame Sound objects for every recipe."""

    def __init__(self) -> None:
        self.enabled: bool = True
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._ready: bool = False
        self._failed: bool = False

    def _ensure(self) -> bool:
        """Initialize the mixer and synthesize all sounds (only once)."""
        if self._ready:
            return True
        if self._failed:
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            init = pygame.mixer.get_init()
            if not init:
                raise RuntimeError("mixer not available")
            rate, size, channels = init
            if size != -16:
                raise RuntimeError(f"unsupported sample size {size}")
            for name, tones in RECIPES.items():
                mono = synthesize(tones, rate)
                if channels > 1:
                    data = array("h")
                    for s in mono:
                        data.extend([s] * channels)
                else:
                    data = mono
                self._sounds[name] = pygame.mixer.Sound(buffer=data.tobytes())
            self._ready = True
        except Exception:
            self._failed = True
        return self._ready

    def preload(self) -> bool:
        """Synthesize everything now (avoids a tiny hitch on the first sound)."""
        return self._ensure()

    def play(self, name: str, volume: float = 1.0) -> None:
        """Play a sound by name. Unknown names and missing audio are ignored."""
        if not self.enabled or not self._ensure():
            return
        snd = self._sounds.get(name)
        if snd is not None:
            snd.set_volume(max(0.0, min(1.0, volume)))
            snd.play()


_bank = _SoundBank()


def play(name: str, volume: float = 1.0) -> None:
    """Play the sound effect ``name`` (see ``RECIPES``)."""
    _bank.play(name, volume)


def preload() -> bool:
    """Prepare all sounds. Returns False if audio is unavailable."""
    return _bank.preload()


def is_enabled() -> bool:
    """True if sound effects are switched on."""
    return _bank.enabled


def set_enabled(value: bool) -> None:
    """Switch sound effects on/off."""
    _bank.enabled = bool(value)


def toggle() -> bool:
    """Flip the audio switch and return the new state."""
    _bank.enabled = not _bank.enabled
    return _bank.enabled
