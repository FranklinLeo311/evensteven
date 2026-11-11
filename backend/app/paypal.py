"""PayPal REST calls (Orders v2): create an order for one friend's share and capture it once they approve."""
import time

import httpx

from .config import get_settings

# currencies PayPal Checkout settles; anything else falls back to the default currency
PAYPAL_CURRENCIES = {"AUD", "BRL", "CAD", "CNY", "CZK", "DKK", "EUR", "HKD", "HUF", "ILS", "JPY", "MYR", "MXN", "TWD", "NZD",
                     "NOK", "PHP", "PLN", "GBP", "SGD", "SEK", "CHF", "THB", "USD"}
NO_DECIMAL_CURRENCIES = {"HUF", "JPY", "TWD"}
_token = {"value": "", "expires": 0.0}


class PayPalError(RuntimeError):
    pass


def settle_currency(currency: str) -> str:
    code = (currency or "").upper()
    return code if code in PAYPAL_CURRENCIES else get_settings().default_currency


def _access_token() -> str:
    if _token["value"] and time.time() < _token["expires"]:
        return _token["value"]
    settings = get_settings()
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise PayPalError("PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are not set in backend/.env")
    response = httpx.post(f"{settings.paypal_base_url}/v1/oauth2/token", auth=(settings.paypal_client_id, settings.paypal_client_secret),
                          data={"grant_type": "client_credentials"}, timeout=30)
    if response.status_code != 200:
        raise PayPalError(f"PayPal sign-in failed ({response.status_code}): {response.text[:300]}")
    body = response.json()
    _token.update(value=body["access_token"], expires=time.time() + body.get("expires_in", 300) - 60)
    return _token["value"]


def _call(method: str, path: str, json: dict | None = None, request_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json"}
    if request_id:
        # PayPal-Request-Id makes a retried create return the same order instead of a second one
        headers["PayPal-Request-Id"] = request_id
    response = httpx.request(method, f"{get_settings().paypal_base_url}{path}", json=json, headers=headers, timeout=30)
    if response.status_code >= 400:
        raise PayPalError(f"PayPal {path} failed ({response.status_code}): {response.text[:500]}")
    return response.json()


def create_order(share_id: str, amount: float, currency: str, description: str, payee_email: str | None) -> dict:
    value = f"{amount:.0f}" if currency in NO_DECIMAL_CURRENCIES else f"{amount:.2f}"
    unit = {"reference_id": share_id, "description": description[:127], "amount": {"currency_code": currency, "value": value}}
    if payee_email:
        # the friend who paid the bill gets the money directly
        unit["payee"] = {"email_address": payee_email}
    return _call("POST", "/v2/checkout/orders", {"intent": "CAPTURE", "purchase_units": [unit]}, request_id=f"order-{share_id}-{value}")


def capture_order(order_id: str) -> dict:
    return _call("POST", f"/v2/checkout/orders/{order_id}/capture", {}, request_id=f"capture-{order_id}")
