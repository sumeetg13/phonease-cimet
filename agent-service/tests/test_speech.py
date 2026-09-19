import os
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from fastapi.testclient import TestClient
from openai import OpenAIError
from phonease.app import app
from phonease.core import Supervisor
from phonease.telephony import Twilio

class SpeechTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ, {'OPENAI_API_KEY':'test-key','AGENT_SERVICE_TOKEN':'test-token',
            'OPENAI_TTS_MODEL':'gpt-4o-mini-tts','OPENAI_TTS_VOICE':'marin'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.client=TestClient(app)
        self.headers={'Authorization':'Bearer test-token'}

    def post(self, text='Hello, I am an AI assistant.'):
        return self.client.post('/speech',headers=self.headers,json={'text':text})

    @patch('phonease.speech.OpenAI')
    def test_requires_service_auth(self, sdk):
        self.assertEqual(self.client.post('/speech',json={'text':'hello'}).status_code,401)
        sdk.assert_not_called()

    @patch('phonease.speech.OpenAI')
    def test_binary_audio_and_server_config(self, sdk):
        create=sdk.return_value.__enter__.return_value.audio.speech.create
        create.return_value.content=b'ID3-test-mp3'
        response=self.post()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,b'ID3-test-mp3')
        self.assertEqual(response.headers['content-type'],'audio/mpeg')
        self.assertEqual(response.headers['cache-control'],'no-store')
        args=create.call_args.kwargs
        self.assertEqual(args['voice'],'marin')
        self.assertEqual(args['model'],'gpt-4o-mini-tts')
        self.assertEqual(args['response_format'],'mp3')
        self.assertIn('Australian',args['instructions'])
        self.assertEqual(sdk.call_args.kwargs['max_retries'],0)

    @patch('phonease.speech.OpenAI')
    def test_rejects_empty_and_oversized_text_before_paid_call(self, sdk):
        for value in ['', 'x'*4097]: self.assertEqual(self.post(value).status_code,422)
        self.assertEqual(self.post('   ').status_code,400)
        sdk.assert_not_called()

    @patch('phonease.speech.OpenAI')
    def test_missing_key_is_explicit(self, sdk):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            self.assertEqual(self.post().status_code,503)
        sdk.assert_not_called()

    @patch('phonease.speech.OpenAI')
    def test_provider_error_does_not_leak_or_retry(self, sdk):
        create=sdk.return_value.__enter__.return_value.audio.speech.create
        create.side_effect=OpenAIError('secret-provider-details')
        response=self.post()
        self.assertEqual(response.status_code,502)
        self.assertNotIn('secret-provider-details',response.text)
        self.assertEqual(create.call_count,1)

    @patch('phonease.speech.OpenAI')
    def test_empty_audio_is_rejected(self, sdk):
        sdk.return_value.__enter__.return_value.audio.speech.create.return_value.content=b''
        self.assertEqual(self.post().status_code,502)

    def test_all_telephone_prompts_and_whisper_use_neural_voice(self):
        with patch.dict(os.environ,{'TWILIO_VOICE':'Polly.Olivia-Neural'}):
            supervisor=Supervisor(); session=supervisor.start()
            adapter=Twilio()
            responses=[adapter.response(session)]
            session=supervisor.turn(session['id'],'human please','human')
            responses.extend([adapter.response(session),adapter.whisper(session)])
            session=supervisor.unavailable(session['id'])
            responses.append(adapter.response(session))
            for body in responses:
                prompts=ET.fromstring(body).findall('.//Say')
                self.assertTrue(prompts)
                for prompt in prompts:
                    self.assertEqual(prompt.attrib['voice'],'Polly.Olivia-Neural')
                    self.assertEqual(prompt.attrib['language'],'en-AU')
