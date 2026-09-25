"""
API URL routing using Django REST Framework routers.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api

router = DefaultRouter()
router.register(r'users', api.UserViewSet, basename='user')
router.register(r'students', api.StudentProfileViewSet, basename='student')
router.register(r'teachers', api.TeacherProfileViewSet, basename='teacher')

urlpatterns = [
    # ViewSets URLs (automatically generated)
    path('', include(router.urls)),
    # custom function-based API views
    path('courses/<int:pk>/enroll/', api.api_course_enroll, name='api_course_enroll'), 
    path('courses/<int:pk>/feedback/', api.api_feedback_create, name='api_feedback_create'), 
    path('status/create/', api.api_status_create, name='api_status_create'), 
    path('courses/', api.api_course_list, name='api_course_list'), 
    path('courses/<int:pk>/', api.api_course_detail, name='api_course_detail'), 
    path('status/', api.api_status_list, name='api_status_list'), 
    path('quote/', api.api_get_daily_quote, name='api_daily_quote'), 
    path('weather/', api.api_get_weather, name='api_weather'), 
    path('course/analyze/', api.api_analyze_course, name='api_analyze_course'),

]
