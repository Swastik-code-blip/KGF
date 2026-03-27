import sys
import os

# ── CHANGE THIS PATH to your actual PythonAnywhere username and project folder ──
project_home = '/home/YOUR_PYTHONANYWHERE_USERNAME/kgf_portal'

if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['FLASK_ENV'] = 'production'

from app import app, init_db
init_db()   # creates DB + default admin on first run

application = app
