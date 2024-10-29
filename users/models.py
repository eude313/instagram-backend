from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.conf import settings
import magic
from django.core.exceptions import ValidationError
import os
from django.db.models.signals import post_save
from django.dispatch import receiver


class CustomUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)

        if not user.profile_picture:
            user.profile_picture = settings.DEFAULT_PROFILE_PICTURE
        
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)

# user model
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    followers_count = models.PositiveIntegerField(default=0)
    following_count = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email
    
    def save(self, *args, **kwargs):
        if not self.profile_picture:
            self.profile_picture = settings.DEFAULT_PROFILE_PICTURE
        super(User, self).save(*args, **kwargs)

# profile model
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    website = models.URLField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    @property
    def profile_picture(self):
        return self.user.profile_picture
    
    # Signals to create or update user profile
    @receiver(post_save, sender=User)
    def create_user_profile(sender, instance, created, **kwargs):
        if created:
            Profile.objects.get_or_create(user=instance)

    @receiver(post_save, sender=User)
    def save_user_profile(sender, instance, **kwargs):
        instance.profile.save()

# Custom file type validation for Media uploads
def validate_file_type(value):
    ext = os.path.splitext(value.name)[1]  # Get the file extension
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.avi']
    if ext.lower() not in valid_extensions:
        raise ValidationError('Unsupported file extension.')

def media_upload_path(instance, filename):
    return f'user_{instance.user.id}/media/{filename}'

class Media(models.Model):
    IMAGE = 'image'
    VIDEO = 'video'
    MEDIA_TYPE_CHOICES = [
        (IMAGE, 'Image'),
        (VIDEO, 'Video'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    media_file = models.FileField(upload_to=media_upload_path, validators=[validate_file_type])
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        ext = os.path.splitext(self.media_file.name)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif']:
            self.media_type = Media.IMAGE
        elif ext in ['.mp4', '.mov', '.avi']:
            self.media_type = Media.VIDEO
        else:
            raise ValidationError('Unsupported file extension.')
        super(Media, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.media_type.capitalize()} uploaded by {self.user.username}"

# post model
class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    caption = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    media = models.ManyToManyField(Media, blank=True, related_name='post_media')
    tags = models.JSONField(default=list, blank=True)  # Store tag positions and usernames

    def __str__(self):
        return f"Post by {self.user.username} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# Reel model
class Reel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.FileField(upload_to='reels/')
    caption = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Reel by {self.user.username} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"


    def clean(self):
        super().clean()

        # Validate the file is a video
        mime = magic.Magic(mime=True)
        file_mime_type = mime.from_buffer(self.video.read())

        if not file_mime_type.startswith('video'):
            raise ValidationError("The uploaded file must be a video.")

# Save post model       
class SavedPost(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_posts')
    post = models.ForeignKey('Post', on_delete=models.CASCADE, null=True, blank=True)
    reel = models.ForeignKey('Reel', on_delete=models.CASCADE, null=True, blank=True)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['user', 'post'], ['user', 'reel']]

    def __str__(self):
        if self.post:
            return f"{self.user.username} saved post {self.post.id}"
        elif self.reel:
            return f"{self.user.username} saved reel {self.reel.id}"

# Story model
class Story(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    media = models.ManyToManyField(Media, blank=True, related_name='story_media')

    def __str__(self):
        return f"Story by {self.user.username} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"

#Chat model
class Chat(models.Model):
    CHAT_TYPES = (
        ('single', 'Single'),
        ('group', 'Group'),
    )
    
    type = models.CharField(max_length=6, choices=CHAT_TYPES, default='single')
    participants = models.ManyToManyField(User, related_name='chats')
    name = models.CharField(max_length=255, blank=True, null=True)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.type == 'single' and not self.name and self.participants.count() == 2:
            participant_usernames = "-".join([p.username for p in self.participants.all()])
            self.name = participant_usernames
        super().save(*args, **kwargs)

    def __str__(self):
        participants = self.participants.all()
        if self.type == 'single' and participants.count() == 2:
            return f"Chat between {participants[0].username} and {participants[1].username}"
        return f"Group: {self.name}" if self.name else "Unnamed Group"

    @property
    def last_message(self):
        return self.messages.order_by('-timestamp').first()

# Messages model
class Message(models.Model):
    MEDIA_TYPES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
    )
    
    chat = models.ForeignKey(Chat, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to='message_media/', blank=True, null=True)
    media_type = models.CharField(max_length=5, choices=MEDIA_TYPES, default='text')
    timestamp = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(User, related_name='read_messages', blank=True)

    def mark_as_read(self, user):
        self.read_by.add(user)
        self.save()

    def __str__(self):
        return f"Message in {self.chat} from {self.sender.username}"

# User status model
class UserStatus(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)

    def mark_online(self):
        self.is_online = True
        self.last_seen = timezone.now()
        self.save()

    def mark_offline(self):
        self.is_online = False
        self.last_seen = timezone.now()
        self.save()

    def update_last_seen(self):
        self.last_seen = timezone.now()
        self.save()

    @classmethod
    def get_or_create_user_status(cls, user):
        user_status, created = cls.objects.get_or_create(user=user)
        return user_status

    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else f'Last seen at {self.last_seen}'}"

# Comments model
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes_count = models.PositiveIntegerField(default=0)
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    def __str__(self):
        if self.post:
            return f"Comment by {self.user.username} on Post {self.post.id}"
        elif self.reel:
            return f"Comment by {self.user.username} on Reel {self.reel.id}"
        else:
            return f"Comment by {self.user.username}"

# Like model
class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['user', 'post'], ['user', 'reel'], ['user', 'comment']]

    def __str__(self):
        if self.post:
            return f"{self.user.username} likes post {self.post.id}"
        elif self.reel:
            return f"{self.user.username} likes reel {self.reel.id}"
        elif self.comment:
            return f"{self.user.username} likes comment {self.comment.id}"

# Follow and followers model
class Follow(models.Model):
    follower = models.ForeignKey(User, related_name='following', on_delete=models.CASCADE)
    followed = models.ForeignKey(User, related_name='followers', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'followed')

    def __str__(self):
        return f"{self.follower.username} follows {self.followed.username}"

# Notifications model
class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('like', 'Like'),
        ('comment', 'Comment'),
        ('follow', 'Follow'),
        ('message', 'Message'),
    )

    recipient = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        if self.notification_type == 'comment':
            return f"{self.sender.username} commented on your post/reel"



 