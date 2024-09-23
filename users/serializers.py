from rest_framework import serializers
from .models import User, Profile, Post, Story, Reel, Message, Follow, Like, Notification, Comment, MediaItem, StoryItem, UserStatus

from django.contrib.auth import authenticate


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'password', 'is_verified', 'is_staff')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if user and user.is_active:
            return {'user': user}
        raise serializers.ValidationError("Incorrect Credentials")

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

class SetNewPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = ['user', 'bio', 'website', 'phone_number', 'gender']

class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user', 'content', 'created_at', 'updated_at', 'likes_count', 'parent_comment']

    def validate_content(self, value):
        if len(value) > 500:
            raise serializers.ValidationError("Comment content cannot exceed 500 characters.")
        return value

class MediaItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaItem
        fields = ['id', 'file', 'media_type', 'order']
        

class PostSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    media_items = MediaItemSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ['id', 'user', 'caption', 'created_at', 'updated_at', 'likes_count', 'comments_count', 'comments', 'media_items']

    def validate_caption(self, value):
        if len(value) > 2200:
            raise serializers.ValidationError("Caption cannot exceed 2200 characters.")
        return value
    
class StoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoryItem
        fields = ['id', 'file', 'media_type', 'order']

class StorySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    media_items = StoryItemSerializer(many=True, read_only=True)

    class Meta:
        model = Story
        fields = ['id', 'user', 'created_at', 'expires_at', 'media_items']

class ReelSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Reel
        fields = ['id', 'user', 'video', 'caption', 'created_at', 'likes_count', 'comments_count', 'comments']


class UserStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserStatus
        fields = ['is_online', 'last_seen']

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    recipient = UserSerializer(read_only=True)
    sender_username = serializers.CharField(write_only=True)
    recipient_username = serializers.CharField(write_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'recipient', 'sender_username', 'recipient_username', 'content', 'media_type', 'file', 'timestamp', 'is_read', 'read_at']
        extra_kwargs = {'file': {'required': False}}

    def validate(self, data):
        if not data.get('content') and not data.get('file'):
            raise serializers.ValidationError("Either content or media file must be provided.")
        return data

    def create(self, validated_data):
        sender_username = validated_data.pop('sender_username')
        recipient_username = validated_data.pop('recipient_username')
        sender = User.objects.get(username=sender_username)
        recipient = User.objects.get(username=recipient_username)
        return Message.objects.create(sender=sender, recipient=recipient, **validated_data)

class FollowSerializer(serializers.ModelSerializer):
    follower = UserSerializer(read_only=True)
    followed = UserSerializer(read_only=True)

    class Meta:
        model = Follow
        fields = ['id', 'follower', 'followed', 'created_at']

class LikeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Like
        fields = ['id', 'user', 'post', 'reel', 'comment', 'created_at']

class NotificationSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)
    sender = UserSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'sender', 'notification_type', 'post', 'message', 'comment', 'timestamp', 'is_read']