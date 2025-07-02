from django.contrib import admin
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseRedirect
from django.urls import reverse


class MagicLinkAdminSite(admin.AdminSite):
    """
    Custom admin site that uses magic link authentication instead of passwords.
    """
    site_header = "ULMG Administration"
    site_title = "ULMG Admin"
    index_title = "Welcome to ULMG Administration"
    
    def login(self, request, extra_context=None):
        """
        Override the admin login to redirect to magic link authentication.
        """
        if request.method == 'GET':
            # Redirect to our custom admin login page
            login_url = reverse('admin:login')
            return HttpResponseRedirect(login_url)
        
        # For POST requests, the magic link authentication is handled by JavaScript
        return super().login(request, extra_context)

    def has_permission(self, request):
        """
        Check if the user has permission to access the admin site.
        """
        return request.user.is_active and request.user.is_staff


# Create the custom admin site instance
admin_site = MagicLinkAdminSite(name='admin') 