from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings
from ulmg.models import MagicLinkToken, Owner


class Command(BaseCommand):
    help = 'Create a magic link for a user (for testing or manual access)'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address of the user')
        parser.add_argument(
            '--print-url',
            action='store_true',
            help='Print the full URL instead of just the token',
        )

    def handle(self, *args, **options):
        email = options['email'].lower().strip()
        
        try:
            # First try to find user by email field
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Then try to find owner by email and get associated user
            try:
                owner = Owner.objects.get(email=email)
                user = owner.user
            except Owner.DoesNotExist:
                raise CommandError(f'No user found with email: {email}')
        
        # Create magic link token
        magic_link = MagicLinkToken.create_for_user(user)
        
        if options['print_url']:
            # For production, you'd want to use the actual domain
            domain = getattr(settings, 'DOMAIN', 'http://localhost:8000')
            magic_url = f"{domain}/accounts/magic-verify/{magic_link.token}/"
            self.stdout.write(
                self.style.SUCCESS(f'Magic link created for {user.email or user.username}:')
            )
            self.stdout.write(magic_url)
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Magic link token created for {user.email or user.username}:')
            )
            self.stdout.write(magic_link.token)
        
        self.stdout.write(
            self.style.WARNING(f'Token expires at: {magic_link.expires_at}')
        ) 