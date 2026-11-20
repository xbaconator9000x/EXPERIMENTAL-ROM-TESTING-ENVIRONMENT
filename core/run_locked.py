#!/usr/bin/env python3
"""Hash-lock actual ROM runs; no ROM content is printed or copied."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("runner", "rom", "sha256", "scenario", "out"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    if not re.fullmatch(r"[a-fA-F0-9]{64}", a.sha256):
        p.error("a verified 64-digit SHA-256 is mandatory")
    actual = hashlib.sha256(Path(a.rom).read_bytes()).hexdigest()
    if actual != a.sha256.lower():
        print("REFUSED: ROM SHA-256 mismatch")
        return 2
    print("Verified ROM SHA-256:", actual, flush=True)
    return subprocess.call([str(Path(a.runner).resolve()), a.rom, a.scenario, a.out], timeout=600)


if __name__ == "__main__":
    raise SystemExit(main())
