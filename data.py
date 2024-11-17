import os
import datetime
from dotenv import load_dotenv

# Load environmental variables from the ".env" file:
load_dotenv()

# Get Stripe API keys:
API_STRIPE_KEY_TEST_PUBLISHABLE = os.getenv("API_STRIPE_KEY_TEST_PUBLISHABLE")
API_STRIPE_KEY_TEST_SECRET = os.getenv("API_STRIPE_KEY_TEST_SECRET")

# Define constants to be used for e-mailing messages submitted via the "Contact Us" web page:
SENDER_EMAIL_GMAIL = os.getenv("SENDER_EMAIL_GMAIL")
SENDER_PASSWORD_GMAIL = os.getenv("SENDER_PASSWORD_GMAIL") # App password (for the app "Python e-mail", NOT the normal password for the account).
SENDER_HOST = os.getenv("SENDER_HOST")
SENDER_PORT = str(os.getenv("SENDER_PORT"))

# Define constant for identifying this site's domain (used in processing payments via Stripe):
SITE_DOMAIN = os.getenv("SITE_DOMAIN")

# Define constant for secret key for CSRF protection:
SECRET_KEY_FOR_CSRF_PROTECTION = os.getenv("SECRET_KEY_FOR_CSRF_PROTECTION")

# Define variable to represent the Flask application object to be used for this website:
app = None

# Define variable to represent the database supporting this website:
db = None

# Initialize constant for sales tax rate to be applied to all orders:
RATE_SALES_TAX = 0.07

# Initialize constant for shipping rate to be applied to all orders:
RATE_SHIPPING = 0.10

# Initialize class variables for database tables:
CartDetails = None
OrderDetails = None
Orders = None
ProductCategories = None
Products = None
UnitsOfMeasure = None
Users = None

# Initialize class variables for web forms:
AddOrEditProductCategoryForm = None
AddOrEditProductForm = None
AddOrEditUOMForm = None
AddOrEditUserForm = None
AddProductToCartForm = None
ContactForm = None
EditCartDetailForm = None
EditOrderForm = None
LoginForm = None
RegisterForm = None
