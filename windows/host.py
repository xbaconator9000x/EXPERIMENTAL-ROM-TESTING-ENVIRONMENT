"""Native Windows desktop host for locally owned GBA regression tests.

Tkinter is part of the standard Windows Python distribution. No service,
network listener, admin rights, GitHub token, or WSL required.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ROMTestingHost"
LIBRARY = ROOT / "roms"
RUNS = ROOT / "runs"
RUNNER = REPO / "build" / "state_runner.exe"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_EXTENSIONS = {".gba"}


def fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def import_rom(source: Path, library: Path = LIBRARY) -> dict:
    source = Path(source).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Select a local .gba file")
    if source.stat().st_size == 0 or source.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Invalid GBA cartridge size")
    library.mkdir(parents=True, exist_ok=True)
    digest = fingerprint(source)
    target = library / (digest + ".gba")
    if not target.exists():
        tmp = library / (digest + ".partial")
        try:
            with source.open("rb") as src, tmp.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            if fingerprint(tmp) != digest:
                raise RuntimeError("ROM changed during import")
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
    if fingerprint(target) != digest:
        raise RuntimeError("ROM library corrupted; refusing launch")
    return {"sha256": digest, "path": str(target), "label": source.name}


def scenario_path(path: Path) -> Path:
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != ".txt":
        raise ValueError("Scenario must be a local .txt file")
    if path.stat().st_size > 64 * 1024:
        raise ValueError("Scenario exceeds 64 KiB")
    # The native state runner has the final strict grammar and frame budget.
    # Reject any unfamiliar instruction before giving it to the emulator.
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) > 1000:
        raise ValueError("Scenario has too many lines")
    for line in lines:
        tokens = line.partition("#")[0].split()
        if tokens and tokens[0] not in {"idle", "press", "wait", "assert", "capture"}:
            raise ValueError("Unsupported scenario instruction")
    return path


def build_command(rom: dict, scenario: Path, output: Path, runner: Path = RUNNER) -> list[str]:
    if not runner.is_file():
        raise FileNotFoundError("Native runner missing. Run windows\\build.ps1 first.")
    digest = rom["sha256"]
    if not SHA256.fullmatch(digest):
        raise ValueError("Invalid ROM fingerprint")
    path = Path(rom["path"]).resolve(strict=True)
    if fingerprint(path) != digest:
        raise ValueError("ROM hash changed since import")
    scenario = scenario_path(scenario)
    return [sys.executable, str(REPO / "core" / "run_locked.py"),
            "--runner", str(runner.resolve()), "--rom", str(path),
            "--sha256", digest, "--scenario", str(scenario), "--out", str(output)]


class Host(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ROM Testing Host | Windows")
        self.geometry("880x610")
        self.minsize(680, 480)
        self.events = queue.Queue()
        self.process = None
        self.worker = None
        self.roms = []
        self.scenario = tk.StringVar()
        self.status = tk.StringVar(value="Ready - tests run on this PC only")
        self.runner_status = tk.StringVar()
        self.selected = tk.StringVar()
        ROOT.mkdir(parents=True, exist_ok=True)
        LIBRARY.mkdir(parents=True, exist_ok=True)
        RUNS.mkdir(parents=True, exist_ok=True)
        self.build_ui()
        self.refresh()
        self.after(100, self.pump)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self):
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="ROM Testing Host", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Private, native Windows mGBA execution. No ROM uploads or web listener.").pack(anchor="w", pady=(0, 14))
        self.runner_label = ttk.Label(frame, textvariable=self.runner_status)
        self.runner_label.pack(anchor="w")
        top = ttk.Frame(frame)
        top.pack(fill="x", pady=12)
        ttk.Button(top, text="Import local ROM", command=self.import_selected).pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=8)
        ttk.Button(top, text="Open local results", command=lambda: os.startfile(str(RUNS))).pack(side="left")
        ttk.Label(frame, text="Local ROM library (SHA-256 verified)").pack(anchor="w")
        self.listbox = tk.Listbox(frame, height=6, exportselection=False)
        self.listbox.pack(fill="x", pady=(4, 12))
        line = ttk.Frame(frame)
        line.pack(fill="x", pady=(0, 12))
        ttk.Entry(line, textvariable=self.scenario).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Choose scenario", command=self.choose_scenario).pack(side="left", padx=(8, 0))
        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        self.start_button = ttk.Button(actions, text="Run selected test", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="Stop test", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Label(actions, textvariable=self.status).pack(side="left", padx=8)
        self.log = tk.Text(frame, height=16, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, pady=(12, 0))

    def append(self, line: str):
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def refresh(self):
        self.runner_status.set("Emulator runner: " + ("ready" if RUNNER.is_file() else "not built - run windows\\build.ps1"))
        self.roms = [{"sha256": p.stem, "path": str(p), "label": p.stem[:16]}
                     for p in sorted(LIBRARY.glob("*.gba")) if SHA256.fullmatch(p.stem)]
        self.listbox.delete(0, "end")
        for rom in self.roms:
            self.listbox.insert("end", rom["label"] + " (" + rom["sha256"][:12] + "...)")

    def import_selected(self):
        name = filedialog.askopenfilename(title="Select your own GBA ROM", filetypes=[("GBA ROM", "*.gba")])
        if not name:
            return
        try:
            item = import_rom(Path(name))
            self.refresh()
            self.append("Imported " + item["label"] + " SHA256=" + item["sha256"])
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc))

    def choose_scenario(self):
        name = filedialog.askopenfilename(title="Select a trusted local scenario",
                    filetypes=[("Scenario", "*.txt")], initialdir=str(REPO / "tests" / "scenarios"))
        if name:
            self.scenario.set(name)

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        indices = self.listbox.curselection()
        if not indices:
            messagebox.showinfo("ROM required", "Import and select a ROM first.")
            return
        try:
            rom = self.roms[indices[0]]
            scenario = scenario_path(Path(self.scenario.get()))
            run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + rom["sha256"][:10]
            folder = RUNS / run_id
            if folder.exists():
                raise FileExistsError("Results directory already exists")
            command = build_command(rom, scenario, folder / "captures")
            folder.mkdir(parents=True)
            (folder / "request.json").write_text(json.dumps({
                "sha256": rom["sha256"], "scenario": str(scenario),
                "created_at": time.time(), "status": "running"}, indent=2), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Cannot start test", str(exc))
            return
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status.set("Running")
        self.worker = threading.Thread(target=self.run_worker, args=(command, folder), daemon=True)
        self.worker.start()

    def run_worker(self, command, folder):
        code = -1
        try:
            env = os.environ.copy()
            msys_bin = Path(env.get("MSYS2_UCRT64_BIN", r"C:\\msys64\\ucrt64\\bin"))
            if msys_bin.is_dir():
                env["PATH"] = str(msys_bin) + os.pathsep + env.get("PATH", "")
            with (folder / "output.log").open("w", encoding="utf-8") as log:
                self.process = subprocess.Popen(command, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, errors="replace",
                    cwd=str(REPO), env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for line in self.process.stdout:
                    log.write(line)
                    log.flush()
                    self.events.put(("line", line.rstrip()))
                code = self.process.wait(timeout=10)
        except Exception as exc:
            self.events.put(("line", "HOST ERROR: " + str(exc)))
        finally:
            (folder / "result.json").write_text(json.dumps({
                "exit_code": code, "status": "passed" if code == 0 else "failed",
                "finished_at": time.time()}, indent=2), encoding="utf-8")
            self.process = None
            self.events.put(("done", code))

    def pump(self):
        while True:
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "line":
                self.append(data)
            elif kind == "done":
                self.status.set("PASS" if data == 0 else "FAILED (exit " + str(data) + ")")
                self.start_button.config(state="normal")
                self.stop_button.config(state="disabled")
        self.after(100, self.pump)

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.status.set("Stopping...")

    def close(self):
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Test running", "Stop the running test and exit?"):
                return
            self.process.kill()
        self.destroy()


if __name__ == "__main__":
    Host().mainloop()
