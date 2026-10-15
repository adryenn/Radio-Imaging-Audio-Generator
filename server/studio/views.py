import hashlib
import ipaddress
import json
import math
import re
from functools import wraps
from uuid import UUID

import stripe
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse, HttpResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from audio_catalog import MODELS
from audio_providers import AudioRequest, ProviderError, generate, validate
from .models import Account, BillingEvent, Generation
from .billing import client, sync_subscription


def error(message, status=400):
    return JsonResponse({'error': message}, status=status)


def body(request, fields):
    if len(request.body) > 12000:
        raise ValueError('Request is too large.')
    data = json.loads(request.body)
    if not isinstance(data, dict) or set(data) - set(fields):
        raise ValueError('Invalid request fields.')
    return data


def limit(request, action, maximum, identity=''):
    # Accept a single normalized address only from an explicitly trusted proxy.
    address = request.META.get('REMOTE_ADDR', '')
    if address in settings.TRUSTED_PROXY_IPS:
        try:
            address = str(ipaddress.ip_address(request.META.get('HTTP_X_REAL_IP', address)))
        except ValueError:
            pass
    raw = action + ':' + (identity if action == 'login-account' else address + ':' + identity)
    key = 'limit:' + hashlib.sha256(raw.encode()).hexdigest()
    cache.add(key, 0, timeout=300)
    try:
        return cache.incr(key) <= maximum
    except ValueError:
        return False


def protected(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return error('Sign in to continue.', 401)
        return view(request, *args, **kwargs)
    return wrapped


def safe(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except (ValueError, TypeError, KeyError, AttributeError, ValidationError, IntegrityError, RecursionError):
            return error('Please check your request and try again.')
        except stripe.StripeError:
            return error('Billing is temporarily unavailable. Please try again later.', 503)
    return wrapped


def account_data(user):
    if not user.is_authenticated:
        return None
    account, _ = Account.objects.get_or_create(user=user)
    return {'email': user.email, 'plan': account.plan, 'credits': account.credits,
            'active': account.status == 'active' and bool(account.expires and account.expires > timezone.now())}


@require_GET
def bootstrap(request):
    models = [{'provider': m.provider, 'task': m.task, 'model': m.model,
               'voices': m.voices, 'style': m.style, 'maxChars': m.max_chars,
               'minSeconds': m.min_seconds, 'maxSeconds': m.max_seconds,
               'instrumental': m.instrumental, 'note': m.note}
              for m in MODELS if m.provider != 'Local MusicGen' and m.model in settings.COMMERCIAL_MODELS]
    return JsonResponse({'csrf': get_token(request), 'user': account_data(request.user), 'models': models,
                         'plans': [{'id': slug, 'name': plan['name'], 'enabled': bool(plan['price'] and plan['credits'] > 0 and settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET)} for slug, plan in settings.PLANS.items()]})


@require_POST
@safe
def signup(request):
    if not limit(request, 'signup', 5):
        return error('Too many attempts. Please try again in a few minutes.', 429)
    data = body(request, ('email', 'password'))
    email, password = data.get('email', ''), data.get('password', '')
    if not isinstance(email, str) or not isinstance(password, str) or len(email) > 150 or len(password) > 128:
        return error('Use a valid email and a password of 12–128 characters.')
    email = email.strip().lower()
    validate_email(email)
    user = get_user_model()(username=email, email=email)
    validate_password(password, user)
    user.set_password(password)
    with transaction.atomic():
        user.save()
        Account.objects.create(user=user)
    login(request, user)
    return JsonResponse({'user': account_data(user), 'csrf': get_token(request)}, status=201)


@require_POST
@safe
def signin(request):
    data = body(request, ('email', 'password'))
    email, password = data.get('email', ''), data.get('password', '')
    if not isinstance(email, str) or not isinstance(password, str) or len(email) > 150 or len(password) > 128:
        return error('Invalid email or password.', 401)
    email = email.strip().lower()
    if not limit(request, 'login-ip', 20) or not limit(request, 'login-account', 8, email.lower()):
        return error('Too many attempts. Please try again in a few minutes.', 429)
    user = authenticate(request, username=email.strip().lower(), password=password)
    if user is None:
        return error('Invalid email or password.', 401)
    login(request, user)
    return JsonResponse({'user': account_data(user), 'csrf': get_token(request)})


@require_POST
def signout(request):
    logout(request)
    return JsonResponse({'csrf': get_token(request)})


@require_POST
@protected
@safe
def checkout(request):
    if not limit(request, 'checkout', 5, str(request.user.pk)):
        return error('Too many requests. Try again later.', 429)
    data = body(request, ('plan', 'requestId'))
    request_id = str(UUID(data.get('requestId', '')))
    plan = settings.PLANS.get(data.get('plan'))
    if not plan or not plan['price'] or plan['credits'] <= 0 or not settings.STRIPE_WEBHOOK_SECRET:
        return error('Subscriptions are not available yet. You can explore the studio.', 503)
    api = client()
    account, _ = Account.objects.get_or_create(user=request.user)
    if account.billing_hold:
        return error('Please contact support about your billing account.', 403)
    if account.subscription:
        sub = api.v1.subscriptions.retrieve(account.subscription)
        if sub.status not in ('canceled', 'incomplete_expired'):
            return error('Manage your existing subscription in billing.', 409)
    if not account.customer:
        customer = api.v1.customers.create({'email': request.user.email}, options={'idempotency_key': f'customer-{request.user.pk}'})
        Account.objects.filter(pk=account.pk, customer__isnull=True).update(customer=customer.id)
        account.refresh_from_db()
    with transaction.atomic():
        account = Account.objects.select_for_update().get(pk=account.pk)
        if account.pending_checkout:
            pending = api.v1.checkout.sessions.retrieve(account.pending_checkout)
            if pending.status == 'open':
                if account.pending_plan != data['plan']:
                    return error('Finish or cancel your existing checkout before choosing another plan.', 409)
                session = pending
            elif pending.status == 'complete':
                return error('Your payment is being confirmed. Refresh your studio shortly.', 409)
            else:
                account.pending_checkout = ''
        if not account.pending_checkout:
            session = api.v1.checkout.sessions.create({
                'customer': account.customer, 'mode': 'subscription',
                'line_items': [{'price': plan['price'], 'quantity': 1}],
                'client_reference_id': str(request.user.pk),
                'success_url': settings.SITE_URL + '/?checkout=returned',
                'cancel_url': settings.SITE_URL + '/?checkout=cancelled',
            }, options={'idempotency_key': f'checkout-{request.user.pk}-{request_id}'})
            account.pending_checkout, account.pending_plan = session.id, data['plan']
            account.save(update_fields=['pending_checkout', 'pending_plan'])
    if not session.url.startswith('https://checkout.stripe.com/'):
        return error('Unexpected checkout destination.', 503)
    return JsonResponse({'url': session.url})


@require_POST
@protected
@safe
def portal(request):
    if not limit(request, 'portal', 10, str(request.user.pk)):
        return error('Too many requests.', 429)
    account = Account.objects.get(user=request.user)
    if not account.customer:
        return error('No billing account is connected yet.')
    session = client().v1.billing_portal.sessions.create({'customer': account.customer, 'return_url': settings.SITE_URL})
    if not session.url.startswith('https://billing.stripe.com/'):
        return error('Unexpected billing destination.', 503)
    return JsonResponse({'url': session.url})


@require_POST
@protected
@safe
def audio(request):
    if not limit(request, 'audio', 10, str(request.user.pk)):
        return error('Too many generation requests. Please wait.', 429)
    data = body(request, ('model', 'text', 'voice', 'style', 'seconds', 'instrumental', 'requestId'))
    request_id = UUID(data.get('requestId', ''))
    spec = next((m for m in MODELS if m.model == data.get('model') and m.model in settings.COMMERCIAL_MODELS and m.provider != 'Local MusicGen'), None)
    if not spec:
        return error('Choose an enabled model.')
    if not settings.PROVIDER_KEYS.get(spec.provider):
        return error('This provider is not connected yet.', 503)
    text = data.get('text', '')
    voice, style = data.get('voice', ''), data.get('style', '')
    seconds = data.get('seconds', 10)
    instrumental = data.get('instrumental', False)
    if not all(isinstance(v, str) for v in (text, voice, style)) or not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not isinstance(instrumental, bool):
        return error('Invalid audio settings.')
    req = AudioRequest(spec, text, settings.PROVIDER_KEYS[spec.provider], voice, style, seconds, instrumental)
    try:
        validate(req)
    except ProviderError as exc:
        return error(str(exc))
    account = Account.objects.get(user=request.user)
    if not account.subscription:
        return error('An active subscription is required for generation.', 402)
    sync_subscription(account, account.subscription)
    # Conservative app-credit schedule, independent of upstream currency prices.
    cost = max(1, math.ceil(len(text) / 100)) if spec.task == 'Speech' else math.ceil(seconds) * (3 if spec.task == 'Music' else 1)
    # Lyria has no duration parameter: reserve a full bounded song allowance.
    if spec.provider == 'Google' and spec.task == 'Music':
        cost = 540
    try:
        with transaction.atomic():
            job = Generation.objects.create(user=request.user, request_id=request_id, credits=cost, grant_invoice=account.grant_invoice)
            changed = Account.objects.filter(pk=account.pk, status='active', billing_hold=False, grant_invoice=account.grant_invoice, expires__gt=timezone.now(), credits__gte=cost).update(credits=F('credits') - cost)
            if not changed:
                raise ValueError('Insufficient credits.')
    except IntegrityError:
        return error('This request was already submitted. Check your last result.', 409)
    except ValueError:
        return error('You need an active plan with enough credits.', 402)
    try:
        result = generate(req)
    except Exception:
        with transaction.atomic():
            refunded = Generation.objects.filter(pk=job.pk, status='reserved').update(status='refunded')
            if refunded:
                Account.objects.filter(pk=account.pk, grant_invoice=job.grant_invoice, billing_hold=False).update(credits=F('credits') + cost)
        return error('Generation failed. Reserved studio credits were returned. Please try again later.', 502)
    Generation.objects.filter(pk=job.pk).update(status='completed')
    response = HttpResponse(result.data, content_type=result.mime)
    response['Content-Disposition'] = f'attachment; filename="creator-audio.{result.extension}"'
    response['Cache-Control'] = 'private, no-store'
    return response


@csrf_exempt
@require_POST
def webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET or not settings.STRIPE_SECRET_KEY:
        return error('Billing is not configured.', 503)
    if len(request.body) > 100000:
        return error('Invalid webhook.', 400)
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers.get('Stripe-Signature', ''), settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return error('Invalid webhook.', 400)
    if BillingEvent.objects.filter(event_id=event.id).exists():
        return JsonResponse({'received': True})
    try:
        obj = event.data.object.to_dict()
        customer = obj.get('customer')
        if event.type == 'charge.dispute.created' and not customer and obj.get('charge'):
            customer = client().v1.charges.retrieve(obj['charge']).customer
        account = Account.objects.filter(customer=customer).first() if isinstance(customer, str) else None
        if account:
            if event.type.startswith('customer.subscription.'):
                sync_subscription(account, obj['id'])
            elif event.type in ('invoice.paid', 'invoice.payment_failed'):
                parent = obj.get('parent') or {}
                sub_id = obj.get('subscription') or (parent.get('subscription_details') or {}).get('subscription')
                if sub_id:
                    sync_subscription(account, sub_id, obj['id'] if event.type == 'invoice.paid' else None)
            elif event.type in ('charge.refunded', 'charge.dispute.created'):
                # Fail closed for risk events; operator must review and restore explicitly.
                Account.objects.filter(pk=account.pk).update(status='review', credits=0, billing_hold=True)
        BillingEvent.objects.get_or_create(event_id=event.id)
    except Exception:
        return error('Billing reconciliation failed. Retry this event.', 503)
    return JsonResponse({'received': True})
