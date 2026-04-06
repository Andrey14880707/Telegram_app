from flask import Blueprint, request, jsonify, session, render_template
from db import get_db

try:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name="du4oyqcl0",
        api_key="556112684556269",
        api_secret="tT04gZYKmEySyCXsCP-SvWn6sio"
    )
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

bp = Blueprint('feed', __name__)


@bp.route('/feed')
def feed():
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM posts ORDER BY created_at DESC'
        ).fetchall()
    posts = [dict(r) for r in rows]
    return render_template('feed.html', posts=posts)


@bp.route('/api/admin/posts', methods=['GET'])
def list_posts():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM posts ORDER BY created_at DESC'
        ).fetchall()
    return jsonify({'posts': [dict(r) for r in rows]})


@bp.route('/api/admin/posts', methods=['POST'])
def create_post():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    text = request.form.get('text', '').strip()
    media_url = ''
    media_type = ''

    if 'file' in request.files and request.files['file'].filename:
        f = request.files['file']
        if not CLOUDINARY_AVAILABLE:
            return jsonify({'success': False, 'error': 'Cloudinary not installed'}), 500
        if f.content_type.startswith('video'):
            result = cloudinary.uploader.upload(f, resource_type='video', folder='barber_feed')
            media_type = 'video'
        else:
            result = cloudinary.uploader.upload(f, folder='barber_feed')
            media_type = 'image'
        media_url = result['secure_url']

    if not text and not media_url:
        return jsonify({'success': False, 'error': 'Пост пустой'}), 400

    with get_db() as conn:
        conn.execute(
            'INSERT INTO posts (text, media_url, media_type) VALUES (?, ?, ?)',
            (text, media_url, media_type)
        )
        conn.commit()
    return jsonify({'success': True})


@bp.route('/api/admin/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:
        row = conn.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
        if row and row['media_url'] and CLOUDINARY_AVAILABLE:
            try:
                # Extract public_id from the Cloudinary URL
                url = row['media_url']
                # URL format: https://res.cloudinary.com/<cloud>/image/upload/v<ver>/<folder>/<public_id>.<ext>
                parts = url.split('/')
                # public_id is folder/filename_without_ext
                folder_and_file = '/'.join(parts[-2:])
                public_id = folder_and_file.rsplit('.', 1)[0]
                resource_type = 'video' if row['media_type'] == 'video' else 'image'
                cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            except Exception:
                pass
        if row:
            conn.execute('DELETE FROM posts WHERE id=?', (post_id,))
            conn.commit()
    return jsonify({'success': True})
