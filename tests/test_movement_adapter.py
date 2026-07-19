import unittest

from surfaceos.inputs import MovementConfirmationAdapter


class MovementAdapterTests(unittest.TestCase):
    def test_disabled_adapter_never_confirms(self):
        adapter = MovementConfirmationAdapter(enabled=False, impact_threshold_g=1.5)
        self.assertFalse(adapter.accepts(3.0))

    def test_enabled_adapter_applies_threshold(self):
        adapter = MovementConfirmationAdapter(enabled=True, impact_threshold_g=1.5)
        self.assertFalse(adapter.accepts(1.49))
        self.assertTrue(adapter.accepts(1.5))


if __name__ == "__main__":
    unittest.main()
