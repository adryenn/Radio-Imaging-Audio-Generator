# Provider architecture and Rafter secure design

Reviewed before implementation, 2026-10-14. Scope: Streamlit UI → validated
request → fixed provider HTTPS endpoint → bounded audio/text response → the
current browser session. Local MusicGen is a separate optional adapter.

## Decisions

- The catalog declares provider, task, model ID, limits, voices and supported
  controls. No arbitrary URLs, filesystem paths or downloaded Python code are
  accepted. New model IDs require a reviewed catalog change; prompt-writing
  model IDs can be configured because they only enter a JSON field.
- Use one maintained HTTP client (httpx) for documented REST APIs rather than
  five SDK dependency trees. TLS verification stays enabled, redirects and
  environment proxy inheritance are disabled. Read responses incrementally,
  cap bytes and elapsed time, and do not automatically retry billable requests.
- Password widgets hold user credentials in their own Streamlit session only.
  Do not cache clients, keys, prompts or audio across sessions; do not write
  generated audio to shared filenames. No operator credentials are exposed to
  anonymous visitors. No raw provider error bodies or exception details reach
  the UI or logs. Provider keys only enter their provider's auth header.
- Provider responses are untrusted JSON/base64/audio. Validate shapes, response
  MIME, audio headers and maximum size. Never fetch a returned URL. No eval,
  pickle, shell, SQL, HTML interpolation or agent tool execution.
- Local MusicGen uses an explicit Facebook model allowlist, safetensors and
  trust_remote_code=False. Imports and weights are lazy, with an operator
  opt-in for local inference. Serialize inference to bound memory pressure.
- Bound text, style, durations and output tokens. Keep speech scripts separate
  from music descriptions. Model output can be edited before generation and is
  rendered as text. Attribution is displayed separately, never spoken.
- Preserve local MusicGen, OpenAI prompt enhancement, playback, prompt download
  and credits. Add audio download and persistent session results.
- Streamlit/httpx are required; torch/transformers/scipy are optional local
  inference dependencies. Remove unused TensorFlow. Resolve exact versions and
  hashed locks from PyPI; CI uses wheels only. Dependency updates use Dependabot.

## STRIDE and abuse cases

Browser→app: users could submit oversized input or try cross-session access.
Validate again in adapters; Streamlit owns session isolation; no shared content
cache. No app login/database/tenant API is added. Deploy behind authentication
and resource limits for any shared production installation.

App→providers: spoofing/tampering controlled by fixed HTTPS origins and TLS;
credential disclosure controlled by scoped headers and generic errors. Provider
retention and billing remain governed by the user's account, not this app.
Prompts contain only the explicitly supplied text/style, never credentials.
Repudiation: provider account usage records are the audit source; app deliberately
retains no sensitive request logs. Cost abuse is bounded per click, with no
retries/fan-out; users bring their own credentials.

App→model registry: model supply chain is a residual trust boundary; fixed
Facebook repos, safetensors, no remote code, optional operator opt-in and a
process-wide lock reduce execution and memory risks. Download bandwidth/cache
size and infrastructure quotas remain the operator's responsibility.

Abuse twins: prompt enhancement→prompt injection (no tools, text output only);
speech/music generation→oversized billable requests (limits, explicit button,
no retries); playback→malformed provider bytes (MIME/signature/size checks);
local generation→parallel memory exhaustion (opt-in + lock).

Residual risks: external services retain data per their terms, models may
ignore creative instructions, API entitlement can vary, and real paid generation
requires account-level smoke testing. Public production hosting additionally
needs TLS, authentication, quotas and isolation supplied by its operator.
Automated Rafter SAST/SCA remains a release gate; user authorized a draft PR
with that scan marked pending when RAFTER_API_KEY is unavailable.
