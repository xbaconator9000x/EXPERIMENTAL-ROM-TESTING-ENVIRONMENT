"""Private local-only GBA preview frames, separate from immutable checkpoints.

This is a read-only display transport: it never creates emulator instances,
accepts controller input, uses a network listener or publishes ROM/save bytes.
The writer atomically replaces a small RGB PPM so a Tk viewer cannot observe
half of a frame. Frame data are display pixels only, not emulator state.
"""
import os
from pathlib import Path

WIDTH=240
HEIGHT=160
RGB_BYTES=WIDTH*HEIGHT*3
HEADER=b"P6\n240 160\n255\n"
MAX_FILE=len(HEADER)+RGB_BYTES


def write_frame(path,rgb):
    if not isinstance(rgb,bytes) or len(rgb)!=RGB_BYTES:
        raise ValueError("Invalid GBA framebuffer")
    path=Path(path)
    if not path.is_absolute() or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Preview path must be an ordinary absolute local file")
    # One writer per campaign. The run controller lock prevents a second
    # writer for the same campaign; this temporary file is never a checkpoint.
    tmp=path.with_name(path.name+".incoming")
    try:
        with tmp.open("wb") as f:
            f.write(HEADER)
            f.write(rgb)
            f.flush()
        os.replace(tmp,path)
    except OSError:
        try:tmp.unlink(missing_ok=True)
        except OSError:pass
        raise


def read_frame(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("No local preview frame")
    with path.open("rb") as f:
        info=os.fstat(f.fileno())
        if info.st_size!=MAX_FILE or f.read(len(HEADER))!=HEADER:
            raise ValueError("Invalid preview format")
        data=f.read(RGB_BYTES+1)
        if len(data)!=RGB_BYTES:
            raise ValueError("Truncated preview frame")
    return data
