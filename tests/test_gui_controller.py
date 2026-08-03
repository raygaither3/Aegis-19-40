import unittest

from src.aegis.mission import MissionController, MissionMode


class MissionControllerGuiContractTests(unittest.TestCase):
    def test_starts_ready_without_frames(self) -> None:
        controller = MissionController()

        self.assertIsNone(controller.current)
        self.assertFalse(controller.has_next)
        self.assertEqual(controller.total_frames, 0)
        self.assertEqual(controller.mode, MissionMode.READY)

    def test_simulation_advances_through_each_frame(self) -> None:
        controller = MissionController()
        controller.start_simulation()

        frames = []
        while controller.has_next:
            frames.append(controller.next_frame())

        self.assertEqual(len(frames), 10)
        self.assertEqual(frames[0].scan_result.scan_number, 1)
        self.assertEqual(frames[-1].scan_result.scan_number, 10)
        self.assertIsNone(controller.next_frame())

    def test_reset_returns_to_ready_state(self) -> None:
        controller = MissionController()
        controller.start_simulation()
        controller.next_frame()

        controller.reset()

        self.assertIsNone(controller.current)
        self.assertFalse(controller.has_next)
        self.assertEqual(controller.mode, MissionMode.READY)


if __name__ == "__main__":
    unittest.main()
