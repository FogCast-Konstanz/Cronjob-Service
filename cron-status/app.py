
"""Cron-runner log status. Does not certify that new weather data were written."""
from datetime import datetime, timezone
import os

from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

LOG_PATH = os.getenv('LOG_PATH')
if not LOG_PATH:
    raise ValueError('LOG_PATH environment variable is not set')

# Scheduler is invoked hourly in the provided crontab. Provisional bounds.
FRESH_MINUTES = 90
LATE_MINUTES = 180
START_MARKERS = ('## Cron scheduler started', 'Cron gestartet')


def read_cronjob_status(now=None):
    now = now or datetime.now(timezone.utc)
    checked_at = now.isoformat().replace('+00:00', 'Z')
    if not os.path.isfile(LOG_PATH):
        return {'status': 'unknown', 'message': 'Cronjob-Logdatei fehlt.',
                'checked_at': checked_at, 'last_activity_at': None}
    try:
        # File modification time is only *last log activity*, not the job start.
        last_modified = datetime.fromtimestamp(os.path.getmtime(LOG_PATH), timezone.utc)
        with open(LOG_PATH, encoding='utf-8', errors='replace') as log:
            lines = log.readlines()[-10000:]
    except OSError:
        return {'status': 'unknown', 'message': 'Cronjob-Logdatei nicht lesbar.',
                'checked_at': checked_at, 'last_activity_at': None}

    last_activity_at = last_modified.isoformat().replace('+00:00', 'Z')
    start_index = next((i for i in range(len(lines) - 1, -1, -1)
                        if any(marker in lines[i] for marker in START_MARKERS)), None)
    if start_index is None:
        return {'status': 'unknown', 'message': 'Kein Scheduler-Start im Log nachgewiesen.',
                'checked_at': checked_at, 'last_activity_at': last_activity_at}

    block = ''.join(lines[start_index:])
    if 'ERROR' in block or 'Job failed' in block or 'Job controlled termination' in block:
        return {'status': 'error', 'message': 'Fehler im letzten Cronjob-Durchlauf.',
                'checked_at': checked_at, 'last_activity_at': last_activity_at}
    if 'Job completed:' not in block:
        return {'status': 'unknown', 'message': 'Kein erfolgreich abgeschlossener Job nachweisbar.',
                'checked_at': checked_at, 'last_activity_at': last_activity_at}

    age_minutes = (now - last_modified).total_seconds() / 60
    if age_minutes < -2:
        status, message = 'unknown', 'Logzeitstempel liegt in der Zukunft.'
    elif age_minutes <= FRESH_MINUTES:
        status, message = 'success', 'Letzter Cron-Durchlauf ohne erkannten Fehler; Datenfrische separat prüfen.'
    elif age_minutes <= LATE_MINUTES:
        status, message = 'warning', 'Cronjob-Logaktivität verspätet.'
    else:
        status, message = 'error', 'Cronjob-Logaktivität veraltet.'
    return {'status': status, 'message': message, 'checked_at': checked_at,
            'last_activity_at': last_activity_at}


@app.route('/status', methods=['GET'])
def cronjob_status():
    response = jsonify(read_cronjob_status())
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.route('/health-check')
def health_check():
    return 'success'


if __name__ == '__main__':
    app.run(debug=True)
