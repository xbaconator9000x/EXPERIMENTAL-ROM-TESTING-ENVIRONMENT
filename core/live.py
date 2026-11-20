"""Local-only, exact-hash emulator transport. No memory writes."""
import hashlib
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time

class LiveError(RuntimeError):
    pass

class Live:
    def __init__(self, runner, rom, sha256):
        data = Path(rom).read_bytes()
        self.sha256 = hashlib.sha256(data).hexdigest()
        if self.sha256 != sha256.lower():
            raise LiveError("ROM SHA-256 mismatch")
        self.tmp = tempfile.TemporaryDirectory(prefix="gba-live-")
        self.proc = None
        self.buffer = b""
        try:
            path = Path(self.tmp.name) / "game.gba"
            path.write_bytes(data)
            self.proc = subprocess.Popen(
                [str(Path(runner).resolve()), str(path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
            if self._line() != "READY":
                raise LiveError("emulator initialization failed")
        except BaseException:
            self.close()
            raise

    def _line(self):
        end = time.monotonic() + 15
        while b"\n" not in self.buffer:
            remain = end - time.monotonic()
            if remain <= 0 or not select.select([self.proc.stdout], [], [], remain)[0]:
                raise LiveError("emulator response timed out")
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise LiveError("emulator exited")
            self.buffer += chunk
            if len(self.buffer) > 240*160*6+10:
                raise LiveError("oversized emulator response")
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line.decode("ascii")

    def _request(self, cmd):
        self.proc.stdin.write((cmd + "\n").encode("ascii"))
        result = self._line()
        if result.startswith("ERR "):
            raise LiveError(result)
        return result

    def read(self, address, size):
        if not 0 <= address <= 0xffffffff or not 1 <= size <= 32768:
            raise LiveError("invalid read")
        result = self._request(f"READ {address:x} {size}")
        if not result.startswith("DATA ") or len(result) != 5 + 2 * size:
            raise LiveError("invalid read response")
        return bytes.fromhex(result[5:])

    def integer(self, address, size):
        return int.from_bytes(self.read(address, size), "little")

    def step(self, keys=0, frames=1):
        if not 0 <= keys <= 1023 or not 1 <= frames <= 600:
            raise LiveError("invalid step")
        result = self._request(f"STEP {keys:x} {frames}")
        if not result.startswith("OK "):
            raise LiveError("invalid frame response")
        return int(result[3:])

    def screenshot(self, path):
        result = self._request("FRAME")
        if not result.startswith("RGB ") or len(result) != 4+240*160*6:
            raise LiveError("invalid screenshot response")
        with open(path, "xb") as file:
            file.write(b"P6\n240 160\n255\n"+bytes.fromhex(result[4:]))

    def close(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.kill()
            self.proc.wait(timeout=5)
            self.proc.stdin.close()
            self.proc.stdout.close()
        self.tmp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
