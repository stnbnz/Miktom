import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.views import _get_mikrotik_api

conn, api = _get_mikrotik_api()
hotspot_user = api.get_resource('/ip/hotspot/user')
print("got resource")
try:
    hotspot_user.add(**{
        'name': 'test12345',
        'password': 'password123',
        'profile': 'default',
        'comment': 'Test user limit-uptime',
        'limit-uptime': '1h',
    })
    print("success")
except Exception as e:
    print(f"Exception: {str(e)}")
finally:
    conn.disconnect()
