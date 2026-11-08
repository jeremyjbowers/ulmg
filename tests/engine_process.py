# ABOUTME: Test helper that builds the real engine binary with cargo and runs it on a free local port.
# ABOUTME: Fails loudly, never skips, when cargo is missing or the engine does not come up.
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import requests

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
FIXTURE_PATH = ENGINE_DIR / "fixtures" / "game.json"
STARTUP_TIMEOUT_SECONDS = 15


class EngineToolMissing(RuntimeError):
    pass


def find_cargo(path=None):
    """Return the cargo executable, or raise with instructions when it is not installed."""
    cargo = shutil.which("cargo", path=path)
    if cargo is None:
        raise EngineToolMissing(
            "cargo is not installed or not on PATH. The engine tests build and run the real "
            "engine in engine/ and cannot pass without it. Install Rust from https://rustup.rs "
            "and run the tests again."
        )
    return cargo


def build_engine():
    """Build the serve binary and return its path."""
    cargo = find_cargo()
    built = subprocess.run(
        [cargo, "build", "--quiet", "--bin", "serve"],
        cwd=ENGINE_DIR,
        capture_output=True,
        text=True,
    )
    if built.returncode != 0:
        raise RuntimeError(f"cargo build failed in {ENGINE_DIR}:\n{built.stderr}")
    target_dir = Path(os.environ.get("CARGO_TARGET_DIR", ENGINE_DIR / "target"))
    if not target_dir.is_absolute():
        target_dir = ENGINE_DIR / target_dir
    return target_dir / "debug" / "serve"


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class EngineProcess:
    """One running engine process. Use `start()` and `stop()`."""

    def __init__(self, binary):
        self.binary = binary
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.process = None
        self.output = None

    def start(self):
        self.output = tempfile.TemporaryFile(mode="w+")
        self.process = subprocess.Popen(
            [str(self.binary)],
            env={**os.environ, "PORT": str(self.port)},
            stdout=self.output,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"the engine exited early:\n{self.read_output()}")
            try:
                if requests.get(f"{self.url}/health", timeout=1).status_code == 200:
                    return self
            except requests.ConnectionError:
                pass
            time.sleep(0.05)
        output = self.read_output()
        self.stop()
        raise RuntimeError(
            f"the engine did not answer {self.url}/health within "
            f"{STARTUP_TIMEOUT_SECONDS} seconds:\n{output}"
        )

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)
        if self.output is not None:
            self.output.close()
            self.output = None

    def read_output(self):
        if self.output is None:
            return ""
        self.output.seek(0)
        return self.output.read()
