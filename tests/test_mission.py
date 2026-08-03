from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.aegis.events import GeoPosition
from src.aegis.mission import (
    MissionController,
    MissionMode,
    build_simulated_drone_events,
    distance_and_bearing,
    events_to_mission_frames,
)
from src.aegis.recording import RecordingStatus, load_recording


class MissionTests(unittest.TestCase):
    def test_simulated_mission_builds_ten_frames(self) -> None:
        events = build_simulated_drone_events()

        frames = events_to_mission_frames(
            events,
            mode=MissionMode.SIMULATED,
        )

        self.assertEqual(len(frames), 10)
        self.assertEqual(frames[0].aircraft_id, "SIM-AEGIS-001")
        self.assertIsNotNone(frames[0].distance_m)
        self.assertIsNotNone(frames[0].bearing_degrees)

    def test_rf_dropout_fades_then_reacquires_contact(self) -> None:
        frames = events_to_mission_frames(
            build_simulated_drone_events(),
            mode=MissionMode.SIMULATED,
        )

        self.assertEqual(frames[6].scan_result.contacts[0].missed_scans, 1)
        self.assertEqual(frames[7].scan_result.contacts[0].missed_scans, 0)
        self.assertEqual(frames[7].scan_result.contacts[0].signal_id, 1)

    def test_distance_and_bearing_for_due_north_target(self) -> None:
        distance, bearing = distance_and_bearing(
            GeoPosition(41.0, -87.0),
            GeoPosition(41.001, -87.0),
        )

        self.assertAlmostEqual(distance, 111.2, delta=0.2)
        self.assertAlmostEqual(bearing, 0.0, delta=0.01)

    def test_controller_records_and_replays_identical_frames(self) -> None:
        with TemporaryDirectory() as temporary:
            recording_path = Path(temporary) / "mission"
            controller = MissionController()
            controller.start_simulation(recording_path)
            recorded_frames = []
            while controller.has_next:
                recorded_frames.append(controller.next_frame())

            loaded = load_recording(recording_path)
            replay = MissionController()
            replay.open_recording(recording_path)
            replayed_frames = []
            while replay.has_next:
                replayed_frames.append(replay.next_frame())

        self.assertEqual(loaded.manifest.status, RecordingStatus.COMPLETE)
        self.assertEqual(len(loaded.events), 19)
        self.assertEqual(
            [frame.distance_m for frame in replayed_frames],
            [frame.distance_m for frame in recorded_frames],
        )
        self.assertTrue(
            all(frame.mode is MissionMode.REPLAY for frame in replayed_frames)
        )

    def test_stopping_early_closes_recording_cleanly(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "early-stop"
            controller = MissionController()
            controller.start_simulation(path)
            controller.next_frame()

            controller.stop()
            loaded = load_recording(path)

        self.assertEqual(loaded.manifest.status, RecordingStatus.COMPLETE)
        self.assertEqual(len(loaded.events), 2)
        self.assertFalse(controller.has_next)


if __name__ == "__main__":
    unittest.main()
