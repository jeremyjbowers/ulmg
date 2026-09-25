# ABOUTME: DO App Platform ASGI entry — Django plus MCP Streamable HTTP at /mcp.
# ABOUTME: Run with uvicorn so owners can connect Claude/Codex/Copilot over HTTPS.
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.do_app_platform.settings")

from django.core.asgi import get_asgi_application

django_app = get_asgi_application()

from ulmg.mcp.http_app import create_site_asgi_application

application = create_site_asgi_application(django_app)
