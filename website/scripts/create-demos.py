"""Compose original synthesized demo cues; no provider calls or licensed samples."""
import math
import struct
import wave
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / 'public/assets'
RATE = 24000
for name, seconds, root in [('intro-demo', 12, 110), ('transition-demo', 3, 165), ('bed-demo', 16, 82.41)]:
    frames = bytearray()
    for i in range(RATE * seconds):
        t = i / RATE
        beat = t % 0.5
        fade = min(t / .15, 1, max(0, (seconds - t) / 1.2))
        notes = [1, 1.5, 2, 2.5, 3, 2.5, 2, 1.5]
        freq = root * notes[int(t * 4) % len(notes)]
        pluck = math.exp(-14 * (t % .25)) * math.sin(2 * math.pi * freq * t)
        bass = .4 * math.sin(2 * math.pi * root * t) * math.exp(-7 * beat)
        kick = .3 * math.sin(2 * math.pi * (45 * beat + 1.4 * (1 - math.exp(-20 * beat)))) * math.exp(-20 * beat)
        air = .07 * math.sin(2 * math.pi * 3520 * t) * math.exp(-60 * (t % .25))
        value = max(-1, min(1, (pluck * .25 + bass + kick + air) * fade))
        frames.extend(struct.pack('<h', int(value * 24000)))
    with wave.open(str(DEST / (name + '.wav')), 'wb') as wav:
        wav.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        wav.writeframes(frames)
