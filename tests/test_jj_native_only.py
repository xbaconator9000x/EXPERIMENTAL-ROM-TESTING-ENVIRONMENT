import unittest
from core.jj_native_only import NativeOnly

class NativeOnlyTests(unittest.TestCase):
    def test_no_model_connection_and_same_checkpoint_label(self):
        controller=NativeOnly("existing-model-label")
        self.assertEqual(controller.model,"existing-model-label")
        self.assertTrue(controller.native_only)
        self.assertFalse(hasattr(controller,"opener"))
        self.assertEqual(controller.fallback_requests,0)
    def test_unsupported_native_state_is_review_without_any_input(self):
        controller=NativeOnly()
        decision=controller.decide(bytes(115200),"finish game",[],[])
        self.assertEqual(decision["actions"],[])
        self.assertTrue(decision["review"])
        self.assertEqual(decision["scene"],"native_state_unclassified")
        self.assertEqual(controller.fallback_requests,1)

if __name__=="__main__":unittest.main()
