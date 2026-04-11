import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY     = os.getenv('SECRET_KEY', 'munchen-barber-x7k2m9p4')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'barber123')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
ADMIN_CHAT_ID  = os.getenv('ADMIN_CHAT_ID', '')

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')

N8N_WEBHOOK = os.getenv('N8N_WEBHOOK', '')

GOOGLE_CLIENT_ID     = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI  = os.getenv('GOOGLE_REDIRECT_URI', '')
GOOGLE_CALENDAR_ID   = os.getenv('GOOGLE_CALENDAR_ID', 'primary')
GCAL_SCOPES = ['https://www.googleapis.com/auth/calendar.events']

_BASE         = '/data' if os.path.isdir('/data') else os.path.dirname(os.path.abspath(__file__))
DB_PATH       = os.getenv('DB_PATH')       or os.path.join(_BASE, 'barber.db')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER') or os.path.join(_BASE, 'uploads')

print(f'[Config] DB_PATH={DB_PATH}  UPLOAD_FOLDER={UPLOAD_FOLDER}')
ALLOWED_EXT   = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

try:
    from google_auth_oauthlib.flow import Flow
    from google.auth.transport.requests import Request as GRequest
    from google.oauth2.credentials import Credentials as GCredentials
    from googleapiclient.discovery import build as gbuild
    GCAL_AVAILABLE = True
except ImportError:
    GCAL_AVAILABLE = False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    SHEETS_ENABLED = bool(os.getenv('GOOGLE_SHEET_ID') and os.getenv('GOOGLE_CREDENTIALS_JSON'))
except ImportError:
    SHEETS_ENABLED = False
