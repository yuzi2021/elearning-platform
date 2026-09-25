"""
WebSocket consumers for real-time features.
Authenticated real-time course discussion with Django Channels.

"""
import json
import logging
from django.db import models
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Async WebSocket consumer for course chat.
    Handles real-time messaging with database persistence.
    """

    async def connect(self):
        """
        Called when WebSocket connection is established.
        Join the course chat room.
        """
        self.course_id = self.scope['url_route']['kwargs']['course_id']
        self.room_group_name = f'chat_course_{self.course_id}'

        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self.user_can_access_course(user.id, user.is_superuser):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info('WebSocket joined course_id=%s user_id=%s', self.course_id, user.id)

    async def disconnect(self, close_code):
        """
        Called when WebSocket connection is closed.
        Leave the room.
        """
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """
        Called when a message is received from WebSocket.
        Resolves the sender from the authenticated session (scope['user']),
        saves to database, then broadcasts to everyone in the room.
        """
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            await self.send_error('Message must be valid JSON.')
            return

        message = data.get('message', '')
        if not isinstance(message, str):
            await self.send_error('Message must be text.')
            return
        message = message.strip()

        if not message:
            return
        if len(message) > 1000:
            await self.send_error('Message must be 1,000 characters or fewer.')
            return

        # Resolve sender from authenticated session — no name passed from client
        user = self.scope.get('user')

        # Determine display name for the broadcast
        if user and user.is_authenticated:
            sender_display = user.get_full_name() or user.username
        else:
            await self.close(code=4401)
            return

        # Save to database using the User FK
        await self.save_message(user, message)

        # Broadcast to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender': sender_display
            }
        )

    async def chat_message(self, event):
        """
        Called when a message is broadcast to the group.
        Send the message to the WebSocket client.
        """
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'type': 'chat'
        }))

    async def send_error(self, message):
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))

    @database_sync_to_async
    def user_can_access_course(self, user_id, is_superuser=False):
        from .models import Course

        courses = Course.objects.filter(pk=self.course_id)
        if is_superuser:
            return courses.exists()
        return courses.filter(
            models.Q(created_by_id=user_id)
            | models.Q(
                enrollments__student_id=user_id,
                enrollments__is_active=True,
            )
        ).exists()

    @database_sync_to_async
    def save_message(self, user, message):
        """
        Save message to database using the sender FK.
        Connections are authorized before acceptance, so every new message has
        an authenticated sender.
        """
        from .models import Course, ChatMessage
        course = Course.objects.get(pk=self.course_id)
        ChatMessage.objects.create(course=course, sender=user, message=message)
