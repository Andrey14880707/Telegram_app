import os
import uuid
from flask import Blueprint, request, jsonify, session, send_from_directory, redirect
from db import get_db
from config import UPLOAD_FOLDER, ALLOWED_EXT

bp = Blueprint('photos', __name__)

# ── Cloudinary helper ────────────────────────────────────────────
def _cloudinary_enabled():
    return bool(os.getenv('CLOUDINARY_URL') or os.getenv('CLOUDINARY_CLOUD_NAME'))

def _cloudinary_upload(file_stream):
    import cloudinary
    import cloudinary.uploader
    if os.getenv('CLOUDINARY_URL'):
        cloudinary.config(cloudinary_url=os.getenv('CLOUDINARY_URL'))
    else:
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET'),
        )
    result = cloudinary.uploader.upload(
        file_stream,
        folder='munchen-barber-portfolio',
        resource_type='image',
    )
    return result['secure_url']

def _cloudinary_delete(public_url):
    try:
        import cloudinary
        import cloudinary.uploader
        if os.getenv('CLOUDINARY_URL'):
            cloudinary.config(cloudinary_url=os.getenv('CLOUDINARY_URL'))
        else:
            cloudinary.config(
                cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
                api_key=os.getenv('CLOUDINARY_API_KEY'),
                api_secret=os.getenv('CLOUDINARY_API_SECRET'),
            )
        # Extract public_id: .../munchen-barber-portfolio/NAME.ext → munchen-barber-portfolio/NAME
        parts = public_url.rsplit('/', 1)
        folder = 'munchen-barber-portfolio'
        name = parts[-1].rsplit('.', 1)[0]
        cloudinary.uploader.destroy(f'{folder}/{name}')
    except Exception:
        pass

def _photo_url(filename):
    """Return a full URL for a photo filename (works for both local and Cloudinary)."""
    if filename.startswith('http'):
        return filename
    return f'/uploads/{filename}'


# ── Routes ──────────────────────────────────────────────────────

@bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@bp.route('/api/photos')
def list_photos():
    try:
        with get_db() as conn:
            try:
                rows = conn.execute(
                    'SELECT * FROM photos ORDER BY sort_order, created_at DESC'
                ).fetchall()
            except Exception:
                # sort_order column may be missing on old DB — fallback
                rows = conn.execute(
                    'SELECT * FROM photos ORDER BY created_at DESC'
                ).fetchall()
    except Exception as e:
        return jsonify({'photos': [], 'error': str(e)})
    photos = []
    for r in rows:
        d = dict(r)
        d['url'] = _photo_url(d['filename'])
        photos.append(d)
    return jsonify({'photos': photos})


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

    if _cloudinary_enabled():
        try:
            stored = _cloudinary_upload(f)           # full https:// URL
        except Exception as e:
            return jsonify({'success': False, 'error': f'Cloudinary: {e}'}), 500
    else:
        filename = f'{uuid.uuid4().hex}.{ext}'
        f.save(os.path.join(UPLOAD_FOLDER, filename))
        stored = filename

    caption  = request.form.get('caption', '')
    category = request.form.get('category', 'Sonstiges')
    with get_db() as conn:
        conn.execute(
            'INSERT INTO photos (filename, caption, category) VALUES (?,?,?)',
            (stored, caption, category)
        )
        conn.commit()
    return jsonify({'success': True, 'filename': stored, 'url': _photo_url(stored)})


@bp.route('/api/admin/photos/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    with get_db() as conn:
        row = conn.execute('SELECT filename FROM photos WHERE id=?', (photo_id,)).fetchone()
        if row:
            fname = row['filename']
            if fname.startswith('http'):
                _cloudinary_delete(fname)
            else:
                try:
                    os.remove(os.path.join(UPLOAD_FOLDER, fname))
                except OSError:
                    pass
            conn.execute('DELETE FROM photos WHERE id=?', (photo_id,))
            conn.commit()
    return jsonify({'success': True})
