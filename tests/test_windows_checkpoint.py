import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from windows.queue_host import validate, run, RUNNER
from windows.local_state import checkpoint_path, store_checkpoint, load_checkpoint, validate_patch, install_patch
from make_gba_fixture import make_rom

def digest(x):return hashlib.sha256(x).hexdigest()

class LocalStateTests(unittest.TestCase):
    def test_immutable_hash_bound_state(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r="1"*64;abi="2"*64
            raw=p/"raw";raw.write_bytes(b"local emulator state")
            state=checkpoint_path(p,r,abi,"bedroom")
            store_checkpoint(state,r,abi,raw)
            self.assertEqual(load_checkpoint(state,r,abi),raw.read_bytes())
            with self.assertRaises(FileExistsError):store_checkpoint(state,r,abi,raw)
            with self.assertRaises(ValueError):load_checkpoint(state,"3"*64,abi)
            with self.assertRaises(ValueError):load_checkpoint(state,r,"3"*64)
            state.write_bytes(state.read_bytes()[:-1]+b"x")
            with self.assertRaises(ValueError):load_checkpoint(state,r,abi)
            with self.assertRaises(ValueError):checkpoint_path(p,r,abi,"../../secret")
    def test_v2_admission_and_bounds(self):
        job={"version":2,"sha256":"0"*64,"scenario":["observe 32 0x02000000","assert 32 0x02000000 1 1"],"checkpoint":"bedroom"}
        self.assertEqual(validate(json.dumps(job)),job)
        self.assertEqual(run(job,threading.Event()),"CAPABILITY_DISABLED")
        for update in ({"checkpoint":"../host"},{"resume":"bedroom"},{"scenario":["observe 32 0x08000000","assert 32 0x02000000 1 1"]},{"version":1},{"resume":"ok.exe"}):
            with self.subTest(update=update),self.assertRaises(ValueError):validate(json.dumps({**job,**update}))
    def test_hash_locked_patch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);a=b"abc123";b=b"aBC123"
            src=p/(digest(a)+".gba");src.write_bytes(a)
            job={"version":1,"source_sha256":digest(a),"target_sha256":digest(b),"edits":[{"offset":1,"old":"6263","new":"4243"}]}
            self.assertEqual(install_patch(job,p),"PATCH_INSTALLED")
            self.assertEqual(src.read_bytes(),a)
            self.assertEqual((p/(digest(b)+".gba")).read_bytes(),b)
            self.assertEqual(install_patch(job,p),"PATCH_INSTALLED")
            self.assertEqual(install_patch({**job,"target_sha256":"f"*64},p),"PATCH_TARGET_MISMATCH")
            wrong={**job,"edits":[{"offset":1,"old":"ffff","new":"4243"}]}
            self.assertEqual(install_patch(wrong,p),"PATCH_SOURCE_MISMATCH")
            for edit in ({"offset":-1,"old":"62","new":"42"},{"offset":1,"old":"62","new":"4243"},{"offset":1,"old":"zz","new":"42"}):
                with self.assertRaises(ValueError):validate_patch(json.dumps({**job,"edits":[edit]}))
            with self.assertRaises(ValueError):validate_patch(json.dumps({**job,"edits":job["edits"]*2}))
    @unittest.skipUnless(RUNNER.is_file(),"Windows native runner not built")
    def test_real_native_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);lib=root/"roms";lib.mkdir();runs=root/"runs";states=root/"states"
            data=make_rom();rom=digest(data);(lib/(rom+".gba")).write_bytes(data)
            job={"version":2,"sha256":rom,"scenario":["wait 32 0x02000000 0xffffffff 1 60","press A 2","assert 32 0x02000000 0xffffffff 0","observe 32 0x02000000"],"checkpoint":"pressed"}
            status=run(job,threading.Event(),RUNNER,lib,runs,checkpoint_root=states,allow_v2=True)
            logs="\n".join(p.read_text(errors="replace") for p in runs.glob("*/native.log"))
            self.assertEqual(status,"PASS",logs)
            follow={"version":2,"sha256":rom,"resume":"pressed","scenario":["assert 32 0x02000000 0xffffffff 0","idle 2","assert 32 0x02000000 0xffffffff 1","capture"]}
            status=run(follow,threading.Event(),RUNNER,lib,runs,checkpoint_root=states,allow_v2=True)
            logs="\n".join(p.read_text(errors="replace") for p in runs.glob("*/native.log"))
            self.assertEqual(status,"PASS",logs)
            self.assertEqual(run(job,threading.Event(),RUNNER,lib,runs,checkpoint_root=states,allow_v2=True),"CHECKPOINT_EXISTS")
            self.assertEqual(run({**follow,"resume":"missing"},threading.Event(),RUNNER,lib,runs,checkpoint_root=states,allow_v2=True),"CHECKPOINT_NOT_FOUND")
