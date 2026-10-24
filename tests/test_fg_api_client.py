# ABOUTME: Tests for FanGraphs HTTP helper that bypasses Cloudflare challenges.
# ABOUTME: Covers UA constant, header injection, brotli decoding, and live downloads.
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from unittest import TestCase as UnitTestCase
from unittest.mock import MagicMock, patch

import requests
import requests_mock
from django.conf import settings
from django.test import TestCase, override_settings

from ulmg import utils
from ulmg.management.commands.live_download_fg_rosters import (
    Command as DownloadFgRostersCommand,
)
from ulmg.management.commands.live_download_fg_stats import (
    Command as DownloadFgStatsCommand,
)

# Brotli body of [{"player":"Zach Neto"}]. FanGraphs uses this encoding when
# the client advertises br.
_ZACH_NETO_ROSTER_BROTLI = bytes(
    [
        139, 11, 128, 91, 123, 34, 112, 108, 97, 121, 101, 114, 34, 58, 34,
        90, 97, 99, 104, 32, 78, 101, 116, 111, 34, 125, 93, 3,
    ]
)


class FgApiClientUnitTestCase(UnitTestCase):
    """Unit tests for FanGraphs request helper."""

    def test_fg_user_agent_is_okhttp_mobile_client(self):
        self.assertEqual(utils.fg_user_agent(), "okhttp/4.12.0")

    def test_fg_get_sends_okhttp_user_agent(self):
        with requests_mock.Mocker() as mocker:
            mocker.get(
                "https://www.fangraphs.com/api/depth-charts/roster?teamid=1",
                json=[{"player": "Zach Neto"}],
                status_code=200,
            )
            response = utils.fg_get(
                "https://www.fangraphs.com/api/depth-charts/roster?teamid=1"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                mocker.last_request.headers["User-Agent"],
                "okhttp/4.12.0",
            )

    def test_fg_get_preserves_caller_headers_and_sets_user_agent(self):
        with requests_mock.Mocker() as mocker:
            mocker.get(
                "https://www.fangraphs.com/api/leaders/major-league/data",
                json={"data": []},
                status_code=200,
            )
            response = utils.fg_get(
                "https://www.fangraphs.com/api/leaders/major-league/data",
                headers={"accept": "application/json"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                mocker.last_request.headers["User-Agent"],
                "okhttp/4.12.0",
            )
            self.assertEqual(
                mocker.last_request.headers["Accept"],
                "application/json",
            )

    def test_fg_get_does_not_let_caller_override_user_agent(self):
        with requests_mock.Mocker() as mocker:
            mocker.get(
                "https://www.fangraphs.com/api/depth-charts/roster?teamid=2",
                json=[],
                status_code=200,
            )
            utils.fg_get(
                "https://www.fangraphs.com/api/depth-charts/roster?teamid=2",
                headers={"User-Agent": "python-requests/2.0"},
            )
            self.assertEqual(
                mocker.last_request.headers["User-Agent"],
                "okhttp/4.12.0",
            )

    def test_brotli_decoder_is_patched(self):
        import importlib.util

        import brotli

        parts = tuple(int(part) for part in brotli.__version__.split(".")[:3])
        self.assertGreaterEqual(
            parts,
            (1, 2, 1),
            "brotli decoder must be >= 1.2.1 (CVE-2026-111497)",
        )
        # CPython uses the brotli package. brotlicffi is the other binding
        # with the same decoder bug, and must not be an older install.
        if importlib.util.find_spec("brotlicffi") is not None:
            import brotlicffi

            cffi_parts = tuple(
                int(part) for part in brotlicffi.__version__.split(".")[:3]
            )
            self.assertGreaterEqual(cffi_parts, (1, 2, 1))

    def test_fg_get_decodes_brotli_json(self):
        payload = _ZACH_NETO_ROSTER_BROTLI

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Encoding", "br")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, fmt, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            response = utils.fg_get(
                f"http://127.0.0.1:{port}/api/depth-charts/roster?teamid=1",
                timeout=5,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("br", response.request.headers["Accept-Encoding"])
            self.assertEqual(response.json(), [{"player": "Zach Neto"}])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


class FgApiClientIntegrationTestCase(TestCase):
    """Integration: live download commands call utils.fg_get."""

    @override_settings(ROSTER_TEAM_IDS=[(1, "LAA", "Angels")])
    @patch("ulmg.management.commands.live_download_fg_rosters.time.sleep")
    @patch("ulmg.management.commands.live_download_fg_rosters.utils.fg_get")
    def test_live_download_fg_rosters_uses_fg_get(self, mock_fg_get, _mock_sleep):
        mock_fg_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"player": "Zach Neto", "teamid": 1}],
        )
        out = StringIO()
        err = StringIO()
        DownloadFgRostersCommand(stdout=out, stderr=err).handle(local_only=True)

        mock_fg_get.assert_called_once()
        called_url = mock_fg_get.call_args[0][0]
        self.assertEqual(
            called_url,
            "https://www.fangraphs.com/api/depth-charts/roster?teamid=1",
        )
        self.assertIn("Angels", out.getvalue())
        self.assertEqual(err.getvalue(), "")

    @patch("ulmg.management.commands.live_download_fg_stats.utils.fg_get")
    def test_live_download_fg_stats_uses_fg_get_for_major_hitters(self, mock_fg_get):
        mock_fg_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": [{"Name": "Aaron Judge"}]},
        )
        cmd = DownloadFgStatsCommand(stdout=StringIO(), stderr=StringIO())
        cmd.season = 2025
        cmd.local_only = True
        cmd.get_fg_major_hitter_season()

        mock_fg_get.assert_called_once()
        called_url = mock_fg_get.call_args[0][0]
        self.assertIn("fangraphs.com/api/leaders/major-league/data", called_url)
        self.assertIn("stats=bat", called_url)


class FgApiClientE2ETestCase(UnitTestCase):
    """End-to-end: real FanGraphs API accepts the okhttp client."""

    def test_fg_get_roster_endpoint_returns_json_list(self):
        url = "https://www.fangraphs.com/api/depth-charts/roster?teamid=1"
        response = utils.fg_get(url, timeout=30)
        self.assertEqual(response.status_code, 200, response.text[:200])
        self.assertNotIn("cf-mitigated", response.headers)
        self.assertIn("br", response.request.headers["Accept-Encoding"])
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIn("player", data[0])
