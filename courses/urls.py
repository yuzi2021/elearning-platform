"""
Courses app URL patterns.
"""
from django.urls import path
from . import views
from . import api
app_name = 'courses'
urlpatterns = [
    # ===== TRADITIONAL VIEWS (Render HTML) =====
    path('', views.home_view, name='home'),
    path('api-docs/', views.api_docs_view, name='api_docs'),
    path('courses/', views.course_list_view, name='course_list'),
    path('courses/<int:pk>/', views.course_detail_view, name='course_detail'),
    path('courses/create/', views.course_create_view, name='course_create'),
    path('courses/<int:pk>/edit/', views.course_edit_view, name='course_edit'),
    path('courses/<int:pk>/chat/', views.course_chat_view, name='course_chat'),
    # ===== Authentication URLs =====
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    # ===== Course Materials =====
    path('courses/<int:course_pk>/upload/', views.upload_material, name='upload_material'),
    path('materials/<int:pk>/download/', views.download_material, name='download_material'),
    path('materials/<int:pk>/delete/', views.delete_material, name='delete_material'),
    # ===== Notifications =====
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    # ===== Search =====
    path('search/', views.search_users, name='search_users'),
    # ===== Student management =====
    path('courses/<int:pk>/students/', views.manage_course_students, name='manage_students'),
    path('enrollments/<int:pk>/toggle/', views.toggle_student_enrollment, name='toggle_enrollment'),
    path('enrollments/<int:pk>/remove/', views.remove_student_enrollment, name='remove_enrollment'),
]
