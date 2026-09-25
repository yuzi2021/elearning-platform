"""End-to-end ASGI tests for course-scoped WebSocket behavior."""
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.test import Client, TransactionTestCase, override_settings

from config.asgi import application
from .models import ChatMessage, Enrollment
from .tests import make_course, make_student, make_teacher


IN_MEMORY_CHANNEL_LAYER = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}
}


@override_settings(CHANNEL_LAYERS=IN_MEMORY_CHANNEL_LAYER)
class ChatConsumerTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.teacher = make_teacher('socket-teacher')
        self.student = make_student('socket-student')
        self.other_student = make_student('socket-outsider')
        self.course = make_course(self.teacher, title='Realtime Systems')
        Enrollment.objects.create(course=self.course, student=self.student)

    def cookie_headers(self, user):
        client = Client()
        client.force_login(user)
        session = client.cookies[settings.SESSION_COOKIE_NAME].value
        return [(b'cookie', f'{settings.SESSION_COOKIE_NAME}={session}'.encode())]

    def test_anonymous_connection_is_rejected(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                application, f'/ws/chat/{self.course.pk}/'
            )
            connected, close_code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(close_code, 4401)

        async_to_sync(scenario)()

    def test_unenrolled_learner_connection_is_rejected(self):
        headers = self.cookie_headers(self.other_student)

        async def scenario():
            communicator = WebsocketCommunicator(
                application, f'/ws/chat/{self.course.pk}/', headers=headers
            )
            connected, close_code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(close_code, 4403)

        async_to_sync(scenario)()

    def test_enrolled_learner_message_is_persisted_and_broadcast(self):
        headers = self.cookie_headers(self.student)

        async def scenario():
            communicator = WebsocketCommunicator(
                application, f'/ws/chat/{self.course.pk}/', headers=headers
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({'message': 'A focused course question'})
            event = await communicator.receive_json_from()
            self.assertEqual(event['type'], 'chat')
            self.assertEqual(event['message'], 'A focused course question')
            await communicator.disconnect()

        async_to_sync(scenario)()
        message = ChatMessage.objects.get(course=self.course)
        self.assertEqual(message.sender, self.student)

    def test_malformed_message_returns_controlled_error(self):
        headers = self.cookie_headers(self.student)

        async def scenario():
            communicator = WebsocketCommunicator(
                application, f'/ws/chat/{self.course.pk}/', headers=headers
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_to(text_data='not-json')
            event = await communicator.receive_json_from()
            self.assertEqual(event['type'], 'error')
            await communicator.disconnect()

        async_to_sync(scenario)()
