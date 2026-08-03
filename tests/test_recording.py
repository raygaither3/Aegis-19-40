from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.aegis.events import (
    NodeType,
    Provenance,
    RfDetectionPayload,
    SensorEvent,
    SensorType,
    create_sensor_event,
)
from src.aegis.recording import (
    EventRecorder,
    EventReplayer,
    RecordingReadError,
    RecordingStatus,
    load_recording,
)


class RecordingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start_time = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)

    def test_recording_round_trip_and_manifest(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "mission-001"
            events = [self._event(index) for index in range(3)]

            with EventRecorder(
                path,
                recording_id="mission-001",
                node_id="sentinel-home-01",
                created_at=self.start_time,
            ) as recorder:
                for event in events:
                    recorder.record(event)

            loaded = load_recording(path)

        self.assertEqual(loaded.events, tuple(events))
        self.assertEqual(loaded.issues, ())
        self.assertEqual(loaded.manifest.status, RecordingStatus.COMPLETE)
        self.assertEqual(loaded.manifest.event_count, 3)
        self.assertIsNotNone(loaded.manifest.closed_at)

    def test_segments_rotate_at_configured_limit(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "mission-002"
            with EventRecorder(
                path,
                recording_id="mission-002",
                node_id="sentinel-home-01",
                max_events_per_segment=2,
            ) as recorder:
                for index in range(5):
                    recorder.record(self._event(index))

            loaded = load_recording(path)

        self.assertEqual(
            loaded.manifest.segments,
            (
                "segment-000001.jsonl",
                "segment-000002.jsonl",
                "segment-000003.jsonl",
            ),
        )
        self.assertEqual(len(loaded.events), 5)

    def test_existing_directory_is_not_overwritten(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "existing"
            path.mkdir()
            marker = path / "keep.txt"
            marker.write_text("preserve", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                EventRecorder(
                    path,
                    recording_id="mission",
                    node_id="sentinel-home-01",
                )

            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_context_exception_marks_recording_interrupted(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "interrupted"
            with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                with EventRecorder(
                    path,
                    recording_id="interrupted",
                    node_id="sentinel-home-01",
                ) as recorder:
                    recorder.record(self._event(0))
                    raise RuntimeError("simulated failure")

            loaded = load_recording(path)

        self.assertEqual(loaded.manifest.status, RecordingStatus.INTERRUPTED)
        self.assertEqual(len(loaded.events), 1)

    def test_recorder_rejects_event_from_different_node(self) -> None:
        with TemporaryDirectory() as temporary:
            recorder = EventRecorder(
                Path(temporary) / "mission",
                recording_id="mission",
                node_id="different-node",
            )
            try:
                with self.assertRaisesRegex(ValueError, "does not match"):
                    recorder.record(self._event(0))
            finally:
                recorder.close(status=RecordingStatus.INTERRUPTED)

    def test_non_strict_load_recovers_around_corrupt_line(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "recoverable"
            with EventRecorder(
                path,
                recording_id="recoverable",
                node_id="sentinel-home-01",
            ) as recorder:
                recorder.record(self._event(0))
                recorder.record(self._event(1))
            segment = path / "segment-000001.jsonl"
            lines = segment.read_text(encoding="utf-8").splitlines()
            segment.write_text(
                lines[0] + "\n{truncated\n" + lines[1] + "\n",
                encoding="utf-8",
            )

            loaded = load_recording(path, strict=False)

        self.assertEqual(len(loaded.events), 2)
        self.assertEqual(len(loaded.issues), 1)
        self.assertEqual(loaded.issues[0].line_number, 2)

    def test_strict_load_rejects_corrupt_line(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "strict"
            with EventRecorder(
                path,
                recording_id="strict",
                node_id="sentinel-home-01",
            ) as recorder:
                recorder.record(self._event(0))
            segment = path / "segment-000001.jsonl"
            segment.write_text("not-json\n", encoding="utf-8")

            with self.assertRaisesRegex(RecordingReadError, "invalid event"):
                load_recording(path)

    def test_manifest_count_mismatch_is_reported(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "count-mismatch"
            with EventRecorder(
                path,
                recording_id="count-mismatch",
                node_id="sentinel-home-01",
            ) as recorder:
                recorder.record(self._event(0))
            manifest_path = path / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["event_count"] = 2
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            loaded = load_recording(path, strict=False)

        self.assertEqual(len(loaded.events), 1)
        self.assertEqual(len(loaded.issues), 1)
        self.assertIn("event count", loaded.issues[0].message)

    def test_replay_without_timing_is_deterministic(self) -> None:
        events = [self._event(index) for index in range(3)]
        received: list[SensorEvent] = []
        delays: list[float] = []
        replayer = EventReplayer(events, sleep=delays.append)

        count = replayer.replay(received.append, speed=0)

        self.assertEqual(count, 3)
        self.assertEqual(received, events)
        self.assertEqual(delays, [])

    def test_replay_speed_scales_original_timing(self) -> None:
        events = [self._event(index) for index in range(3)]
        delays: list[float] = []
        replayer = EventReplayer(events, sleep=delays.append)

        replayer.replay(lambda _: None, speed=2.0)

        self.assertEqual(delays, [0.5, 0.5])

    def _event(self, sequence: int) -> SensorEvent:
        return create_sensor_event(
            node_id="sentinel-home-01",
            node_type=NodeType.SENTINEL,
            sensor_id="simulator-rf",
            sensor_type=SensorType.SIMULATOR,
            observed_at=self.start_time + timedelta(seconds=sequence),
            sequence_number=sequence,
            provenance=Provenance.SIMULATED,
            payload=RfDetectionPayload(
                center_frequency_hz=2_437_000_000 + sequence * 1_000,
                bandwidth_hz=20_000_000,
                peak_power_db=-55.0,
                noise_floor_db=-91.0,
            ),
        )


if __name__ == "__main__":
    unittest.main()
