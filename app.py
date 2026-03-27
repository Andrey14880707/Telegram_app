from flask import Flask, render_template, request, jsonify, session, Response, send_from_directory
import sqlite3
import os
import csv
import io
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import requests as http_requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import atexit
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'munchen-barber-x7k2m9p4')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
ADMIN_CHAT_ID  = os.getenv('ADMIN_CHAT_ID', '')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'barber123')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
N8N_WEBHOOK = os.getenv('N8N_WEBHOOK', 'https://usteem.app.n8n.cloud/webhook-test/barber-booking')

# On Render (and similar) use /data (persistent disk); locally use project dir
_BASE = '/data' if os.path.isdir('/data') else os.path.dirname(__file__)
DB_PATH       = os.path.join(_BASE, 'barber.db')
UPLOAD_FOLDER = os.path.join(_BASE, 'uploads')
ALLOWED_EXT   = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Serve uploaded photos (needed when not in static/)
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# Optional Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
    SHEETS_ENABLED = bool(os.getenv('GOOGLE_SHEET_ID') and os.getenv('GOOGLE_CREDENTIALS_JSON'))
except ImportError:
    SHEETS_ENABLED = False


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT DEFAULT '',
            telegram TEXT DEFAULT '',
            service TEXT NOT NULL,
            price INTEGER NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'EUR',
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            comment TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            reminder_24h INTEGER DEFAULT 0,
            reminder_2h_sent INTEGER DEFAULT 0,
            followup_sent INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            caption TEXT DEFAULT '',
            category TEXT DEFAULT 'Sonstiges',
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    # Add category column to existing photos tables (migration)
    try:
        conn.execute("ALTER TABLE photos ADD COLUMN category TEXT DEFAULT 'Sonstiges'")
    except Exception:
        pass
    # Add reminder columns (migration for existing DBs)
    for col_def in [
        "ALTER TABLE appointments ADD COLUMN reminder_2h_sent INTEGER DEFAULT 0",
        "ALTER TABLE appointments ADD COLUMN followup_sent INTEGER DEFAULT 0",
    ]:
        try:
            conn.execute(col_def)
        except Exception:
            pass
    conn.execute('''
        CREATE TABLE IF NOT EXISTS blocked_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            reason TEXT DEFAULT ''
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS working_hours (
            weekday INTEGER PRIMARY KEY,
            is_open INTEGER DEFAULT 1,
            open_hour INTEGER DEFAULT 10,
            close_hour INTEGER DEFAULT 20
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS blocked_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            reason TEXT DEFAULT '',
            UNIQUE(date, time)
        )
    ''')
    # Insert default hours if table is empty
    if conn.execute('SELECT COUNT(*) FROM working_hours').fetchone()[0] == 0:
        defaults = [
            (0, 0, 10, 20),  # Mo closed
            (1, 1, 10, 20),  # Di
            (2, 1, 10, 20),  # Mi
            (3, 1, 10, 20),  # Do
            (4, 1, 10, 20),  # Fr
            (5, 1, 9,  18),  # Sa
            (6, 0, 10, 20),  # So closed
        ]
        conn.executemany(
            'INSERT INTO working_hours (weekday, is_open, open_hour, close_hour) VALUES (?,?,?,?)',
            defaults
        )
    conn.commit()
    conn.close()


# ── Notifications ─────────────────────────────────────────────────────────────

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
        msg['To'] = to_email
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
        html = f'<html><body style="font-family:sans-serif;background:#0f0f0f;color:#f0f0f0;padding:2rem">{text.replace(chr(10),"<br>")}</body></html>'
        send_email(row['email'], 'München Barber — Termininfo', html)
        sent = True
    return sent


def send_to_n8n(payload: dict):
    """POST booking data to n8n webhook (fire-and-forget)."""
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
            ws.append_row(['ID', 'Name', 'Telefon', 'E-Mail', 'Telegram',
                           'Service', 'Preis (€)', 'Datum', 'Zeit', 'Status',
                           'Kommentar', 'Erstellt'])
        ws.append_row(row_data)
    except Exception as e:
        print(f'[Sheets] {e}')


# ── Scheduler ─────────────────────────────────────────────────────────────────

def check_reminders():
    conn = get_db()
    now = datetime.now()

    # ── 24h reminder ──────────────────────────────────────────────────────────
    d24 = (now + timedelta(hours=24)).strftime('%Y-%m-%d')
    t24_lo = (now + timedelta(hours=23, minutes=30)).strftime('%H:%M')
    t24_hi = (now + timedelta(hours=24, minutes=30)).strftime('%H:%M')
    rows_24 = conn.execute('''
        SELECT * FROM appointments
        WHERE status='confirmed' AND reminder_24h=0
        AND date=? AND time>=? AND time<=?
    ''', (d24, t24_lo, t24_hi)).fetchall()
    for row in rows_24:
        send_to_n8n({
            'event_type': 'reminder_24h',
            'id': row['id'], 'name': row['name'], 'phone': row['phone'],
            'email': row['email'], 'telegram': row['telegram'],
            'service': row['service'], 'price': row['price'], 'currency': 'EUR',
            'date': row['date'], 'time': row['time'],
        })
        msg = (
            f"✂ <b>München Barber — Terminerinnerung</b>\n\n"
            f"Hallo {row['name']}! Dein Termin ist <b>morgen</b>:\n"
            f"📅 {row['date']} · ⏰ {row['time']}\n"
            f"💈 {row['service']} — {row['price']}€\n\n"
            f"Bis morgen! Bei Fragen: @barbermunich1"
        )
        if notify_client(row, msg):
            conn.execute('UPDATE appointments SET reminder_24h=1 WHERE id=?', (row['id'],))

    # ── 2h reminder ───────────────────────────────────────────────────────────
    d2 = now.strftime('%Y-%m-%d')
    t2_lo = (now + timedelta(hours=1, minutes=45)).strftime('%H:%M')
    t2_hi = (now + timedelta(hours=2, minutes=15)).strftime('%H:%M')
    rows_2h = conn.execute('''
        SELECT * FROM appointments
        WHERE status='confirmed' AND reminder_2h_sent=0
        AND date=? AND time>=? AND time<=?
    ''', (d2, t2_lo, t2_hi)).fetchall()
    for row in rows_2h:
        send_to_n8n({
            'event_type': 'reminder_2h',
            'id': row['id'], 'name': row['name'], 'phone': row['phone'],
            'email': row['email'], 'telegram': row['telegram'],
            'service': row['service'], 'price': row['price'], 'currency': 'EUR',
            'date': row['date'], 'time': row['time'],
        })
        msg = (
            f"⏰ <b>München Barber — In 2 Stunden!</b>\n\n"
            f"Hallo {row['name']}! Dein Termin ist <b>in 2 Stunden</b>:\n"
            f"📅 {row['date']} · ⏰ {row['time']}\n"
            f"💈 {row['service']} — {row['price']}€\n\n"
            f"Bis gleich! Bei Fragen: @barbermunich1"
        )
        if notify_client(row, msg):
            conn.execute('UPDATE appointments SET reminder_2h_sent=1 WHERE id=?', (row['id'],))

    # ── 21-day follow-up ──────────────────────────────────────────────────────
    cutoff = (now - timedelta(days=21)).strftime('%Y-%m-%d')
    rows_fu = conn.execute('''
        SELECT * FROM appointments
        WHERE status IN ('confirmed', 'completed') AND followup_sent=0
        AND date=?
    ''', (cutoff,)).fetchall()
    for row in rows_fu:
        send_to_n8n({
            'event_type': 'followup_21d',
            'id': row['id'], 'name': row['name'], 'phone': row['phone'],
            'email': row['email'], 'telegram': row['telegram'],
            'service': row['service'], 'price': row['price'], 'currency': 'EUR',
            'date': row['date'], 'time': row['time'],
        })
        msg = (
            f"💈 <b>München Barber — Zeit für einen neuen Schnitt!</b>\n\n"
            f"Hey {row['name']}! Es ist schon 3 Wochen her — \n"
            f"Zeit für deinen nächsten Termin?\n\n"
            f"Jetzt buchen: https://munchen-barber.onrender.com/#termin\n"
            f"Bei Fragen: @barbermunich1"
        )
        if notify_client(row, msg):
            conn.execute('UPDATE appointments SET followup_sent=1 WHERE id=?', (row['id'],))

    conn.commit()
    conn.close()


# ── Working hours ─────────────────────────────────────────────────────────────

HOURS = {
    # weekday() 0=Mon, 6=Sun  (fallback defaults)
    0: None,              # Mo — Geschlossen
    1: (10, 20),          # Di
    2: (10, 20),          # Mi
    3: (10, 20),          # Do
    4: (10, 20),          # Fr
    5: (9, 18),           # Sa
    6: None,              # So — Geschlossen
}


def get_hours():
    """Load working hours from DB; fall back to HOURS dict if DB is empty."""
    try:
        conn = get_db()
        rows = conn.execute('SELECT * FROM working_hours ORDER BY weekday').fetchall()
        conn.close()
        if not rows:
            return HOURS
        result = {}
        for r in rows:
            if r['is_open']:
                result[r['weekday']] = (r['open_hour'], r['close_hour'])
            else:
                result[r['weekday']] = None
        return result
    except Exception:
        return HOURS


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/api/admin/check')
def admin_check():
    return jsonify({'authenticated': bool(session.get('admin'))})


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    if data.get('password') == ADMIN_PASSWORD:
        session['admin'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Falsches Passwort'})


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin', None)
    return jsonify({'success': True})


@app.route('/api/slots')
def get_slots():
    date_str = request.args.get('date', '')
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'slots': [], 'closed': True})

    hours = get_hours()
    h_range = hours.get(d.weekday())
    if h_range is None:
        return jsonify({'slots': [], 'closed': True})

    start_h, end_h = h_range
    all_slots, h, m = [], start_h, 0
    while h < end_h:
        all_slots.append(f'{h:02d}:{m:02d}')
        m += 30
        if m >= 60:
            m, h = 0, h + 1

    conn = get_db()
    # Check full day block
    if conn.execute("SELECT id FROM blocked_dates WHERE date=?", (date_str,)).fetchone():
        conn.close()
        return jsonify({'slots': [], 'closed': True})

    # Get bookings
    booked = {r['time'] for r in conn.execute(
        "SELECT time FROM appointments WHERE date=? AND status NOT IN ('cancelled', 'deleted')", (date_str,)
    ).fetchall()}

    # Get blocked slots
    blocked_s = {r['time'] for r in conn.execute(
        "SELECT time FROM blocked_slots WHERE date=?", (date_str,)
    ).fetchall()}

    conn.close()

    now = datetime.now()
    available = []
    for slot in all_slots:
        if slot in booked or slot in blocked_s:
            continue
        # If today, hide past slots
        if date_str == now.strftime('%Y-%m-%d'):
            if datetime.strptime(f'{date_str} {slot}', '%Y-%m-%d %H:%M') <= now + timedelta(minutes=15):
                continue
        available.append(slot)

    return jsonify({
        'slots': available,
        'booked': sorted(list(booked)),
        'blocked': sorted(list(blocked_s)),
        'closed': False
    })


@app.route('/api/availability')
def availability():
    today = datetime.now().date()
    disabled = []
    hours = get_hours()
    conn = get_db()
    blocked = {r['date'] for r in conn.execute('SELECT date FROM blocked_dates').fetchall()}
    for i in range(61):
        d = today + timedelta(days=i)
        date_str = d.strftime('%Y-%m-%d')
        if date_str in blocked:
            disabled.append(date_str)
            continue
        wd = d.weekday()
        h_range = hours.get(wd)
        if h_range is None:
            disabled.append(date_str)
            continue
        start_h, end_h = h_range
        total_slots = (end_h - start_h) * 2
        booked_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM appointments WHERE date=? AND status!='cancelled'",
            (date_str,)
        ).fetchone()['cnt']
        if booked_count >= total_slots:
            disabled.append(date_str)
    conn.close()
    return jsonify({'disabled': disabled})


@app.route('/api/book', methods=['POST'])
def book():
    data = request.get_json() or {}
    for f in ('name', 'phone', 'service', 'date', 'time'):
        if not data.get(f):
            return jsonify({'success': False, 'error': f'Feld «{f}» ist erforderlich'})

    parts = data['service'].split('|')
    service_name = parts[0]
    price = int(parts[1]) if len(parts) > 1 else 0

    conn = get_db()
    if conn.execute(
        "SELECT id FROM appointments WHERE date=? AND time=? AND status!='cancelled'",
        (data['date'], data['time'])
    ).fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Dieser Termin ist bereits vergeben'})

    cur = conn.execute('''
        INSERT INTO appointments (name,phone,email,telegram,service,price,date,time,comment)
        VALUES (?,?,?,?,?,?,?,?,?)
    ''', (data['name'], data['phone'],
          data.get('email', ''), data.get('telegram', ''),
          service_name, price,
          data['date'], data['time'],
          data.get('comment', '')))
    apt_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Notify admin
    if ADMIN_CHAT_ID:
        send_telegram(ADMIN_CHAT_ID,
            f"🔔 <b>Neuer Termin!</b>\n\n"
            f"👤 {data['name']} · 📞 {data['phone']}\n"
            f"💈 {service_name} — {price}€\n"
            f"📅 {data['date']} · ⏰ {data['time']}\n"
            f"💬 {data.get('comment') or '—'}"
        )

    # Confirmation email to client
    if data.get('email'):
        send_email(
            data['email'],
            'München Barber — Termin bestätigt',
            f'''<html><body style="font-family:sans-serif;background:#0f0f0f;color:#f0f0f0;padding:2rem;max-width:500px;margin:0 auto">
            <h2 style="color:#d4af37">München Barber</h2>
            <p>Hallo <b>{data['name']}</b>, dein Termin wurde erfolgreich gebucht!</p>
            <table style="margin:1.5rem 0;border-collapse:collapse;width:100%">
              <tr><td style="padding:.5rem;color:#999">Service</td><td style="padding:.5rem"><b>{service_name}</b></td></tr>
              <tr><td style="padding:.5rem;color:#999">Datum</td><td style="padding:.5rem"><b>{data['date']}</b></td></tr>
              <tr><td style="padding:.5rem;color:#999">Zeit</td><td style="padding:.5rem"><b>{data['time']}</b></td></tr>
              <tr><td style="padding:.5rem;color:#999">Preis</td><td style="padding:.5rem"><b>{price}€</b></td></tr>
            </table>
            <p>Bei Fragen: <a href="https://t.me/barbermunich1" style="color:#d4af37">@barbermunich1</a></p>
            </body></html>'''
        )

    # n8n webhook
    send_to_n8n({
        'event_type': 'booking_confirmation',
        'id':       apt_id,
        'name':     data['name'],
        'phone':    data['phone'],
        'email':    data.get('email', ''),
        'telegram': data.get('telegram', ''),
        'service':  service_name,
        'price':    price,
        'currency': 'EUR',
        'date':     data['date'],
        'time':     data['time'],
        'comment':  data.get('comment', ''),
        'status':   'pending',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source':   'website',
    })

    # Google Sheets sync
    sync_to_sheets([
        apt_id, data['name'], data['phone'],
        data.get('email', ''), data.get('telegram', ''),
        service_name, price,
        data['date'], data['time'], 'pending',
        data.get('comment', ''), datetime.now().strftime('%Y-%m-%d %H:%M')
    ])

    return jsonify({'success': True, 'message': 'Termin erstellt! Bis bald 🙌'})


@app.route('/api/admin/appointments')
def list_appointments():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    status  = request.args.get('status', '')
    date_f  = request.args.get('date', '')
    search  = request.args.get('search', '')

    q, params = 'SELECT * FROM appointments WHERE 1=1', []
    if status: q += ' AND status=?'; params.append(status)
    if date_f: q += ' AND date=?';   params.append(date_f)
    if search:
        q += ' AND (name LIKE ? OR phone LIKE ?)'; params += [f'%{search}%', f'%{search}%']
    q += ' ORDER BY date DESC, time ASC'

    conn = get_db()
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return jsonify({'appointments': [dict(r) for r in rows]})


@app.route('/api/admin/clients')
def list_clients():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    clients = conn.execute('''
        SELECT
            phone,
            MAX(name) AS name,
            MAX(email) AS email,
            MAX(telegram) AS telegram,
            COUNT(*) AS total_bookings,
            SUM(CASE WHEN status!='cancelled' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN status='confirmed' THEN price ELSE 0 END) AS total_spent,
            MAX(date) AS last_date,
            MIN(created_at) AS first_seen
        FROM appointments
        GROUP BY phone
        ORDER BY total_bookings DESC, last_date DESC
    ''').fetchall()
    conn.close()
    return jsonify({'clients': [dict(c) for c in clients]})


@app.route('/api/admin/client/<phone>')
def client_history(phone):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM appointments WHERE phone=? ORDER BY date DESC, time ASC', (phone,)
    ).fetchall()
    conn.close()
    return jsonify({'history': [dict(r) for r in rows]})


@app.route('/api/admin/appointments/<int:apt_id>', methods=['PATCH'])
def patch_appointment(apt_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    new_status = data.get('status')
    if new_status not in ('pending', 'confirmed', 'cancelled', 'completed', 'deleted'):
        return jsonify({'error': 'Invalid status'})

    conn = get_db()
    conn.execute('UPDATE appointments SET status=? WHERE id=?', (new_status, apt_id))
    conn.commit()

    row = conn.execute('SELECT * FROM appointments WHERE id=?', (apt_id,)).fetchone()
    if row:
        send_to_n8n({
            'event_type': 'status_changed',
            'id':       apt_id,
            'name':     row['name'],
            'phone':    row['phone'],
            'service':  row['service'],
            'price':    row['price'],
            'currency': 'EUR',
            'date':     row['date'],
            'time':     row['time'],
            'status':   new_status,
        })

    if new_status == 'confirmed':
        if row:
            notify_client(row,
                f"✅ <b>Termin bestätigt!</b>\n\n"
                f"{row['name']}, dein Termin ist bestätigt:\n"
                f"📅 {row['date']} · ⏰ {row['time']}\n"
                f"💈 {row['service']} — {row['price']}€\n\nBis dann! ✂"
            )
    conn.close()
    return jsonify({'success': True})


@app.route('/api/admin/appointments/reschedule', methods=['POST'])
def reschedule():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    apt_id = data.get('id')
    new_date = data.get('date')
    new_time = data.get('time')

    if not all([apt_id, new_date, new_time]):
        return jsonify({'success': False, 'error': 'Fehlende Daten'})

    conn = get_db()
    # Check if slot is taken
    conflict = conn.execute(
        "SELECT id FROM appointments WHERE date=? AND time=? AND status NOT IN ('cancelled', 'deleted') AND id!=?",
        (new_date, new_time, apt_id)
    ).fetchone()
    if conflict:
        conn.close()
        return jsonify({'success': False, 'error': 'Dieser Slot ist bereits belegt'})

    conn.execute('UPDATE appointments SET date=?, time=? WHERE id=?', (new_date, new_time, apt_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/admin/block-slots', methods=['POST'])
def block_slots():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    date_str = data.get('date')
    times = data.get('times', []) # List of times like ["10:00", "10:30"]
    reason = data.get('reason', 'Blockiert')

    if not date_str or not times:
        return jsonify({'success': False, 'error': 'Datum/Uhrzeit fehlt'})

    conn = get_db()
    for t in times:
        try:
            conn.execute('INSERT INTO blocked_slots (date, time, reason) VALUES (?, ?, ?)', (date_str, t, reason))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/admin/block-slots', methods=['DELETE'])
def unblock_slots():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    date_str = data.get('date')
    times = data.get('times', [])

    conn = get_db()
    for t in times:
        conn.execute('DELETE FROM blocked_slots WHERE date=? AND time=?', (date_str, t))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/admin/remind/<int:apt_id>', methods=['POST'])
def manual_remind(apt_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    row = conn.execute('SELECT * FROM appointments WHERE id=?', (apt_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Not found'})

    msg = (
        f"✂ <b>München Barber — Terminerinnerung</b>\n\n"
        f"{row['name']}, denk an deinen Termin:\n"
        f"📅 {row['date']} · ⏰ {row['time']}\n"
        f"💈 {row['service']} — {row['price']}€\n\n"
        f"Bei Fragen: @barbermunich1"
    )
    sent = notify_client(row, msg)
    return jsonify({'success': sent,
                    'message': 'Erinnerung gesendet ✓' if sent else 'Keine Kontaktdaten hinterlegt'})


@app.route('/api/admin/stats')
def stats():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    today      = datetime.now().strftime('%Y-%m-%d')
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
    month_pref = datetime.now().strftime('%Y-%m')

    result = {
        'today':         conn.execute("SELECT COUNT(*) FROM appointments WHERE date=? AND status!='cancelled'",(today,)).fetchone()[0],
        'week':          conn.execute("SELECT COUNT(*) FROM appointments WHERE date>=? AND status!='cancelled'",(week_start,)).fetchone()[0],
        'total':         conn.execute("SELECT COUNT(*) FROM appointments WHERE status!='cancelled'").fetchone()[0],
        'pending':       conn.execute("SELECT COUNT(*) FROM appointments WHERE status='pending'").fetchone()[0],
        'clients':       conn.execute("SELECT COUNT(DISTINCT phone) FROM appointments WHERE status!='cancelled'").fetchone()[0],
        'rev_today':     conn.execute("SELECT COALESCE(SUM(price),0) FROM appointments WHERE date=? AND status='confirmed'",(today,)).fetchone()[0],
        'rev_month':     conn.execute("SELECT COALESCE(SUM(price),0) FROM appointments WHERE date LIKE ? AND status='confirmed'",(month_pref+'%',)).fetchone()[0],
    }
    conn.close()
    return jsonify(result)


@app.route('/api/admin/export')
def export_csv():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute('SELECT * FROM appointments ORDER BY date DESC').fetchall()
    conn.close()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['ID','Name','Telefon','E-Mail','Telegram','Service','Preis (€)',
                'Datum','Uhrzeit','Status','Kommentar','Erstellt'])
    for r in rows:
        w.writerow([r['id'], r['name'], r['phone'], r['email'], r['telegram'],
                    r['service'], r['price'], r['date'], r['time'],
                    r['status'], r['comment'], r['created_at']])
    return Response(
        '\ufeff' + out.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=termine.csv'}
    )


# ── Photos ────────────────────────────────────────────────────────────────────

@app.route('/api/photos')
def list_photos():
    conn = get_db()
    rows = conn.execute('SELECT * FROM photos ORDER BY sort_order, created_at DESC').fetchall()
    conn.close()
    return jsonify({'photos': [dict(r) for r in rows]})


@app.route('/api/admin/photos', methods=['POST'])
def upload_photo():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Keine Datei'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'success': False, 'error': 'Kein Dateiname'}), 400
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED_EXT:
        return jsonify({'success': False, 'error': 'Dateityp nicht erlaubt'}), 400
    filename = f'{uuid.uuid4().hex}.{ext}'
    f.save(os.path.join(UPLOAD_FOLDER, filename))
    caption  = request.form.get('caption', '')
    category = request.form.get('category', 'Sonstiges')
    conn = get_db()
    conn.execute('INSERT INTO photos (filename, caption, category) VALUES (?, ?, ?)', (filename, caption, category))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'filename': filename})


@app.route('/api/admin/photos/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    row = conn.execute('SELECT filename FROM photos WHERE id=?', (photo_id,)).fetchone()
    if row:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, row['filename']))
        except OSError:
            pass
        conn.execute('DELETE FROM photos WHERE id=?', (photo_id,))
        conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Working hours (admin) ──────────────────────────────────────────────────────

@app.route('/api/admin/hours', methods=['GET'])
def get_hours_api():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute('SELECT * FROM working_hours ORDER BY weekday').fetchall()
    conn.close()
    return jsonify({'hours': [dict(r) for r in rows]})


@app.route('/api/admin/hours', methods=['POST'])
def save_hours():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    hours_list = data.get('hours', [])
    conn = get_db()
    for h in hours_list:
        conn.execute(
            'UPDATE working_hours SET is_open=?, open_hour=?, close_hour=? WHERE weekday=?',
            (1 if h.get('is_open') else 0, h.get('open_hour', 10), h.get('close_hour', 20), h['weekday'])
        )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Blocked dates (admin) ──────────────────────────────────────────────────────

@app.route('/api/admin/blocked', methods=['GET'])
def list_blocked():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute('SELECT * FROM blocked_dates ORDER BY date').fetchall()
    conn.close()
    return jsonify({'blocked': [dict(r) for r in rows]})


@app.route('/api/admin/blocked', methods=['POST'])
def add_blocked():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    date_str = data.get('date', '')
    reason   = data.get('reason', '')
    if not date_str:
        return jsonify({'success': False, 'error': 'Datum fehlt'}), 400
    conn = get_db()
    try:
        conn.execute('INSERT INTO blocked_dates (date, reason) VALUES (?, ?)', (date_str, reason))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # already blocked
    conn.close()
    return jsonify({'success': True})


@app.route('/api/admin/blocked/<date_str>', methods=['DELETE'])
def remove_blocked(date_str):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    conn.execute('DELETE FROM blocked_dates WHERE date=?', (date_str,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/admin/test-email')
def test_email():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    if not SMTP_USER or not SMTP_PASS:
        return jsonify({'ok': False, 'error': f'SMTP_USER/SMTP_PASS not set. SMTP_USER={SMTP_USER!r}'})
    ok = send_email(SMTP_USER, 'München Barber — Test Email', '<h2>Email funktioniert!</h2><p>SMTP ist korrekt konfiguriert.</p>')
    if ok:
        return jsonify({'ok': True, 'message': f'Test email sent to {SMTP_USER}'})
    else:
        return jsonify({'ok': False, 'error': 'send_email returned False — check server logs'})


# ── Boot ──────────────────────────────────────────────────────────────────────

init_db()

if not os.environ.get('WERKZEUG_RUN_MAIN'):
    import pytz
    _sched = BackgroundScheduler(daemon=True, timezone=pytz.utc)
    _sched.add_job(check_reminders, IntervalTrigger(minutes=30), id='reminders', replace_existing=True)
    _sched.start()
    atexit.register(_sched.shutdown)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8088)
