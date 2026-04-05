from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from db import get_db
from notifications import send_telegram, send_to_n8n, sync_to_sheets
from gcal_helpers import gcal_create_event
from config import ADMIN_CHAT_ID

bp = Blueprint('booking', __name__)

HOURS_DEFAULT = {
    0: None, 1: (10,20), 2: (10,20), 3: (10,20), 4: (10,20), 5: (9,18), 6: None
}


def get_hours():
    try:
        with get_db() as conn:
            rows = conn.execute('SELECT * FROM working_hours ORDER BY weekday').fetchall()
        if not rows:
            return HOURS_DEFAULT
        result = {}
        for r in rows:
            result[r['weekday']] = (r['open_hour'], r['close_hour']) if r['is_open'] else None
        return result
    except Exception:
        return HOURS_DEFAULT


@bp.route('/api/slots')
def get_slots():
    date_str = request.args.get('date', '')
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'slots': [], 'closed': True})

    hours   = get_hours()
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

    with get_db() as conn:
        if conn.execute('SELECT id FROM blocked_dates WHERE date=?', (date_str,)).fetchone():
            return jsonify({'slots': [], 'closed': True})
        booked = {r['time'] for r in conn.execute(
            "SELECT time FROM appointments WHERE date=? AND status NOT IN ('cancelled','deleted')",
            (date_str,)
        ).fetchall()}
        blocked_s = {r['time'] for r in conn.execute(
            'SELECT time FROM blocked_slots WHERE date=?', (date_str,)
        ).fetchall()}

    now = datetime.now()
    available = []
    for slot in all_slots:
        if slot in booked or slot in blocked_s:
            continue
        if date_str == now.strftime('%Y-%m-%d'):
            if datetime.strptime(f'{date_str} {slot}', '%Y-%m-%d %H:%M') <= now + timedelta(minutes=15):
                continue
        available.append(slot)

    return jsonify({
        'slots':   available,
        'booked':  sorted(booked),
        'blocked': sorted(blocked_s),
        'closed':  False,
    })


@bp.route('/api/availability')
def availability():
    today  = datetime.now().date()
    hours  = get_hours()
    disabled = []
    with get_db() as conn:
        blocked = {r['date'] for r in conn.execute('SELECT date FROM blocked_dates').fetchall()}
        for i in range(61):
            d        = today + timedelta(days=i)
            date_str = d.strftime('%Y-%m-%d')
            if date_str in blocked:
                disabled.append(date_str)
                continue
            h_range = hours.get(d.weekday())
            if h_range is None:
                disabled.append(date_str)
                continue
            total  = (h_range[1] - h_range[0]) * 2
            booked = conn.execute(
                "SELECT COUNT(*) AS cnt FROM appointments WHERE date=? AND status!='cancelled'",
                (date_str,)
            ).fetchone()['cnt']
            if booked >= total:
                disabled.append(date_str)
    return jsonify({'disabled': disabled})


@bp.route('/api/book', methods=['POST'])
def book():
    data = request.get_json() or {}
    for f in ('name', 'phone', 'service', 'date', 'time'):
        if not data.get(f):
            return jsonify({'success': False, 'error': f'Feld «{f}» ist erforderlich'})

    parts        = data['service'].split('|')
    service_name = parts[0]
    price        = int(parts[1]) if len(parts) > 1 else 0

    with get_db() as conn:
        if conn.execute(
            "SELECT id FROM appointments WHERE date=? AND time=? AND status NOT IN ('cancelled','deleted')",
            (data['date'], data['time'])
        ).fetchone():
            return jsonify({'success': False, 'error': 'Dieser Termin ist bereits vergeben'})

        is_admin       = data.get('source') == 'admin'
        initial_status = 'confirmed' if is_admin else 'pending'

        cur = conn.execute('''
            INSERT INTO appointments (name,phone,email,telegram,service,price,date,time,comment,status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', (data['name'], data['phone'], data.get('email',''), data.get('telegram',''),
              service_name, price, data['date'], data['time'], data.get('comment',''), initial_status))
        apt_id = cur.lastrowid
        conn.commit()

        gcal_event_id = gcal_create_event({
            'name': data['name'], 'phone': data['phone'], 'email': data.get('email',''),
            'service': service_name, 'price': price,
            'date': data['date'], 'time': data['time'], 'comment': data.get('comment',''),
        })
        if gcal_event_id:
            conn.execute('UPDATE appointments SET google_event_id=? WHERE id=?', (gcal_event_id, apt_id))
            conn.commit()

    if ADMIN_CHAT_ID and not is_admin:
        send_telegram(ADMIN_CHAT_ID,
            f"🔔 <b>Neuer Termin!</b>\n\n"
            f"👤 {data['name']} · 📞 {data['phone']}\n"
            f"💈 {service_name} — {price}€\n"
            f"📅 {data['date']} · ⏰ {data['time']}\n"
            f"💬 {data.get('comment') or '—'}"
        )

    send_to_n8n({
        'event_type': 'booking_confirmation',
        'id': apt_id, 'name': data['name'], 'phone': data['phone'],
        'email': data.get('email',''), 'telegram': data.get('telegram',''),
        'service': service_name, 'price': price, 'currency': 'EUR',
        'date': data['date'], 'time': data['time'],
        'comment': data.get('comment',''), 'status': 'pending',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'source': 'website',
    })

    sync_to_sheets([
        apt_id, data['name'], data['phone'], data.get('email',''), data.get('telegram',''),
        service_name, price, data['date'], data['time'], 'pending',
        data.get('comment',''), datetime.now().strftime('%Y-%m-%d %H:%M'),
    ])

    return jsonify({'success': True, 'message': 'Termin erstellt! Bis bald 🙌'})
