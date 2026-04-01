from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/router_status', views.router_status, name='router_status'),
    path('api/backup', views.trigger_backup, name='trigger_backup'),
]
