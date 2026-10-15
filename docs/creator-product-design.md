# Creator subscription product — secure design before implementation

Audience: podcasters and content creators. Radio imaging informs sonic craft;
this product is not sold as a radio-station service. Selected direction: first
visual concept, near-black, ivory condensed headings, lime accents, cinematic
microphone. Working name Creator Imaging Studio until user selects a brand.

## Product and payment scope

Public responsive landing page with playable examples, workflow and plan entry;
creator studio with exact voiceover scripts / music and effect descriptions,
editable generated audio, playback/download. Real account and subscription API
foundation; payments are unavailable until operator configures Stripe products,
webhook secret and approved plans. Never show a successful payment or grant
credits from a redirect or local demo. Local demonstrations explicitly labelled.
Pricing and included credits are configuration, not fabricated promises.

## Rafter authentication, storage, API and STRIDE decisions

Browser → Django on same origin → database; Django → fixed Stripe/provider
origins. Vite serves the frontend in development only, proxying API to Django.
Django sessions and CSRF middleware, built-in password hashing/validation; no
custom crypto, password reset/token system or browser-stored bearer tokens.
Production cookies Secure, HttpOnly session, SameSite=Lax; explicit hosts and
trusted origins, HTTPS, secret key/database required. Logout invalidates session.
Account identity always from authenticated session, never client supplied user ID.

Use Django ORM user ownership checks for all profile, billing and generation
operations. No arbitrary lookup endpoints. No raw SQL or request mass assignment.
User email/account ID is PII; password hash is credential; customer/subscription
IDs are payment metadata; no cards are handled by our app. Stripe hosted Checkout
and customer portal handle card data and subscription self-service. App stores
only account, entitlement and generation accounting, no generated audio/scripts.
Logs must not contain keys, auth bodies or provider errors. Production database,
backups and secrets managed/encrypted by host; remove local session data on logout.
Account deletion and legally appropriate billing retention require launch policy.
No auto email sends added before mail delivery/configuration is selected.

Stripe secret API keys never reach React. Server allowlists plans mapped to
Stripe price IDs. Session-authenticated CSRF-protected checkout creation, fixed
site origin for return URLs, idempotency keys for external mutations. Portal
customer ID comes only from profile. Webhooks verify signature against raw body
with Stripe SDK and its timestamp tolerance; deduplicate event IDs transactionally.
Read current subscription/invoice from Stripe rather than trusting event arrival
order. Entitlement comes from paid invoice and active subscription with a known
price/customer mapping; unknown/free/malformed objects fail closed. Cancellation
or payment failure removes generation eligibility. Do not grant on checkout URL.

Generation: reuses allowlisted provider adapters and limits, paid entitlements
verified server-side. Reserve bounded credits with atomic update before network;
job ID scoped to user prevents duplicate generation; no billable retries. Provider
failures return generic error and refund reserved app credits once; upstream
billing may still apply. Outputs delivered in response and kept in browser memory.
Local MusicGen excluded from commercial service; provider/model availability is
an operator-controlled commercial allowlist, with music rights/resale explicitly
reviewed before enablement. AI keys from host secret manager via runtime injection.

Abuse twins: signup→credential stuffing (password validation and throttle);
checkout→price tampering (server plan mapping); webhook→replay/refill (verified
signature and unique invoice/event IDs); generate→parallel overspending (atomic
credit reserve, idempotency); download→cross-user exposure (no shared output path).

Spoofing/tampering: TLS, framework sessions/CSRF, SDK signature verification.
Repudiation: durable accounting identifiers, no sensitive content logging.
Disclosure: ORM ownership, scoped headers, no cross-session content cache.
Denial/cost abuse: field/body/time/size bounds, throttled auth/generation,
credits reserved before provider calls. Elevation: no client-controlled roles,
customers, credit grants or provider URLs. No model tools/agency or executable
model output.

Residual launch gates: provider commercial/resale eligibility, approved product
name/domain/pricing, Stripe account and webhook configuration, transactional email
and recovery flow, production infrastructure/TLS/secrets/backups, final Rafter
remote SAST/SCA (user previously authorized draft PR with scan pending). Mocked
integration tests are not live purchase or provider-quality verification.
