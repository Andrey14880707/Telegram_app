import os
import uuid
from flask import Blueprint, request, jsonify, session, send_from_directory
from db import get_db
from config import UPLOAD_FOLDER, ALLOWED_EXT

bp = Blueprint('photos', __name__)


@bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@bp.route('/api/photos')
def list_photos():
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM photos ORDER BY sort_order, created_at DESC'
        ).fetchall()
    return jsonify({'photos': [dict(r) for r in rows]})


@bp.route('/api/admin/photos', methods=['POST'])
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
    with get_db() as conn:
        conn.execute(
            'INSERT INTO photos (filename, caption, category) VALUES (?,?,?)',
            (filename, caption, category)
        )
        conn.commit()
    return jsonify({'success': True, 'filename': filename})


@bp.route('/api/admin/photos/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    with get_db() as conn:
        row = conn.execute('SELECT filename FROM photos WHERE id=?', (photo_id,)).fetchone()
        if row:
            try:
                os.remove(os.path.join(UPLOAD_FOLDER, row['filename']))
            except OSError:
                pass
            conn.execute('DELETE FROM photos WHERE id=?', (photo_id,))
            conn.commit()
    return jsonify({'success': True})
