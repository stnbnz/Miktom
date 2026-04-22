from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/router_status', views.router_status, name='router_status'),
    path('api/system_health', views.system_health, name='system_health'),
    path('api/backup', views.trigger_backup, name='trigger_backup'),
    path('api/backup_history', views.backup_history, name='backup_history'),
    path('api/reboot', views.reboot_router, name='reboot_router'),
    path('api/reset', views.reset_router, name='reset_router'),

    # Voucher Billing
    path('voucher/', views.voucher_page, name='voucher_page'),
    path('active-users/', views.active_users, name='active_users'),
    path('settings/', views.settings_page, name='settings_page'),
    path('api/voucher/generate', views.generate_vouchers, name='generate_vouchers'),
    path('api/voucher/list', views.get_vouchers, name='get_vouchers'),
    path('api/voucher/delete/<str:code>', views.delete_voucher, name='delete_voucher'),
    path('api/voucher/delete_batch', views.delete_vouchers_batch, name='delete_vouchers_batch'),
    path('voucher/print', views.print_vouchers, name='print_vouchers'),
    path('api/active_users_data', views.active_users_data, name='active_users_data'),
    path('api/kick_user', views.kick_hotspot_user, name='kick_hotspot_user'),
    path('api/manage_blocked_user', views.manage_blocked_user, name='manage_blocked_user'),
    
    # PPPoE Management
    path('pppoe/', views.pppoe_page, name='pppoe_page'),
    path('api/pppoe/list', views.get_pppoe_users, name='get_pppoe_users'),
    path('api/pppoe/add', views.add_pppoe_user, name='add_pppoe_user'),
    path('api/pppoe/delete/<str:username>', views.delete_pppoe_user, name='delete_pppoe_user'),
    
    # Router Management
    path('api/routers', views.get_routers, name='get_routers'),
    path('api/add_router', views.add_router, name='add_router'),
    path('api/delete_router/<int:id>', views.delete_router, name='delete_router'),
    path('api/set_active_router', views.set_active_router, name='set_active_router'),
    
    # Real-time updates
    path('api/sse', views.sse_updates, name='sse_updates'),
]
