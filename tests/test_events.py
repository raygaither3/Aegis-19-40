from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import json
import unittest

from src.aegis.events import (
    DataState,
    EventType,
    GeoPosition,
    HealthStatus,
    NodeType,
    Provenance,
    RemoteIdObservationPayload,
    RfDetectionPayload,
    SCHEMA_VERSION,
    SensorEvent,
    SensorHealthPayload,
    SensorType,
    create_sensor_event,
)


class SensorEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observed_at = datetime(
            2026, 8, 2, 2, 30, tzinfo=timezone.utc
        )

    def test_rf_event_round_trip(self) -> None:
        event = create_sensor_event(
            node_id="sentinel-home-01",
            node_type=NodeType.SENTINEL,
            sensor_id="sdr-01",
            sensor_type=SensorType.SDR,
            observed_at=self.observed_at,
            sequence_number=14,
            provenance=Provenance.MEASURED,
            payload=RfDetectionPayload(
                center_frequency_hz=2_437_000_000,
                bandwidth_hz=20_000_000,
                peak_power_db=-51.5,
                noise_floor_db=-91.0,
            ),
        )

        restored = SensorEvent.from_json(event.to_json())

        self.assertEqual(restored, event)
        self.assertEqual(restored.event_type, EventType.RF_DETECTION)
        self.assertEqual(restored.schema_version, SCHEMA_VERSION)

    def test_remote_id_event_round_trip_preserves_positions(self) -> None:
        event = create_sensor_event(
            node_id="command-home-01",
            node_type=NodeType.COMMAND,
            sensor_id="remote-id-01",
            sensor_type=SensorType.REMOTE_ID,
            observed_at=self.observed_at,
            sequence_number=3,
            provenance=Provenance.MEASURED,
            payload=RemoteIdObservationPayload(
                aircraft_id="RID-TEST-001",
                position=GeoPosition(
                    latitude_degrees=41.881832,
                    longitude_degrees=-87.623177,
                    altitude_m=92.0,
                    horizontal_accuracy_m=4.0,
                ),
                speed_mps=12.5,
                heading_degrees=214.0,
                operator_position=GeoPosition(
                    latitude_degrees=41.882,
                    longitude_degrees=-87.624,
                ),
            ),
        )

        restored = SensorEvent.from_json(event.to_json(indent=2))

        self.assertEqual(restored, event)
        self.assertEqual(
            restored.event_type, EventType.REMOTE_ID_OBSERVATION
        )

    def test_health_event_round_trip_preserves_enum(self) -> None:
        event = create_sensor_event(
            node_id="scout-01",
            node_type=NodeType.SCOUT,
            sensor_id="system",
            sensor_type=SensorType.SYSTEM,
            observed_at=self.observed_at,
            sequence_number=0,
            provenance=Provenance.MEASURED,
            data_state=DataState.CURRENT,
            payload=SensorHealthPayload(
                status=HealthStatus.DEGRADED,
                message="Receiver temperature elevated",
            ),
        )

        restored = SensorEvent.from_json(event.to_json())

        self.assertEqual(restored, event)

    def test_event_is_immutable(self) -> None:
        event = self._rf_event()

        with self.assertRaises(FrozenInstanceError):
            event.sequence_number = 9  # type: ignore[misc]

    def test_timestamp_must_include_timezone(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone"):
            create_sensor_event(
                node_id="test-node",
                node_type=NodeType.DEVELOPMENT,
                sensor_id="simulator",
                sensor_type=SensorType.SIMULATOR,
                observed_at=datetime(2026, 8, 2, 2, 30),
                sequence_number=0,
                provenance=Provenance.SIMULATED,
                payload=RfDetectionPayload(100.0, 10.0, -50.0, -90.0),
            )

    def test_timestamp_serializes_in_utc(self) -> None:
        event = create_sensor_event(
            node_id="test-node",
            node_type=NodeType.DEVELOPMENT,
            sensor_id="simulator",
            sensor_type=SensorType.SIMULATOR,
            observed_at=self.observed_at.astimezone(
                timezone(timedelta(hours=-5))
            ),
            sequence_number=0,
            provenance=Provenance.SIMULATED,
            payload=RfDetectionPayload(100.0, 10.0, -50.0, -90.0),
        )

        self.assertTrue(event.to_dict()["observed_at"].endswith("Z"))

    def test_unknown_schema_version_is_rejected(self) -> None:
        data = self._rf_event().to_dict()
        data["schema_version"] = "2.0"

        with self.assertRaisesRegex(ValueError, "unsupported schema"):
            SensorEvent.from_dict(data)

    def test_missing_field_is_rejected(self) -> None:
        data = self._rf_event().to_dict()
        del data["node_id"]

        with self.assertRaisesRegex(ValueError, "missing fields"):
            SensorEvent.from_dict(data)

    def test_invalid_position_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "latitude"):
            GeoPosition(latitude_degrees=91.0, longitude_degrees=0.0)

    def test_invalid_sensor_payload_pair_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Remote ID"):
            create_sensor_event(
                node_id="test-node",
                node_type=NodeType.DEVELOPMENT,
                sensor_id="camera-01",
                sensor_type=SensorType.OPTICAL,
                observed_at=self.observed_at,
                sequence_number=0,
                provenance=Provenance.MEASURED,
                payload=RemoteIdObservationPayload(
                    aircraft_id="RID-TEST",
                    position=GeoPosition(41.0, -87.0),
                ),
            )

    def test_json_is_deterministic(self) -> None:
        event = self._rf_event()

        first = event.to_json()
        second = event.to_json()

        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["event_type"], "rf_detection")

    def _rf_event(self) -> SensorEvent:
        return create_sensor_event(
            node_id="development-01",
            node_type=NodeType.DEVELOPMENT,
            sensor_id="simulator",
            sensor_type=SensorType.SIMULATOR,
            observed_at=self.observed_at,
            sequence_number=1,
            provenance=Provenance.SIMULATED,
            payload=RfDetectionPayload(
                center_frequency_hz=100_000_000,
                bandwidth_hz=20_000,
                peak_power_db=-60.0,
                noise_floor_db=-90.0,
            ),
        )


if __name__ == "__main__":
    unittest.main()
