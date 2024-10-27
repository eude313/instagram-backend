from rest_framework import serializers
from .models import User, Profile, Post, Story, Reel, Message, Follow, Like, Notification, Comment, Media, UserStatus
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken, TokenError
from django.utils import timezone


class UserSerializer(serializers.ModelSerializer):
    has_story = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'username', 'password', 'is_verified', 'is_staff', 'has_story', 'profile_picture')
        extra_kwargs = {'password': {'write_only': True}}

    def get_has_story(self, obj):
        return Story.objects.filter(user=obj, expires_at__gt=timezone.now()).exists()

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def get_profile_picture(self, obj):
        if obj.profile_picture:
            return self.context.get('request').build_absolute_uri(obj.profile_picture.url)
        return self.context.get('request').build_absolute_uri(settings.MEDIA_URL + settings.DEFAULT_PROFILE_PICTURE)

# LoginSerializer: Authenticates the user based on email and password
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if user and user.is_active:
            refresh = RefreshToken.for_user(user)
            return {
                'user': user,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        raise serializers.ValidationError("Incorrect Credentials")

# ValidateTokenSerializer: Validates the token and returns the user if valid
class ValidateTokenSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, value):
        try:
            AccessToken(value)
        except TokenError:
            raise serializers.ValidationError("Invalid token")
        return value

    def validate(self, attrs):
        token = attrs.get('token')
        try:
            access_token = AccessToken(token)
            user = User.objects.get(id=access_token['user_id'])
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return attrs

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

class SetNewPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    is_staff = serializers.BooleanField(source='user.is_staff', read_only=True)
    is_verified = serializers.BooleanField(source='user.is_verified', read_only=True)
    has_story = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ['username', 'email', 'first_name', 'last_name', 'bio', 'website', 'phone_number', 'gender', 'profile_picture', 'is_staff', 'is_verified', 'has_story']
        read_only_fields = ['username', 'email', 'is_staff', 'is_verified']


    def get_has_story(self, obj):
        return Story.objects.filter(user=obj.user, expires_at__gt=timezone.now()).exists()

    def get_profile_picture(self, obj):
        if obj.user.profile_picture:
            return self.context['request'].build_absolute_uri(obj.user.profile_picture.url)
        return self.context['request'].build_absolute_uri(settings.MEDIA_URL + settings.DEFAULT_PROFILE_PICTURE)

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user

        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        return super().update(instance, validated_data)

class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'user', 'content', 'created_at', 'updated_at', 'likes_count', 'parent_comment']

    def validate_content(self, value):
        if len(value) > 500:
            raise serializers.ValidationError("Comment content cannot exceed 500 characters.")
        return value

class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = ['id', 'media_file', 'media_type']
        
    def validate_media_file(self, value):
        if value.size > 10 * 1024 * 1024:  # 10MB limit
            raise serializers.ValidationError("File size too large. Max size is 10MB.")
        return value
   
class PostSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    latest_comment = serializers.SerializerMethodField()
    media = MediaSerializer(many=True, read_only=False)

    class Meta:
        model = Post
        fields = ['id', 'user', 'caption', 'created_at', 'updated_at', 'likes_count', 'comments_count', 'comments', 'latest_comment', 'media']

    def get_latest_comment(self, obj):
        latest_comment = obj.comments.order_by('-created_at').first()
        if latest_comment:
            return CommentSerializer(latest_comment).data
        return None
    
    def validate_caption(self, value):
        if len(value) > 2200:
            raise serializers.ValidationError("Caption cannot exceed 2200 characters.")
        return value
    
class LikeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Like
        fields = ['id', 'user', 'post', 'reel', 'comment', 'created_at']

class StorySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    media = MediaSerializer(many=True, read_only=False)

    class Meta:
        model = Story
        fields = ['id', 'user', 'created_at', 'expires_at', 'media']

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

class NotificationSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)
    sender = UserSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'sender', 'notification_type', 'post', 'message', 'comment', 'timestamp', 'is_read']