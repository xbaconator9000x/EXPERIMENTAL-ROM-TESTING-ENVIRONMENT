"""Local-only, exact-hash emulator transport. No memory writes."""
import hashlib
import os
from pathlib import Path
import queue
import threading
import subprocess
import tempfile
import time

class LiveError(RuntimeError):
    pass

class Live:
    def __init__(self, runner, rom, sha256):
        rom=Path(rom)
        if not 0<rom.stat().st_size<=32*1024*1024:
            raise LiveError("Invalid ROM size")
        data = rom.read_bytes()
        self.sha256 = hashlib.sha256(data).hexdigest()
        if self.sha256 != sha256.lower():
            raise LiveError("ROM SHA-256 mismatch")
        self.tmp = tempfile.TemporaryDirectory(prefix="gba-live-")
        self.proc = None
        self.responses=queue.Queue()
        self.reader=None
        try:
            path = Path(self.tmp.name) / "game.gba"
            path.write_bytes(data)
            env=os.environ.copy()
            if os.name=="nt":
                env["PATH"]=env.get("MSYS2_UCRT64_BIN",r"C:\msys64\ucrt64\bin")+os.pathsep+env.get("PATH","")
            self.proc = subprocess.Popen(
                [str(Path(runner).resolve()), str(path)], cwd=self.tmp.name, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=-1,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            self.reader=threading.Thread(target=self._read_loop,daemon=True)
            self.reader.start()
            if self._line() != "READY":
                raise LiveError("emulator initialization failed")
        except BaseException:
            self.close()
            raise

    def _read_loop(self):
        # select() cannot wait on anonymous subprocess pipes on Windows.
        try:
            while True:
                line=self.proc.stdout.readline(240*160*6+12)
                if not line:
                    self.responses.put(LiveError("emulator exited"));return
                if len(line)>240*160*6+10 or not line.endswith(b"\n"):
                    self.responses.put(LiveError("oversized emulator response"));return
                self.responses.put(line[:-1].rstrip(b"\r").decode("ascii"))
        except (OSError,UnicodeError,ValueError):
            self.responses.put(LiveError("emulator transport failed"))

    def _line(self):
        try:result=self.responses.get(timeout=15)
        except queue.Empty:raise LiveError("emulator response timed out") from None
        if isinstance(result,Exception):raise result
        return result

    def _request(self, cmd):
        self.proc.stdin.write((cmd + "\n").encode("ascii"))
        self.proc.stdin.flush()
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

    def rgb(self):
        result=self._request("FRAME")
        if not result.startswith("RGB ") or len(result)!=4+240*160*6:
            raise LiveError("invalid screenshot response")
        return bytes.fromhex(result[4:])

    def screenshot(self,path):
        with open(path,"xb") as file:
            file.write(b"P6\n240 160\n255\n"+self.rgb())

    def save_state(self):
        target=Path(self.tmp.name)/"checkpoint.bin"
        target.unlink(missing_ok=True)
        if self._request("SAVE")!="OK state" or not 0<target.stat().st_size<=2*1024*1024:
            raise LiveError("invalid native checkpoint")
        return target.read_bytes()

    def load_state(self,data):
        if not isinstance(data,bytes) or not 0<len(data)<=2*1024*1024:
            raise LiveError("invalid native checkpoint size")
        (Path(self.tmp.name)/"checkpoint.bin").write_bytes(data)
        if self._request("LOAD")!="OK state":raise LiveError("checkpoint rejected")

    def close(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.kill()
            self.proc.wait(timeout=5)
            self.proc.stdin.close()
            if self.reader is not None:self.reader.join(timeout=2)
            self.proc.stdout.close()
        self.tmp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
