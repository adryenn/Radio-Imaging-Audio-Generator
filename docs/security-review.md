# Rafter code review — 2026-10-14

Manual review using `rafter-secure-design`, `rafter-code-review` web-app and LLM
walkthroughs. Scope: catalog, provider adapters, Streamlit UI, dependencies and
CI/devcontainer configuration. Automated Rafter is **pending**, not passed:
`rafter run` exits 127 (command unavailable), and RAFTER_API_KEY is not configured.
The user explicitly authorized a draft PR with this scan pending. Do not treat
this document as remote SAST/SCA or a production approval.

## Web application walk

| Category | Evidence / result |
| --- | --- |
| A01 access control | `radio_imaging_app.py:32` user-supplied keys; `:89` results are session-local. No account/DB/admin routes added. Hosting auth/quotas are an operator requirement. |
| A02 crypto/secrets | `audio_providers.py:21` fixed HTTPS origins; `:89` default TLS verification; `:37` credential excluded from repr; `:79` provider-specific auth headers; `.gitignore` excludes secrets. No app cryptography/password storage. |
| A03 injection | `audio_providers.py:64` voice path allowlist; `:53` catalog allowlist; `:92` JSON serialization. No SQL, shell, eval or HTML interpolation. `radio_imaging_app.py:101` renders result descriptions as text. |
| A04 design | `docs/security-design.md` records trust boundaries/abuse cases. `audio_providers.py:55` bounds text, `:68` duration and `:105` response bytes/time. Billable calls require explicit buttons and have no retries. |
| A05 misconfiguration | `.devcontainer/devcontainer.json` no longer disables CORS/XSRF. `audio_providers.py:90` disables redirects and environment proxies. UI generic fallback errors at `radio_imaging_app.py:94`. |
| A06 dependencies | Exact/hash-locked cloud and optional local requirements; no TensorFlow or legacy OpenAI SDK. Wheel-only CI installs, weekly Dependabot. Separate pip-audit results recorded below. Rafter SCA pending. |
| A07 authentication | No app authentication added; session handling belongs to Streamlit. Keys are password widgets, never shared global config; public deployment still needs operator authentication. |
| A08 integrity | `audio_providers.py:225` safetensors and remote-code disabled; catalog restricts Facebook repos. CI actions pinned to commits with read-only token. Public model repos remain an upstream trust assumption. |
| A09 logs | No request bodies, raw exceptions, model output or credentials logged. Errors are stable app messages (`audio_providers.py:93`, `:109`). Provider account records supply usage audit, not an app audit database. |
| A10 SSRF | Origins fixed at `audio_providers.py:21`; paths fixed except a validated voice ID. Redirects disabled at `:90`. Returned Google URLs are never fetched (`:134`). |

## LLM walk

| Category | Evidence / result |
| --- | --- |
| LLM01 prompt injection | `audio_providers.py:205` separates instructions and input; prompts have no tool/function execution. Model output is text for user review, not authority. |
| LLM02 disclosure | Only explicit text/style reaches providers; keys are headers, not payloads. `radio_imaging_app.py:35` retention/session behavior disclosed. Provider retention follows account terms. |
| LLM03 supply chain | Reviewed first-party API sources in `docs/providers.md`; local model IDs fixed; safe weight loading `audio_providers.py:220`. Package locks are hash-pinned. |
| LLM04 poisoning | N/A: no training, feedback data pipeline or RAG corpus. |
| LLM05 output handling | `audio_providers.py:113` JSON shape guard, `:134` strict base64 and MIME, `:123` nonempty size/header checks. These identify format; they are not a full media decoder/AV scan. Browser handles playback. No model output is executable. |
| LLM06 agency | N/A: no tools or autonomous actions. Only explicit prompt and audio buttons call providers. |
| LLM07 prompt leakage | `audio_providers.py:201` static nonsecret generation instruction; keys never enter it. |
| LLM08 vectors | N/A: no embeddings or vector retrieval. |
| LLM09 reliance | `radio_imaging_app.py:19` AI disclosure; `:62` review/edit step. Generated scripts require editorial review before broadcast. |
| LLM10 consumption | Input/duration caps, bounded HTTP response and output-token budget (`audio_providers.py:207`), no retries, one local inference at a time (`:233`). Cross-session aggregate hosting limits remain an operator responsibility. |

## Verification and remaining gates

- 24 offline tests pass: every cloud model preset dispatch, request contracts,
  auth headers, forbidden controls, invalid inputs, redirects, quota/error
  sanitization, response size/MIME/base64, local safe loading and mono/stereo
  conversion, UI generation/review/edit/persistence/clear flows.
- Cloud dependency audit: `pip-audit -r requirements.txt --disable-pip --no-deps`:
  no known vulnerabilities in the resolved cloud lock (2026-10-14).
- Optional local dependency audit: initial Transformers 4.57.6 had known
  vulnerabilities; upgraded to the current patched 5.x release. Repeated
  pip-audit on requirements-local.txt: no known vulnerabilities.
- Local weight metadata verified against all offered Facebook repositories;
  mono medium/large omitted because no safetensors weights were published.
- Installed the optional hashed lock and verified actual MusicGen imports with
  Transformers 5.19.0, PyTorch 2.14.1 and SciPy 1.17.1.
- Live paid provider calls and actual MusicGen weight inference were not run.
- Rafter remote SAST/SCA must run in a configured environment before merge.
