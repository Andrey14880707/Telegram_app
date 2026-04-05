import os
import atexit
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from db import get_db
from notifications import notify_client, send_to_n8n


def check_reminders():
    try:
        _run_reminders()
    except Exception as e:
        print(f'[Scheduler] check_reminders error: {e}')


def _run_reminders():
    conn = get_db()
    now  = datetime.now()

    # 24h reminder
    d24    = (now + timedelta(hours=24)).strftime('%Y-%m-%d')
    t24_lo = (now + timedelta(hours=23, minutes=30)).strftime('%H:%M')
    t24_hi = (now + timedelta(hours=24, minutes=30)).strftime('%H:%M')
    for row in conn.execute('''
        SELECT * FROM appointments
        WHERE status='confirmed' AND reminder_24h=0
        AND date=? AND time>=? AND time<=?
    ''', (d24, t24_lo, t24_hi)).fetchall():
        send_to_n8n({'event_type': 'reminder_24h', **_apt_payload(row)})
        msg = (
            f"✂ <b>München Barber — Terminerinnerung</b>\n\n"
            f"Hallo {row['name']}! Dein Termin ist <b>morgen</b>:\n"
            f"📅 {row['date']} · ⏰ {row['time']}\n"
            f"💈 {row['service']} — {row['price']}€\n\nBis morgen! @barbermunich1"
        )
        if notify_client(row, msg):
            conn.execute('UPDATE appointments SET reminder_24h=1 WHERE id=?', (row['id'],))

    # 2h reminder
    d2    = now.strftime('%Y-%m-%d')
    t2_lo = (now + timedelta(hours=1, minutes=45)).strftime('%H:%M')
    t2_hi = (now + timedelta(hours=2, minutes=15)).strftime('%H:%M')
    for row in conn.execute('''
        SELECT * FROM appointments
        WHERE status='confirmed' AND reminder_2h_sent=0
        AND date=? AND time>=? AND time<=?
    ''', (d2, t2_lo, t2_hi)).fetchall():
        send_to_n8n({'event_type': 'reminder_2h', **_apt_payload(row)})
        msg = (
            f"⏰ <b>München Barber — In 2 Stunden!</b>\n\n"
            f"Hallo {row['name']}! Dein Termin ist <b>in 2 Stunden</b>:\n"
            f"📅 {row['date']} · ⏰ {row['time']}\n"
            f"💈 {row['service']} — {row['price']}€\n\nBis gleich! @barbermunich1"
        )
        if notify_client(row, msg):
            conn.execute('UPDATE appointments SET reminder_2h_sent=1 WHERE id=?', (row['id'],))

    # 21-day follow-up
    cutoff = (now - timedelta(days=21)).strftime('%Y-%m-%d')
    for row in conn.execute('''
        SELECT * FROM appointments
        WHERE status IN ('confirmed','completed') AND followup_sent=0 AND date=?
    ''', (cutoff,)).fetchall():
        send_to_n8n({'event_type': 'followup_21d', **_apt_payload(row)})
        msg = (
            f"💈 <b>München Barber — Zeit für einen neuen Schnitt!</b>\n\n"
            f"Hey {row['name']}! Es ist schon 3 Wochen her —\n"
            f"Zeit für deinen nächsten Termin?\n\n"
            f"Jetzt buchen: https://munchen-barber.onrender.com/#termin\n"
            f"@barbermunich1"
        )
        if notify_client(row, msg):
            conn.execute('UPDATE appointments SET followup_sent=1 WHERE id=?', (row['id'],))

    conn.commit()
    conn.close()


def _apt_payload(row):
    return {
        'id': row['id'], 'name': row['name'], 'phone': row['phone'],
        'email': row['email'], 'telegram': row['telegram'],
        'service': row['service'], 'price': row['price'], 'currency': 'EUR',
        'date': row['date'], 'time': row['time'],
    }


def start_scheduler():
    if os.environ.get('WERKZEUG_RUN_MAIN'):
        return
    import pytz
    sched = BackgroundScheduler(daemon=True, timezone=pytz.utc)
    sched.add_job(check_reminders, IntervalTrigger(minutes=30),
                  id='reminders', replace_existing=True)
    sched.start()
    atexit.register(sched.shutdown)
