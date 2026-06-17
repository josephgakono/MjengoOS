import base64
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class DarajaServiceError(Exception):
    """Raised when Safaricom Daraja rejects or cannot process a request."""


def normalize_mpesa_phone_number(phone_number):
    """Normalize common Kenyan phone formats to Daraja's 2547XXXXXXXX or 2541XXXXXXXX format."""

    phone = str(phone_number).strip().replace(' ', '').replace('-', '').replace('+', '')

    if phone.startswith('0'):
        phone = f'254{phone[1:]}'
    elif phone.startswith('7') or phone.startswith('1'):
        phone = f'254{phone}'

    if not phone.isdigit() or len(phone) != 12 or not phone.startswith('254'):
        raise ValueError('Enter a valid Kenyan phone number in the format 2547XXXXXXXX or 2541XXXXXXXX.')

    return phone


class DarajaService:
    OAUTH_PATH = '/oauth/v1/generate?grant_type=client_credentials'
    STK_PUSH_PATH = '/mpesa/stkpush/v1/processrequest'

    @classmethod
    def get_access_token(cls):
        # OAuth credentials are read from settings, which are populated by environment variables.
        consumer_key = cls._required_setting('MPESA_CONSUMER_KEY')
        consumer_secret = cls._required_setting('MPESA_CONSUMER_SECRET')
        credentials = f'{consumer_key}:{consumer_secret}'.encode('utf-8')
        encoded_credentials = base64.b64encode(credentials).decode('utf-8')

        response = cls._request_json(
            cls._build_url(cls.OAUTH_PATH),
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
        normalized_phone_number = normalize_mpesa_phone_number(phone_number)

        # STK Push amount must be a whole-number Kenyan shilling value for Daraja.
        amount_value = int(Decimal(amount))
        payload = {
            'BusinessShortCode': shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': amount_value,
            'PartyA': normalized_phone_number,
            'PartyB': shortcode,
            'PhoneNumber': normalized_phone_number,
            'CallBackURL': callback_url,
            'AccountReference': str(account_reference),
            'TransactionDesc': transaction_desc,
        }

        return cls._request_json(
            cls._build_url(cls.STK_PUSH_PATH),
            method='POST',
            headers={'Authorization': f'Bearer {access_token}'},
            payload=payload,
        )

    @staticmethod
    def _build_url(path):
        base_url = getattr(settings, 'MPESA_BASE_URL', '').rstrip('/')
        if not base_url:
            raise ImproperlyConfigured('MPESA_BASE_URL must be configured before using Daraja payments.')
        return f'{base_url}{path}'

    @staticmethod
    def _required_setting(name):
        value = getattr(settings, name, '')
        if not value:
            raise ImproperlyConfigured(f'{name} must be configured before using Daraja payments.')
        return value

    @staticmethod
    def _request_json(url, method='POST', headers=None, payload=None):
        headers = {
            'Accept': 'application/json',
            **(headers or {}),
        }

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            status_code = exc.response.status_code if exc.response is not None else 'error'
            raise DarajaServiceError(f'Daraja HTTP {status_code}: {detail}') from exc
        except requests.RequestException as exc:
            raise DarajaServiceError(f'Unable to reach Daraja: {exc}') from exc
        except ValueError as exc:
            raise DarajaServiceError('Daraja returned an invalid JSON response.') from exc
