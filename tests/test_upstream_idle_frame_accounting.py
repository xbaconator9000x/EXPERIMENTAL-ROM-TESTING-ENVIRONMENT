"""Regression: native idle polling must respect exact frame budgets."""
import unittest
from core.upstream_skills import SkillTransport


class FakeLive:
    def __init__(self):
        self.frames = 0
    def step(self, mask, frames):
        assert mask == 0
        self.frames += frames
    def rgb(self):
        return bytes(240 * 160 * 3)


class IdleFrameAccountingTests(unittest.TestCase):
    def transport(self):
        t = SkillTransport(FakeLive(), max_frames=100)
        t.start()
        return t

    def test_stable_poll_exact_frames(self):
        t = self.transport()
        self.assertTrue(t.wait_until_idle(max_frames=12, stable=8))
        self.assertEqual(t.live.frames, 12)
        self.assertEqual(t.frames, 12)
        self.assertEqual(t.actions, [[0, 4], [0, 4], [0, 4]])

    def test_timeout_does_not_add_hidden_release_frames(self):
        t = self.transport()
        self.assertFalse(t.wait_until_idle(max_frames=8, stable=8))
        self.assertEqual(t.live.frames, 8)

    def test_partial_last_poll_obeys_budget(self):
        t = self.transport()
        self.assertFalse(t.wait_until_idle(max_frames=6, stable=8))
        self.assertEqual(t.live.frames, 6)


if __name__ == "__main__":
    unittest.main()
