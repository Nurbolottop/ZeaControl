from django.urls import path
from apps.projects.views import (
    dashboard_view,
    project_detail_view,
    project_action_view,
    servers_view,
    billing_view,
)

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('project/<slug:slug>/', project_detail_view, name='project_detail'),
    path('project/<slug:slug>/<str:action>/', project_action_view, name='project_action'),
    path('servers/', servers_view, name='servers'),
    path('billing/', billing_view, name='billing'),
]
