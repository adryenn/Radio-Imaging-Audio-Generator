import base64
import io
import json
import os
import unittest
import wave
from dataclasses import replace
from unittest.mock import MagicMock, patch

import httpx

import audio_providers as ap
from audio_catalog import MODELS, ModelSpec, models_for

MP3 = b'ID3' + b'\x00' * 32
buffer = io.BytesIO()
with wave.open(buffer, 'wb') as wav:
    wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
    wav.writeframes(b'\0\0' * 10)
WAV = buffer.getvalue()


def request(spec, **kw):
    return ap.AudioRequest(spec, 'Station sound', 'test-key',
                           spec.voices[0] if spec.voices else 'voice_123', **kw)


def google_response(data=WAV, mime='audio/wav'):
    return json.dumps({'steps': [{'type': 'model_output', 'content': [
        {'type': 'audio', 'mime_type': mime, 'data': base64.b64encode(data).decode()}]}]}).encode()


class ProviderContracts(unittest.TestCase):
    @patch.object(ap, '_post')
    def test_every_cloud_preset_dispatches(self, post):
        for spec in MODELS:
            if spec.provider == 'Local MusicGen':
                continue
            with self.subTest(model=spec.model):
                post.return_value = ((google_response(MP3, 'audio/mpeg') if spec.task == 'Music'
                                      else google_response()) if spec.provider == 'Google'
                                     else WAV if spec.provider == 'Cartesia' else MP3, '')
                result = ap.generate(request(spec))
                provider, path, key, payload = post.call_args.args[:4]
                self.assertEqual(provider, spec.provider)
                self.assertEqual(key, 'test-key')
                self.assertNotIn('api_key', payload)
                self.assertTrue(result.data)
                self.assertEqual(payload.get('model', payload.get('model_id')), spec.model)

    @patch.object(ap, '_post', return_value=(MP3, 'audio/mpeg'))
    def test_openai_style_and_legacy_voices(self, post):
        ap.generate(request(MODELS[0], style='Warm announcer'))
        self.assertEqual(post.call_args.args[3]['instructions'], 'Warm announcer')
        legacy = models_for('Speech', 'OpenAI')[-1]
        ap.generate(request(legacy))
        self.assertNotIn('instructions', post.call_args.args[3])
        with self.assertRaises(ap.ProviderError):
            ap.generate(replace(request(legacy), voice='marin'))
        with self.assertRaises(ap.ProviderError):
            ap.generate(request(legacy, style='warm'))

    @patch.object(ap, '_post', return_value=(MP3, 'audio/mpeg'))
    def test_eleven_music_units_and_instrumental(self, post):
        ap.generate(request(models_for('Music', 'ElevenLabs')[0], seconds=12.5, instrumental=True))
        self.assertEqual(post.call_args.args[1], '/v1/music?output_format=mp3_44100_128')
        self.assertEqual(post.call_args.args[3]['music_length_ms'], 12500)
        self.assertTrue(post.call_args.args[3]['force_instrumental'])

    @patch.object(ap, '_post', return_value=(MP3, 'audio/mpeg'))
    def test_effect_duration(self, post):
        ap.generate(request(models_for('Sound effects')[0], seconds=0.5))
        self.assertEqual(post.call_args.args[3]['duration_seconds'], 0.5)

    @patch.object(ap, '_post', return_value=(google_response(), 'application/json'))
    def test_gemini_38_script_and_style_are_separate(self, post):
        ap.generate(request(models_for('Speech', 'Google')[0], style='calm'))
        payload = post.call_args.args[3]
        self.assertEqual(payload['input'][0]['content'][0]['text'], 'Station sound')
        self.assertEqual(payload['input'][0]['content'][0]['annotations'][0]['style'], 'calm')
        self.assertEqual(payload['generation_config']['speech_config'], [{'voice': 'Kore'}])
        self.assertEqual(payload['response_format']['mime_type'], 'audio/wav')

    @patch.object(ap, '_post', return_value=(google_response(MP3, 'audio/mpeg'), 'application/json'))
    def test_lyria_has_no_invented_duration_field(self, post):
        ap.generate(request(models_for('Music', 'Google')[0]))
        self.assertEqual(post.call_args.args[3], {'model': 'lyria-3.5', 'input': 'Station sound'})

    @patch.object(ap, '_post', return_value=(WAV, 'audio/wav'))
    def test_cartesia_current_schema(self, post):
        ap.generate(request(models_for('Speech', 'Cartesia')[0]))
        self.assertEqual(post.call_args.args[3]['voice'], 'voice_123')
        self.assertEqual(post.call_args.args[3]['output_format']['container'], 'wav')

    @patch.object(ap, '_post')
    def test_prompt_responses_api_and_no_attribution(self, post):
        post.return_value = (json.dumps({'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': ' Your station. '}]}]}).encode(), 'application/json')
        self.assertEqual(ap.enhance_prompt('idea', 'Speech', 'test-key', 'gpt-5.4-mini'), 'Your station.')
        payload = post.call_args.args[3]
        self.assertFalse(payload['store'])
        self.assertEqual(payload['max_output_tokens'], 1000)
        self.assertIn('verbatim', payload['instructions'])
        self.assertEqual(payload['input'], 'idea')

    @patch.object(ap, '_post', return_value=(b'{"output": []}', 'application/json'))
    def test_empty_prompt_response_is_safe_error(self, post):
        with self.assertRaises(ap.ProviderError):
            ap.enhance_prompt('idea', 'Music', 'test-key', 'gpt-5.4-mini')


class ValidationTests(unittest.TestCase):
    @patch.object(ap, '_post')
    def test_reject_before_network(self, post):
        speech = request(models_for('Speech', 'ElevenLabs')[0])
        bad = [replace(speech, voice='../admin'), replace(speech, api_key=''),
               replace(speech, api_key='key\r\nInjected: yes'), replace(speech, text=' '),
               replace(speech, text='x' * 5000), replace(speech, style='x' * 1001),
               replace(speech, spec=ModelSpec('OpenAI', 'Music', 'not-supported'))]
        effect = request(models_for('Sound effects')[0])
        bad += [replace(effect, seconds=x) for x in (0, 31, float('nan'), float('inf'))]
        for item in bad:
            with self.subTest(item=item):
                with self.assertRaises(ap.ProviderError):
                    ap.generate(item)
        post.assert_not_called()
        self.assertNotIn('test-key', repr(speech))

    def test_google_blocked_invalid_base64_and_bad_mime(self):
        for payload in (b'{}', b'{"steps": []}', b'not-json', b'{"steps": null}',
                        b'{"steps":[{"type":"model_output","content":[{"type":"audio","mime_type":"audio/wav","data":"@@"}]}]}',
                        google_response(b'not audio'), google_response(WAV, 'text/html')):
            with self.subTest(payload=payload):
                with self.assertRaises(ap.ProviderError):
                    ap._google_audio(payload)

    @patch.dict(os.environ, {}, clear=True)
    def test_local_disabled_before_loading_weights(self):
        with patch.object(ap, '_load_musicgen') as loader:
            with self.assertRaisesRegex(ap.ProviderError, 'disabled'):
                ap.generate(request(models_for('Music', 'Local MusicGen')[0]))
            loader.assert_not_called()

    @patch.dict(os.environ, {'ENABLE_LOCAL_MUSICGEN': '1'})
    def test_local_busy(self):
        ap.LOCAL_LOCK.acquire()
        try:
            with self.assertRaisesRegex(ap.ProviderError, 'busy'):
                ap.generate(request(models_for('Music', 'Local MusicGen')[0]))
        finally:
            ap.LOCAL_LOCK.release()

    def test_catalog_unique_and_bounded(self):
        self.assertEqual(len(MODELS), len(set((m.provider, m.task, m.model) for m in MODELS)))
        for spec in MODELS:
            self.assertLessEqual(spec.max_chars, 4100)
            self.assertLessEqual(spec.max_seconds, 180)


class HTTPBoundaryTests(unittest.TestCase):
    def call_with(self, handler, provider='OpenAI', **kwargs):
        real_client = httpx.Client
        transport = httpx.MockTransport(handler)
        def client_factory(**options):
            self.assertFalse(options['follow_redirects'])
            self.assertFalse(options['trust_env'])
            return real_client(transport=transport, **options)
        with patch.object(ap.httpx, 'Client', side_effect=client_factory):
            return ap._post(provider, '/test', 'private-test-key', {'input': 'hello'}, **kwargs)

    def test_headers_and_fixed_origins(self):
        for provider in ap.ORIGINS:
            def handler(req):
                self.assertEqual(str(req.url), ap.ORIGINS[provider] + '/test')
                auth = 'xi-api-key' if provider == 'ElevenLabs' else 'x-goog-api-key' if provider == 'Google' else 'Authorization'
                self.assertIn('private-test-key', req.headers[auth])
                self.assertNotIn(b'private-test-key', req.content)
                if provider == 'Cartesia':
                    self.assertEqual(req.headers['Cartesia-Version'], '2026-08-14')
                return httpx.Response(200, json={})
            self.call_with(handler, provider)

    def test_reject_redirect_error_and_wrong_mime_without_leak(self):
        for code, mime in [(302, 'application/json'), (401, 'application/json'),
                           (429, 'application/json'), (500, 'application/json'), (200, 'text/html')]:
            with self.assertRaises(ap.ProviderError) as error:
                self.call_with(lambda req: httpx.Response(code, headers={
                    'content-type': mime, 'location': 'http://127.0.0.1'}, content=b'private-test-key'))
            self.assertNotIn('private-test-key', str(error.exception))

    def test_size_limit_and_timeout(self):
        with patch.object(ap, 'MAX_RESPONSE', 5):
            with self.assertRaisesRegex(ap.ProviderError, 'limit'):
                self.call_with(lambda req: httpx.Response(200, json={'too': 'large'}))
        def timeout(req):
            raise httpx.ReadTimeout('private-test-key')
        with self.assertRaises(ap.ProviderError) as error:
            self.call_with(timeout)
        self.assertNotIn('private-test-key', str(error.exception))

    def test_audio_mime_and_signature(self):
        data, _ = self.call_with(lambda req: httpx.Response(200, content=MP3,
                                 headers={'content-type': 'audio/mpeg'}), accept='audio/mpeg')
        self.assertEqual(ap._audio(data, 'mp3').extension, 'mp3')
        with self.assertRaises(ap.ProviderError):
            ap._audio(b'<html>', 'mp3')

class LocalMusicGenTests(unittest.TestCase):
    @patch.dict(os.environ, {'ENABLE_LOCAL_MUSICGEN': '1'})
    def test_local_mono_stereo_duration_and_no_shared_file(self):
        import contextlib
        import sys
        import types
        import numpy as np
        fake_torch = types.ModuleType('torch')
        fake_torch.inference_mode = contextlib.nullcontext
        fake_scipy = types.ModuleType('scipy')
        fake_io = types.ModuleType('scipy.io')
        writer = MagicMock()
        writer.write.side_effect = lambda target, rate, samples: target.write(WAV)
        fake_io.wavfile = writer
        fake_scipy.io = fake_io
        for channels in (1, 2):
            tensor = MagicMock()
            tensor.detach.return_value.cpu.return_value.numpy.return_value = np.zeros((channels, 100))
            model = MagicMock()
            model.generate.return_value = [tensor]
            model.config.audio_encoder.sampling_rate = 32000
            processor = MagicMock(return_value={'input_ids': 'test'})
            with patch.dict(sys.modules, {'torch': fake_torch, 'scipy': fake_scipy, 'scipy.io': fake_io}), \
                 patch.object(ap, '_load_musicgen', return_value=(processor, model)):
                result = ap.generate(request(models_for('Music', 'Local MusicGen')[0], seconds=2))
            self.assertEqual(result.extension, 'wav')
            self.assertEqual(model.generate.call_args.kwargs['max_new_tokens'], 100)
            target, rate, samples = writer.write.call_args.args
            self.assertIsInstance(target, io.BytesIO)
            self.assertEqual(rate, 32000)
            self.assertEqual(samples.shape, (100,) if channels == 1 else (100, 2))
            self.assertFalse(ap.LOCAL_LOCK.locked())

    def test_weight_loader_disables_remote_code_and_pickle(self):
        import sys
        import types
        transformers = types.ModuleType('transformers')
        transformers.AutoProcessor = MagicMock()
        transformers.MusicgenForConditionalGeneration = MagicMock()
        ap._load_musicgen.cache_clear()
        with patch.dict(sys.modules, {'transformers': transformers}):
            ap._load_musicgen('facebook/musicgen-small')
        transformers.MusicgenForConditionalGeneration.from_pretrained.assert_called_once_with(
            'facebook/musicgen-small', trust_remote_code=False, use_safetensors=True)
        ap._load_musicgen.cache_clear()


if __name__ == '__main__':
    unittest.main()
