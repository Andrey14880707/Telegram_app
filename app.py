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
app.secret_key = os.getenv('SECRET_KEY', 'barber-secret-x7k2m9p4')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'barber123')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
DB_PATH = os.path.join(os.path.dirname(__file__), 'barber.db')


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
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            comment TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            reminder_24h INTEGER DEFAULT 0,
            reminder_2h INTEGER DEFAULT 0,
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
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f'[Email] {e}')
        return False


def notify_client(row, message_text):
    sent = False
    if row['telegram']:
        sent = send_telegram(row['telegram'], message_text)
    if row['email']:
        html = '<html><body style="font-family:sans-serif;background:#111;color:#f0f0f0;padding:2rem">'
        html += message_text.replace('<b>', '<strong>').replace('</b>', '</strong>').replace('\n', '<br>')
        html += '</body></html>'
        send_email(row['email'], 'BarberShop — Уведомление', html)
        sent = True
    return sent


# ── Scheduler ─────────────────────────────────────────────────────────────────

def check_reminders():
    """Run every 30 min. Send 24h reminders for confirmed appointments."""
    conn = get_db()
    now = datetime.now()
    target_date = (now + timedelta(hours=24)).strftime('%Y-%m-%d')
    t_start = (now + timedelta(hours=23, minutes=30)).strftime('%H:%M')
    t_end = (now + timedelta(hours=24, minutes=30)).strftime('%H:%M')

    rows = conn.execute('''
        SELECT * FROM appointments
        WHERE status = 'confirmed' AND reminder_24h = 0
        AND date = ? AND time >= ? AND time <= ?
    ''', (target_date, t_start, t_end)).fetchall()

    for row in rows:
        msg = (
            f"✂ <b>BarberShop — Напоминание</b>\n\n"
            f"Привет, {row['name']}! Напоминаем о вашей записи <b>завтра</b>:\n"
            f"📅 Дата: {row['date']}\n"
            f"⏰ Время: {row['time']}\n"
            f"💈 Услуга: {row['service']}\n"
            f"💰 Стоимость: {row['price']}₽\n\n"
            f"Ждём вас! 🙌\nЕсли планы изменились, звоните: +7 (999) 123-45-67"
        )
        if notify_client(row, msg):
            conn.execute('UPDATE appointments SET reminder_24h = 1 WHERE id = ?', (row['id'],))

    conn.commit()
    conn.close()


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
    return jsonify({'success': False, 'error': 'Неверный пароль'})


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin', None)
    return jsonify({'success': True})


@app.route('/api/slots')
def get_slots():
    date_str = request.args.get('date', '')
    if not date_str:
        return jsonify({'slots': []})
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'slots': []})

    wd = d.weekday()
    if wd < 5:
        start_h, end_h = 9, 20
    elif wd == 5:
        start_h, end_h = 10, 19
    else:
        start_h, end_h = 10, 17

    all_slots = []
    h, m = start_h, 0
    while h < end_h:
        all_slots.append(f'{h:02d}:{m:02d}')
        m += 30
        if m >= 60:
            m = 0
            h += 1

    conn = get_db()
    booked = {r['time'] for r in conn.execute(
        "SELECT time FROM appointments WHERE date = ? AND status != 'cancelled'",
        (date_str,)
    ).fetchall()}
    conn.close()

    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    available = []
    for slot in all_slots:
        if slot in booked:
            continue
        if date_str == today:
            slot_dt = datetime.strptime(f'{date_str} {slot}', '%Y-%m-%d %H:%M')
            if slot_dt <= now + timedelta(minutes=30):
                continue
        available.append(slot)

    return jsonify({'slots': available})


@app.route('/api/book', methods=['POST'])
def book():
    data = request.get_json() or {}
    for field in ('name', 'phone', 'service', 'date', 'time'):
        if not data.get(field):
            return jsonify({'success': False, 'error': f'Поле «{field}» обязательно'})

    parts = data['service'].split('|')
    service_name = parts[0]
    price = int(parts[1]) if len(parts) > 1 else 0

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM appointments WHERE date = ? AND time = ? AND status != 'cancelled'",
        (data['date'], data['time'])
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({'success': False, 'error': 'Это время уже занято, выберите другое'})

    conn.execute('''
        INSERT INTO appointments (name, phone, email, telegram, service, price, date, time, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['name'], data['phone'],
        data.get('email', ''), data.get('telegram', ''),
        service_name, price,
        data['date'], data['time'],
        data.get('comment', '')
    ))
    conn.commit()
    conn.close()

    if ADMIN_CHAT_ID:
        send_telegram(ADMIN_CHAT_ID,
            f"🔔 <b>Новая запись!</b>\n\n"
            f"👤 {data['name']}\n📞 {data['phone']}\n"
            f"💈 {service_name} — {price}₽\n"
            f"📅 {data['date']} в {data['time']}\n"
            f"💬 {data.get('comment') or '—'}"
        )

    return jsonify({'success': True, 'message': 'Запись создана! Ждём вас 🙌'})


@app.route('/api/admin/appointments')
def list_appointments():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    status = request.args.get('status', '')
    date_f = request.args.get('date', '')
    search = request.args.get('search', '')

    q = 'SELECT * FROM appointments WHERE 1=1'
    params = []
    if status:
        q += ' AND status = ?'; params.append(status)
    if date_f:
        q += ' AND date = ?'; params.append(date_f)
    if search:
        q += ' AND (name LIKE ? OR phone LIKE ?)'; params += [f'%{search}%', f'%{search}%']
    q += ' ORDER BY date DESC, time ASC'

    conn = get_db()
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return jsonify({'appointments': [dict(r) for r in rows]})


@app.route('/api/admin/appointments/<int:apt_id>', methods=['PATCH'])
def patch_appointment(apt_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    new_status = data.get('status')
    if new_status not in ('pending', 'confirmed', 'cancelled'):
        return jsonify({'error': 'Invalid status'})

    conn = get_db()
    conn.execute('UPDATE appointments SET status = ? WHERE id = ?', (new_status, apt_id))
    conn.commit()

    if new_status == 'confirmed':
        row = conn.execute('SELECT * FROM appointments WHERE id = ?', (apt_id,)).fetchone()
        if row:
            notify_client(row,
                f"✅ <b>Запись подтверждена!</b>\n\n"
                f"{row['name']}, ваша запись подтверждена:\n"
                f"📅 {row['date']} в {row['time']}\n"
                f"💈 {row['service']} — {row['price']}₽\n\nДо встречи! ✂"
            )
    conn.close()
    return jsonify({'success': True})


@app.route('/api/admin/remind/<int:apt_id>', methods=['POST'])
def manual_remind(apt_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    row = conn.execute('SELECT * FROM appointments WHERE id = ?', (apt_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Not found'})

    msg = (
        f"✂ <b>Напоминание о записи — BarberShop</b>\n\n"
        f"{row['name']}, напоминаем о вашей записи:\n"
        f"📅 {row['date']} в {row['time']}\n"
        f"💈 {row['service']} — {row['price']}₽\n\n"
        f"Если планы изменились — звоните: +7 (999) 123-45-67"
    )
    sent = notify_client(row, msg)
    if sent:
        return jsonify({'success': True, 'message': 'Напоминание отправлено'})
    return jsonify({'success': False, 'message': 'Нет контактов для рассылки (Telegram / Email)'})


@app.route('/api/admin/stats')
def stats():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')

    result = {
        'today': conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE date=? AND status!='cancelled'", (today,)
        ).fetchone()[0],
        'week': conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE date>=? AND status!='cancelled'", (week_start,)
        ).fetchone()[0],
        'total': conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE status!='cancelled'"
        ).fetchone()[0],
        'pending': conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE status='pending'"
        ).fetchone()[0],
        'revenue_today': conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM appointments WHERE date=? AND status='confirmed'", (today,)
        ).fetchone()[0],
        'revenue_month': conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM appointments WHERE date LIKE ? AND status='confirmed'",
            (datetime.now().strftime('%Y-%m') + '%',)
        ).fetchone()[0],
    }
    conn.close()
    return jsonify(result)


@app.route('/api/admin/export')
def export_csv():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    rows = conn.execute('SELECT * FROM appointments ORDER BY date DESC, time ASC').fetchall()
    conn.close()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['ID', 'Имя', 'Телефон', 'Email', 'Telegram',
                     'Услуга', 'Цена', 'Дата', 'Время', 'Статус', 'Комментарий', 'Создано'])
    for r in rows:
        writer.writerow([r['id'], r['name'], r['phone'], r['email'], r['telegram'],
                         r['service'], r['price'], r['date'], r['time'],
                         r['status'], r['comment'], r['created_at']])

    return Response(
        '\ufeff' + out.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=appointments.csv'}
    )


# ── Startup ───────────────────────────────────────────────────────────────────

init_db()

if not os.environ.get('WERKZEUG_RUN_MAIN'):
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_reminders, IntervalTrigger(minutes=30), id='reminders', replace_existing=True)
    scheduler.start()
    atexit.register(scheduler.shutdown)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
