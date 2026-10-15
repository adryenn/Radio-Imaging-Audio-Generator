from django.conf import settings
from django.db import models

class Account(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    customer = models.CharField(max_length=100, unique=True, null=True)
    subscription = models.CharField(max_length=100, blank=True)
    pending_checkout = models.CharField(max_length=120, blank=True)
    pending_plan = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=30, default='inactive')
    billing_hold = models.BooleanField(default=False)
    grant_invoice = models.CharField(max_length=120, blank=True)
    plan = models.CharField(max_length=20, blank=True)
    credits = models.PositiveIntegerField(default=0)
    expires = models.DateTimeField(null=True)

class BillingEvent(models.Model):
    event_id = models.CharField(max_length=120, unique=True)
    created = models.DateTimeField(auto_now_add=True)

class CreditGrant(models.Model):
    invoice = models.CharField(max_length=120, unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

class Generation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request_id = models.UUIDField()
    grant_invoice = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, default='reserved')
    credits = models.PositiveIntegerField()
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'request_id'], name='unique_user_generation')]
