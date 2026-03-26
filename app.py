from flask import Flask, render_template, request, jsonify, session, Response
import sqlite3
import os
import csv
import io
from datetime import datetime, timedelta
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
DB_PATH   = os.path.join(os.path.dirname(__file__), 'barber.db')

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
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
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
    target_date = (now + timedelta(hours=24)).strftime('%Y-%m-%d')
    t0 = (now + timedelta(hours=23, minutes=30)).strftime('%H:%M')
    t1 = (now + timedelta(hours=24, minutes=30)).strftime('%H:%M')

    rows = conn.execute('''
        SELECT * FROM appointments
        WHERE status='confirmed' AND reminder_24h=0
        AND date=? AND time>=? AND time<=?
    ''', (target_date, t0, t1)).fetchall()

    for row in rows:
        msg = (
            f"✂ <b>München Barber — Terminerinnerung</b>\n\n"
            f"Hallo {row['name']}! Dein Termin ist <b>morgen</b>:\n"
            f"📅 {row['date']} · ⏰ {row['time']}\n"
            f"💈 {row['service']} — {row['price']}€\n\n"
            f"Bis morgen! Bei Fragen: @barbermunich1"
        )
        if notify_client(row, msg):
            conn.execute('UPDATE appointments SET reminder_24h=1 WHERE id=?', (row['id'],))

    conn.commit()
    conn.close()


# ── Working hours ─────────────────────────────────────────────────────────────

HOURS = {
    # weekday() 0=Mon, 6=Sun
    0: None,              # Mo — Geschlossen
    1: (10, 20),          # Di
    2: (10, 20),          # Mi
    3: (10, 20),          # Do
    4: (10, 20),          # Fr
    5: (9, 18),           # Sa
    6: None,              # So — Geschlossen
}


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

    h_range = HOURS.get(d.weekday())
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
    booked = {r['time'] for r in conn.execute(
        "SELECT time FROM appointments WHERE date=? AND status!='cancelled'", (date_str,)
    ).fetchall()}
    conn.close()

    now = datetime.now()
    available = []
    for slot in all_slots:
        if slot in booked:
            continue
        if date_str == now.strftime('%Y-%m-%d'):
            if datetime.strptime(f'{date_str} {slot}', '%Y-%m-%d %H:%M') <= now + timedelta(minutes=30):
                continue
        available.append(slot)

    return jsonify({'slots': available, 'closed': False})


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

    # n8n webhook
    send_to_n8n({
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
    if new_status not in ('pending', 'confirmed', 'cancelled'):
        return jsonify({'error': 'Invalid status'})

    conn = get_db()
    conn.execute('UPDATE appointments SET status=? WHERE id=?', (new_status, apt_id))
    conn.commit()

    row = conn.execute('SELECT * FROM appointments WHERE id=?', (apt_id,)).fetchone()
    if row:
        send_to_n8n({
            'event':    'status_changed',
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


# ── Boot ──────────────────────────────────────────────────────────────────────

init_db()

if not os.environ.get('WERKZEUG_RUN_MAIN'):
    import pytz
    _sched = BackgroundScheduler(daemon=True, timezone=pytz.utc)
    _sched.add_job(check_reminders, IntervalTrigger(minutes=30), id='reminders', replace_existing=True)
    _sched.start()
    atexit.register(_sched.shutdown)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
