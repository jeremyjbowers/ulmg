# ABOUTME: Dev ASGI entry — Django site plus HTTPS MCP at /mcp.
# ABOUTME: Use uvicorn config.dev.asgi:application for local MCP-over-HTTP testing.
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.dev.settings")

from django.core.asgi import get_asgi_application

django_app = get_asgi_application()

from ulmg.mcp.http_app import create_site_asgi_application

application = create_site_asgi_application(django_app)
