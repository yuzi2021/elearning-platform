""" 
WebSocket URL routing. 
Like urls.py but for WebSocket connections. 
"""
from django.urls import re_path
from .  import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<course_id>\w+)/$', consumers.ChatConsumer.as_asgi()),
]