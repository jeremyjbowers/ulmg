import datetime
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
from django.middleware.csrf import get_token

from ulmg import models, utils

logger = logging.getLogger(__name__)


def magic_login_request(request):
    """
    View to handle both password and magic link authentication.
    """
    if request.method == 'POST':
        # Log CSRF debugging info
        csrf_token_from_request = request.POST.get('csrfmiddlewaretoken', 'NOT_PROVIDED')
        csrf_token_from_session = get_token(request)
        logger.info(f"CSRF Debug - Token from request: {csrf_token_from_request[:10]}..., Token from session: {csrf_token_from_session[:10]}...")
        
        password = request.POST.get('password', '')
        login_method = request.POST.get('login_method', 'password')
        

        
        # Handle password authentication
        if login_method == 'password' and password:
            # Simple username/password authentication
            username = request.POST.get('username', '').strip()
            if not username:
                messages.error(request, 'Please enter your username.')
                return render(request, 'registration/login.html')
            
            authenticated_user = authenticate(request, username=username, password=password)
            if authenticated_user:
                login(request, authenticated_user)
                messages.success(request, 'You have been logged in successfully!')
                next_url = request.POST.get('next', '').strip()
                if not next_url:
                    next_url = '/'
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password.')
                return render(request, 'registration/login.html')
        
        # Handle magic link authentication
        elif login_method == 'magic_link':
            email = request.POST.get('email', '').strip().lower()
            if not email:
                messages.error(request, 'Please enter your email address.')
                return render(request, 'registration/login.html')
            
            try:
                # First try to find user by email field
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Then try to find owner by email and get associated user
                try:
                    owner = models.Owner.objects.get(email=email)
                    user = owner.user
                except models.Owner.DoesNotExist:
                    # Don't reveal whether email exists or not for security
                    messages.success(
                        request, 
                        'If that email address is in our system, you will receive a magic link shortly.'
                    )
                    return render(request, 'registration/login.html')
            
            # Create magic link token
            magic_link = models.MagicLinkToken.create_for_user(user)
            
            # Build magic link URL
            magic_url = request.build_absolute_uri(
                reverse('magic_login_verify', kwargs={'token': magic_link.token})
            )
            
            # Send email
            email_result = utils.send_email(
                from_email="ULMG <noreply@theulmg.com>",
                to_emails=[email],
                subject="Your ULMG Magic Link",
                text=f"""
Hi there,

Click the link below to log in to ULMG. This link will work for 60 days.

{magic_url}

If you didn't request this, you can safely ignore this email.

Thanks,
The ULMG Team
                """.strip()
            )
            
            messages.success(
                request, 
                'If that email address is in our system, you will receive a magic link shortly.'
            )
            
            return render(request, 'registration/login.html')
        
        else:
            messages.error(request, 'Please enter your username and password or request a magic link.')
            return render(request, 'registration/login.html')
    
    return render(request, 'registration/login.html')


def admin_login_view(request):
    """
    Custom admin login view that handles both password and magic link authentication.
    """
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if username and password:
            # Simple username/password authentication
            authenticated_user = authenticate(request, username=username, password=password)
            if authenticated_user and authenticated_user.is_staff:
                login(request, authenticated_user)
                messages.success(request, 'You have been logged in successfully!')
                
                # Redirect to the admin index or the 'next' parameter
                next_url = request.POST.get('next', '').strip() or request.GET.get('next', '').strip() or '/admin/'
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please enter both username and password.')
    
    # For GET requests or failed authentication, show the login form
    context = {
        'title': 'Log in',
        'app_path': request.get_full_path(),
        'username': request.user.get_username(),
    }
    
    return render(request, 'admin/login.html', context)


def magic_login_verify(request, token):
    """
    View to verify a magic link token and log the user in.
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    is_mobile = any(mobile_ua in user_agent.lower() for mobile_ua in ['mobile', 'iphone', 'android', 'ipad'])
    
    logger.info(f"Magic link verification attempt - Token: {token[:10]}..., Mobile: {is_mobile}, User Agent: {user_agent[:50]}...")
    
    # Log all GET parameters for debugging
    logger.info(f"GET parameters: {dict(request.GET)}")
    
    user = models.MagicLinkToken.authenticate(token)
    
    if user:
        login(request, user)
        messages.success(request, 'You have been logged in successfully!')
        
        # Redirect to 'next' parameter if provided, otherwise to home
        next_url = request.GET.get('next', '').strip()
        if not next_url:
            next_url = '/'
        logger.info(f"Successful login - User: {user.username}, Next URL: {next_url}, Mobile: {is_mobile}, Token: {token[:10]}...")
        return redirect(next_url)
    else:
        logger.warning(f"Failed login attempt - Token: {token[:10]}..., Mobile: {is_mobile}, User Agent: {user_agent[:100]}...")
        messages.error(
            request, 
            'This magic link is invalid or has expired. Please request a new one.'
        )
        return redirect('login')


@csrf_exempt
@require_http_methods(["POST"])
def admin_magic_login_request(request):
    """
    API endpoint for admin to request magic links for themselves.
    This replaces the standard admin login.
    """
    email = request.POST.get('email', '').strip().lower()
    
    if not email:
        return JsonResponse({'error': 'Email is required'}, status=400)
    
    try:
        # First try to find user by email field
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Then try to find owner by email and get associated user
        try:
            owner = models.Owner.objects.get(email=email)
            user = owner.user
        except models.Owner.DoesNotExist:
            # Don't reveal whether email exists or not
            return JsonResponse({'message': 'If that email is in our system, you will receive a magic link.'})
    
    # Only allow staff users to use admin magic login
    if not user.is_staff:
        return JsonResponse({'message': 'If that email is in our system, you will receive a magic link.'})
    
    # Create magic link token
    magic_link = models.MagicLinkToken.create_for_user(user)
    
    # Build magic link URL for admin
    magic_url = request.build_absolute_uri(
        reverse('admin_magic_login_verify', kwargs={'token': magic_link.token})
    )
    
    # Send email
    utils.send_email(
        from_email="ULMG Admin <admin@theulmg.com>",
        to_emails=[email],
        subject="Your ULMG Admin Magic Link",
        text=f"""
Hi {user.first_name or user.username},

Click the link below to log in to the ULMG admin. This link will work for 60 days.

{magic_url}

If you didn't request this, please contact the admin immediately.

Thanks,
The ULMG System
        """.strip()
    )
    
    return JsonResponse({'message': 'If that email is in our system, you will receive a magic link.'})


def admin_magic_login_verify(request, token):
    """
    View to verify a magic link token for admin and log the user in.
    """
    user = models.MagicLinkToken.authenticate(token)
    
    if user and user.is_staff:
        login(request, user)
        messages.success(request, 'You have been logged in to the admin successfully!')
        return redirect('/admin/')
    else:
        messages.error(
            request, 
            'This admin magic link is invalid, has expired, or you do not have admin access.'
        )
        return redirect('/admin/') 