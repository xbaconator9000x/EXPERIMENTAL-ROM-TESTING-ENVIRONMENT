"""Fail-closed source contract for partially executed upstream skills."""
import inspect
import unittest
from core import upstream_campaign

class CheckpointAbortContract(unittest.TestCase):
    def test_stopped_skill_restores_prior_state_before_next_checkpoint(self):
        source=inspect.getsource(upstream_campaign.campaign)
        start=source.index('if result.startswith("SKILL_STOPPED:")')
        end=source.index('else:\n                    after=live.rgb();next_state=live.save_state()',start)
        branch=source[start:end]
        self.assertIn("live.load_state(state)",branch)
        self.assertIn("live.rgb()!=rgb",branch)
        self.assertIn("next_state=state",branch)
        self.assertLess(branch.index("live.load_state(state)"),branch.index("next_state=state"))
    def test_stopped_skill_keeps_failure_history(self):
        source=inspect.getsource(upstream_campaign.campaign)
        self.assertIn('"result":result',source)
        self.assertIn('meta["history"]=(meta["history"]+[entry])[-20:]',source)

if __name__=="__main__":
    unittest.main()
