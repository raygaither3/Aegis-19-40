import unittest

from src.aegis.gui import ScenarioController


class ScenarioControllerTests(unittest.TestCase):
    def test_starts_before_first_scan(self) -> None:
        controller = ScenarioController()

        self.assertIsNone(controller.current)
        self.assertTrue(controller.has_next)
        self.assertEqual(controller.total_scans, 5)

    def test_advances_through_each_scan(self) -> None:
        controller = ScenarioController()

        results = []
        while controller.has_next:
            results.append(controller.next_scan())

        self.assertEqual(len(results), 5)
        self.assertEqual(results[0].scan_number, 1)
        self.assertEqual(results[-1].scan_number, 5)
        self.assertIsNone(controller.next_scan())

    def test_reset_returns_to_ready_state(self) -> None:
        controller = ScenarioController()
        controller.next_scan()

        controller.reset()

        self.assertIsNone(controller.current)
        self.assertTrue(controller.has_next)


if __name__ == "__main__":
    unittest.main()
