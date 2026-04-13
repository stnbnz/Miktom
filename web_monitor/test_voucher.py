import sys
import os
sys.path.append("d:/Project/miktom/web_monitor")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')

import django
django.setup()

from dashboard.views import _get_mikrotik_api

try:
    conn, api = _get_mikrotik_api()
    print("Profiles:")
    for p in api.get_resource('/ip/hotspot/user/profile').get():
        print(p)
except Exception as e:
    print(f"Error: {e}")
