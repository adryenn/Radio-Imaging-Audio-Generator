# Rafter creator website review

2026-10-14. Manual `rafter-secure-design` and `rafter-code-review` web/API/LLM
walkthrough applied to the new creator website and Django account/payment API.
This is a draft foundation, **not cleared for production**. Remote `rafter run`
is still pending (command/key absent); the user's draft-with-scan-pending
exception remains recorded. Dependency audits are separate from remote SAST.

## Findings fixed during review

- Current Stripe SDK resources are not dicts: convert retrieved subscription and
  webhook objects via `.to_dict()` before schema checks. Real SDK fixtures and
  genuine HMAC tests caught the incompatibility.
- Prevent multiple simultaneous checkout sessions: lock account, reuse open
  session, block conflicting plan and completed-but-unconfirmed sessions;
  mutation idempotency keys scoped to user. PostgreSQL required in production.
- Refund/dispute hold must survive future subscription refreshes: persist
  `billing_hold`, reject new checkout and generation, never auto-regrant.
- Prevent old billing events from replacing a different live subscription.
- Bind job reservation and refund to the same invoice grant. A renewal cannot
  receive a prior month's refund or be charged using stale grant identity.
- Normalize login email before account throttling; keep account throttle
  independent of rotating IP. Only accept X-Real-IP from explicitly trusted
  proxy addresses and validate it as one IP.
- Set all API responses private/no-store so CSRF and account data cannot enter
  a shared CDN cache. No shared generated output paths.
- Updated vulnerable starter build dependencies to patched versions; npm and
  pip audits report no known vulnerabilities in the final frontend/web locks.

## Web/API walk with evidence

| Surface | Evidence / result |
| --- | --- |
| A01/API1/API5 object/function access | `server/studio/views.py:60` session guard; `:157` checkout account from request.user; `:197` portal caller-owned customer; `:212` generation user only. No user-supplied customer/owner/credit/role fields. |
| A02/A07/API2 credentials | Django authentication/hash validation in `views.py:102`/`:123`; sessions/CSRF middleware and secure production cookie settings in `config/settings.py:24`/`:39`. No homemade crypto or browser-stored bearer tokens. Logout invalidates server session. |
| A03/API3 injection/mass assignment | `views.py:34` explicit JSON field allowlist; ORM only; no raw SQL/shell or template HTML. React escapes content. Shared provider module validates model/voice/path inputs. |
| A04/API4/API6 costs/abuse | `views.py:43` bounded TTL throttles; `:245` atomic conditional credits; `models.py:33` per-user unique request; `billing.py:39` unique invoice grant. App limits complement gateway/provider quotas. |
| A05/API8 config | Production secret/DB/Redis/HTTPS validation in `config/settings.py:6`; trusted proxy opt-in `:20`; native CSRF on every browser POST. `webhook` is the sole CSRF exception and requires SDK signature. Frontend and backend communicate same-origin. |
| A06/A08 dependencies/integrity | Hash-locked web requirements, npm lock; pinned CI actions; wheel-only/script-disabled installs. No arbitrary executable weights in commercial website. Rafter remote SCA remains pending. |
| A09 logs | Stable errors in `views.py:30`/`:69`; no API key/password/request content logging. Accounting retains IDs/state, not prompts or audio. Production must supply encrypted backups/retention policy. |
| A10/API7 SSRF | Reuse reviewed fixed provider origins; SDK Stripe endpoints fixed. No user-provided fetch/base URLs. Stripe return origin is operator config; checkout and portal destinations allowlisted. |
| API9 inventory | Website README lists every route, method and auth rule. Separate Streamlit beta remains a distinct local app, not a paid bypass route. |
| API10 provider consumption | Stripe state is re-read, SDK objects normalized, known price/customer/quantity/paid/current-status checked in `billing.py:14`. Provider response bounds and MIME/signature checks reused. No automatic billable retries. |
| Webhooks | `views.py:269` raw-body signature/time verification, unique event/invoice IDs, current-state reconciliation, safe retry on failure. `charge.dispute.created` resolves customer via charge; risk holds persist. |

## LLM walk

LLM01/05/06/07: text never gains tools/SQL/shell authority; no new autonomous
agent; no secrets in prompts; output played/downloaded as bounded audio only.
LLM02: only user-supplied content/style goes to the configured provider; no audio
or script persistence on server. LLM03: fixed reviewed model catalog and explicit
commercial allowlist; local noncommercial MusicGen cannot be enabled via web
configuration. LLM04/08: no training/RAG/vector store. LLM09: AI disclosure in
voice studio, editable scripts and manual review. LLM10: input/duration caps,
provider timeout/response-size limits, subscription/credit check before generation,
no retries/fan-out, bounded workers and operator quotas required at launch.

## Accepted draft limitations / release blockers

This is not a completed production subscription service. Final brand/domain,
pricing/allowances/margins, commercial provider terms, Stripe test/live account
and webhook setup, transactional email verification/password recovery, support,
privacy/terms/deletion policies, production TLS/DB/cache/secrets/backups and remote
Rafter SAST/SCA are still required. No real checkout or paid generation was run.
Process termination after reservation requires reconciliation; the system does
not automatically retry a potentially billable request. Audio is browser-local
and not recoverable from a server library after the response is lost.

## Validation

24 existing provider/Streamlit tests; 21 new backend account/billing/generation
and abuse tests; 4 frontend packaging tests; production frontend build. Browser
checks cover desktop/mobile, native modal/navigation, waveform playback/pause,
starter scripts, separate task content, auth-entry screens and unavailable
checkout. Automated tests mock Stripe/provider network mutations, while signature
tests exercise actual Stripe SDK verification with local signed fixtures.

Repository agent configuration contains only the user's accepted product
preferences in `website/AGENTS.md`; third-party starter instructions are not
forwarded into the repository. Its generated third-party instruction text was
replaced before publication. No new third-party skill/MCP/config was installed.
