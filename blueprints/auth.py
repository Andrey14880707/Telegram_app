from flask import Blueprint, request, jsonify, session
from config import ADMIN_PASSWORD

bp = Blueprint('auth', __name__)


@bp.route('/api/admin/check')
def admin_check():
    return jsonify({'authenticated': bool(session.get('admin'))})


@bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    if data.get('password') == ADMIN_PASSWORD:
        session.permanent = True
        session['admin'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Falsches Passwort'})


@bp.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin', None)
    return jsonify({'success': True})
