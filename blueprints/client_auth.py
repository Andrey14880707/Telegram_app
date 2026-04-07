from flask import Blueprint, request, jsonify, session, render_template, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db
from notifications import send_to_n8n, send_email
from gcal_helpers import gcal_update_event
from datetime import datetime

bp = Blueprint('client_auth', __name__)


@bp.route('/login')
def login_page():
    if session.get('client_id'):
        return redirect('/profile')
    return render_template('login.html')


@bp.route('/register')
def register_page():
    if session.get('client_id'):
        return redirect('/profile')
    return render_template('register.html')


@bp.route('/profile')
def profile_page():
    if not session.get('client_id'):
        return redirect('/login?next=/profile')
    return render_template('profile.html')


@bp.route('/api/client/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name     = data.get('name', '').strip()
    phone    = data.get('phone', '').strip()
    email    = data.get('email', '').strip()
    telegram = data.get('telegram', '').strip()
    password = data.get('password', '')
    confirm  = data.get('confirm', '')

    if not name or not phone or not password:
        return jsonify({'success': False, 'error': 'Name, Telefon und Passwort sind erforderlich'})
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Passwort muss mindestens 6 Zeichen lang sein'})
    if password != confirm:
        return jsonify({'success': False, 'error': 'Passwörter stimmen nicht überein'})

    with get_db() as conn:
        if conn.execute('SELECT id FROM client_accounts WHERE phone=?', (phone,)).fetchone():
            return jsonify({'success': False, 'error': 'Diese Telefonnummer ist bereits registriert'})

        cur = conn.execute(
            'INSERT INTO client_accounts (name, phone, email, telegram, password_hash) VALUES (?,?,?,?,?)',
            (name, phone, email, telegram, generate_password_hash(password))
        )
        client_id = cur.lastrowid
        conn.commit()

    session['client_id'] = client_id
    return jsonify({'success': True})


@bp.route('/api/client/login', methods=['POST'])
def login():
    data     = request.get_json() or {}
    phone    = data.get('phone', '').strip()
    password = data.get('password', '')

    if not phone or not password:
        return jsonify({'success': False, 'error': 'Telefon und Passwort sind erforderlich'})

    with get_db() as conn:
        client = conn.execute('SELECT * FROM client_accounts WHERE phone=?', (phone,)).fetchone()
        if not client or not check_password_hash(client['password_hash'], password):
            return jsonify({'success': False, 'error': 'Falsche Telefonnummer oder Passwort'})

        conn.execute(
            'UPDATE client_accounts SET last_login=? WHERE id=?',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client['id'])
        )
        conn.commit()

    session['client_id'] = client['id']
    return jsonify({'success': True})


@bp.route('/api/client/logout', methods=['POST'])
def logout():
    session.pop('client_id', None)
    return jsonify({'success': True})


@bp.route('/api/client/me')
def me():
    client_id = session.get('client_id')
    if not client_id:
        return jsonify({'authenticated': False})
    with get_db() as conn:
        client = conn.execute(
            'SELECT id, name, phone, email, telegram FROM client_accounts WHERE id=?',
            (client_id,)
        ).fetchone()
    if not client:
        session.pop('client_id', None)
        return jsonify({'authenticated': False})
    return jsonify({
        'authenticated': True,
        'id':       client['id'],
        'name':     client['name'],
        'phone':    client['phone'],
        'email':    client['email'],
        'telegram': client['telegram'],
    })


@bp.route('/api/client/reschedule', methods=['POST'])
def reschedule():
    client_id = session.get('client_id')
    if not client_id:
        return jsonify({'success': False, 'error': 'Nicht angemeldet'}), 401

    data     = request.get_json() or {}
    apt_id   = data.get('id')
    new_date = data.get('date', '').strip()
    new_time = data.get('time', '').strip()

    if not apt_id or not new_date or not new_time:
        return jsonify({'success': False, 'error': 'Fehlende Daten'})

    with get_db() as conn:
        client = conn.execute(
            'SELECT phone FROM client_accounts WHERE id=?', (client_id,)
        ).fetchone()
        if not client:
            return jsonify({'success': False, 'error': 'Klient nicht gefunden'}), 404

        apt = conn.execute(
            "SELECT * FROM appointments WHERE id=? AND phone=? AND status IN ('pending','confirmed')",
            (apt_id, client['phone'])
        ).fetchone()
        if not apt:
            return jsonify({'success': False,
                            'error': 'Termin nicht gefunden oder nicht umbuchbar'})

        try:
            apt_dt = datetime.strptime(f"{apt['date']} {apt['time']}", '%Y-%m-%d %H:%M')
        except ValueError:
            return jsonify({'success': False, 'error': 'Ungültiges Datum'})
        if apt_dt <= datetime.now():
            return jsonify({'success': False,
                            'error': 'Vergangene Termine können nicht verschoben werden'})

        if conn.execute(
            "SELECT id FROM appointments WHERE date=? AND time=? "
            "AND status NOT IN ('cancelled','deleted') AND id!=?",
            (new_date, new_time, apt_id)
        ).fetchone():
            return jsonify({'success': False, 'error': 'Dieser Zeitslot ist bereits belegt'})

        old_date = apt['date']
        old_time = apt['time']

        conn.execute('UPDATE appointments SET date=?,time=? WHERE id=?',
                     (new_date, new_time, apt_id))
        conn.commit()
        row = conn.execute('SELECT * FROM appointments WHERE id=?', (apt_id,)).fetchone()

    # Sync Google Calendar
    if row and row['google_event_id']:
        gcal_update_event(row['google_event_id'], dict(row))

    # Email notification to client
    if row and row['email']:
        send_email(
            row['email'], 'München Barber — Termin verschoben',
            f'''<html><body style="font-family:sans-serif;background:#0f0f0f;color:#f0f0f0;
                padding:2rem;max-width:500px;margin:0 auto">
            <h2 style="color:#d4af37">München Barber</h2>
            <p>Hallo <b>{row["name"]}</b>, dein Termin wurde erfolgreich verschoben.</p>
            <table style="margin:1.5rem 0;border-collapse:collapse;width:100%">
              <tr><td style="padding:.5rem;color:#999">War</td>
                  <td style="padding:.5rem;text-decoration:line-through;color:#888">
                      {old_date} · {old_time}</td></tr>
              <tr><td style="padding:.5rem;color:#999">Neu</td>
                  <td style="padding:.5rem"><b style="color:#d4af37">
                      {new_date} · {new_time}</b></td></tr>
              <tr><td style="padding:.5rem;color:#999">Service</td>
                  <td style="padding:.5rem">{row["service"]} — {row["price"]}€</td></tr>
            </table>
            <p>Bei Fragen: <a href="https://t.me/barbermunich1"
               style="color:#d4af37">@barbermunich1</a></p>
            </body></html>'''
        )

    send_to_n8n({
        'event_type': 'rescheduled_by_client',
        'id': apt_id, 'name': row['name'] if row else '',
        'phone': row['phone'] if row else '',
        'service': row['service'] if row else '',
        'old_date': old_date, 'old_time': old_time,
        'new_date': new_date, 'new_time': new_time,
    })

    return jsonify({'success': True, 'message': 'Termin erfolgreich verschoben!'})


@bp.route('/api/client/bookings')
def bookings():
    client_id = session.get('client_id')
    if not client_id:
        return jsonify({'success': False, 'error': 'Nicht angemeldet'}), 401
    with get_db() as conn:
        client = conn.execute(
            'SELECT phone FROM client_accounts WHERE id=?', (client_id,)
        ).fetchone()
        if not client:
            return jsonify({'success': False, 'error': 'Klient nicht gefunden'}), 404
        rows = conn.execute(
            '''SELECT id, service, price, date, time, status, comment, created_at
               FROM appointments WHERE phone=?
               ORDER BY date DESC, time DESC''',
            (client['phone'],)
        ).fetchall()
    return jsonify({'success': True, 'bookings': [dict(r) for r in rows]})
