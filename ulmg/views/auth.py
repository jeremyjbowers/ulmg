import datetime
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.conf import settings
from django.urls import reverse

from ulmg import models, utils


def magic_login_request(request):
    """
    View to request a magic link. User enters their email.
    """
    if request.method == 'POST':
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
    
    return render(request, 'registration/login.html')


def magic_login_verify(request, token):
    """
    View to verify a magic link token and log the user in.
    """
    user = models.MagicLinkToken.authenticate(token)
    
    if user:
        login(request, user)
        messages.success(request, 'You have been logged in successfully!')
        
        # Redirect to 'next' parameter if provided, otherwise to home
        next_url = request.GET.get('next', '/')
        return redirect(next_url)
    else:
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