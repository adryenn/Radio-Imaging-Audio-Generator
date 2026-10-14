"""Reviewed capability catalog; model names are data, never URLs or code."""
from dataclasses import dataclass


OPENAI_VOICES = ('alloy', 'ash', 'ballad', 'coral', 'echo', 'fable', 'nova',
                 'onyx', 'sage', 'shimmer', 'verse', 'marin', 'cedar')
LEGACY_VOICES = ('alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer')
GEMINI_VOICES = (
    'Kore', 'Puck', 'Charon', 'Fenrir', 'Aoede', 'Leda', 'Orus', 'Zephyr',
    'Callirrhoe', 'Autonoe', 'Enceladus', 'Iapetus', 'Umbriel', 'Algieba',
    'Despina', 'Erinome', 'Algenib', 'Rasalgethi', 'Laomedeia', 'Achernar',
    'Alnilam', 'Schedar', 'Gacrux', 'Pulcherrima', 'Achird', 'Zubenelgenubi',
    'Vindemiatrix', 'Sadachbia', 'Sadaltager', 'Sulafat',
)


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    task: str
    model: str
    max_chars: int = 4000
    voices: tuple[str, ...] = ()
    style: bool = False
    min_seconds: float = 0
    max_seconds: float = 0
    instrumental: bool = False
    note: str = ''


MODELS = tuple(
    [ModelSpec('OpenAI', 'Speech', m, voices=OPENAI_VOICES, style=True)
     for m in ('gpt-4o-mini-tts', 'gpt-4o-mini-tts-2025-12-15')]
    + [ModelSpec('OpenAI', 'Speech', m, voices=LEGACY_VOICES)
       for m in ('tts-1', 'tts-1-hd')]
    + [ModelSpec('ElevenLabs', 'Speech', m,
                 note='Enter a voice ID available to your ElevenLabs account. Use inline audio tags only where the model supports them.')
       for m in ('eleven_v4', 'eleven_v4_turbo', 'eleven_v3',
                 'eleven_multilingual_v2', 'eleven_flash_v2_5', 'eleven_turbo_v2_5')]
    + [ModelSpec('ElevenLabs', 'Music', m, max_chars=4100,
                 min_seconds=3, max_seconds=180, instrumental=True,
                 note='App limits music to 180 seconds per request; account access and charges apply.')
       for m in ('music_v2_5', 'music_v2', 'music_v1')]
    + [ModelSpec('ElevenLabs', 'Sound effects', 'eleven_text_to_sound_v2',
                 min_seconds=0.5, max_seconds=30)]
    + [ModelSpec('Google', 'Speech', m, voices=GEMINI_VOICES, style=True)
       for m in ('gemini-3.8-flash-tts', 'gemini-3.8-flash-lite-tts')]
    + [ModelSpec('Google', 'Music', m,
                 note='30-second clip (preview).' if 'clip' in m else
                      'Song duration is controlled through your prompt; there is no exact duration control.')
       for m in ('lyria-3.5', 'lyria-3-clip-preview')]
    + [ModelSpec('Cartesia', 'Speech', 'sonic-3.6',
                 note='Enter a voice UUID from your Cartesia account.')]
    + [ModelSpec('Local MusicGen', 'Music', 'facebook/musicgen-' + size,
                 min_seconds=1, max_seconds=25,
                 note='Optional local weights; substantial RAM/download needed. MusicGen weights are CC-BY-NC 4.0, not MIT.')
       for size in ('small', 'stereo-small', 'stereo-medium', 'stereo-large')]
)


def models_for(task: str, provider: str | None = None) -> tuple[ModelSpec, ...]:
    return tuple(m for m in MODELS if m.task == task and
                 (provider is None or m.provider == provider))
