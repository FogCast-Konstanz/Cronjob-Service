from flask import Flask, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

LOG_PATH = os.getenv('LOG_PATH')
if not LOG_PATH:
    raise ValueError('LOG_PATH environment variable is not set')

def read_cronjob_status():
    log_file_path = LOG_PATH
    if not os.path.exists(log_file_path):
        return {'status': 'unknown', 'message': 'Log-Datei nicht gefunden'}

    try:
        with open(log_file_path, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        return {'status': 'unknown', 'message': f'Fehler beim Lesen der Log-Datei: {e}'}

    if not lines:
        return {'status': 'unknown', 'message': 'Log-Datei ist leer'}

    # Search start of last cron run
    last_run_start = None
    for i in range(len(lines) - 1, -1, -1):
        if "Cron gestartet" in lines[i]:
            last_run_start = i
            break

    if last_run_start is not None:
        last_run_block = lines[last_run_start:]
    else:
        last_run_block = lines

    block = ''.join(last_run_block)

    # Prüfe den letzten Block auf Fehlerindikatoren
    if "ERROR" in block:
        status = 'error'
    else:
        status = 'success'

    return {'status': status}

@app.route('/cronjob-status', methods=['GET'])
def cronjob_status():
    status = read_cronjob_status()
    return jsonify(status)

@app.route('/health-check')
def health_check():
    return "success"

if __name__ == '__main__':
    app.run(debug=True)
