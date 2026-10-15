# API compatibility notes

Checked 2026-10-14 against first-party docs. All adapters make one synchronous
request; no request is made on import, widget changes or initial page load.
Access to a documented model still depends on the provider account.

| Adapter | Contract and format | Official sources |
| --- | --- | --- |
| OpenAI speech | POST `/v1/audio/speech`; model/input/voice/response_format=mp3. Only mini-TTS accepts instructions; legacy voices are restricted. | [Guide](https://developers.openai.com/api/docs/guides/text-to-speech), [Reference](https://developers.openai.com/api/reference/go/resources/audio/subresources/speech/methods/create) |
| OpenAI prompt | POST `/v1/responses`; instructions/input, max_output_tokens=1000, store=false; extract output message text. | [Responses](https://developers.openai.com/api/reference/resources/responses/methods/create), [Default text model](https://developers.openai.com/api/docs/models/gpt-5.4-mini) |
| Eleven speech | POST `/v1/text-to-speech/{voice_id}`; text/model_id; MP3. Voice ID is validated before path construction. | [Convert](https://elevenlabs.io/docs/api-reference/text-to-speech/convert), [Models](https://elevenlabs.io/docs/overview/models) |
| Eleven music | POST `/v1/music`; prompt/model_id/music_length_ms/force_instrumental; MP3. App requests 3–180 seconds though API permits longer. | [Compose](https://elevenlabs.io/docs/api-reference/music/compose) |
| Eleven effects | POST `/v1/sound-generation`; text/model_id/duration_seconds (0.5–30); MP3. | [Effects](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert) |
| Google speech | POST `/v1beta/interactions`; structured user_input, optional speech_metadata.style, generation_config.speech_config array; unary WAV, base64 in model_output steps. This schema is specific to Gemini 3.8 TTS. | [Speech guide](https://ai.google.dev/gemini-api/docs/speech-generation) |
| Google music | Same Interactions endpoint, text input, model `lyria-3.5` or Clip preview. Default MP3 in audio blocks. Clip is 30 seconds; 3.5 duration is prompt-guided. | [Lyria guide](https://ai.google.dev/gemini-api/docs/music-generation) |
| Cartesia speech | POST `/tts/bytes`; model_id/transcript/voice UUID string/output_format (WAV pcm_s16le 44100); Authorization Bearer and Cartesia-Version `2026-08-14`. | [Bytes reference](https://docs.cartesia.ai/api-reference/tts/bytes) |
| MusicGen | Transformers AutoProcessor + MusicgenForConditionalGeneration, 50 autoregressive tokens/sec, mono/stereo WAV in memory. | [Transformers](https://huggingface.co/docs/transformers/model_doc/musicgen), [Weight license](https://huggingface.co/facebook/musicgen-small) |

No arbitrary model override is provided for audio: similarly named models may
require incompatible schemas. Legacy Gemini 2.5/3.1 TTS uses a different API;
its IDs must not be inserted into the Gemini 3.8 adapter. Live/realtime models,
speech-to-speech models and transcription models have different input/response
contracts and are intentionally absent from file-generation selectors.

MusicGen safetensors availability was checked with Hugging Face repository
metadata. Mono medium/large do not publish safetensors and are omitted rather
than falling back to pickle weights. The original mono small and the three
stereo sizes publish safetensors.
