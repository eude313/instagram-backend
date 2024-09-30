from django.contrib import admin
from .models import User, Profile, Post, Story, Reel, Message, Follow, Like, Notification, Comment, Media, UserStatus, SavedPost

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'gender', 'phone_number')
    search_fields = ('user__username', 'phone_number')

@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'uploaded_at']
    list_filter = ['media_type', 'uploaded_at']
    search_fields = ['user__username', 'media_file']

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['user', 'caption', 'created_at', 'likes_count', 'comments_count']
    list_filter = ['created_at']
    search_fields = ['user__username', 'caption']

@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'expires_at']
    list_filter = ['created_at', 'expires_at']
    search_fields = ['user__username']

@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = ['user', 'caption', 'created_at', 'likes_count', 'comments_count']
    list_filter = ['created_at']
    search_fields = ['user__username']

@admin.register(SavedPost)
class SavedPostAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'reel', 'saved_at']
    search_fields = ['user__username', 'post__id', 'reel__id']
    
@admin.register(UserStatus)
class UserStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_online', 'last_seen')
    list_filter = ('is_online',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('last_seen',)

    def get_readonly_fields(self, request, obj=None):
        if obj: 
            return self.readonly_fields + ('user',)
        return self.readonly_fields

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'timestamp', 'is_read')
    search_fields = ('sender__username', 'recipient__username', 'content')

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('follower', 'followed', 'created_at')
    search_fields = ('follower__username', 'followed__username')

@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_type', 'created_at')
    search_fields = ('user__username',)

    def content_type(self, obj):
        if obj.post:
            return 'Post'
        elif obj.reel:
            return 'Reel'
        elif obj.comment:
            return 'Comment'
        return 'Unknown'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'sender', 'notification_type', 'timestamp', 'is_read')
    search_fields = ('recipient__username', 'sender__username')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_type', 'created_at', 'likes_count')
    search_fields = ('user__username', 'content')

    def content_type(self, obj):
        if obj.post:
            return 'Post'
        elif obj.reel:
            return 'Reel'
        return 'Unknown'
