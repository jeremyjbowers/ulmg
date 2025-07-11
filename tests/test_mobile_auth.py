# ABOUTME: Test mobile device authentication flows and magic link functionality
# ABOUTME: Covers mobile browser behavior, email client interactions, and responsive auth

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from ulmg import models, utils


class MobileAuthTestCase(TestCase):
    """Test magic link authentication specifically for mobile devices"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.mobile_user_agents = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36',
            'Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
        ]
    
    def test_mobile_magic_link_request_with_mobile_user_agent(self):
        """Test magic link request from mobile device"""
        with patch('ulmg.utils.send_email') as mock_send_email:
            mock_send_email.return_value = True
            
            for user_agent in self.mobile_user_agents:
                response = self.client.post(
                    reverse('login'),
                    data={'email': 'test@example.com'},
                    HTTP_USER_AGENT=user_agent
                )
                
                # Should succeed regardless of user agent
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'you will receive a magic link')
                
                # Should have created a magic link token
                self.assertTrue(
                    models.MagicLinkToken.objects.filter(user=self.user).exists()
                )
    
    def test_mobile_magic_link_verification_preserves_next_parameter(self):
        """Test that mobile magic link verification preserves 'next' parameter"""
        target_url = '/my/team/'
        
        for user_agent in self.mobile_user_agents:
            # Create a fresh token for each test
            magic_link = models.MagicLinkToken.create_for_user(self.user)
            
            response = self.client.get(
                reverse('magic_login_verify', kwargs={'token': magic_link.token}) + f'?next={target_url}',
                HTTP_USER_AGENT=user_agent
            )
            
            # Should redirect to next parameter
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, target_url)
    
    def test_mobile_magic_link_verification_with_url_parameters(self):
        """Test magic link verification with various URL parameters common on mobile"""
        
        # Test with utm parameters (common from email clients)
        test_url_templates = [
            '/?utm_source=email&utm_medium=magic_link',
            '/?next=/my/team/&utm_source=email',
            '/?fbclid=test123&gclid=test456',
        ]
        
        for url_template in test_url_templates:
            for user_agent in self.mobile_user_agents:
                # Create fresh token for each test
                magic_link = models.MagicLinkToken.create_for_user(self.user)
                test_url = f'/accounts/magic-verify/{magic_link.token}{url_template}'
                
                response = self.client.get(test_url, HTTP_USER_AGENT=user_agent)
                
                # Should still work with extra parameters
                self.assertEqual(response.status_code, 302)
                # Should be logged in
                self.assertTrue(response.wsgi_request.user.is_authenticated)
    
    def test_mobile_magic_link_with_encoded_urls(self):
        """Test magic link verification with URL encoded parameters"""
        
        # Test with encoded next parameter (common from email clients)
        encoded_next = '/my/team/?tab=roster&filter=active'
        import urllib.parse
        encoded_url = urllib.parse.quote(encoded_next)
        
        for user_agent in self.mobile_user_agents:
            # Create fresh token for each test
            magic_link = models.MagicLinkToken.create_for_user(self.user)
            
            response = self.client.get(
                reverse('magic_login_verify', kwargs={'token': magic_link.token}) + f'?next={encoded_url}',
                HTTP_USER_AGENT=user_agent
            )
            
            # Should handle encoded URLs properly
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, encoded_next)
    
    def test_mobile_session_persistence_after_magic_link_login(self):
        """Test that mobile browsers maintain session after magic link login"""
        
        for user_agent in self.mobile_user_agents:
            # Create fresh token for each test
            magic_link = models.MagicLinkToken.create_for_user(self.user)
            client = Client()
            
            # Use magic link to log in
            response = client.get(
                reverse('magic_login_verify', kwargs={'token': magic_link.token}),
                HTTP_USER_AGENT=user_agent
            )
            
            # Should be redirected and logged in
            self.assertEqual(response.status_code, 302)
            
            # Test that subsequent requests maintain session
            response = client.get('/', HTTP_USER_AGENT=user_agent)
            self.assertTrue(response.wsgi_request.user.is_authenticated)
            self.assertEqual(response.wsgi_request.user.id, self.user.id)
    
    def test_mobile_magic_link_with_malformed_tokens(self):
        """Test mobile handling of malformed or truncated magic link tokens"""
        magic_link = models.MagicLinkToken.create_for_user(self.user)
        
        # Test various malformed tokens that might occur on mobile
        malformed_tokens = [
            magic_link.token[:-5],  # Truncated token
            magic_link.token + 'extra',  # Token with extra characters
            magic_link.token.replace('-', ''),  # Token with dashes removed
            magic_link.token.replace('_', ''),  # Token with underscores removed
            '',  # Empty token
            'invalid-token-123'  # Completely invalid token
        ]
        
        for token in malformed_tokens:
            for user_agent in self.mobile_user_agents:
                response = self.client.get(
                    reverse('magic_login_verify', kwargs={'token': token}),
                    HTTP_USER_AGENT=user_agent
                )
                
                # Should redirect to login with error
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse('login'))
                
                # Should not be logged in
                self.assertFalse(response.wsgi_request.user.is_authenticated)
    
    def test_mobile_magic_link_email_client_simulation(self):
        """Test magic link flow simulating email client behavior"""
        with patch('ulmg.utils.send_email') as mock_send_email:
            mock_send_email.return_value = True
            
            for user_agent in self.mobile_user_agents:
                # Step 1: Request magic link
                response = self.client.post(
                    reverse('login'),
                    data={'email': 'test@example.com'},
                    HTTP_USER_AGENT=user_agent
                )
                
                # Step 2: Simulate email client opening link
                magic_link = models.MagicLinkToken.objects.filter(user=self.user).first()
                self.assertIsNotNone(magic_link)
                
                # Step 3: Simulate click from email client (different session)
                email_client = Client()
                response = email_client.get(
                    reverse('magic_login_verify', kwargs={'token': magic_link.token}),
                    HTTP_USER_AGENT=user_agent
                )
                
                # Should successfully log in
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.wsgi_request.user.is_authenticated)
    
    def test_mobile_magic_link_with_special_characters_in_next(self):
        """Test magic link with special characters in next parameter"""
        
        # Test URLs with special characters that might break on mobile
        special_urls = [
            '/search/?q=player%20name&category=hitters',
            '/team/123/?tab=roster&sort=name&order=asc',
            '/draft/?round=1&pick=15&type=open',
        ]
        
        for next_url in special_urls:
            for user_agent in self.mobile_user_agents:
                # Create fresh token for each test
                magic_link = models.MagicLinkToken.create_for_user(self.user)
                
                response = self.client.get(
                    reverse('magic_login_verify', kwargs={'token': magic_link.token}) + f'?next={next_url}',
                    HTTP_USER_AGENT=user_agent
                )
                
                # Should preserve complex next URLs
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, next_url)
    
    def test_mobile_magic_link_token_expiration(self):
        """Test mobile handling of expired magic link tokens"""
        # Create expired token
        expired_token = models.MagicLinkToken.objects.create(
            user=self.user,
            token='expired-token-123',
            expires_at=timezone.now() - timedelta(days=1),
            used=False
        )
        
        for user_agent in self.mobile_user_agents:
            response = self.client.get(
                reverse('magic_login_verify', kwargs={'token': expired_token.token}),
                HTTP_USER_AGENT=user_agent
            )
            
            # Should redirect to login with error
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('login'))
            
            # Should not be logged in
            self.assertFalse(response.wsgi_request.user.is_authenticated)
    
    def test_mobile_responsive_login_form(self):
        """Test that login form is properly responsive on mobile"""
        for user_agent in self.mobile_user_agents:
            response = self.client.get(
                reverse('login'),
                HTTP_USER_AGENT=user_agent
            )
            
            # Should return login form
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'name="email"')
            self.assertContains(response, 'type="email"')
            self.assertContains(response, 'Send Magic Link')
            
            # Should have mobile-friendly viewport
            self.assertContains(response, 'viewport')
            self.assertContains(response, 'width=device-width')
    
    def test_mobile_magic_link_multiple_use_should_work_within_grace_period(self):
        """Test that mobile users can use magic links multiple times within 5 minutes"""
        magic_link = models.MagicLinkToken.create_for_user(self.user)
        mobile_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        
        # First use should work
        response = self.client.get(
            reverse('magic_login_verify', kwargs={'token': magic_link.token}),
            HTTP_USER_AGENT=mobile_ua
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        
        # Second use should work (within grace period for mobile)
        response = self.client.get(
            reverse('magic_login_verify', kwargs={'token': magic_link.token}),
            HTTP_USER_AGENT=mobile_ua
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        
        # Third use should also work (within grace period)
        response = self.client.get(
            reverse('magic_login_verify', kwargs={'token': magic_link.token}),
            HTTP_USER_AGENT=mobile_ua
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
    
    def test_mobile_magic_link_multiple_use_fails_after_grace_period(self):
        """Test that magic links fail after the 5-minute grace period"""
        from unittest.mock import patch
        from django.utils import timezone
        from datetime import timedelta
        
        magic_link = models.MagicLinkToken.create_for_user(self.user)
        mobile_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        
        # First use should work
        response = self.client.get(
            reverse('magic_login_verify', kwargs={'token': magic_link.token}),
            HTTP_USER_AGENT=mobile_ua
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        
        # Mock time to be 6 minutes later
        future_time = timezone.now() + timedelta(minutes=6)
        with patch('django.utils.timezone.now', return_value=future_time):
            # Should fail after grace period
            response = self.client.get(
                reverse('magic_login_verify', kwargs={'token': magic_link.token}),
                HTTP_USER_AGENT=mobile_ua
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('login'))


class MobileAuthIntegrationTestCase(TestCase):
    """Integration tests for mobile auth flows"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        # Create owner record for more realistic testing
        self.owner = models.Owner.objects.create(
            user=self.user,
            email='test@example.com',
            name='Test Owner'
        )
    
    def test_full_mobile_auth_flow(self):
        """Test complete mobile authentication flow"""
        client = Client()
        mobile_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        
        with patch('ulmg.utils.send_email') as mock_send_email:
            mock_send_email.return_value = True
            
            # Step 1: Request magic link
            response = client.post(
                reverse('login'),
                data={'email': 'test@example.com'},
                HTTP_USER_AGENT=mobile_ua
            )
            
            # Step 2: Verify magic link was created
            magic_link = models.MagicLinkToken.objects.filter(user=self.user).first()
            self.assertIsNotNone(magic_link)
            
            # Step 3: Use magic link
            response = client.get(
                reverse('magic_login_verify', kwargs={'token': magic_link.token}),
                HTTP_USER_AGENT=mobile_ua
            )
            
            # Step 4: Verify successful login
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.wsgi_request.user.is_authenticated)
            
            # Step 5: Verify token was marked as used
            magic_link.refresh_from_db()
            self.assertTrue(magic_link.used)
            
            # Step 6: Verify subsequent requests work
            response = client.get('/', HTTP_USER_AGENT=mobile_ua)
            self.assertTrue(response.wsgi_request.user.is_authenticated)