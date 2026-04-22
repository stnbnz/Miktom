import sys
import os
import django

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_monitor'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
django.setup()

from dashboard.models import Router
from dashboard.views import _get_mikrotik_api_for_router

router = Router.objects.first()
if not router:
    print("No router.")
    sys.exit()

conn, api = _get_mikrotik_api_for_router(router)
print("Connected.")

hs = api.get_resource('/ip/hotspot/user')
try:
    hs.add(name="testuser123_456", password="123", profile="default")
    print("Added hotspot user.")
except Exception as e:
    print("Add err:", e)

users = hs.get(**{'name': 'testuser123_456'})
print("Users found:", users)
if users:
    try:
        hs.remove(id=users[0]['.id'])
        print("Removed correctly.")
    except Exception as e:
        print("Remove error:", e)

conn.disconnect()
