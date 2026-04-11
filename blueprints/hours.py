import sqlite3
from flask import Blueprint, request, jsonify, session
from db import get_db

bp = Blueprint('hours', __name__)


def _require_admin():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    return None


@bp.route('/api/admin/hours', methods=['GET'])
def get_hours_api():
    if err := _require_admin(): return err
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM working_hours ORDER BY weekday').fetchall()
    return jsonify({'hours': [dict(r) for r in rows]})


@bp.route('/api/admin/hours', methods=['POST'])
def save_hours():
    if err := _require_admin(): return err
    data = request.get_json() or {}
    hours = data.get('hours', [])
    if not hours:
        return jsonify({'success': False, 'error': 'No hours data'}), 400
    try:
        with get_db() as conn:
            # ensure rows exist (upsert)
            for h in hours:
                conn.execute(
                    '''INSERT INTO working_hours (weekday, is_open, open_hour, close_hour)
                       VALUES (?,?,?,?)
                       ON CONFLICT(weekday) DO UPDATE SET
                         is_open=excluded.is_open,
                         open_hour=excluded.open_hour,
                         close_hour=excluded.close_hour''',
                    (h['weekday'], 1 if h.get('is_open') else 0,
                     h.get('open_hour', 10), h.get('close_hour', 20))
                )
            conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/admin/blocked', methods=['GET'])
def list_blocked():
    if err := _require_admin(): return err
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM blocked_dates ORDER BY date').fetchall()
    return jsonify({'blocked': [dict(r) for r in rows]})


@bp.route('/api/admin/blocked', methods=['POST'])
def add_blocked():
    if err := _require_admin(): return err
    data     = request.get_json() or {}
    date_str = data.get('date', '')
    reason   = data.get('reason', '')
    if not date_str:
        return jsonify({'success': False, 'error': 'Datum fehlt'}), 400
    with get_db() as conn:
        try:
            conn.execute('INSERT INTO blocked_dates (date,reason) VALUES (?,?)', (date_str, reason))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
    return jsonify({'success': True})


@bp.route('/api/admin/blocked/<date_str>', methods=['DELETE'])
def remove_blocked(date_str):
    if err := _require_admin(): return err
    with get_db() as conn:
        conn.execute('DELETE FROM blocked_dates WHERE date=?', (date_str,))
        conn.commit()
    return jsonify({'success': True})
