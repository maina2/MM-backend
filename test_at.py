import africastalking

# Initialize Africa’s Talking with your credentials
africastalking.initialize(
    username='sandbox',
    api_key='atsk_68dd6882b6a70bb2be8f22acc084850c609b4ce8cd53eaebee0e8af5a00a85c8f233410e'
)

# Test for Payment service
try:
    payment = africastalking.Payment
    print("Payment service found!")
except AttributeError:
    print("Payment service not found in africastalking module.")
    payment = None

# If payment service is found, test the connection
if payment:
    try:
        balance = payment.wallet_balance()
        print("Connection successful! Wallet balance:", balance)
    except Exception as e:
        print("Connection failed:", str(e))