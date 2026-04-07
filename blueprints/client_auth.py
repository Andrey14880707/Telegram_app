from flask import Blueprint, request, jsonify, session, render_template, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db
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
