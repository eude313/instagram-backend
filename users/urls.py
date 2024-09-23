from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, 
    LoginView,
    UserViewSet,
    ProfileViewSet,
    PostViewSet,
    StoryViewSet,
    ReelViewSet,
    MessageViewSet,
    FollowViewSet,
    LikeViewSet,
    NotificationViewSet,
    CommentViewSet,

    RegisterView, 
    LoginView, 
    LogoutView, 
    PasswordResetView, 
    PasswordResetConfirmView,
    ValidateTokenView
) 

router = DefaultRouter()

router.register(r'users', UserViewSet)
router.register(r'profiles', ProfileViewSet)
router.register(r'posts', PostViewSet)
router.register(r'stories', StoryViewSet, basename='story')
router.register(r'reels', ReelViewSet)
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'follows', FollowViewSet)
router.register(r'likes', LikeViewSet)
router.register(r'notifications', NotificationViewSet)
router.register(r'comments', CommentViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/password-reset/', PasswordResetView.as_view(), name='password_reset'),
    path('auth/password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('auth/validate-token/', ValidateTokenView.as_view(), name='validate_token'),
    path('users/search/', UserViewSet.as_view({'get': 'search'}), name='user-search'),
    path('posts/<int:pk>/save/', PostViewSet.as_view({'post': 'save_post'}), name='save-post'),
    path('posts/<int:pk>/unsave/', PostViewSet.as_view({'post': 'unsave_post'}), name='unsave-post'),
    path('reels/<int:pk>/save/', ReelViewSet.as_view({'post': 'save_reel'}), name='save-reel'),
    path('reels/<int:pk>/unsave/', ReelViewSet.as_view({'post': 'unsave_reel'}), name='unsave-reel'),
]