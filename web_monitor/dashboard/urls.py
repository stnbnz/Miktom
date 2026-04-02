from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/router_status', views.router_status, name='router_status'),
    path('api/backup', views.trigger_backup, name='trigger_backup'),
    path('api/backup_history', views.backup_history, name='backup_history'),
    path('api/reboot', views.reboot_router, name='reboot_router'),
    path('api/reset', views.reset_router, name='reset_router'),
]
