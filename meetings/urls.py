from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # Dashboard & projects
    path('', views.dashboard, name='dashboard'),
    path('projects/create/', views.create_project, name='create_project'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<int:project_id>/delete/', views.delete_project, name='delete_project'),
    path('projects/<int:project_id>/chat/', views.project_chat, name='project_chat'),
    # Meetings
    path('meetings/upload/', views.upload_meeting, name='upload_meeting'),
    path('meetings/add-link/', views.add_bot_to_meeting, name='add_bot_to_meeting'),
    path('meetings/<int:meeting_id>/', views.meeting_detail, name='meeting_detail'),
    path('meetings/<int:meeting_id>/delete/', views.delete_meeting, name='delete_meeting'),
    path('meetings/<int:meeting_id>/reprocess/', views.reprocess_meeting, name='reprocess_meeting'),
    path('search/', views.search, name='search'),
    # Webhooks
    path('webhook/recall/', views.recall_webhook, name='recall_webhook'),
    # API
    path('api/meetings/<int:meeting_id>/status/', views.meeting_status_api, name='meeting_status_api'),
]

