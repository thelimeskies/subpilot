"""Preflight: prep a payment method that always fails, for the dunning path.

Run inside the web container::

    python manage.py shell < scripts/e2e_preflight.py
"""
from apps.customers.models import Customer, PaymentMethod
from apps.accounts.models import Merchant

merchant = Merchant.objects.get(slug="acme")
chinedu = Customer.objects.get(merchant=merchant, email="chinedu@example.com")
pm = chinedu.payment_methods.filter(is_default=True).first()
if pm is None:
    print("FAIL: chinedu has no default PM")
else:
    pm.token = "tok_fail_insufficient"  # encrypted via property setter
    pm.save(update_fields=["token_encrypted", "updated_at"])
    print(f"OK preflight: chinedu.pm={pm.id} token now triggers insufficient_funds")
