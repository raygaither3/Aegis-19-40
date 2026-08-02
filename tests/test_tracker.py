import unittest

from src.aegis.signal_detector import DetectedSignal
from src.aegis.tracker import SignalTracker, TrackState


def detection(center_frequency_hz: float) -> DetectedSignal:
    return DetectedSignal(
        start_frequency_hz=center_frequency_hz - 5_000,
        end_frequency_hz=center_frequency_hz + 5_000,
        center_frequency_hz=center_frequency_hz,
        bandwidth_hz=10_000,
        peak_power_db=-60.0,
        power_above_noise_db=30.0,
    )


class SignalTrackerTests(unittest.TestCase):
    def test_new_contact_is_tentative(self) -> None:
        tracker = SignalTracker()

        tracks = tracker.update([detection(100_000_000)], current_time=10.0)

        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].signal_id, 1)
        self.assertEqual(tracks[0].confidence, 20.0)
        self.assertEqual(tracks[0].state, TrackState.TENTATIVE)

    def test_repeated_detection_confirms_and_caps_contact(self) -> None:
        tracker = SignalTracker(confidence_gain=45.0)

        tracker.update([detection(100_000_000)], current_time=10.0)
        tracks = tracker.update([detection(100_005_000)], current_time=11.0)
        tracks = tracker.update([detection(100_010_000)], current_time=12.0)

        self.assertEqual(tracks[0].confidence, 100.0)
        self.assertEqual(tracks[0].detection_count, 3)
        self.assertEqual(tracks[0].state, TrackState.CONFIRMED)
        self.assertEqual(tracks[0].age_seconds, 2.0)

    def test_missed_scan_decays_contact(self) -> None:
        tracker = SignalTracker(confidence_decay=15.0)
        tracker.update([detection(100_000_000)], current_time=10.0)

        tracks = tracker.update([], current_time=11.0)

        self.assertEqual(tracks[0].confidence, 5.0)
        self.assertEqual(tracks[0].missed_scans, 1)
        self.assertEqual(tracks[0].state, TrackState.FADING)

    def test_contact_expires_at_zero_confidence(self) -> None:
        tracker = SignalTracker(initial_confidence=20.0, confidence_decay=10.0)
        tracker.update([detection(100_000_000)], current_time=10.0)
        tracker.update([], current_time=11.0)

        tracks = tracker.update([], current_time=12.0)

        self.assertEqual(tracks, [])

    def test_contact_expires_after_missed_scan_limit(self) -> None:
        tracker = SignalTracker(
            initial_confidence=100.0,
            confidence_decay=1.0,
            max_missed_scans=1,
        )
        tracker.update([detection(100_000_000)], current_time=10.0)
        tracker.update([], current_time=11.0)

        tracks = tracker.update([], current_time=12.0)

        self.assertEqual(tracks, [])

    def test_contact_reacquires_same_id(self) -> None:
        tracker = SignalTracker()
        tracker.update([detection(100_000_000)], current_time=10.0)
        tracker.update([], current_time=11.0)

        tracks = tracker.update(
            [detection(100_005_000)],
            current_time=12.0,
        )

        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].signal_id, 1)
        self.assertEqual(tracks[0].missed_scans, 0)
        self.assertEqual(tracks[0].detection_count, 2)

    def test_frequency_tolerance_is_inclusive(self) -> None:
        tracker = SignalTracker(frequency_tolerance_hz=25_000)
        tracker.update([detection(100_000_000)], current_time=10.0)

        tracks = tracker.update(
            [detection(100_025_000)],
            current_time=11.0,
        )

        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].signal_id, 1)

    def test_detection_outside_tolerance_creates_new_contact(self) -> None:
        tracker = SignalTracker(frequency_tolerance_hz=25_000)
        tracker.update([detection(100_000_000)], current_time=10.0)

        tracks = tracker.update(
            [detection(100_025_001)],
            current_time=11.0,
        )

        self.assertEqual(len(tracks), 2)
        self.assertEqual({track.signal_id for track in tracks}, {1, 2})

    def test_one_track_cannot_match_two_detections_in_one_scan(self) -> None:
        tracker = SignalTracker(frequency_tolerance_hz=25_000)
        tracker.update([detection(100_000_000)], current_time=10.0)

        tracks = tracker.update(
            [detection(99_990_000), detection(100_010_000)],
            current_time=11.0,
        )

        self.assertEqual(len(tracks), 2)
        self.assertEqual(sum(track.detection_count for track in tracks), 3)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SignalTracker(max_missed_scans=-1)


if __name__ == "__main__":
    unittest.main()
