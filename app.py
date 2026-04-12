from flask import Flask, render_template
from config import SECRET_KEY, UPLOAD_FOLDER
from datetime import timedelta
import os
# v2026.04.12

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
print(f'[Boot] SECRET_KEY prefix={SECRET_KEY[:6]}  len={len(SECRET_KEY)}')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Blueprints ────────────────────────────────────────────────────────────────
from blueprints.auth          import bp as auth_bp
from blueprints.booking       import bp as booking_bp
from blueprints.admin_apts    import bp as admin_apts_bp
from blueprints.admin_clients import bp as admin_clients_bp
from blueprints.photos        import bp as photos_bp
from blueprints.hours         import bp as hours_bp
from blueprints.gcal_routes   import bp as gcal_bp
from blueprints.feed          import bp as feed_bp
from blueprints.client_auth   import bp as client_auth_bp

for bp in (auth_bp, booking_bp, admin_apts_bp, admin_clients_bp, photos_bp, hours_bp, gcal_bp, feed_bp, client_auth_bp):
    app.register_blueprint(bp)

import json as _json
@app.template_filter('fromjson')
def fromjson_filter(s):
    try:
        return _json.loads(s or '[]')
    except Exception:
        return []

# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/ping')
def ping():
    from flask import jsonify
    from db import get_db
    from config import DB_PATH
    try:
        with get_db() as conn:
            apts    = conn.execute('SELECT COUNT(*) FROM appointments').fetchone()[0]
            clients = conn.execute('SELECT COUNT(*) FROM client_accounts').fetchone()[0]
            photos  = conn.execute('SELECT COUNT(*) FROM photos').fetchone()[0]
            statuses = dict(conn.execute(
                "SELECT status, COUNT(*) FROM appointments GROUP BY status"
            ).fetchall())
            sample = [dict(r) for r in conn.execute(
                "SELECT id, name, phone, status FROM appointments LIMIT 3"
            ).fetchall()]
        return jsonify({'ok': True, 'appointments': apts, 'client_accounts': clients,
                        'photos': photos, 'db_path': DB_PATH,
                        'statuses': statuses, 'sample': sample})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── Boot ──────────────────────────────────────────────────────────────────────
from db import init_db, get_db
from scheduler import start_scheduler

try:
    init_db()
except Exception as e:
    print(f'[Boot] init_db failed: {e}')

# Force WAL checkpoint so new process sees all committed data from previous instance
try:
    from db import get_db as _gdb
    with _gdb() as _c:
        _c.execute('PRAGMA wal_checkpoint(FULL)')
        _apts = _c.execute('SELECT COUNT(*) FROM appointments').fetchone()[0]
        _statuses = dict(_c.execute('SELECT status, COUNT(*) FROM appointments GROUP BY status').fetchall())
        print(f'[Boot] WAL checkpoint done. appointments={_apts} statuses={_statuses}')
except Exception as e:
    print(f'[Boot] WAL checkpoint failed: {e}')

def migrate_uploads():
    """
    On each deploy Render recreates the container from git.
    Any photos tracked in git live in <app>/uploads/ but the app
    serves from UPLOAD_FOLDER (e.g. /data/uploads/).
    This function copies missing files and registers them in the DB.
    """
    import shutil, pathlib
    git_dir    = pathlib.Path(__file__).parent / 'uploads'
    target_dir = pathlib.Path(UPLOAD_FOLDER)
    target_dir.mkdir(parents=True, exist_ok=True)

    if git_dir.resolve() == target_dir.resolve():
        return  # same directory, nothing to do

    ALLOWED = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    try:
        with get_db() as conn:
            for src in git_dir.iterdir():
                if src.suffix.lower().lstrip('.') not in ALLOWED:
                    continue
                dst = target_dir / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
                    print(f'[Boot] copied {src.name} → {target_dir}')
                # Register in photos table if missing
                if not conn.execute('SELECT id FROM photos WHERE filename=?', (src.name,)).fetchone():
                    conn.execute(
                        "INSERT INTO photos (filename, caption, category) VALUES (?,?,?)",
                        (src.name, '', 'Portfolio')
                    )
                    print(f'[Boot] registered {src.name} in photos table')
            conn.commit()
    except Exception as e:
        print(f'[Boot] migrate_uploads failed: {e}')

try:
    migrate_uploads()
except Exception as e:
    print(f'[Boot] migrate_uploads outer failed: {e}')

try:
    start_scheduler()
except Exception as e:
    print(f'[Boot] start_scheduler failed: {e}')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8088)
