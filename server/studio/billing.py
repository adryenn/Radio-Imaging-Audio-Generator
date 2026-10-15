from datetime import datetime, timezone
import stripe
from django.conf import settings
from django.db import transaction
from .models import Account, CreditGrant


def client():
    if not settings.STRIPE_SECRET_KEY:
        raise ValueError('Subscriptions are not configured yet.')
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY, max_network_retries=0)


def sync_subscription(account, subscription_id, grant_invoice=None):
    """Reconcile latest Stripe state, never event order or a browser redirect."""
    sub = client().v1.subscriptions.retrieve(subscription_id, {'expand': ['latest_invoice']}).to_dict()
    if sub['customer'] != account.customer:
        raise ValueError('Billing account mismatch.')
    if account.subscription and account.subscription != subscription_id:
        existing = client().v1.subscriptions.retrieve(account.subscription)
        if existing.status not in ('canceled', 'incomplete_expired'):
            return
        if not grant_invoice:
            return
    items = sub['items']['data']
    plan = next((slug for slug, p in settings.PLANS.items()
                 if len(items) == 1 and items[0]['price']['id'] == p['price'] and p['price']
                 and items[0].get('quantity', 1) == 1), None)
    invoice = sub.get('latest_invoice')
    paid = isinstance(invoice, dict) and invoice.get('status') == 'paid'
    end = items[0].get('current_period_end', sub.get('current_period_end', 0)) if items else 0
    status = 'active' if plan and paid and sub['status'] == 'active' else 'inactive'
    with transaction.atomic():
        current = Account.objects.select_for_update().get(pk=account.pk)
        current.pending_checkout, current.pending_plan = '', ''
        current.subscription, current.plan, current.status = sub['id'], plan or '', 'review' if current.billing_hold else status
        current.expires = datetime.fromtimestamp(end, timezone.utc) if end else None
        if status == 'active' and not current.billing_hold and grant_invoice and invoice['id'] == grant_invoice and invoice.get('billing_reason') in ('subscription_create', 'subscription_cycle'):
            _, created = CreditGrant.objects.get_or_create(invoice=grant_invoice, defaults={'account': current})
            if created:
                current.credits = settings.PLANS[plan]['credits']
                current.grant_invoice = grant_invoice
        current.save()
    account.refresh_from_db()
