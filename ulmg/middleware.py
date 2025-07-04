from django.shortcuts import redirect
from django.urls import reverse, resolve
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect


class LoginRequiredMiddleware:
    """
    Middleware that requires a user to be authenticated to view any page.
    Exempts login/logout URLs and API endpoints that might need public access.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        
        # Skip authentication check for exempt URLs
        if self.is_exempt_url(request):
            response = self.get_response(request)
            return response
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            # Redirect to magic link login
            return redirect('login')
        
        response = self.get_response(request)
        return response

    def is_exempt_url(self, request):
        """
        Check if the current URL should be exempt from login requirements.
        """
        # Get the URL name
        try:
            url_name = resolve(request.path_info).url_name
            url_namespace = resolve(request.path_info).namespace
        except:
            return False
        
        # Always allow admin URLs for staff users (but still require authentication in admin)
        if request.path.startswith('/admin/'):
            return True
            
        # Exempt auth-related URLs
        auth_exempt_urls = [
            'login',
            'logout', 
            'magic_login_verify',
            'admin_magic_login_request',
            'admin_magic_login_verify',
        ]
        
        # Exempt specific URL names
        if url_name in auth_exempt_urls:
            return True
            
        # Exempt static files and media
        if (request.path.startswith('/static/') or 
            request.path.startswith('/media/') or
            request.path.startswith('/favicon.ico')):
            return True
            
        return False 