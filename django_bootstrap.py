"""
Shared Django bootstrap for all standalone MikroTik automation scripts.

Usage:
    from django_bootstrap import setup_django, get_router
    setup_django()
    # Now you can import Django models
    from dashboard.models import Router, SpeedtestLog, etc.
"""
import os
import sys


def setup_django():
    """Initialize Django environment for standalone scripts."""
    # Add web_monitor directory to Python path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    web_monitor_dir = os.path.join(base_dir, 'web_monitor')
    
    if web_monitor_dir not in sys.path:
        sys.path.insert(0, web_monitor_dir)
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_monitor.settings')
    
    import django
    django.setup()


def get_router(router_ip=None):
    """
    Get router from database.
    
    Args:
        router_ip: Optional IP address to look up specific router.
                   If None, returns the first active router or any router.
    
    Returns:
        Router instance or None
    """
    from dashboard.models import Router
    
    if router_ip:
        router = Router.objects.filter(ip_address=router_ip).first()
        if router:
            return router
    
    # Try active router first, then any router
    return Router.objects.filter(is_active=True).first() or Router.objects.first()


def get_router_or_exit(router_ip=None):
    """Same as get_router but exits if no router found."""
    router = get_router(router_ip)
    if not router:
        print("Error: Tidak ada router di database. Tambahkan router via dashboard Settings terlebih dahulu.")
        sys.exit(1)
    return router


def get_mikrotik_api(router):
    """
    Connect to MikroTik router via API.
    
    Args:
        router: Router model instance
    
    Returns:
        Tuple of (connection, api)
    """
    import routeros_api
    
    connection = routeros_api.RouterOsApiPool(
        router.ip_address,
        username=router.username,
        password=router.password,
        port=router.port,
        plaintext_login=True
    )
    return connection, connection.get_api()
