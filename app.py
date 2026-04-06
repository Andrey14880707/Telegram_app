from flask import Flask, render_template
from config import SECRET_KEY, UPLOAD_FOLDER
import os

app = Flask(__name__)
app.secret_key = SECRET_KEY
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

for bp in (auth_bp, booking_bp, admin_apts_bp, admin_clients_bp, photos_bp, hours_bp, gcal_bp, feed_bp):
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

# ── Boot ──────────────────────────────────────────────────────────────────────
from db import init_db
from scheduler import start_scheduler

init_db()
start_scheduler()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8088)
