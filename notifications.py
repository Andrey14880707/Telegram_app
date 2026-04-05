import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests as http_requests
from config import (
    TELEGRAM_TOKEN, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
    N8N_WEBHOOK, SHEETS_ENABLED
)


def send_telegram(chat_id, message):
    if not chat_id or not TELEGRAM_TOKEN:
        return False
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    try:
        r = http_requests.post(url, json={
            'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'
        }, timeout=10)
        return r.ok
    except Exception as e:
        print(f'[Telegram] {e}')
        return False


def send_email(to_email, subject, html_body):
    if not SMTP_USER or not SMTP_PASS or not to_email:
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_USER
        msg['To']   = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f'[Email] {e}')
        return False


def notify_client(row, text):
    sent = False
    if row['telegram']:
        sent = send_telegram(row['telegram'], text)
    if row['email']:
        html = (
            '<html><body style="font-family:sans-serif;background:#0f0f0f;'
            'color:#f0f0f0;padding:2rem">'
            + text.replace('\n', '<br>')
            + '</body></html>'
        )
        send_email(row['email'], 'München Barber — Termininfo', html)
        sent = True
    return sent


def send_to_n8n(payload: dict):
    if not N8N_WEBHOOK:
        return
    try:
        http_requests.post(N8N_WEBHOOK, json=payload, timeout=8)
    except Exception as e:
        print(f'[n8n] {e}')


def sync_to_sheets(row_data):
    if not SHEETS_ENABLED:
        return
    try:
        import json as _json
        import gspread
        from google.oauth2.service_account import Credentials
        creds_json = _json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON', '{}'))
        creds = Credentials.from_service_account_info(
            creds_json,
            scopes=['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(os.getenv('GOOGLE_SHEET_ID'))
        ws = sh.get_worksheet(0)
        if not ws.cell(1, 1).value:
            ws.append_row(['ID','Name','Telefon','E-Mail','Telegram',
                           'Service','Preis (€)','Datum','Zeit','Status',
                           'Kommentar','Erstellt'])
        ws.append_row(row_data)
    except Exception as e:
        print(f'[Sheets] {e}')
