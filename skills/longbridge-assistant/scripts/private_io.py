"""Private POSIX storage; no broker payloads in diagnostics."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile

MAX_BYTES = 16 * 1024 * 1024


class SafeError(Exception):
    """Contains a safe reason code only."""


def private_root(value: str) -> Path:
    if os.name != "posix":
        raise SafeError("runtime_os_not_verified")
    path = Path(value).expanduser()
    if path.is_symlink():
        raise SafeError("output_symlink")
    path = path.resolve()
    if any((parent / ".git").exists() for parent in [path, *path.parents]):
        raise SafeError("output_inside_git")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise SafeError("output_not_owned")
    os.chmod(path, 0o700)
    return path


def load_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise SafeError("input_unavailable")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SafeError("input_schema")
    return value


def write_json(path: Path, value: dict) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2))


def write_text(path: Path, value: str) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise SafeError("output_symlink")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def lock(root: Path):
    path = root / ".run-lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafeError("run_in_progress")
        yield
    finally:
        os.close(fd)
