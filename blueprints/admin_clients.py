from flask import Blueprint, request, jsonify, session
from db import get_db

bp = Blueprint('admin_clients', __name__)


def _require_admin():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    return None


@bp.route('/api/admin/clients')
def list_clients():
    if err := _require_admin(): return err
    with get_db() as conn:
        clients = conn.execute('''
            SELECT
                phone,
                MAX(name)  AS name,
                MAX(email) AS email,
                MAX(telegram) AS telegram,
                COUNT(*) AS total_bookings,
                SUM(CASE WHEN status!='cancelled' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status='confirmed'  THEN price ELSE 0 END) AS total_spent,
                MAX(date)       AS last_date,
                MIN(created_at) AS first_seen
            FROM appointments
            GROUP BY phone
            ORDER BY total_bookings DESC, last_date DESC
        ''').fetchall()
    return jsonify({'clients': [dict(c) for c in clients]})


@bp.route('/api/admin/client/<phone>', methods=['GET'])
def client_history(phone):
    if err := _require_admin(): return err
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM appointments WHERE phone=? ORDER BY date DESC, time ASC', (phone,)
        ).fetchall()
    return jsonify({'history': [dict(r) for r in rows]})


@bp.route('/api/admin/client/<phone>', methods=['DELETE'])
def delete_client(phone):
    if err := _require_admin(): return err
    with get_db() as conn:
        conn.execute('DELETE FROM appointments WHERE phone=?', (phone,))
        conn.commit()
    return jsonify({'success': True})
