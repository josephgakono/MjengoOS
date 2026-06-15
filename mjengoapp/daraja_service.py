import base64
import json
from datetime import datetime
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class DarajaServiceError(Exception):
    """Raised when Safaricom Daraja rejects or cannot process a request."""


class DarajaService:
    OAUTH_URL = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    STK_PUSH_URL = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'

    @classmethod
    def get_access_token(cls):
        # OAuth credentials are read from settings, which are populated by environment variables.
        consumer_key = cls._required_setting('MPESA_CONSUMER_KEY')
        consumer_secret = cls._required_setting('MPESA_CONSUMER_SECRET')
        credentials = f'{consumer_key}:{consumer_secret}'.encode('utf-8')
        encoded_credentials = base64.b64encode(credentials).decode('utf-8')

        response = cls._request_json(
            cls.OAUTH_URL,
            method='GET',
            headers={'Authorization': f'Basic {encoded_credentials}'},
        )
        access_token = response.get('access_token')
        if not access_token:
            raise DarajaServiceError('Daraja OAuth response did not include an access token.')
        return access_token

    @classmethod
    def generate_password_and_timestamp(cls):
        # Daraja expects the password to be base64(shortcode + passkey + timestamp).
        shortcode = cls._required_setting('MPESA_SHORTCODE')
        passkey = cls._required_setting('MPESA_PASSKEY')
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        raw_password = f'{shortcode}{passkey}{timestamp}'.encode('utf-8')
        password = base64.b64encode(raw_password).decode('utf-8')
        return password, timestamp

    @classmethod
    def send_stk_push(cls, phone_number, amount, account_reference, transaction_desc):
        access_token = cls.get_access_token()
        password, timestamp = cls.generate_password_and_timestamp()
        shortcode = cls._required_setting('MPESA_SHORTCODE')
        callback_url = cls._required_setting('MPESA_CALLBACK_URL')

        # STK Push amount must be a whole-number Kenyan shilling value for Daraja.
        amount_value = int(Decimal(amount))
        payload = {
            'BusinessShortCode': shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': amount_value,
            'PartyA': phone_number,
            'PartyB': shortcode,
            'PhoneNumber': phone_number,
            'CallBackURL': callback_url,
            'AccountReference': str(account_reference),
            'TransactionDesc': transaction_desc,
        }

        return cls._request_json(
            cls.STK_PUSH_URL,
            method='POST',
            headers={'Authorization': f'Bearer {access_token}'},
            payload=payload,
        )

    @staticmethod
    def _required_setting(name):
        value = getattr(settings, name, '')
        if not value:
            raise ImproperlyConfigured(f'{name} must be configured before using Daraja payments.')
        return value

    @staticmethod
    def _request_json(url, method='POST', headers=None, payload=None):
        request_headers = {
            'Accept': 'application/json',
            **(headers or {}),
        }
        data = None
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
            request_headers['Content-Type'] = 'application/json'

        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            detail = exc.read().decode('utf-8')
            raise DarajaServiceError(f'Daraja HTTP {exc.code}: {detail}') from exc
        except URLError as exc:
            parsed_url = urlparse(url)
            raise DarajaServiceError(f'Unable to reach Daraja host {parsed_url.netloc}: {exc.reason}') from exc
        except json.JSONDecodeError as exc:
            raise DarajaServiceError('Daraja returned an invalid JSON response.') from exc
