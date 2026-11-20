"""Windows host safety and command construction regression tests (no retail ROMs)."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from make_gba_fixture import make_rom
from windows.host import build_command, fingerprint, import_rom, scenario_path


class WindowsHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rom = self.root / "my-game.gba"
        self.rom.write_bytes(make_rom())
        self.library = self.root / "private-library"
        self.scenario = self.root / "test.txt"
        self.scenario.write_text("idle 5\nassert 32 0x02000000 0xffffffff 1\n", encoding="utf-8")
        self.runner = self.root / "state_runner.exe"
        self.runner.write_bytes(b"fixture binary")

    def test_import_reproducible_and_content_addressed(self):
        first = import_rom(self.rom, self.library)
        second = import_rom(self.rom, self.library)
        self.assertEqual(first["path"], second["path"])
        self.assertEqual(Path(first["path"]).name, first["sha256"] + ".gba")
        self.assertEqual(len(list(self.library.glob("*.gba"))), 1)
        self.assertEqual(first["sha256"], fingerprint(self.rom))

    def test_modified_rom_rejected_after_import(self):
        entry = import_rom(self.rom, self.library)
        Path(entry["path"]).write_bytes(b"tampered")
        with self.assertRaises(RuntimeError):
            import_rom(self.rom, self.library)
        with self.assertRaises(ValueError):
            build_command(entry, self.scenario, self.root / "captures", self.runner)

    def test_untrusted_scenario_rejected(self):
        self.scenario.write_text("shell curl https://example.com\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            scenario_path(self.scenario)

    def test_non_gba_rejected(self):
        self.rom.rename(self.root / "random.exe")
        with self.assertRaises(ValueError):
            import_rom(self.root / "random.exe", self.library)

    def test_hash_locked_command_never_runs_shell(self):
        entry = import_rom(self.rom, self.library)
        command = build_command(entry, self.scenario, self.root / "captures", self.runner)
        self.assertEqual(command[0], __import__("sys").executable)
        self.assertIn("--sha256", command)
        self.assertIn(entry["sha256"], command)
        self.assertEqual(command[-1], str((self.root / "captures")))
        self.assertNotIn("powershell", " ".join(command).lower())

    def test_scenario_size_limit(self):
        self.scenario.write_text("# x\n" * 15000, encoding="utf-8")
        with self.assertRaises(ValueError):
            scenario_path(self.scenario)


if __name__ == "__main__":
    unittest.main()
