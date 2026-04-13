from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/router_status', views.router_status, name='router_status'),
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
    path('voucher/print', views.print_vouchers, name='print_vouchers'),
    path('api/active_users_data', views.active_users_data, name='active_users_data'),
    path('api/kick_user', views.kick_hotspot_user, name='kick_hotspot_user'),
    
    # Router Management
    path('api/routers', views.get_routers, name='get_routers'),
    path('api/add_router', views.add_router, name='add_router'),
    path('api/delete_router/<int:id>', views.delete_router, name='delete_router'),
    path('api/set_active_router', views.set_active_router, name='set_active_router'),
]
