import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from audio_providers import AudioResult

APP = str(Path(__file__).resolve().parents[1] / 'radio_imaging_app.py')


def widget(elements, label):
    return next(e for e in elements if e.label == label)


class StreamlitWorkflowTests(unittest.TestCase):
    def test_task_switching_and_capability_controls(self):
        app = AppTest.from_file(APP).run()
        self.assertFalse(app.exception)
        widget(app.selectbox, 'Audio type').select('Speech').run()
        self.assertFalse(app.exception)
        self.assertTrue(any(x.label == 'Delivery instructions (optional)' for x in app.text_area))
        widget(app.selectbox, 'Audio model').select('tts-1').run()
        self.assertFalse(any(x.label == 'Delivery instructions (optional)' for x in app.text_area))
        self.assertNotIn('marin', widget(app.selectbox, 'Voice').options)
        widget(app.selectbox, 'Audio provider').select('Google').run()
        self.assertFalse(app.exception)
        self.assertIn('Kore', widget(app.selectbox, 'Voice').options)
        widget(app.selectbox, 'Audio type').select('Sound effects').run()
        self.assertFalse(app.exception)
        self.assertEqual(widget(app.slider, 'Duration (seconds)').max, 30)

    @patch('audio_providers.generate', return_value=AudioResult(b'ID3test', 'audio/mpeg', 'mp3'))
    def test_generation_persists_across_reruns_and_clears(self, generate):
        app = AppTest.from_file(APP).run()
        widget(app.text_area, 'Reviewed audio description').input('Bright music bed').run()
        widget(app.text_input, 'ElevenLabs API key').input('test-key').run()
        widget(app.button, '▶ Generate Audio').click().run()
        self.assertFalse(app.exception)
        generate.assert_called_once()
        self.assertEqual(generate.call_args.args[0].text, 'Bright music bed')
        self.assertEqual(app.session_state['audio_description'], 'Bright music bed')
        other_session = AppTest.from_file(APP).run()
        self.assertNotIn('audio_result', other_session.session_state)
        self.assertEqual(widget(other_session.text_input, 'ElevenLabs API key').value, '')
        app.run()
        self.assertEqual(app.session_state['audio_result'].data, b'ID3test')
        generate.assert_called_once()
        widget(app.button, 'Clear session content and audio').click().run()
        self.assertFalse(app.exception)
        self.assertNotIn('audio_result', app.session_state)

    @patch('audio_providers.enhance_prompt', return_value='Your station. Your music.')
    def test_prompt_can_be_reviewed_and_edited(self, enhance):
        app = AppTest.from_file(APP).run()
        widget(app.text_area, 'Your draft idea').input('upbeat station').run()
        widget(app.button, '📄 Generate Prompt').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(widget(app.text_area, 'Reviewed audio description').value, 'Your station. Your music.')
        widget(app.text_area, 'Reviewed audio description').input('Edited music bed').run()
        self.assertEqual(app.session_state['content_Music'], 'Edited music bed')

    def test_blank_generation_shows_safe_validation(self):
        app = AppTest.from_file(APP).run()
        widget(app.button, '▶ Generate Audio').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)


if __name__ == '__main__':
    unittest.main()
