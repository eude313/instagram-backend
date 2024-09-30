from rest_framework import viewsets, permissions, status, generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import User, Profile, Post, Story, Reel, Message, Follow, Like, Notification, Comment, SavedPost
from rest_framework.response import Response
from .serializers import (
    UserSerializer, 
    ProfileSerializer, 
    PostSerializer, 
    StorySerializer,              
    ReelSerializer, 
    MessageSerializer, 
    FollowSerializer, 
    LikeSerializer, 
    NotificationSerializer, 
    CommentSerializer, 

    LoginSerializer, 
    PasswordResetSerializer, 
    SetNewPasswordSerializer
)
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import action
from .permissions import IsOwnerOrReadOnly, IsAdminUserOrReadOnly
from django.db.models import Q
from django.db.models import F
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "user": UserSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            })
        else:
            return Response(
                {"detail": serializer.errors.get('non_field_errors', "Invalid login credentials.")},
                status=status.HTTP_400_BAD_REQUEST
            )
    
class ValidateTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"valid": True})

class LogoutView(APIView):
    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)

class PasswordResetView(generics.GenericAPIView):
    serializer_class = PasswordResetSerializer
    permission_classes = []

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"
            send_mail(
                'Password Reset',
                f'Click the following link to reset your password: {reset_url}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        return Response({"detail": "Password reset email has been sent."}, status=status.HTTP_200_OK)

class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = SetNewPasswordSerializer
    permission_classes = []

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        uid = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"detail": "Invalid reset link"}, status=status.HTTP_400_BAD_REQUEST)
        
        if default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            return Response({"detail": "Password has been reset successfully."}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Invalid reset link"}, status=status.HTTP_400_BAD_REQUEST)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUserOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'first_name']

    @action(detail=False, methods=['GET'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            users = self.queryset.filter(
                Q(username__icontains=query) |
                Q(email__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            ).distinct()[:20]  
        else:
            users = User.objects.none()
        
        serializer = self.get_serializer(users, many=True)
        return Response(serializer.data)

class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=['GET', 'PATCH'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        profile = request.user.profile
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        elif request.method == 'PATCH':
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['DELETE'], permission_classes=[permissions.IsAuthenticated])
    def remove_profile_picture(self, request):
        profile = request.user.profile
        if profile.profile_picture:
            profile.profile_picture.delete()
            profile.profile_picture = None
            profile.save()
            return Response({"message": "Profile picture removed successfully"}, status=status.HTTP_204_NO_CONTENT)
        return Response({"error": "No profile picture to remove"}, status=status.HTTP_400_BAD_REQUEST)

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all().order_by('-created_at')
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"detail": "You do not have permission to delete this post."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['POST'])
    def like(self, request, pk=None):
        post = self.get_object()
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if created:
            post.likes_count = F('likes_count') + 1
            post.save()
            return Response({"detail": "Post liked."}, status=status.HTTP_201_CREATED)
        return Response({"detail": "Post already liked."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'])
    def unlike(self, request, pk=None):
        post = self.get_object()
        deleted, _ = Like.objects.filter(user=request.user, post=post).delete()
        if deleted:
            post.likes_count = F('likes_count') - 1
            post.save()
            return Response({"detail": "Post unliked."}, status=status.HTTP_200_OK)
        return Response({"detail": "Post was not liked."}, status=status.HTTP_400_BAD_REQUEST)

    
    @action(detail=True, methods=['POST'])
    def add_comment(self, request, pk=None):
        post = self.get_object()
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user, post=post)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['POST'])
    def save_post(self, request, pk=None):
        post = self.get_object()
        saved_post, created = SavedPost.objects.get_or_create(user=request.user, post=post)
        if created:
            return Response({"detail": "Post saved."}, status=status.HTTP_201_CREATED)
        return Response({"detail": "Post already saved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'])
    def unsave_post(self, request, pk=None):
        post = self.get_object()
        deleted, _ = SavedPost.objects.filter(user=request.user, post=post).delete()
        if deleted:
            return Response({"detail": "Post unsaved."}, status=status.HTTP_200_OK)
        return Response({"detail": "Post was not saved."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['GET'])
    def get_share_link(self, request, pk=None):
        post = self.get_object()
        share_link = f"{request.scheme}://{request.get_host()}/posts/{post.id}/"
        return Response({"share_link": share_link}, status=status.HTTP_200_OK)

class StoryViewSet(viewsets.ModelViewSet):
    queryset = Story.objects.all().order_by('-created_at')
    serializer_class = StorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        following = Follow.objects.filter(follower=user).values_list('followed', flat=True)
        return Story.objects.filter(user__in=following, expires_at__gt=timezone.now()).order_by('-created_at')

    @action(detail=False, methods=['GET'])
    def following_stories(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        story = serializer.save(user=self.request.user)
        story_items_data = self.request.data.get('story_items', [])
        for item_data in story_items_data:
            StoryItem.objects.create(story=story, **item_data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"detail": "You do not have permission to update this story."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"detail": "You do not have permission to delete this story."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['GET'])
    def my_stories(self, request):
        stories = Story.objects.filter(user=request.user).order_by('-created_at')
        serializer = self.get_serializer(stories, many=True)
        return Response(serializer.data)

class ReelViewSet(viewsets.ModelViewSet):
    queryset = Reel.objects.all().order_by('-created_at')
    serializer_class = ReelSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['POST'])
    def save_reel(self, request, pk=None):
        reel = self.get_object()
        saved_reel, created = SavedPost.objects.get_or_create(user=request.user, reel=reel)
        if created:
            return Response({"detail": "Reel saved."}, status=status.HTTP_201_CREATED)
        return Response({"detail": "Reel already saved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'])
    def unsave_reel(self, request, pk=None):
        reel = self.get_object()
        deleted, _ = SavedPost.objects.filter(user=request.user, reel=reel).delete()
        if deleted:
            return Response({"detail": "Reel unsaved."}, status=status.HTTP_200_OK)
        return Response({"detail": "Reel was not saved."}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['POST'])
    def like(self, request, pk=None):
        reel = self.get_object()
        like, created = Like.objects.get_or_create(user=request.user, reel=reel)
        if created:
            reel.likes_count = F('likes_count') + 1
            reel.save()
            return Response({"detail": "Reel liked."}, status=status.HTTP_201_CREATED)
        return Response({"detail": "Reel already liked."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'])
    def unlike(self, request, pk=None):
        reel = self.get_object()
        deleted, _ = Like.objects.filter(user=request.user, reel=reel).delete()
        if deleted:
            reel.likes_count = F('likes_count') - 1
            reel.save()
            return Response({"detail": "Reel unliked."}, status=status.HTTP_200_OK)
        return Response({"detail": "Reel was not liked."}, status=status.HTTP_400_BAD_REQUEST)

class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(sender=user) | Q(recipient=user))

    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)
        self.send_message_notification(message)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().order_by('-timestamp')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user == instance.recipient:
            instance.mark_as_read()
            self.send_read_notification(instance)
            return Response(self.get_serializer(instance).data)
        return Response({"error": "You do not have permission to mark this message as read."}, status=status.HTTP_403_FORBIDDEN)

    def create(self, request, *args, **kwargs):
        media_file = request.FILES.get('file')
        media_type = request.data.get('media_type')

        if not request.data.get('content') and not media_file:
            return Response(
                {"error": "Either content or a media file must be provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if media_file and media_type not in ['image', 'video', 'audio']:
            return Response({"error": "Invalid media type."}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    def send_message_notification(self, message):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{message.recipient.id}",
            {
                "type": "chat.message",
                "message": MessageSerializer(message).data
            }
        )

    def send_read_notification(self, message):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{message.sender.id}",
            {
                "type": "message.read",
                "message_id": message.id
            }
        )
        
class FollowViewSet(viewsets.ModelViewSet):
    queryset = Follow.objects.all()
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['follower__username', 'followed__username'] 
    search_fields = ['follower__username', 'followed__username']

    def get_queryset(self):
        """
        Optionally restricts the returned follows to those related to the current user.
        """
        user = self.request.user
        return Follow.objects.filter(follower=user) 

class LikeViewSet(viewsets.ModelViewSet):
    queryset = Like.objects.all()
    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]