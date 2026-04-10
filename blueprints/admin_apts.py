import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, Response
from db import get_db
from notifications import notify_client, send_to_n8n, send_email
from gcal_helpers import gcal_delete_event, gcal_update_event
from config import SMTP_USER

bp = Blueprint('admin_apts', __name__)

VALID_STATUSES = {'pending', 'confirmed', 'cancelled', 'completed', 'deleted'}


def _require_admin():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    return None


@bp.route('/api/admin/appointments')
def list_appointments():
    if err := _require_admin(): return err
    status = request.args.get('status', '')
    date_f = request.args.get('date', '')
    search = request.args.get('search', '')

    q, params = 'SELECT * FROM appointments WHERE 1=1', []
    if status: q += ' AND status=?';                    params.append(status)
    if date_f: q += ' AND date=?';                     params.append(date_f)
    if search:
        q += ' AND (name LIKE ? OR phone LIKE ?)';     params += [f'%{search}%', f'%{search}%']
    q += " ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'confirmed' THEN 1 ELSE 2 END, date ASC, time ASC"

    with get_db() as conn:
        rows = conn.execute(q, params).fetchall()
    return jsonify({'appointments': [dict(r) for r in rows]})


@bp.route('/api/admin/appointments/<int:apt_id>', methods=['PATCH'])
def patch_appointment(apt_id):
    if err := _require_admin(): return err
    data       = request.get_json() or {}
    new_status = data.get('status')
    if new_status not in VALID_STATUSES:
        return jsonify({'error': 'Invalid status'})

    with get_db() as conn:
        conn.execute('UPDATE appointments SET status=? WHERE id=?', (new_status, apt_id))
        conn.commit()
        row = conn.execute('SELECT * FROM appointments WHERE id=?', (apt_id,)).fetchone()

    if row and new_status in ('cancelled', 'deleted') and row['google_event_id']:
        gcal_delete_event(row['google_event_id'])

    if row:
        send_to_n8n({
            'event_type': 'status_changed', 'id': apt_id,
            'name': row['name'], 'phone': row['phone'],
            'service': row['service'], 'price': row['price'], 'currency': 'EUR',
            'date': row['date'], 'time': row['time'], 'status': new_status,
        })

    if new_status == 'confirmed' and row:
        notify_client(row,
            f"✅ <b>Termin bestätigt!</b>\n\n"
            f"{row['name']}, dein Termin ist bestätigt:\n"
            f"📅 {row['date']} · ⏰ {row['time']}\n"
            f"💈 {row['service']} — {row['price']}€\n\nBis dann! ✂"
        )
    return jsonify({'success': True})


@bp.route('/api/admin/appointments/reschedule', methods=['POST'])
def reschedule():
    if err := _require_admin(): return err
    data     = request.get_json() or {}
    apt_id   = data.get('id')
    new_date = data.get('date')
    new_time = data.get('time')
    if not all([apt_id, new_date, new_time]):
        return jsonify({'success': False, 'error': 'Fehlende Daten'})

    with get_db() as conn:
        if conn.execute(
            "SELECT id FROM appointments WHERE date=? AND time=? AND status NOT IN ('cancelled','deleted') AND id!=?",
            (new_date, new_time, apt_id)
        ).fetchone():
            return jsonify({'success': False, 'error': 'Dieser Slot ist bereits belegt'})

        conn.execute('UPDATE appointments SET date=?,time=? WHERE id=?', (new_date, new_time, apt_id))
        conn.commit()
        row = conn.execute('SELECT * FROM appointments WHERE id=?', (apt_id,)).fetchone()

    if row and row['google_event_id']:
        gcal_update_event(row['google_event_id'], dict(row))

    if row and row['email']:
        old_date = data.get('old_date', '')
        old_time = data.get('old_time', '')
        send_email(
            row['email'], 'München Barber — Termin verschoben',
            f'''<html><body style="font-family:sans-serif;background:#0f0f0f;color:#f0f0f0;padding:2rem;max-width:500px;margin:0 auto">
            <h2 style="color:#d4af37">München Barber</h2>
            <p>Hallo <b>{row["name"]}</b>, dein Termin wurde verschoben.</p>
            <table style="margin:1.5rem 0;border-collapse:collapse;width:100%">
              <tr><td style="padding:.5rem;color:#999">War</td><td style="padding:.5rem;text-decoration:line-through;color:#888">{old_date} · {old_time}</td></tr>
              <tr><td style="padding:.5rem;color:#999">Neu</td><td style="padding:.5rem"><b style="color:#d4af37">{new_date} · {new_time}</b></td></tr>
              <tr><td style="padding:.5rem;color:#999">Service</td><td style="padding:.5rem">{row["service"]} — {row["price"]}€</td></tr>
            </table>
            <p>Bei Fragen: <a href="https://t.me/barbermunich1" style="color:#d4af37">@barbermunich1</a></p>
            </body></html>'''
        )
    return jsonify({'success': True})


@bp.route('/api/admin/remind/<int:apt_id>', methods=['POST'])
def manual_remind(apt_id):
    if err := _require_admin(): return err
    with get_db() as conn:
        row = conn.execute('SELECT * FROM appointments WHERE id=?', (apt_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'})
    msg = (
        f"✂ <b>München Barber — Terminerinnerung</b>\n\n"
        f"{row['name']}, denk an deinen Termin:\n"
        f"📅 {row['date']} · ⏰ {row['time']}\n"
        f"💈 {row['service']} — {row['price']}€\n\nBei Fragen: @barbermunich1"
    )
    sent = notify_client(row, msg)
    return jsonify({'success': sent,
                    'message': 'Erinnerung gesendet ✓' if sent else 'Keine Kontaktdaten hinterlegt'})


@bp.route('/api/admin/stats')
def stats():
    if err := _require_admin(): return err
    now         = datetime.now()
    today       = now.strftime('%Y-%m-%d')
    week_start  = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
    month_pref  = now.strftime('%Y-%m')
    with get_db() as conn:
        result = {
            'today':     conn.execute("SELECT COUNT(*) FROM appointments WHERE date=? AND status!='cancelled'",(today,)).fetchone()[0],
            'week':      conn.execute("SELECT COUNT(*) FROM appointments WHERE date>=? AND status!='cancelled'",(week_start,)).fetchone()[0],
            'total':     conn.execute("SELECT COUNT(*) FROM appointments WHERE status!='cancelled'").fetchone()[0],
            'pending':   conn.execute("SELECT COUNT(*) FROM appointments WHERE status='pending'").fetchone()[0],
            'clients':   conn.execute("SELECT COUNT(DISTINCT phone) FROM appointments WHERE status!='cancelled'").fetchone()[0],
            'rev_today': conn.execute("SELECT COALESCE(SUM(price),0) FROM appointments WHERE date=? AND status='confirmed'",(today,)).fetchone()[0],
            'rev_month': conn.execute("SELECT COALESCE(SUM(price),0) FROM appointments WHERE date LIKE ? AND status='confirmed'",(month_pref+'%',)).fetchone()[0],
        }
    return jsonify(result)


@bp.route('/api/admin/analytics')
def analytics():
    if err := _require_admin(): return err
    with get_db() as conn:
        monthly = conn.execute("""
            SELECT strftime('%Y-%m', date) as month,
                   COALESCE(SUM(price),0) as revenue,
                   COUNT(*) as bookings
            FROM appointments
            WHERE status IN ('confirmed','completed')
              AND date >= date('now','-6 months')
            GROUP BY month ORDER BY month
        """).fetchall()
        daily = conn.execute("""
            SELECT date, COUNT(*) as count
            FROM appointments
            WHERE status NOT IN ('cancelled','deleted')
              AND date >= date('now','-30 days')
            GROUP BY date ORDER BY date
        """).fetchall()
        services = conn.execute("""
            SELECT service, COUNT(*) as count, COALESCE(SUM(price),0) as revenue
            FROM appointments
            WHERE status IN ('confirmed','completed')
            GROUP BY service ORDER BY count DESC
        """).fetchall()
        hours = conn.execute("""
            SELECT time, COUNT(*) as count
            FROM appointments
            WHERE status NOT IN ('cancelled','deleted')
            GROUP BY time ORDER BY time
        """).fetchall()
        statuses = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM appointments GROUP BY status
        """).fetchall()
    return jsonify({
        'monthly':  [dict(r) for r in monthly],
        'daily':    [dict(r) for r in daily],
        'services': [dict(r) for r in services],
        'hours':    [dict(r) for r in hours],
        'statuses': [dict(r) for r in statuses],
    })


@bp.route('/api/admin/export')
def export_csv():
    if err := _require_admin(): return err
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM appointments ORDER BY date DESC').fetchall()
    out = io.StringIO()
    w   = csv.writer(out)
    w.writerow(['ID','Name','Telefon','E-Mail','Telegram','Service','Preis (€)',
                'Datum','Uhrzeit','Status','Kommentar','Erstellt'])
    for r in rows:
        w.writerow([r['id'],r['name'],r['phone'],r['email'],r['telegram'],
                    r['service'],r['price'],r['date'],r['time'],
                    r['status'],r['comment'],r['created_at']])
    return Response(
        '\ufeff' + out.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=termine.csv'}
    )


@bp.route('/api/admin/test-email')
def test_email():
    if err := _require_admin(): return err
    from notifications import send_email as _send
    if not SMTP_USER:
        return jsonify({'ok': False, 'error': 'SMTP_USER not set'})
    ok = _send(SMTP_USER, 'München Barber — Test Email',
               '<h2>Email funktioniert!</h2><p>SMTP ist korrekt konfiguriert.</p>')
    return jsonify({'ok': ok, 'message': f'Sent to {SMTP_USER}' if ok else 'Check server logs'})


@bp.route('/api/admin/send-email', methods=['POST'])
def send_email_to_client():
    if err := _require_admin(): return err
    data  = request.get_json() or {}
    email = data.get('email', '')
    name  = data.get('name', '')
    msg   = data.get('message', '')
    if not email or not msg:
        return jsonify({'ok': False, 'error': 'email/message fehlt'})
    html = (
        f'<html><body style="font-family:sans-serif;background:#0f0f0f;color:#f0f0f0;padding:2rem;max-width:500px;margin:0 auto">'
        f'<h2 style="color:#d4af37">München Barber</h2>'
        f'<p>Hallo <b>{name}</b>,</p>'
        f'<p style="white-space:pre-wrap">{msg}</p>'
        f'<p style="margin-top:2rem;color:#888">Bei Fragen: '
        f'<a href="https://t.me/barbermunich1" style="color:#d4af37">@barbermunich1</a></p>'
        f'</body></html>'
    )
    ok = send_email(email, 'München Barber', html)
    return jsonify({'ok': ok, 'error': '' if ok else 'SMTP nicht konfiguriert'})


@bp.route('/api/admin/block-slots', methods=['POST'])
def block_slots():
    if err := _require_admin(): return err
    data     = request.get_json() or {}
    date_str = data.get('date')
    times    = data.get('times', [])
    reason   = data.get('reason', 'Blockiert')
    if not date_str or not times:
        return jsonify({'success': False, 'error': 'Datum/Uhrzeit fehlt'})
    import sqlite3
    with get_db() as conn:
        for t in times:
            try:
                conn.execute('INSERT INTO blocked_slots (date,time,reason) VALUES (?,?,?)', (date_str, t, reason))
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    return jsonify({'success': True})


@bp.route('/api/admin/block-slots', methods=['DELETE'])
def unblock_slots():
    if err := _require_admin(): return err
    data     = request.get_json() or {}
    date_str = data.get('date')
    times    = data.get('times', [])
    with get_db() as conn:
        for t in times:
            conn.execute('DELETE FROM blocked_slots WHERE date=? AND time=?', (date_str, t))
        conn.commit()
    return jsonify({'success': True})
