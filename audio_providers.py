"""Small REST adapters with shared validation and bounded, session-local results."""
import base64
import binascii
import io
import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache

import httpx

from audio_catalog import MODELS, ModelSpec

MAX_RESPONSE = 32 * 1024 * 1024
MAX_SECONDS = 240
LOCAL_LOCK = threading.Lock()
ORIGINS = {
    'OpenAI': 'https://api.openai.com',
    'ElevenLabs': 'https://api.elevenlabs.io',
    'Google': 'https://generativelanguage.googleapis.com',
    'Cartesia': 'https://api.cartesia.ai',
}


class ProviderError(ValueError):
    """Safe message suitable for display; never carries provider response bodies."""


@dataclass(frozen=True)
class AudioRequest:
    spec: ModelSpec
    text: str
    api_key: str = field(default='', repr=False)
    voice: str = ''
    style: str = ''
    seconds: float = 10
    instrumental: bool = False


@dataclass(frozen=True)
class AudioResult:
    data: bytes
    mime: str
    extension: str


def validate(request: AudioRequest) -> None:
    s = request.spec
    if s not in MODELS:
        raise ProviderError('Select a supported model from the catalog.')
    if not isinstance(request.text, str) or not 1 <= len(request.text.strip()) <= s.max_chars:
        raise ProviderError(f'Enter between 1 and {s.max_chars} characters.')
    if s.provider != 'Local MusicGen':
        key = request.api_key
        if not isinstance(key, str) or not key.strip() or len(key) > 512 or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise ProviderError('Enter a valid API key for the selected provider.')
    if s.task == 'Speech':
        if s.voices and request.voice not in s.voices:
            raise ProviderError('Select a supported voice for this model.')
        if not s.voices and not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', request.voice):
            raise ProviderError('Enter a valid provider voice ID.')
    if len(request.style) > 1000 or (request.style and not s.style):
        raise ProviderError('This model does not support these delivery instructions.')
    if s.max_seconds:
        if not math.isfinite(request.seconds) or not s.min_seconds <= request.seconds <= s.max_seconds:
            raise ProviderError(f'Duration must be {s.min_seconds}–{s.max_seconds} seconds.')
    if request.instrumental and not s.instrumental:
        raise ProviderError('This model has no guaranteed instrumental control; describe it in the prompt.')


def _post(provider: str, path: str, key: str, payload: dict,
          accept: str = 'application/json') -> tuple[bytes, str]:
    # All call sites pass fixed paths; no model-provided URL is ever followed.
    headers = {'Accept': accept}
    if provider == 'ElevenLabs':
        headers['xi-api-key'] = key
    elif provider == 'Google':
        headers['x-goog-api-key'] = key
    else:
        headers['Authorization'] = 'Bearer ' + key
    if provider == 'Cartesia':
        headers['Cartesia-Version'] = '2026-08-14'
    started = time.monotonic()
    try:
        with httpx.Client(timeout=httpx.Timeout(120, connect=10),
                          follow_redirects=False, trust_env=False) as client:
            with client.stream('POST', ORIGINS[provider] + path,
                               headers=headers, json=payload) as response:
                if response.status_code != 200:
                    messages = {401: 'API key was rejected.', 403: 'Your account cannot access this model.',
                                429: 'Provider quota or rate limit reached. Try again later.'}
                    raise ProviderError(messages.get(response.status_code,
                                        'Provider request failed. Check model access and account status.'))
                mime = response.headers.get('content-type', '').split(';')[0].lower()
                allowed = {'application/json'} if accept == 'application/json' else {
                    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 'application/octet-stream'}
                if mime not in allowed:
                    raise ProviderError('Provider returned an unexpected content type.')
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    if len(chunks) + len(chunk) > MAX_RESPONSE or time.monotonic() - started > MAX_SECONDS:
                        raise ProviderError('Provider response exceeded the app size or time limit.')
                    chunks.extend(chunk)
                return bytes(chunks), mime
    except httpx.HTTPError:
        raise ProviderError('Could not reach the provider securely. Please try again later.') from None


def _json(data: bytes) -> dict:
    try:
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, RecursionError, UnicodeError):
        raise ProviderError('Provider returned invalid JSON.') from None


def _audio(data: bytes, expected: str) -> AudioResult:
    if not data or len(data) > MAX_RESPONSE:
        raise ProviderError('Provider returned empty or oversized audio.')
    if expected == 'wav' and data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return AudioResult(data, 'audio/wav', 'wav')
    if expected == 'mp3' and (data[:3] == b'ID3' or
                             (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224)):
        return AudioResult(data, 'audio/mpeg', 'mp3')
    raise ProviderError('Provider returned invalid or unsupported audio.')


def _google_audio(data: bytes) -> AudioResult:
    try:
        blocks = [content for step in _json(data)['steps'] if step.get('type') == 'model_output'
                  for content in step.get('content', []) if content.get('type') == 'audio']
        block = blocks[-1]
        mime = block.get('mime_type', '')
        if mime not in ('audio/wav', 'audio/mpeg', 'audio/mp3'):
            raise ProviderError('Google returned an unsupported audio format.')
        decoded = base64.b64decode(block['data'], validate=True)
        return _audio(decoded, 'wav' if mime == 'audio/wav' else 'mp3')
    except (KeyError, IndexError, TypeError, AttributeError, binascii.Error):
        raise ProviderError('Google returned no usable audio. The request may have been blocked.') from None


def generate(request: AudioRequest) -> AudioResult:
    validate(request)
    s, text = request.spec, request.text.strip()
    if s.provider == 'Local MusicGen':
        return _local_audio(request)
    if s.provider == 'OpenAI':
        payload = {'model': s.model, 'input': text, 'voice': request.voice, 'response_format': 'mp3'}
        if request.style:
            payload['instructions'] = request.style
        data, _ = _post(s.provider, '/v1/audio/speech', request.api_key, payload, 'audio/mpeg')
        return _audio(data, 'mp3')
    if s.provider == 'ElevenLabs':
        if s.task == 'Speech':
            path = '/v1/text-to-speech/' + request.voice + '?output_format=mp3_44100_128'
            payload = {'text': text, 'model_id': s.model}
        elif s.task == 'Music':
            path = '/v1/music?output_format=mp3_44100_128'
            payload = {'prompt': text, 'model_id': s.model,
                       'music_length_ms': round(request.seconds * 1000),
                       'force_instrumental': request.instrumental}
        else:
            path = '/v1/sound-generation?output_format=mp3_44100_128'
            payload = {'text': text, 'model_id': s.model, 'duration_seconds': request.seconds}
        data, _ = _post(s.provider, path, request.api_key, payload, 'audio/mpeg')
        return _audio(data, 'mp3')
    if s.provider == 'Google':
        payload = {'model': s.model}
        if s.task == 'Speech':
            content = {'type': 'text', 'text': text}
            if request.style:
                content['annotations'] = [{'type': 'speech_metadata', 'style': request.style}]
            payload.update(input=[{'type': 'user_input', 'content': [content]}],
                           response_format={'type': 'audio', 'mime_type': 'audio/wav'},
                           generation_config={'speech_config': [{'voice': request.voice}]})
        else:
            # Lyria defaults to MP3 and controls length through the prompt.
            payload['input'] = text
        data, _ = _post(s.provider, '/v1beta/interactions', request.api_key, payload)
        return _google_audio(data)
    if s.provider == 'Cartesia':
        data, _ = _post(s.provider, '/tts/bytes', request.api_key,
                        {'model_id': s.model, 'transcript': text, 'voice': request.voice,
                         'output_format': {'container': 'wav', 'encoding': 'pcm_s16le',
                                           'sample_rate': 44100}}, 'audio/wav')
        return _audio(data, 'wav')
    raise ProviderError('Unsupported provider.')


def enhance_prompt(text: str, task: str, api_key: str, model: str) -> str:
    if task not in ('Speech', 'Music', 'Sound effects') or not 1 <= len(text.strip()) <= 4000:
        raise ProviderError('Enter an idea of up to 4000 characters.')
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', model):
        raise ProviderError('Enter a valid OpenAI prompt model ID.')
    # Reuse credential validation without making an audio request.
    validate(AudioRequest(MODELS[0], text, api_key, 'coral'))
    instruction = ('Write only a short radio imaging script to be spoken verbatim. No stage directions.'
                   if task == 'Speech' else
                   f'Write only a concise {task.lower()} generation prompt under 150 words. No attribution.')
    data, _ = _post('OpenAI', '/v1/responses', api_key,
                    {'model': model, 'instructions': instruction, 'input': text,
                     'max_output_tokens': 1000, 'store': False})
    try:
        result = '\n'.join(c['text'] for item in _json(data)['output']
                           if item.get('type') == 'message'
                           for c in item.get('content', []) if c.get('type') == 'output_text').strip()
        if not 1 <= len(result) <= 4000:
            raise ValueError
        return result
    except (KeyError, TypeError, AttributeError, ValueError):
        raise ProviderError('No usable prompt was returned. Edit your idea manually or try again.') from None


@lru_cache(maxsize=1)
def _load_musicgen(model_id: str):
    from transformers import AutoProcessor, MusicgenForConditionalGeneration
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=False)
    model = MusicgenForConditionalGeneration.from_pretrained(
        model_id, trust_remote_code=False, use_safetensors=True)
    model.eval()
    return processor, model


def _local_audio(request: AudioRequest) -> AudioResult:
    if os.environ.get('ENABLE_LOCAL_MUSICGEN') != '1':
        raise ProviderError('Local MusicGen is disabled. Set ENABLE_LOCAL_MUSICGEN=1 and install requirements-local.txt.')
    if not LOCAL_LOCK.acquire(blocking=False):
        raise ProviderError('Local MusicGen is busy. Please try again after the current generation.')
    try:
        import torch
        from scipy.io import wavfile
        processor, model = _load_musicgen(request.spec.model)
        inputs = processor(text=[request.text], padding=True, return_tensors='pt')
        with torch.inference_mode():
            audio = model.generate(**inputs, max_new_tokens=math.ceil(request.seconds * 50))
        # [batch, channels, samples] -> mono [samples] or interleaved [samples, channels].
        samples = audio[0].detach().cpu().numpy().T
        if samples.shape[1] == 1:
            samples = samples[:, 0]
        buffer = io.BytesIO()
        wavfile.write(buffer, model.config.audio_encoder.sampling_rate, samples)
        return _audio(buffer.getvalue(), 'wav')
    except ImportError:
        raise ProviderError('Install requirements-local.txt to enable local MusicGen.') from None
    except Exception:
        raise ProviderError('Local generation failed. Check installed dependencies, model access and available memory.') from None
    finally:
        LOCAL_LOCK.release()
