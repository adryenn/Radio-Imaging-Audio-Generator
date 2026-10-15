import hashlib
import hmac
import json
import time
from datetime import timedelta
from uuid import uuid4
from unittest.mock import MagicMock, patch

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from audio_providers import AudioResult, ProviderError
from .models import Account, BillingEvent, CreditGrant, Generation
from .billing import sync_subscription

PLANS = {'creator': {'name': 'Creator', 'price': 'price_creator', 'credits': 100}}


def obj(data):
    return stripe.StripeObject.construct_from(data, 'sk_test_fixture')


def subscription(status='active', invoice='in_1', price='price_creator', customer='cus_1', reason='subscription_cycle'):
    return obj({'id': 'sub_1', 'status': status, 'customer': customer,
                'items': {'data': [{'price': {'id': price}, 'quantity': 1,
                                    'current_period_end': int(time.time()) + 86400}]},
                'latest_invoice': {'id': invoice, 'status': 'paid', 'billing_reason': reason}})


@override_settings(WHITENOISE_ROOT=None)
class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='creator@example.test', email='creator@example.test', password='Creator!secure-password-123')
        self.account = Account.objects.create(user=self.user, customer='cus_1', subscription='sub_1', status='active', credits=100,
                                              expires=timezone.now() + timedelta(days=1), grant_invoice='in_1')
    def post(self, route, data, client=None):
        return (client or self.client).post('/api/' + route, data=json.dumps(data), content_type='application/json')


class AccountsTests(Base):
    def test_bootstrap_exposes_no_credentials_or_billing_ids(self):
        self.client.force_login(self.user)
        response = self.client.get('/api/bootstrap')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        payload = response.json()
        self.assertNotIn('customer', payload['user'])
        self.assertNotIn('password', json.dumps(payload))
        self.assertNotIn('api_key', json.dumps(payload))
        self.assertTrue(all(m['provider'] != 'Local MusicGen' for m in payload['models']))

    def test_csrf_is_required_for_login_signup_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        for route in ('signin', 'signup', 'signout', 'checkout', 'audio'):
            self.assertEqual(self.post(route, {}, client).status_code, 403)
        client.get('/api/bootstrap')
        token = client.cookies['csrftoken'].value
        response = client.post('/api/signin', data=json.dumps({'email': self.user.email, 'password': 'Creator!secure-password-123'}), content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_signup_login_logout_and_session_isolation(self):
        response = self.post('signup', {'email': 'new@example.test', 'password': 'NovelCreator!much-safer-555'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get('/api/bootstrap').json()['user']['email'], 'new@example.test')
        self.assertIsNone(Client().get('/api/bootstrap').json()['user'])
        self.post('signout', {})
        self.assertIsNone(self.client.get('/api/bootstrap').json()['user'])
        self.assertEqual(self.post('signin', {'email': 'new@example.test', 'password': 'NovelCreator!much-safer-555'}).status_code, 200)

    def test_weak_password_mass_assignment_and_invalid_json(self):
        self.assertEqual(self.post('signup', {'email': 'weak@example.test', 'password': '123'}).status_code, 400)
        self.assertEqual(self.post('signup', {'email': 'weak@example.test', 'password': 'A!verylongSecret-523', 'is_staff': True}).status_code, 400)
        self.assertEqual(self.client.post('/api/signin', data='[', content_type='application/json').status_code, 400)

    def test_login_rate_limit_is_generic(self):
        for _ in range(8):
            self.assertEqual(self.post('signin', {'email': 'missing@example.test', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.post('signin', {'email': 'missing@example.test', 'password': 'wrong'}).status_code, 429)

    def test_paid_endpoints_require_session(self):
        for route in ('checkout', 'portal', 'audio'):
            self.assertEqual(self.post(route, {}).status_code, 401)


@override_settings(PLANS=PLANS, STRIPE_SECRET_KEY='sk_test_fixture', STRIPE_WEBHOOK_SECRET='whsec_fixture')
class BillingTests(Base):
    @patch('studio.billing.client')
    def test_invoice_grant_is_once_and_refills_only_paid_cycle(self, client):
        client.return_value.v1.subscriptions.retrieve.return_value = subscription()
        self.account.credits = 30; self.account.save()
        sync_subscription(self.account, 'sub_1', 'in_1')
        self.assertEqual(self.account.credits, 100)
        self.account.credits = 25; self.account.save()
        sync_subscription(self.account, 'sub_1', 'in_1')
        self.assertEqual(self.account.credits, 25)
        self.assertEqual(CreditGrant.objects.count(), 1)
        client.return_value.v1.subscriptions.retrieve.return_value = subscription(invoice='in_2', reason='subscription_update')
        sync_subscription(self.account, 'sub_1', 'in_2')
        self.assertEqual(self.account.credits, 25)

    @patch('studio.billing.client')
    def test_unknown_price_unpaid_cancelled_and_billing_hold_fail_closed(self, client):
        for sub in [subscription(price='price_unknown'), subscription(status='canceled')]:
            client.return_value.v1.subscriptions.retrieve.return_value = sub
            sync_subscription(self.account, 'sub_1', 'in_1')
            self.assertEqual(self.account.status, 'inactive')
        sub = subscription(); sub['latest_invoice']['status'] = 'open'
        client.return_value.v1.subscriptions.retrieve.return_value = sub
        sync_subscription(self.account, 'sub_1', 'in_1')
        self.assertEqual(self.account.status, 'inactive')
        self.account.billing_hold = True; self.account.save()
        client.return_value.v1.subscriptions.retrieve.return_value = subscription()
        sync_subscription(self.account, 'sub_1', 'in_1')
        self.assertEqual(self.account.status, 'review')

    @patch('studio.billing.client')
    def test_customer_mismatch_is_rejected(self, client):
        client.return_value.v1.subscriptions.retrieve.return_value = subscription(customer='cus_other')
        with self.assertRaises(ValueError):
            sync_subscription(self.account, 'sub_1', 'in_1')

    def test_checkout_redirect_cannot_grant_credits(self):
        self.client.force_login(self.user)
        self.client.get('/?checkout=returned')
        self.assertEqual(self.client.get('/api/bootstrap').json()['user']['credits'], 100)
        self.assertEqual(CreditGrant.objects.count(), 0)

    @patch('studio.views.client')
    def test_checkout_price_customer_and_idempotency_are_server_owned(self, client):
        self.client.force_login(self.user)
        self.account.subscription = ''; self.account.save()
        client.return_value.v1.checkout.sessions.create.return_value = obj({'id': 'cs_1', 'url': 'https://checkout.stripe.com/c/pay/cs_1'})
        request_id = str(uuid4())
        response = self.post('checkout', {'plan': 'creator', 'requestId': request_id})
        self.assertEqual(response.status_code, 200)
        args = client.return_value.v1.checkout.sessions.create.call_args
        self.assertEqual(args.args[0]['customer'], 'cus_1')
        self.assertEqual(args.args[0]['line_items'][0]['price'], 'price_creator')
        self.assertIn(request_id, args.kwargs['options']['idempotency_key'])
        self.assertEqual(self.post('checkout', {'plan': 'creator', 'requestId': str(uuid4()), 'price': 'price_free'}).status_code, 400)

    @patch('studio.views.client')
    def test_open_checkout_is_reused(self, client):
        self.client.force_login(self.user)
        self.account.subscription = ''; self.account.pending_checkout = 'cs_open'; self.account.pending_plan = 'creator'; self.account.save()
        client.return_value.v1.checkout.sessions.retrieve.return_value = obj({'id': 'cs_open', 'status': 'open', 'url': 'https://checkout.stripe.com/c/pay/cs_open'})
        self.assertEqual(self.post('checkout', {'plan': 'creator', 'requestId': str(uuid4())}).status_code, 200)
        client.return_value.v1.checkout.sessions.create.assert_not_called()

    def test_missing_or_forged_webhook_signature_is_rejected(self):
        response = self.client.post('/api/stripe/webhook', data='{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='bad')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(BillingEvent.objects.exists())

    @patch('studio.views.sync_subscription')
    def test_real_signature_validates_and_event_replay_is_deduped(self, sync):
        payload = json.dumps({'id': 'evt_paid', 'object': 'event', 'type': 'invoice.paid', 'data': {'object': {'id': 'in_1', 'object': 'invoice', 'customer': 'cus_1', 'parent': {'subscription_details': {'subscription': 'sub_1'}}}}})
        timestamp = int(time.time())
        digest = hmac.new(b'whsec_fixture', f'{timestamp}.{payload}'.encode(), hashlib.sha256).hexdigest()
        for _ in range(2):
            response = self.client.post('/api/stripe/webhook', data=payload, content_type='application/json', HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={digest}')
            self.assertEqual(response.status_code, 200)
        sync.assert_called_once()
        self.assertEqual(BillingEvent.objects.count(), 1)

    @patch('studio.views.client')
    def test_portal_uses_only_current_users_customer(self, client):
        self.client.force_login(self.user)
        client.return_value.v1.billing_portal.sessions.create.return_value = obj({'url': 'https://billing.stripe.com/p/session/test'})
        self.assertEqual(self.post('portal', {}).status_code, 200)
        self.assertEqual(client.return_value.v1.billing_portal.sessions.create.call_args.args[0]['customer'], 'cus_1')


@override_settings(COMMERCIAL_MODELS={'gpt-4o-mini-tts'}, PROVIDER_KEYS={'OpenAI': 'test-key'})
class GenerationTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.data = {'model': 'gpt-4o-mini-tts', 'text': 'Hello creators.', 'voice': 'coral', 'style': '', 'seconds': 10, 'instrumental': False, 'requestId': str(uuid4())}

    @patch('studio.views.sync_subscription')
    @patch('studio.views.generate', return_value=AudioResult(b'ID3test', 'audio/mpeg', 'mp3'))
    def test_generation_reserves_once_and_returns_private_audio(self, generate, sync):
        response = self.post('audio', self.data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.account.refresh_from_db(); self.assertEqual(self.account.credits, 99)
        self.assertEqual(self.post('audio', self.data).status_code, 409)
        generate.assert_called_once()
        self.assertEqual(Generation.objects.get().status, 'completed')

    @patch('studio.views.sync_subscription')
    @patch('studio.views.generate', side_effect=RuntimeError('provider test-key raw error'))
    def test_failure_refunds_without_leaking_provider_error(self, generate, sync):
        response = self.post('audio', self.data)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn(b'test-key', response.content)
        self.account.refresh_from_db(); self.assertEqual(self.account.credits, 100)
        self.assertEqual(Generation.objects.get().status, 'refunded')

    @patch('studio.views.sync_subscription')
    @patch('studio.views.generate')
    def test_no_credits_or_expired_plan_never_calls_provider(self, generate, sync):
        for values in [{'credits': 0}, {'credits': 100, 'expires': timezone.now() - timedelta(days=1)}, {'credits': 100, 'expires': timezone.now()+timedelta(days=1), 'billing_hold': True}]:
            Account.objects.filter(pk=self.account.pk).update(**values)
            self.data['requestId'] = str(uuid4())
            self.assertEqual(self.post('audio', self.data).status_code, 402)
        generate.assert_not_called()
        self.assertFalse(Generation.objects.exists())

    @patch('studio.views.generate')
    def test_unapproved_local_models_and_malicious_voice_rejected(self, generate):
        for changes in [{'model': 'facebook/musicgen-small'}, {'voice': '../admin'}, {'customer': 'cus_other'}, {'text': 'x' * 5000}, {'seconds': 'large'}]:
            response = self.post('audio', {**self.data, **changes})
            self.assertEqual(response.status_code, 400)
        generate.assert_not_called()

class AbuseBoundaryTests(Base):
    def test_account_throttle_survives_rotating_ip_and_email_padding(self):
        for i in range(8):
            response = self.client.post('/api/signin', data=json.dumps({'email': ' ' * i + 'creator@example.test', 'password': 'wrong'}), content_type='application/json', REMOTE_ADDR=f'198.51.100.{i+1}')
            self.assertEqual(response.status_code, 401)
        response = self.client.post('/api/signin', data=json.dumps({'email': '  creator@example.test  ', 'password': 'wrong'}), content_type='application/json', REMOTE_ADDR='198.51.100.100')
        self.assertEqual(response.status_code, 429)

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_fixture', STRIPE_SECRET_KEY='sk_test_fixture')
    def test_stale_signature_does_not_process_event(self):
        payload = json.dumps({'id': 'evt_old', 'object': 'event', 'type': 'invoice.paid', 'data': {'object': {}}})
        stamp = int(time.time()) - 1000
        digest = hmac.new(b'whsec_fixture', f'{stamp}.{payload}'.encode(), hashlib.sha256).hexdigest()
        response = self.client.post('/api/stripe/webhook', data=payload, content_type='application/json', HTTP_STRIPE_SIGNATURE=f't={stamp},v1={digest}')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(BillingEvent.objects.exists())
