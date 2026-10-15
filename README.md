# 🎙️ Radio Imaging Audio Generator

A Streamlit app for radio producers and music creators. Write an idea, optionally
expand it with OpenAI, review/edit the content, then generate and download speech,
music beds or sound effects. Original MusicGen generation and Bilsimaging credits
are preserved. Prompt enhancement is optional and uses the current Responses API.

## Setup (Python 3.11)

```sh
python3.11 -m venv .venv
source .venv/bin/activate
pip install --only-binary=:all: -r requirements.txt
streamlit run radio_imaging_app.py
```

The default install supports cloud generation without downloading ML weights.
Enter your own API key in the sidebar for the chosen provider. API access,
regional availability, subscription requirements and charges vary by account.
There are no automatic billable retries or silent switches to another provider.
No paid generation is part of the automated tests.

For the original local MusicGen workflow:

```sh
pip install --only-binary=:all: -r requirements-local.txt
ENABLE_LOCAL_MUSICGEN=1 streamlit run radio_imaging_app.py
```

Local generation needs substantial RAM (especially stereo medium/large models), an
initial Hugging Face weight download, and a supported PyTorch platform. CPU
inference can be slow. Only the reviewed Facebook models can load, remote code
is disabled, safetensors are required, and inference is serialized. MusicGen
weights use **CC-BY-NC 4.0**; the app's MIT license does not grant commercial rights
to those weights or their use. Check all provider/model terms before broadcast.

## Provider/model catalog

Verified against the linked official documentation on **2026-10-14**. These are
compatible presets, not a guarantee of account entitlement or a list of every
model on the market. See [API notes](docs/providers.md) for contracts and sources.

| Provider | Capability | Presets |
| --- | --- | --- |
| OpenAI | Speech | `gpt-4o-mini-tts`, dated `2025-12-15` snapshot; `tts-1`, `tts-1-hd` |
| ElevenLabs | Speech | `eleven_v4`, `eleven_v4_turbo`, `eleven_v3`, multilingual v2, flash/turbo v2.5 |
| ElevenLabs | Music | `music_v2_5`, `music_v2`, `music_v1` |
| ElevenLabs | Sound effects | `eleven_text_to_sound_v2` |
| Google | Speech | `gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts` |
| Google | Music | `lyria-3.5`, `lyria-3-clip-preview` (preview) |
| Cartesia | Speech | `sonic-3.6` |
| Local MusicGen | Music | small and stereo small/medium/large |

OpenAI prompt writing defaults to `gpt-5.4-mini`. Change the sidebar value or
`OPENAI_PROMPT_MODEL` to any Responses-compatible text model available to you.
Speech models receive the exact script, never a music description or attribution.
Delivery instructions appear only for models supporting a separate style field.
ElevenLabs and Cartesia voices use account-specific IDs; OpenAI and Gemini use
model-specific voice selectors. Music/effects duration controls appear only when
the API accepts them. Lyria duration is described in the prompt (Clip is fixed at
30 seconds), not passed as an invented duration parameter. Local duration is
approximate; Eleven music is capped by this app at 180 seconds per request.

## Usage

1. Select the audio type, provider and model and enter its API key.
2. Enter a final script/description directly, or use **Generate Prompt** with an
   OpenAI key, then edit the result.
3. Set supported voice, style, duration or instrumental controls.
4. Click **Generate Audio**, listen, and download the MP3/WAV.
5. Results and the reviewed description persist across normal UI reruns. Use
   **Clear session content and audio** to remove them; disconnect/reload to clear
   session credentials. Do not share a browser session containing API keys.

Speech is AI-generated; disclose this to listeners and use authorized voices.
Cloning, uploads, transcription, realtime voice conversations, multi-speaker
orchestration and automatic voice/music mixing are outside this file-generation
workflow. Realtime and transcription models cannot replace a TTS adapter.
No unofficial Suno/Udio wrappers or arbitrary remote model loaders are included.

## Configuration and extension

`audio_catalog.py` contains immutable `ModelSpec` entries with provider, task,
model ID, voices and input limits. Add compatible IDs there after verifying their
API contract. `audio_providers.py` validates requests and dispatches to isolated
REST/local adapters, returning `AudioResult(bytes, MIME, extension)`.

For a new provider, add its **fixed HTTPS origin**, authentication and payload
adapter, a catalog entry, contract tests and official docs. Never let user/model
input supply a base URL or weight repository. Credentials enter only auth
headers; no generated files, keys or prompts are written to disk or shared
between sessions. The sole global cache holds public MusicGen weights.

The app does not provide hosting authentication or aggregate quotas. For shared
production hosting, add TLS, access control and infrastructure resource limits.
Provider data retention follows that provider's terms. See the
[Rafter design and threat model](docs/security-design.md).

## Development and verification

```sh
python -m unittest discover -s tests -v
uv pip compile requirements.in --universal --generate-hashes -o requirements.txt
uv pip compile requirements-local.in --universal --generate-hashes -o requirements-local.txt
rafter run
```

Lockfiles contain exact transitive versions and hashes, resolved for Python 3.11.
Use the same Python version when regenerating them. CI installs wheels only,
runs provider contract/security tests and Streamlit UI tests; Dependabot checks
weekly. Tests mock network calls and local weights. A maintainer should smoke
test each paid provider with their own account before merging; no claim is made
that mocked contracts verify live entitlement, audio quality or paid behavior.

Automated Rafter SAST/SCA is **pending** until a configured runner with
`RAFTER_API_KEY` executes `rafter run`. Manual review is documented separately;
it is not a substitute for a successful remote scan. The user authorized opening
a draft PR with this limitation recorded.

## Credits and support

Created by Bilel Aroua / [Bilsimaging](https://bilsimaging.com), continuing the
[Radio Imaging & MusicGen GPT](https://chat.openai.com/g/g-65x53n87E-radio-imaging-musicgen-ai).
[Video tutorials](https://www.youtube.com/playlist?list=PLwEbW4bdYBSDe6qAJRFiWGyHSW-JR-B0_)
· [Buy me a Coffee](https://ko-fi.com/bilsimaging)
· [Contact](mailto:contact@bilsimaging.com)

Application code: [MIT](LICENSE). Model/provider licensing is separate.

## Creator subscription website (new)

The new [Creator Imaging Studio website](website/README.md) is specifically for
podcasters and content creators, learning from radio imaging's sonic craft. It
adds a React landing page/studio and a separate Django account/billing backend.
The existing Streamlit app remains independent and usable. The website's brand,
pricing and payment/provider configuration are pending; it is not publicly
launched or accepting payments. See its README for the local preview, production
launch gates and tested subscription architecture.
