import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, redirect
from config import GCAL_AVAILABLE, GCAL_SCOPES
from gcal_helpers import (
    get_gcal_creds, gcal_client_config, load_gcal_tokens, save_gcal_tokens, get_gcal_service
)
from db import get_db, set_setting

bp = Blueprint('gcal', __name__)


def _require_admin():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    return None


@bp.route('/api/admin/google/status')
def gcal_status():
    if err := _require_admin(): return err
    c          = get_gcal_creds()
    configured = bool(GCAL_AVAILABLE and c['client_id'] and c['client_secret'] and c['redirect_uri'])
    connected  = bool(load_gcal_tokens())
    return jsonify({
        'configured': configured,
        'connected':  connected,
        'debug': {
            'lib_installed':    GCAL_AVAILABLE,
            'has_client_id':    bool(c['client_id']),
            'has_client_secret': bool(c['client_secret']),
            'has_redirect_uri': bool(c['redirect_uri']),
            'redirect_uri':     c['redirect_uri'],
        }
    })


@bp.route('/api/debug/gcal')
def gcal_debug():
    google_vars = {k: v[:12]+'...' for k, v in os.environ.items() if 'GOOGLE' in k}
    return jsonify({
        'lib_installed':    GCAL_AVAILABLE,
        'google_env_vars': google_vars,
    })


@bp.route('/api/admin/google/connect')
def gcal_connect():
    if err := _require_admin(): return err
    c = get_gcal_creds()
    if not GCAL_AVAILABLE or not c['client_id'] or not c['client_secret'] or not c['redirect_uri']:
        return jsonify({'error': 'Client ID, Secret und Redirect URI erforderlich'}), 400
    from google_auth_oauthlib.flow import Flow
    flow      = Flow.from_client_config(gcal_client_config(), scopes=GCAL_SCOPES, redirect_uri=c['redirect_uri'])
    auth_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    set_setting('gcal_oauth_state', state)
    return jsonify({'auth_url': auth_url})


@bp.route('/api/admin/google/callback')
def gcal_callback():
    state       = request.args.get('state', '')
    saved_state = __import__('db').get_setting('gcal_oauth_state')
    if not saved_state or state != saved_state:
        return 'Invalid state parameter', 400
    if not GCAL_AVAILABLE:
        return 'google-auth-oauthlib not installed', 500
    try:
        from google_auth_oauthlib.flow import Flow
        c    = get_gcal_creds()
        flow = Flow.from_client_config(
            gcal_client_config(), scopes=GCAL_SCOPES,
            redirect_uri=c['redirect_uri'], state=state
        )
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        flow.fetch_token(authorization_response=request.url.replace('http://', 'https://', 1))
        creds = flow.credentials
        save_gcal_tokens({
            'token':         creds.token,
            'refresh_token': creds.refresh_token,
            'expiry':        creds.expiry.isoformat() if creds.expiry else None,
        })
        set_setting('gcal_oauth_state', '')
    except Exception as e:
        print(f'[GCal] callback error: {e}')
        return f'Ошибка авторизации: {e}', 500
    return redirect('/admin?gcal=connected')


@bp.route('/api/admin/google/disconnect', methods=['POST'])
def gcal_disconnect():
    if err := _require_admin(): return err
    with get_db() as conn:
        conn.execute('DELETE FROM google_tokens WHERE id=1')
        conn.commit()
    return jsonify({'success': True})


@bp.route('/api/admin/google/save-credentials', methods=['POST'])
def gcal_save_credentials():
    if err := _require_admin(): return err
    data = request.get_json() or {}
    if data.get('client_id'):     set_setting('gcal_client_id',     data['client_id'].strip())
    if data.get('client_secret'): set_setting('gcal_client_secret', data['client_secret'].strip())
    if data.get('redirect_uri'):  set_setting('gcal_redirect_uri',  data['redirect_uri'].strip())
    set_setting('gcal_calendar_id', data.get('calendar_id', 'primary').strip())
    return jsonify({'success': True})


@bp.route('/api/debug/gcal-test')
def gcal_test():
    c       = get_gcal_creds()
    tokens  = load_gcal_tokens()
    service = get_gcal_service()
    if not service:
        return jsonify({'error': 'get_gcal_service returned None',
                        'has_tokens': bool(tokens),
                        'has_client_id': bool(c['client_id'])})
    try:
        now   = datetime.now()
        event = {
            'summary': '✂ TEST — München Barber',
            'start': {'dateTime': now.strftime('%Y-%m-%dT%H:%M:%S'),                     'timeZone': 'Europe/Berlin'},
            'end':   {'dateTime': (now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S'), 'timeZone': 'Europe/Berlin'},
        }
        result = service.events().insert(calendarId=c['calendar_id'], body=event, sendUpdates='none').execute()
        service.events().delete(calendarId=c['calendar_id'], eventId=result['id']).execute()
        return jsonify({'success': True, 'message': 'Google Calendar работает!'})
    except Exception as e:
        return jsonify({'error': str(e)})
