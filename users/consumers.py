import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message, UserStatus, User
from django.utils import timezone
from .serializers import MessageSerializer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.user_group_name = f"user_{self.user.id}"

        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        await self.accept()

        await self.update_user_status(True)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )

        await self.update_user_status(False)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')

        if message_type == 'chat.message':
            await self.handle_chat_message(text_data_json)
        elif message_type == 'message.read':
            await self.handle_message_read(text_data_json)

    async def chat_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'chat.message',
            'message': message
        }))

    async def message_read(self, event):
        message_id = event['message_id']
        await self.send(text_data=json.dumps({
            'type': 'message.read',
            'message_id': message_id
        }))

    @database_sync_to_async
    def update_user_status(self, is_online):
        user_status = UserStatus.get_or_create_user_status(self.user)
        if is_online:
            user_status.mark_online()
        else:
            user_status.mark_offline()

    @database_sync_to_async
    def handle_chat_message(self, data):
        sender = self.scope["user"]
        recipient_username = data.get('recipient')
        content = data.get('content')
        
        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            return
        
        message = Message.objects.create(
            sender=sender,
            recipient=recipient,
            content=content
        )
        
        serializer = MessageSerializer(message)
        return serializer.data

    @database_sync_to_async
    def handle_message_read(self, data):
        message_id = data.get('message_id')
        try:
            message = Message.objects.get(id=message_id, recipient=self.user)
            message.mark_as_read()
        except Message.DoesNotExist:
            pass