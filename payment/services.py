import requests
import base64
from datetime import datetime,timedelta
import logging
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

logger = logging.getLogger(__name__)

class MpesaService:
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.base_url = getattr(settings, 'MPESA_BASE_URL', 'https://sandbox.safaricom.co.ke')
        self.access_token = None
        self.token_expiry = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(requests.RequestException),
        before_sleep=lambda retry_state: logger.warning(f"Retrying M-Pesa request: attempt {retry_state.attempt_number}")
    )
    def get_access_token(self):
        if self.access_token and self.token_expiry and self.token_expiry > datetime.now():
            return self.access_token
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        credentials = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {credentials}"}
        logger.info("Requesting M-Pesa access token")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        self.access_token = data.get('access_token')
        self.token_expiry = datetime.now() + timedelta(seconds=int(data.get('expires_in', 3600)) - 300)
        logger.info("M-Pesa access token obtained successfully")
        return self.access_token

    def generate_password(self, timestamp):
        data_to_encode = f"{self.shortcode}{self.passkey}{timestamp}"
        return base64.b64encode(data_to_encode.encode()).decode()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(requests.RequestException),
        before_sleep=lambda retry_state: logger.warning(f"Retrying STK Push: attempt {retry_state.attempt_number}")
    )
    def stk_push(self, phone_number, amount, account_reference, transaction_desc, callback_url):
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = self.generate_password(timestamp)
        headers = {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json"
        }
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": str(int(amount)),
            "PartyA": phone_number,
            "PartyB": self.shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc
        }
        logger.info(f"Initiating STK Push for {phone_number}, amount: {amount}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.info(f"STK Push response: {data}")
        return data