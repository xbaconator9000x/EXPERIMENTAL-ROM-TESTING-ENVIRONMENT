import struct
import unittest
import zlib
from core.prepare_rom import apply

def n(x):
    o=bytearray()
    while True:
        b=x&127;x>>=7
        if not x:return bytes(o)+bytes([b|128])
        o.append(b);x-=1

def patch(src,dst,actions):
    b=b"BPS1"+n(len(src))+n(len(dst))+n(0)+actions+struct.pack("<II",zlib.crc32(src),zlib.crc32(dst))
    return b+struct.pack("<I",zlib.crc32(b))

class BPSTests(unittest.TestCase):
    def test_all_modes_and_overlap(self):
        s=b"abcdef"
        d=b"abXYefefef"
        # source read ab, literal XY, source copy ef, overlapping target copy efef
        p=patch(s,d,n(4)+n(5)+b"XY"+n(6)+n(8)+n(15)+n(8))
        self.assertEqual(apply(s,p),d)
    def test_wrong_source(self):
        p=patch(b"a",b"a",n(0))
        with self.assertRaisesRegex(ValueError,"CRC"):
            apply(b"b",p)
    def test_wrong_patch_crc(self):
        p=patch(b"a",b"a",n(0))
        with self.assertRaisesRegex(ValueError,"CRC"):
            apply(b"a",p[:-1]+bytes([p[-1]^1]))
    def test_invalid_target_copy(self):
        p=patch(b"a",b"x",n(3)+n(0))
        with self.assertRaisesRegex(ValueError,"copy"):
            apply(b"a",p)
    def test_trailing_payload(self):
        p=patch(b"a",b"a",n(0)+n(0))
        with self.assertRaisesRegex(ValueError,"trailing"):
            apply(b"a",p)
