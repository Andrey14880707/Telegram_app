import json
from datetime import datetime, timedelta
from config import GCAL_AVAILABLE, GCAL_SCOPES
from db import get_db, get_setting, set_setting

try:
    from google.auth.transport.requests import Request as GRequest
    from google.oauth2.credentials import Credentials as GCredentials
    from googleapiclient.discovery import build as gbuild
except ImportError:
    pass


def get_gcal_creds():
    from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, GOOGLE_CALENDAR_ID
    return {
        'client_id':     get_setting('gcal_client_id')     or GOOGLE_CLIENT_ID,
        'client_secret': get_setting('gcal_client_secret') or GOOGLE_CLIENT_SECRET,
        'redirect_uri':  get_setting('gcal_redirect_uri')  or GOOGLE_REDIRECT_URI,
        'calendar_id':   get_setting('gcal_calendar_id')   or GOOGLE_CALENDAR_ID or 'primary',
    }


def gcal_client_config():
    c = get_gcal_creds()
    return {
        "web": {
            "client_id": c['client_id'],
            "client_secret": c['client_secret'],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def load_gcal_tokens():
    with get_db() as conn:
        row = conn.execute('SELECT token_data FROM google_tokens WHERE id=1').fetchone()
    return json.loads(row['token_data']) if row else None


def save_gcal_tokens(token_dict):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO google_tokens (id, token_data, updated_at)
            VALUES (1, ?, datetime('now','localtime'))
            ON CONFLICT(id) DO UPDATE SET token_data=excluded.token_data, updated_at=excluded.updated_at
        ''', (json.dumps(token_dict),))
        conn.commit()


def get_gcal_service():
    if not GCAL_AVAILABLE:
        return None
    c = get_gcal_creds()
    if not c['client_id'] or not c['client_secret']:
        return None
    token_data = load_gcal_tokens()
    if not token_data:
        return None
    try:
        creds = GCredentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=c['client_id'],
            client_secret=c['client_secret'],
            scopes=GCAL_SCOPES,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
            save_gcal_tokens({
                'token':         creds.token,
                'refresh_token': creds.refresh_token,
                'expiry':        creds.expiry.isoformat() if creds.expiry else None,
            })
        return gbuild('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f'[GCal] get_service error: {e}')
        return None


def gcal_create_event(apt):
    service = get_gcal_service()
    if not service:
        return None
    try:
        dt_start = datetime.strptime(f"{apt['date']} {apt['time']}", '%Y-%m-%d %H:%M')
        dt_end   = dt_start + timedelta(hours=1)
        event = {
            'summary': f'✂ {apt["service"]} — {apt["name"]}',
            'description': (
                f'Клиент: {apt["name"]}\nТелефон: {apt["phone"]}\nЦена: {apt["price"]}€'
                + (f'\nКомментарий: {apt["comment"]}' if apt.get('comment') else '')
            ),
            'start': {'dateTime': dt_start.strftime('%Y-%m-%dT%H:%M:%S'), 'timeZone': 'Europe/Berlin'},
            'end':   {'dateTime': dt_end.strftime('%Y-%m-%dT%H:%M:%S'),   'timeZone': 'Europe/Berlin'},
            'reminders': {'useDefault': False, 'overrides': [
                {'method': 'popup', 'minutes': 120},
                {'method': 'popup', 'minutes': 30},
            ]},
        }
        if apt.get('email'):
            event['attendees'] = [{'email': apt['email']}]
        cal_id = get_gcal_creds()['calendar_id']
        result = service.events().insert(
            calendarId=cal_id, body=event,
            sendUpdates='all' if apt.get('email') else 'none'
        ).execute()
        return result.get('id')
    except Exception as e:
        print(f'[GCal] create_event error: {e}')
        return None


def gcal_update_event(event_id, apt):
    service = get_gcal_service()
    if not service or not event_id:
        return False
    try:
        dt_start = datetime.strptime(f"{apt['date']} {apt['time']}", '%Y-%m-%d %H:%M')
        dt_end   = dt_start + timedelta(hours=1)
        cal_id = get_gcal_creds()['calendar_id']
        event  = service.events().get(calendarId=cal_id, eventId=event_id).execute()
        event['summary'] = f'✂ {apt["service"]} — {apt["name"]}'
        event['start']   = {'dateTime': dt_start.strftime('%Y-%m-%dT%H:%M:%S'), 'timeZone': 'Europe/Berlin'}
        event['end']     = {'dateTime': dt_end.strftime('%Y-%m-%dT%H:%M:%S'),   'timeZone': 'Europe/Berlin'}
        service.events().update(
            calendarId=cal_id, eventId=event_id, body=event,
            sendUpdates='all' if apt.get('email') else 'none'
        ).execute()
        return True
    except Exception as e:
        print(f'[GCal] update_event error: {e}')
        return False


def gcal_delete_event(event_id):
    service = get_gcal_service()
    if not service or not event_id:
        return False
    try:
        service.events().delete(
            calendarId=get_gcal_creds()['calendar_id'], eventId=event_id
        ).execute()
        return True
    except Exception as e:
        print(f'[GCal] delete_event error: {e}')
        return False
