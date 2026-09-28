# ABOUTME: Guards against local ulmg MCP code shadowing the installed mcp SDK.
# ABOUTME: App Platform often puts the ulmg package dir on sys.path.
import importlib
import sys
from pathlib import Path
from unittest import TestCase


class McpSdkImportUnitTestCase(TestCase):
    def test_sdk_mcp_is_not_local_ulmg_package(self):
        import mcp

        mcp_file = Path(mcp.__file__).resolve()
        repo_ulmg = Path(__file__).resolve().parents[1] / "ulmg"
        self.assertFalse(
            str(mcp_file).startswith(str(repo_ulmg)),
            f"Installed mcp SDK shadowed by local package: {mcp_file}",
        )
        self.assertTrue(
            any(part in {"site-packages", "dist-packages"} for part in mcp_file.parts),
            f"Expected site-packages mcp, got {mcp_file}",
        )

    def test_fastmcp_imports_when_ulmg_package_dir_on_sys_path(self):
        """Reproduce DO App Platform layout: .../ulmg on sys.path."""
        ulmg_pkg_dir = str(Path(__file__).resolve().parents[1] / "ulmg")
        saved_modules = {
            name: mod
            for name, mod in list(sys.modules.items())
            if name == "mcp" or name.startswith("mcp.")
        }
        try:
            for name in list(saved_modules):
                del sys.modules[name]
            sys.path.insert(0, ulmg_pkg_dir)

            import mcp
            from mcp.server.fastmcp import FastMCP

            self.assertTrue(
                any(
                    part in {"site-packages", "dist-packages"}
                    for part in Path(mcp.__file__).resolve().parts
                ),
                f"mcp still shadowed: {mcp.__file__}",
            )
            self.assertIsNotNone(FastMCP)
        finally:
            if sys.path and sys.path[0] == ulmg_pkg_dir:
                sys.path.pop(0)
            for name in list(sys.modules):
                if name == "mcp" or name.startswith("mcp."):
                    del sys.modules[name]
            sys.modules.update(saved_modules)


class McpAppImportIntegrationTestCase(TestCase):
    def test_mcp_app_tools_import_with_ulmg_dir_on_path(self):
        ulmg_pkg_dir = str(Path(__file__).resolve().parents[1] / "ulmg")
        saved_modules = {
            name: mod
            for name, mod in list(sys.modules.items())
            if name == "mcp"
            or name.startswith("mcp.")
            or name.startswith("ulmg.mcp_app")
        }
        try:
            for name in list(saved_modules):
                del sys.modules[name]
            sys.path.insert(0, ulmg_pkg_dir)

            tools = importlib.import_module("ulmg.mcp_app.tools")
            http_app = importlib.import_module("ulmg.mcp_app.http_app")
            self.assertTrue(callable(tools.build_mcp))
            self.assertTrue(callable(http_app.create_mcp_http_app))
        finally:
            if sys.path and sys.path[0] == ulmg_pkg_dir:
                sys.path.pop(0)
            for name in list(sys.modules):
                if (
                    name == "mcp"
                    or name.startswith("mcp.")
                    or name.startswith("ulmg.mcp_app")
                ):
                    del sys.modules[name]
            sys.modules.update(saved_modules)


class McpAppImportE2ETestCase(TestCase):
    def test_asgi_factory_builds_under_shadow_path(self):
        ulmg_pkg_dir = str(Path(__file__).resolve().parents[1] / "ulmg")
        saved_modules = {
            name: mod
            for name, mod in list(sys.modules.items())
            if name == "mcp"
            or name.startswith("mcp.")
            or name.startswith("ulmg.mcp_app")
        }
        try:
            for name in list(saved_modules):
                del sys.modules[name]
            sys.path.insert(0, ulmg_pkg_dir)

            from ulmg.mcp_app.http_app import create_mcp_http_app

            app = create_mcp_http_app()
            self.assertIsNotNone(app)
        finally:
            if sys.path and sys.path[0] == ulmg_pkg_dir:
                sys.path.pop(0)
            for name in list(sys.modules):
                if (
                    name == "mcp"
                    or name.startswith("mcp.")
                    or name.startswith("ulmg.mcp_app")
                ):
                    del sys.modules[name]
            sys.modules.update(saved_modules)
