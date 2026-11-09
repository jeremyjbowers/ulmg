# ABOUTME: Test helper that builds the real engine binary with cargo and runs it on a free local port.
# ABOUTME: Builds once per process under a file lock, shares one engine per test process, and fails loudly when cargo is missing.
import atexit
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from filelock import FileLock

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


def target_dir():
    """Cargo's target directory for the engine crate."""
    target = Path(os.environ.get("CARGO_TARGET_DIR", ENGINE_DIR / "target"))
    if not target.is_absolute():
        target = ENGINE_DIR / target
    return target


def build_lock_path():
    """The file lock parallel test workers take before building, so only one runs cargo at a time."""
    return target_dir() / "ulmg-test-build.lock"


_built_binary = None


def build_engine():
    """
    Build the serve binary and return its path. Each process builds once;
    parallel workers take turns under a file lock in the target directory,
    so the first compiles and the rest find it up to date.
    """
    global _built_binary
    cargo = find_cargo()
    if _built_binary is not None and _built_binary.exists():
        return _built_binary
    lock_path = build_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(lock_path)):
        built = subprocess.run(
            [cargo, "build", "--quiet", "--bin", "serve"],
            cwd=ENGINE_DIR,
            capture_output=True,
            text=True,
        )
    if built.returncode != 0:
        raise RuntimeError(f"cargo build failed in {ENGINE_DIR}:\n{built.stderr}")
    _built_binary = target_dir() / "debug" / "serve"
    return _built_binary


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


# (process id, EngineProcess) for the engine this process started.
_shared_engine = (None, None)


def shared_engine():
    """
    The test process's one running engine, started on first use and stopped
    when the process exits. The engine is stateless, so every test class in
    a process (each parallel worker is its own process) can share it.
    """
    global _shared_engine
    owner, engine = _shared_engine
    if owner == os.getpid() and engine.process.poll() is None:
        return engine
    engine = EngineProcess(build_engine()).start()
    atexit.register(engine.stop)
    _shared_engine = (os.getpid(), engine)
    return engine
