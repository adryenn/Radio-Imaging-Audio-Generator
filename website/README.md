# Creator Imaging Studio website

Audience: **podcasters and content creators**. Radio imaging contributes the
craft of sonic identity, not the target market. The user selected the first dark,
cinematic/lime concept, then explicitly corrected the audience. Creator Imaging
Studio is a working name, not a confirmed brand/domain.

## Local preview

At repository root, use Python 3.11 and the shared isolated environment:

```sh
uv pip install --python .venv/bin/python --only-binary :all: --require-hashes -r requirements-web.txt
.venv/bin/python server/manage.py migrate
.venv/bin/python server/manage.py runserver 127.0.0.1:8000 --noreload
```

In this folder:

```sh
npm ci --ignore-scripts
npm run dev -- --host 127.0.0.1 --port 4173 --strictPort
```

Open `http://localhost:4173`. The Vite proxy sends `/api` to the loopback Django
service; the browser uses same-origin cookies/CSRF, no CORS wildcard or tokens in
localStorage. `server/.env.example` lists settings, but it is intentionally not
loaded automatically: inject values in the process or hosting secret manager.
The original `streamlit run radio_imaging_app.py` workflow remains available.

## What works now

- Responsive creator-focused landing page, navigation and native dialogs.
- Three original synthesized music demos, waveform seeking, play/pause and WAV
  downloads. Only one demo plays at once. They contain no third-party samples;
  regenerate with `python website/scripts/create-demos.py` from repo root.
- Studio tabs, separate scripts/descriptions per task, starter ideas, voice/style
  settings, generated-audio playback and downloads.
- Real Django account creation/sign-in/logout, sessions, CSRF, password validation
  and throttling. Production still needs the email recovery/verification and
  support flows described below; do not mistake local accounts for launch readiness.
- Stripe hosted Checkout and billing portal APIs. Price/customer IDs are selected
  server-side, checkout uses idempotency and an open session is reused to prevent
  duplicate subscriptions. A return URL cannot grant access or credits.
- Signed Stripe webhook reconciliation, paid invoice credit grants, active-plan
  checks, atomic credit reservation, request deduplication and one-time refunds
  on generation errors. Risk/refund events put the account on a persistent hold.
- Commercial provider/model allowlist. MusicGen is kept in the original local app
  and excluded from paid generation. Default web allowlist is OpenAI mini-TTS;
  add music/effects only after the relevant commercial/resale review.

## What is deliberately unavailable until configured

Checkout remains disabled unless Stripe secret + webhook secret, a price ID and
positive credit allowance exist for the plan. No prices or quotas were invented.
The public UI shows plan concepts, not active offers. No payment has been taken.
Paid generation also needs the configured provider key and verified entitlement.
There is no free trial, unlimited promise, team collaboration or live generation
claim. Account entitlements are not fabricated in browser state.

## Production launch requirements

1. Confirm brand, domain, currency, prices, credit allowances and fair-use policy.
   Current app-credit schedule: speech 1/100 characters rounded up; effects
   1/second; music 3/second; Lyria reserves 540 per song (no exact duration API).
   Validate margins from provider invoices before publishing offers.
2. Confirm commercial/resale rights for each enabled provider/model. Standard
   MusicGen weights are noncommercial. ElevenLabs music resale requires approved
   reseller terms, separately from output-use rights. Podcast/video usage still
   requires checking plan/provider terms; do not claim blanket rights.
3. Configure Stripe test mode first, monthly recurring prices with quantity 1,
   customer portal, and `/api/stripe/webhook` for invoice.paid,
   invoice.payment_failed, customer.subscription.created/updated/deleted,
   charge.refunded and charge.dispute.created. The tested adapter is based on the
   current Stripe Python v1 service namespace and invoice parent schema.
4. Complete transactional email, email verification, password recovery, support,
   privacy/terms and deletion/retention policies before public onboarding.
5. Deploy behind HTTPS on commercial hosting with PostgreSQL, Redis, encrypted
   backups and secrets manager; set APP_ENV=production, SITE_URL, ALLOWED_HOSTS,
   strong DJANGO_SECRET_KEY, DATABASE_URL and REDIS_URL. The app refuses production
   SQLite or missing secrets/cache. Keep the backend behind the trusted proxy.
   Only set TRUST_PROXY_TLS=1 / TRUSTED_PROXY_IPS when that proxy strips incoming
   forwarding headers and sets X-Forwarded-Proto / a single X-Real-IP itself.
6. Build frontend before starting backend; WhiteNoise serves `dist/client` with
   index handling. From repo root: `gunicorn --chdir server config.wsgi:application
   --bind 127.0.0.1:8000 --timeout 300`. The WSGI entrypoint imports the shared audio adapters from the repo root.
   Use a bounded worker pool and provider quotas.
7. Run signed test-mode checkout/renewal/cancellation/refund and paid-provider
   smoke tests. No such real transactions were performed during this build.
   Reconcile jobs left `reserved` after process termination manually; retries do
   not issue another upstream generation automatically. Failed prior-period jobs
   never refill a newer month's allowance. Audio is not retained server-side.
8. Run the required Rafter remote SAST/SCA before merge/launch. It remains pending
   because CLI/key are unavailable; user previously permitted a draft PR with this
   gate clearly recorded. Manual review and dependency audits are not substitutes.

The frontend starter preserves Sites packaging, but deploying that static Worker
alone **does not deploy Django or provide accounts/payments**. The full product
needs the same-origin backend. Nothing was publicly deployed.

## API inventory

| Route | Method | Authorization / purpose |
| --- | --- | --- |
| `/api/bootstrap` | GET | Public config + only the caller's account; private/no-store CSRF bootstrap |
| `/api/signup`, `/api/signin` | POST | CSRF + validation + IP/account throttles |
| `/api/signout` | POST | CSRF, invalidate caller's session |
| `/api/checkout` | POST | Auth + CSRF, allowlisted plan and server-owned customer |
| `/api/portal` | POST | Auth + CSRF, caller's customer only |
| `/api/audio` | POST | Auth + CSRF, fresh subscription check, allowlist and atomic credits |
| `/api/stripe/webhook` | POST | SDK signature/timestamp verification over raw body; only CSRF exception |

## Verification

```sh
python -m unittest discover -s tests -v
python server/manage.py test studio
cd website && npm run build && npm run test:sites
npm audit
```

Backend tests cover SDK object conversion, real webhook HMAC verification,
replay/credit deduplication, plan/customer tampering, protected routes, CSRF,
account/session isolation, quota reservation/refund and error redaction. All
provider/Stripe network mutations are mocked: passing tests do not prove account
entitlement, provider audio quality or real payment behavior.
