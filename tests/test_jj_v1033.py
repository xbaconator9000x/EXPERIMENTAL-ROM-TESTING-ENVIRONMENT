import unittest

from core.jj_fast import SHA, SHA_V1033, ADMITTED_SHA256S
from core.jj_battle import FINGERPRINTS, MOVE_CB_V1033, fingerprints_for
from core.rom_catalog import JJ, JJ_V1033


class ExactReleaseTests(unittest.TestCase):
    def test_new_rom_identity_requires_exact_sha256(self):
        self.assertEqual(SHA, JJ)
        self.assertEqual(SHA_V1033, JJ_V1033)
        self.assertEqual(ADMITTED_SHA256S, frozenset((SHA, SHA_V1033)))
        self.assertEqual(len(SHA_V1033), 64)

    def test_move_menu_fingerprint_is_version_scoped(self):
        move = 0x0802EA11
        self.assertNotEqual(FINGERPRINTS[move], MOVE_CB_V1033)
        self.assertEqual(fingerprints_for(SHA)[move], FINGERPRINTS[move])
        self.assertEqual(fingerprints_for(SHA_V1033)[move], MOVE_CB_V1033)
        self.assertEqual(fingerprints_for(SHA_V1033)[0x08011101], FINGERPRINTS[0x08011101])
        self.assertEqual(fingerprints_for("0" * 64), {})

    def test_repaired_release_does_not_generalize_to_other_patches(self):
        self.assertNotIn("0" * 64, ADMITTED_SHA256S)
        self.assertNotIn("0" * 64, (JJ, JJ_V1033))


if __name__ == "__main__":
    unittest.main()
