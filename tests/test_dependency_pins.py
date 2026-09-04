# ABOUTME: Ensures App Platform uses uv: no requirements.txt, and pyproject pins match uv.lock.
# ABOUTME: DigitalOcean prefers pip if requirements.txt exists, so that file must stay gone.

import re
import tomllib
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]


def _normalize_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_pyproject_pins(path):
    data = tomllib.loads(path.read_text())
    pins = {}
    for dep in data["project"]["dependencies"]:
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^;#\s]+)", dep.strip())
        if not match:
            raise AssertionError(f"Expected a pinned pyproject dependency, got: {dep}")
        pins[_normalize_name(match.group(1))] = match.group(2)
    return pins


def _parse_uv_lock_versions(path):
    data = tomllib.loads(path.read_text())
    versions = {}
    for package in data.get("package", []):
        name = _normalize_name(package["name"])
        if name == "ulmg":
            continue
        versions[name] = package["version"]
    return versions


class DependencyPinUnitTestCase(TestCase):
    def test_requirements_txt_is_absent(self):
        self.assertFalse(
            (ROOT / "requirements.txt").exists(),
            "requirements.txt makes App Platform use pip instead of uv",
        )

    def test_pyproject_dependencies_are_pinned(self):
        pins = _parse_pyproject_pins(ROOT / "pyproject.toml")
        self.assertGreater(len(pins), 0)


class DependencyPinIntegrationTestCase(TestCase):
    def test_uv_lock_contains_every_pyproject_pin(self):
        pyproject = _parse_pyproject_pins(ROOT / "pyproject.toml")
        locked = _parse_uv_lock_versions(ROOT / "uv.lock")
        missing = {
            name: version
            for name, version in pyproject.items()
            if locked.get(name) != version
        }
        self.assertEqual(missing, {})


class DependencyPinE2ETestCase(TestCase):
    def test_uv_export_matches_pyproject_pins(self):
        import subprocess

        export = subprocess.run(
            [
                "uv",
                "export",
                "--frozen",
                "--no-dev",
                "--no-hashes",
                "--no-emit-project",
                "--format",
                "requirements-txt",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        exported = {}
        for raw in export.stdout.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "sys_platform == 'win32'" in line:
                continue
            match = re.match(r"^([A-Za-z0-9_.-]+)==([^;#\s]+)", line)
            if match:
                exported[_normalize_name(match.group(1))] = match.group(2)

        pyproject = _parse_pyproject_pins(ROOT / "pyproject.toml")
        self.assertEqual(pyproject, exported)
