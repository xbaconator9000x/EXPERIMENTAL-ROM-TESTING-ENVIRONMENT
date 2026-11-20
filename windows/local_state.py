"""Immutable, private emulator states and exact-hash ROM-only repair deployment."""
import hashlib
import json
from pathlib import Path
import re
import os
import tempfile

NAME=re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
HASH=re.compile(r"[0-9a-f]{64}")
HEX=re.compile(r"(?:[0-9a-f]{2})+")
MAX_STATE=2*1024*1024
MAX_ROM=32*1024*1024
MAX_EDITS=128
MAX_BYTES=8192
MAGIC=b"ROMHOST-CHECKPOINT-1\n"

def sha(data):return hashlib.sha256(data).hexdigest()

def checkpoint_path(root,rom,runner,name):
    if not HASH.fullmatch(rom) or not HASH.fullmatch(runner) or not NAME.fullmatch(name):
        raise ValueError("Invalid checkpoint identity")
    return Path(root)/rom/runner/(name+".state")

def atomic_new(path,data):
    """Publish complete immutable file on the same volume; never overwrite."""
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix=".new-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        # Atomic no-replace hard link. NTFS and normal Linux filesystems support it.
        os.link(temp,path)
    finally:
        Path(temp).unlink(missing_ok=True)

def store_checkpoint(dest,rom,runner,raw):
    raw=Path(raw)
    if raw.is_symlink() or not raw.is_file() or not 0<raw.stat().st_size<=MAX_STATE:
        raise ValueError("Invalid native state")
    data=raw.read_bytes()
    if not 0<len(data)<=MAX_STATE:raise ValueError("Invalid native state")
    dest=Path(dest)
    if dest.exists():raise FileExistsError(dest)
    if dest.parent.exists() and sum(1 for _ in dest.parent.glob("*.state"))>=64:
        raise ValueError("Checkpoint quota reached")
    header=json.dumps({"rom":rom,"runner":runner,"size":len(data),"sha256":sha(data)},separators=(",",":"),sort_keys=True).encode("ascii")
    atomic_new(dest,MAGIC+header+b"\n"+data)

def load_checkpoint(path,rom,runner):
    path=Path(path)
    if path.is_symlink() or not 0<path.stat().st_size<=MAX_STATE+1024:
        raise ValueError("Invalid state envelope")
    with path.open("rb") as f:
        magic=f.readline(64);header=f.readline(1024);data=f.read(MAX_STATE+1)
    if magic!=MAGIC or not header.endswith(b"\n"):raise ValueError("Invalid state envelope")
    meta=json.loads(header)
    if not data or len(data)>MAX_STATE or meta!={"rom":rom,"runner":runner,"size":len(data),"sha256":sha(data)}:
        raise ValueError("Checkpoint integrity or revision mismatch")
    return data

def validate_patch(body):
    """Only equal-length ROM byte replacements, bounded and source/target hash locked."""
    if not isinstance(body,str) or len(body)>65536:raise ValueError("Invalid patch body")
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError("Duplicate key")
            d[k]=v
        return d
    job=json.loads(body,object_pairs_hook=unique)
    if type(job) is not dict or set(job)!={"version","source_sha256","target_sha256","edits"} or type(job["version"]) is not int or job["version"]!=1:
        raise ValueError("Invalid patch schema")
    for field in ("source_sha256","target_sha256"):
        if type(job[field]) is not str or not HASH.fullmatch(job[field]):raise ValueError("Invalid ROM digest")
    if job["source_sha256"]==job["target_sha256"]:raise ValueError("No-op patch")
    edits=job["edits"]
    if type(edits) is not list or not 1<=len(edits)<=MAX_EDITS:raise ValueError("Invalid edits")
    total=0;end=0
    for e in edits:
        if type(e) is not dict or set(e)!={"offset","old","new"} or type(e["offset"]) is not int:
            raise ValueError("Invalid edit")
        a=e["offset"]
        if any(type(e[k]) is not str or not HEX.fullmatch(e[k]) for k in ("old","new")):
            raise ValueError("Invalid bytes")
        n=len(e["old"])//2
        if len(e["old"])!=len(e["new"]) or e["old"]==e["new"] or a<end or a+n>MAX_ROM:
            raise ValueError("Unsorted, overlapping or out-of-bounds edit")
        end=a+n;total+=n
        if total>MAX_BYTES:raise ValueError("Patch budget exceeded")
    return job

def install_patch(job,library):
    job=validate_patch(json.dumps(job))
    root=Path(library)
    source=root/(job["source_sha256"]+".gba")
    target=root/(job["target_sha256"]+".gba")
    if not source.is_file():return "ROM_NOT_REGISTERED"
    if source.is_symlink() or not 0<source.stat().st_size<=MAX_ROM:return "PATCH_SOURCE_MISMATCH"
    data=bytearray(source.read_bytes())
    if not 0<len(data)<=MAX_ROM or sha(data)!=job["source_sha256"]:return "PATCH_SOURCE_MISMATCH"
    for e in job["edits"]:
        a=e["offset"];old=bytes.fromhex(e["old"]);new=bytes.fromhex(e["new"])
        if a+len(old)>len(data) or data[a:a+len(old)]!=old:return "PATCH_SOURCE_MISMATCH"
        data[a:a+len(old)]=new
    if sha(data)!=job["target_sha256"]:return "PATCH_TARGET_MISMATCH"
    if target.exists():
        if target.is_symlink() or not target.is_file() or target.stat().st_size!=len(data) or sha(target.read_bytes())!=job["target_sha256"]:
            return "PATCH_TARGET_MISMATCH"
        return "PATCH_INSTALLED"
    try:atomic_new(target,data)
    except FileExistsError:
        if target.is_symlink() or not target.is_file() or target.stat().st_size!=len(data) or sha(target.read_bytes())!=job["target_sha256"]:
            return "PATCH_TARGET_MISMATCH"
    return "PATCH_INSTALLED"
