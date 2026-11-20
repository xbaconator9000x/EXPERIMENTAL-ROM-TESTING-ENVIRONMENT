"""Reconstruct a locally owned ROM from a hash-locked BPS. Never upload game data."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

def apply(source, patch, max_size=32*1024*1024):
    if len(patch)<19 or patch[:4]!=b"BPS1":
        raise ValueError("invalid BPS header")
    end=len(patch)-12
    sc,tc,pc=struct.unpack_from("<III",patch,end)
    if zlib.crc32(patch[:-4])!=pc or zlib.crc32(source)!=sc:
        raise ValueError("input CRC mismatch")
    pos=4
    def num():
        nonlocal pos
        n=0; shift=1
        for _ in range(6):
            if pos>=end: raise ValueError("truncated varint")
            b=patch[pos];pos+=1
            n+=(b&127)*shift
            if b&128:return n
            shift*=128;n+=shift
        raise ValueError("oversized varint")
    def delta():
        n=num()
        return -(n>>1) if n&1 else n>>1
    ss,ds,meta=num(),num(),num()
    if ss!=len(source) or not 0<ds<=max_size or meta>end-pos:
        raise ValueError("invalid sizes")
    pos+=meta
    out=bytearray();sr=tr=0
    while len(out)<ds:
        a=num();mode=a&3;n=(a>>2)+1
        if n>ds-len(out):raise ValueError("target overflow")
        if mode==0:
            off=len(out)
            if off+n>len(source):raise ValueError("source read overflow")
            out.extend(source[off:off+n])
        elif mode==1:
            if pos+n>end:raise ValueError("literal overflow")
            out.extend(patch[pos:pos+n]);pos+=n
        elif mode==2:
            sr+=delta()
            if sr<0 or sr+n>len(source):raise ValueError("source copy overflow")
            out.extend(source[sr:sr+n]);sr+=n
        else:
            tr+=delta()
            if not 0<=tr<len(out):raise ValueError("target copy overflow")
            for _ in range(n):
                out.append(out[tr]);tr+=1
    if pos!=end or zlib.crc32(out)!=tc:
        raise ValueError("target CRC or trailing payload mismatch")
    return bytes(out)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def prepare(source,patch,manifest,version,out):
    s=Path(source).read_bytes()
    p=Path(patch).read_bytes()
    m=json.loads(Path(manifest).read_text())
    if sha(s)!=m["source_sha256"]:
        raise ValueError("original ROM SHA-256 mismatch")
    b=next(b for b in m["builds"] if b["version"]==version)
    if sha(p)!=b["patch_sha256"]:
        raise ValueError("patch SHA-256 mismatch")
    result=apply(s,p)
    if sha(result)!=b["sha256"]:
        raise ValueError("target SHA-256 mismatch")
    # Exclusive creation prevents overwriting an existing ROM.
    with open(out,"xb") as file:
        file.write(result)
    return sha(result)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("source","patch","manifest","version","out"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    print("Verified local ROM:",prepare(a.source,a.patch,a.manifest,a.version,a.out))
