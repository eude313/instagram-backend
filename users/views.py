from django.db.models import Count, Prefetch, Q, F
from rest_framework import viewsets, permissions, status, generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    User, 
    Profile, 
    Post, 
    Story, 
    Reel,
    Message, 
    Follow, 
    Like, 
    Notification, 
    Comment, 
    SavedPost, 
    Chat, 
    UserStatus
)
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
    ChatSerializer, 
    UserStatusSerializer,

    
    LoginSerializer, 
    PasswordResetSerializer, 
    SetNewPasswordSerializer,
    ValidateTokenSerializer
)  
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import action
from .permissions import IsOwnerOrReadOnly, IsAdminUserOrReadOnly
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.pagination import PageNumberPagination

from users import serializers
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "user": UserSerializer(user, context={'request': request}).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

# LoginView: Handles user login and returns JWT tokens (refresh and access)
logger = logging.getLogger(__name__)

class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            serializer = LoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            user = serializer.validated_data['user']
            refresh = serializer.validated_data['refresh']
            access = serializer.validated_data['access']
            
            response = Response({
                'user': UserSerializer(user, context={'request': request}).data,
                'refresh': refresh,
                'access': access
            }, status=status.HTTP_200_OK)
            
            # Add CORS headers to the response
            response["Access-Control-Allow-Origin"] = "http://127.0.0.1:3000"
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            
            return response
            
        except serializers.ValidationError as e:
            logger.error(f"Login validation error: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in LoginView")
            return Response(
                {'error': 'An unexpected error occurred'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class ValidateTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'user': UserSerializer(request.user, context={'request': request}).data
        })
      
# class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            logger.exception("Logout error")
            return Response(
                {'error': 'Invalid token'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class LogoutView(APIView):
    permission_classes = []  

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                return Response({'error': 'Refresh token required'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            logger.exception("Logout error")
            return Response(
                {'error': 'Invalid token'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
             
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
        
    @action(detail=False, methods=['GET'])
    def suggestions(self, request):
        current_user = request.user
        page_size = 5
        show_all = request.query_params.get('show_all', 'false').lower() == 'true'
        
        # Get users who follow current user but aren't followed back
        users_following_me = User.objects.filter(
            following__followed=current_user
        ).exclude(
            followers__follower=current_user
        )
        
        # Get followers of users that current user follows
        followed_users_followers = User.objects.filter(
            following__followed__in=Follow.objects.filter(
                follower=current_user
            ).values_list('followed', flat=True)
        ).exclude(
            id__in=Follow.objects.filter(
                follower=current_user
            ).values_list('followed', flat=True)
        ).exclude(id=current_user.id)
        
        # Combine and remove duplicates
        suggested_users = users_following_me.union(
            followed_users_followers
        )
        
        # If no suggestions found based on connections, get random users
        if not suggested_users.exists():
            suggested_users = User.objects.exclude(
                id=current_user.id
            ).exclude(
                id__in=Follow.objects.filter(
                    follower=current_user
                ).values_list('followed', flat=True)
            ).filter(
                is_active=True
            ).order_by('?')  # Random ordering
        else:
            suggested_users = suggested_users.order_by('?')
        
        # Add additional filters to get more relevant random users
        suggested_users = suggested_users.annotate(
            followers_count=Count('followers'),
            posts_count=Count('post')
        ).filter(
            is_active=True
        ).order_by(
            '-followers_count',  # Prioritize users with more followers
            '-posts_count',      # Then users with more posts
            '?'                  # Finally, add some randomness
        )
        
        # Limit to 10 users if show_all is True, otherwise use pagination
        if show_all:
            suggested_users = suggested_users[:10]
            serializer = UserSerializer(suggested_users, many=True, context={'request': request})
            return Response(serializer.data)
        else:
            paginator = PageNumberPagination()
            paginator.page_size = page_size
            paginated_users = paginator.paginate_queryset(suggested_users, request)
            serializer = UserSerializer(paginated_users, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def random_users(self, request):
        """
        Get a list of random users excluding the current user and those already followed.
        This is used as a fallback when there are no connection-based suggestions.
        """
        current_user = request.user
        limit = int(request.query_params.get('limit', 5))
        
        random_users = User.objects.exclude(
            Q(id=current_user.id) |
            Q(id__in=Follow.objects.filter(follower=current_user).values_list('followed', flat=True))
        ).annotate(
            followers_count=Count('followers'),
            posts_count=Count('post')
        ).filter(
            is_active=True
        ).order_by(
            '-followers_count',
            '-posts_count',
            '?'
        )[:limit]
        
        serializer = UserSerializer(random_users, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['GET'])
    def hover_details(self, request, pk=None):
        try:
            user = self.get_object()
            current_user = request.user
            
            # Get the user's profile
            profile = Profile.objects.get(user=user)
            
            # Get follow relationship information
            is_followed = Follow.objects.filter(follower=current_user, followed=user).exists()
            follows_you = Follow.objects.filter(follower=user, followed=current_user).exists()
            
            # Get follower and following counts
            followers_count = Follow.objects.filter(followed=user).count()
            following_count = Follow.objects.filter(follower=user).count()
            
            # Get latest posts with media
            latest_posts = Post.objects.filter(user=user).prefetch_related('media').order_by('-created_at')[:3]
            
            response_data = {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'profile_picture': request.build_absolute_uri(user.profile_picture.url) if user.profile_picture else None,
                    'is_verified': user.is_verified,
                    'is_staff': user.is_staff,
                    'bio': profile.bio if profile else None,
                    'is_followed': is_followed,
                    'follows_you': follows_you
                },
                'stats': {
                    'posts_count': Post.objects.filter(user=user).count(),
                    'followers_count': followers_count,
                    'following_count': following_count,
                },
                'latest_posts': [{
                    'id': post.id,
                    'media': [{
                        'media_type': media.media_type,
                        'media_file': request.build_absolute_uri(media.media_file.url)
                    } for media in post.media.all()]
                } for post in latest_posts]
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
   
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

class PostPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    max_page_size = 100

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all().order_by('-created_at')
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = PostPagination   
    
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

# class ChatViewSet(viewsets.ModelViewSet):
#     serializer_class = ChatSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         return Chat.objects.filter(participants=self.request.user)

#     @action(detail=False, methods=['POST'])
#     def create_or_get(self, request): 
#         participants = request.data.get('participants', [])
#         chat_type = request.data.get('type', 'single')
#         name = request.data.get('name')

#         # Add some debugging prints
#         print(f"Received request data: {request.data}")
#         print(f"Participants: {participants}")
#         print(f"Chat type: {chat_type}")
#         print(f"Name: {name}")

#         if not participants:
#             return Response(
#                 {"error": "Participants list cannot be empty"}, 
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if chat_type == 'single' and len(participants) != 2:
#             return Response(
#                 {"error": "Single chat must have exactly 2 participants"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             if chat_type == 'single':
#                 # Check if chat already exists
#                 existing_chat = Chat.objects.filter(
#                     type='single',
#                     participants__id__in=participants  # Modified this line
#                 ).annotate(
#                     participant_count=Count('participants')
#                 ).filter(participant_count=len(participants))

#                 if existing_chat.exists():
#                     return Response(
#                         self.get_serializer(existing_chat.first()).data
#                     )

#             # Create new chat
#             chat = Chat.objects.create(type=chat_type, name=name)
#             chat.participants.set(participants)
#             return Response(
#                 self.get_serializer(chat).data,
#                 status=status.HTTP_201_CREATED
#             )
#         except Exception as e:  # Catch all exceptions for now (refine later)
#             print(f"Error creating chat: {e}")
#             return Response(
#                 {"error": "An error occurred while creating the chat."},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

class ChatViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Optimize the queryset with select_related and prefetch_related
        return Chat.objects.filter(
            participants=self.request.user
        ).prefetch_related(
            'participants',
            Prefetch(
                'messages',
                queryset=Message.objects.order_by('-timestamp')[:1],
                to_attr='latest_message'
            )
        ).order_by('-updated_at')

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in ChatViewSet.list: {str(e)}")
            return Response(
                {"error": "Failed to retrieve chats"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['POST'])
    def create_or_get(self, request):
        try:
            participants = request.data.get('participants', [])
            chat_type = request.data.get('type', 'single')
            name = request.data.get('name')

            # Validate participants and chat type
            if not participants:
                return Response(
                    {"error": "Participants list cannot be empty"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Convert participants to integers and remove duplicates
            participants = list(set(map(int, participants)))
            
            # Validate participant existence
            existing_users = User.objects.filter(id__in=participants).count()
            if existing_users != len(participants):
                return Response(
                    {"error": "One or more participants do not exist"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if chat_type == 'single':
                if len(participants) != 2:
                    return Response(
                        {"error": "Single chat must have exactly 2 participants"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Find existing single chat
                existing_chat = Chat.objects.filter(
                    type='single',
                    participants__id__in=participants
                ).annotate(
                    participant_count=Count('participants')
                ).filter(participant_count=2)
                
                for chat in existing_chat:
                    # Check if this chat has exactly these participants
                    chat_participants = set(chat.participants.values_list('id', flat=True))
                    if chat_participants == set(participants):
                        return Response(self.get_serializer(chat).data)

                # Create new chat if none exists
                user1 = User.objects.get(id=participants[0])
                user2 = User.objects.get(id=participants[1])
                name = f"{user1.username}-{user2.username}"

            # Create new chat
            chat = Chat.objects.create(type=chat_type, name=name)
            chat.participants.set(participants)
            chat.save()

            return Response(
                self.get_serializer(chat).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in create_or_get: {str(e)}")
            return Response(
                {"error": "An error occurred while creating the chat.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# class ChatViewSet(viewsets.ModelViewSet):
#     serializer_class = ChatSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         return Chat.objects.filter(participants=self.request.user)

#     @action(detail=False, methods=['POST'])
#     def create_or_get(self, request): 
#         participants = request.data.get('participants', [])
#         chat_type = request.data.get('type', 'single')
#         name = request.data.get('name')

#         # Validate participants and chat type
#         if not participants:
#             return Response({"error": "Participants list cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)
        
#         unique_participants = list(set(participants))
#         if len(unique_participants) != len(participants):
#             return Response({"error": "Duplicate participants are not allowed"}, status=status.HTTP_400_BAD_REQUEST)

#         if chat_type == 'single' and (len(participants) != 2 or participants[0] == participants[1]):
#             return Response({"error": "Single chat must have exactly 2 unique participants"}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             # Check if a single chat between these participants already exists
#             if chat_type == 'single':
#                 participant1, participant2 = participants
#                 existing_chat = Chat.objects.filter(
#                     type='single',
#                     participants__id=participant1
#                 ).filter(
#                     participants__id=participant2
#                 ).annotate(
#                     num_participants=Count('participants')
#                 ).filter(num_participants=2).first()

#                 if existing_chat:
#                     return Response(self.get_serializer(existing_chat).data)

#                 # If no existing chat found, create a new one with a name based on participants
#                 name = f"{User.objects.get(id=participant1).username}-{User.objects.get(id=participant2).username}"

#             # Create the new chat
#             chat = Chat.objects.create(type=chat_type, name=name)
#             chat.participants.set(participants)

#             return Response(self.get_serializer(chat).data, status=status.HTTP_201_CREATED)

#         except Exception as e:
#             return Response({"error": "An error occurred while creating the chat.", "detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # @action(detail=False, methods=['POST'])
    # def create_or_get(self, request): 
    #     participants = request.data.get('participants', [])
    #     chat_type = request.data.get('type', 'single')
    #     name = request.data.get('name')

    #     # Add some debugging prints
    #     print(f"Received request data: {request.data}")
    #     print(f"Participants: {participants}")
    #     print(f"Chat type: {chat_type}")
    #     print(f"Name: {name}")

    #     # Validate participants
    #     if not participants:
    #         return Response(
    #             {"error": "Participants list cannot be empty"}, 
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     # Remove duplicates and validate participants
    #     unique_participants = list(set(participants))
    #     if len(unique_participants) != len(participants):
    #         return Response(
    #             {"error": "Duplicate participants are not allowed"},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     # Validate single chat requirements
    #     if chat_type == 'single':
    #         if len(participants) != 2:
    #             return Response(
    #                 {"error": "Single chat must have exactly 2 participants"},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )
    #         if participants[0] == participants[1]:
    #             return Response(
    #                 {"error": "Cannot create a chat with yourself"},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )

    #     try:
    #         if chat_type == 'single':
    #             # Find chats that contain both participants
    #             participant1, participant2 = participants
    #             existing_chat = Chat.objects.filter(
    #                 type='single',
    #                 participants__id=participant1
    #             ).filter(
    #                 participants__id=participant2
    #             ).annotate(
    #                 num_participants=Count('participants')
    #             ).filter(num_participants=2).first()

    #             if existing_chat:
    #                 return Response(
    #                     self.get_serializer(existing_chat).data
    #                 )

    #         # If no existing chat found, create new chat
    #         chat = Chat.objects.create(type=chat_type, name=name)
    #         chat.participants.set(participants)
            
    #         return Response(
    #             self.get_serializer(chat).data,
    #             status=status.HTTP_201_CREATED
    #         )

    #     except Exception as e:
    #         print(f"Error creating chat: {str(e)}")
    #         return Response(
    #             {
    #                 "error": "An error occurred while creating the chat.",
    #                 "detail": str(e)
    #             },
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )

class UserStatusViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserStatusSerializer
    
    def get_queryset(self):
        return UserStatus.objects.all()

    @action(detail=False, methods=['post'])
    def update_status(self, request):
        """
        Updates user's online status and last seen
        """
        user_status = UserStatus.get_or_create_user_status(request.user)
        status_type = request.data.get('status', 'online')

        if status_type == 'online':
            user_status.mark_online()
        else:
            user_status.mark_offline()

        self._notify_status_change(user_status)
        
        serializer = self.get_serializer(user_status)
        return Response(serializer.data)

    def _notify_status_change(self, user_status):
        """
        Notifies relevant users about status change
        """
        channel_layer = get_channel_layer()
        status_data = self.get_serializer(user_status).data
        
        # Notify users who have an active chat with this user
        chats = Chat.objects.filter(participants=user_status.user)
        for chat in chats:
            for participant in chat.participants.all():
                if participant != user_status.user:
                    async_to_sync(channel_layer.group_send)(
                        f"user_{participant.id}",
                        {
                            "type": "user.status",
                            "status": status_data
                        }
                    )

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