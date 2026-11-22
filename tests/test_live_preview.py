import tempfile
import unittest
from pathlib import Path

from core.live_preview import HEIGHT, WIDTH, HEADER, MAX_FILE, write_frame, read_frame


class LocalPreviewTests(unittest.TestCase):
    def test_atomic_preview_is_local_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/"live-frame.ppm"
            a=bytes((12,31,80))* (WIDTH*HEIGHT)
            b=bytes((120,200,30))* (WIDTH*HEIGHT)
            write_frame(path,a)
            self.assertEqual(read_frame(path),a)
            self.assertEqual(path.stat().st_size,MAX_FILE)
            self.assertTrue(path.read_bytes().startswith(HEADER))
            write_frame(path,b)
            self.assertEqual(read_frame(path),b)
            self.assertFalse(path.with_name(path.name+".incoming").exists())

    def test_incomplete_and_unsafe_frames_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"live-frame.ppm"
            with self.assertRaises(ValueError):write_frame(path,b"hello")
            with self.assertRaises(ValueError):read_frame(path)
            path.write_bytes(HEADER+b"\0"*12)
            with self.assertRaises(ValueError):read_frame(path)
            path.write_bytes(b"wrong"+b"\0"*(MAX_FILE-5))
            with self.assertRaises(ValueError):read_frame(path)
            path.unlink()
            try:path.symlink_to(Path(tmp)/"not-real")
            except (NotImplementedError,OSError):return
            with self.assertRaises(ValueError):read_frame(path)
            with self.assertRaises(ValueError):write_frame(path,bytes(115200))


if __name__=="__main__":
    unittest.main()
