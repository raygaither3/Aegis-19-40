"""Versioned, hardware-independent event contracts for Project Aegis."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import math
from typing import Any, TypeAlias
from uuid import UUID, uuid4


SCHEMA_VERSION = "1.0"


class NodeType(str, Enum):
    SCOUT = "scout"
    TRACKER = "tracker"
    SENTINEL = "sentinel"
    AIR_NODE = "air_node"
    RELAY = "relay"
    COMMAND = "command"
    DEVELOPMENT = "development"


class SensorType(str, Enum):
    SDR = "sdr"
    REMOTE_ID = "remote_id"
    OPTICAL = "optical"
    THERMAL = "thermal"
    ACOUSTIC = "acoustic"
    GPS = "gps"
    IMU = "imu"
    COMPASS = "compass"
    ENVIRONMENTAL = "environmental"
    SYSTEM = "system"
    SIMULATOR = "simulator"


class Provenance(str, Enum):
    MEASURED = "measured"
    INFERRED = "inferred"
    SIMULATED = "simulated"
    REPLAYED = "replayed"


class DataState(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    OFFLINE = "offline"


class EventType(str, Enum):
    RF_DETECTION = "rf_detection"
    REMOTE_ID_OBSERVATION = "remote_id_observation"
    SENSOR_HEALTH = "sensor_health"


@dataclass(frozen=True)
class GeoPosition:
    latitude_degrees: float
    longitude_degrees: float
    altitude_m: float | None = None
    horizontal_accuracy_m: float | None = None
    vertical_accuracy_m: float | None = None

    def __post_init__(self) -> None:
        _require_finite("latitude_degrees", self.latitude_degrees)
        _require_finite("longitude_degrees", self.longitude_degrees)
        if not -90 <= self.latitude_degrees <= 90:
            raise ValueError("latitude_degrees must be between -90 and 90")
        if not -180 <= self.longitude_degrees <= 180:
            raise ValueError("longitude_degrees must be between -180 and 180")
        _validate_optional_finite("altitude_m", self.altitude_m)
        _validate_optional_nonnegative(
            "horizontal_accuracy_m", self.horizontal_accuracy_m
        )
        _validate_optional_nonnegative(
            "vertical_accuracy_m", self.vertical_accuracy_m
        )


@dataclass(frozen=True)
class RfDetectionPayload:
    center_frequency_hz: float
    bandwidth_hz: float
    peak_power_db: float
    noise_floor_db: float

    def __post_init__(self) -> None:
        _require_positive("center_frequency_hz", self.center_frequency_hz)
        _require_nonnegative("bandwidth_hz", self.bandwidth_hz)
        _require_finite("peak_power_db", self.peak_power_db)
        _require_finite("noise_floor_db", self.noise_floor_db)


@dataclass(frozen=True)
class RemoteIdObservationPayload:
    aircraft_id: str
    position: GeoPosition
    speed_mps: float | None = None
    heading_degrees: float | None = None
    operator_position: GeoPosition | None = None

    def __post_init__(self) -> None:
        if not self.aircraft_id.strip():
            raise ValueError("aircraft_id cannot be empty")
        _validate_optional_nonnegative("speed_mps", self.speed_mps)
        if self.heading_degrees is not None:
            _require_finite("heading_degrees", self.heading_degrees)
            if not 0 <= self.heading_degrees < 360:
                raise ValueError(
                    "heading_degrees must be greater than or equal to 0 "
                    "and less than 360"
                )


@dataclass(frozen=True)
class SensorHealthPayload:
    status: HealthStatus
    message: str = ""


EventPayload: TypeAlias = (
    RfDetectionPayload
    | RemoteIdObservationPayload
    | SensorHealthPayload
)


@dataclass(frozen=True)
class SensorEvent:
    """Immutable event envelope shared by local and networked modules."""

    event_id: str
    node_id: str
    node_type: NodeType
    sensor_id: str
    sensor_type: SensorType
    observed_at: datetime
    sequence_number: int
    provenance: Provenance
    data_state: DataState
    payload: EventPayload
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema version: {self.schema_version}"
            )
        try:
            UUID(self.event_id)
        except (ValueError, AttributeError) as error:
            raise ValueError("event_id must be a valid UUID") from error
        if not self.node_id.strip():
            raise ValueError("node_id cannot be empty")
        if not self.sensor_id.strip():
            raise ValueError("sensor_id cannot be empty")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must include timezone information")
        if self.sequence_number < 0:
            raise ValueError("sequence_number cannot be negative")
        _validate_sensor_payload_pair(self.sensor_type, self.payload)

    @property
    def event_type(self) -> EventType:
        return _event_type_for_payload(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type.value,
            "observed_at": _format_utc(self.observed_at),
            "sequence_number": self.sequence_number,
            "provenance": self.provenance.value,
            "data_state": self.data_state.value,
            "payload": _payload_to_dict(self.payload),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
            separators=None if indent is not None else (",", ":"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SensorEvent":
        required_fields = {
            "schema_version",
            "event_id",
            "event_type",
            "node_id",
            "node_type",
            "sensor_id",
            "sensor_type",
            "observed_at",
            "sequence_number",
            "provenance",
            "data_state",
            "payload",
        }
        missing = required_fields - data.keys()
        if missing:
            raise ValueError(f"event is missing fields: {sorted(missing)}")
        if data["schema_version"] != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema version: {data['schema_version']}"
            )
        event_type = EventType(data["event_type"])
        payload_data = data["payload"]
        if not isinstance(payload_data, dict):
            raise ValueError("payload must be an object")
        payload = _payload_from_dict(event_type, payload_data)
        return cls(
            schema_version=data["schema_version"],
            event_id=data["event_id"],
            node_id=data["node_id"],
            node_type=NodeType(data["node_type"]),
            sensor_id=data["sensor_id"],
            sensor_type=SensorType(data["sensor_type"]),
            observed_at=_parse_timestamp(data["observed_at"]),
            sequence_number=data["sequence_number"],
            provenance=Provenance(data["provenance"]),
            data_state=DataState(data["data_state"]),
            payload=payload,
        )

    @classmethod
    def from_json(cls, value: str) -> "SensorEvent":
        data = json.loads(value)
        if not isinstance(data, dict):
            raise ValueError("event JSON must contain an object")
        return cls.from_dict(data)


def create_sensor_event(
    *,
    node_id: str,
    node_type: NodeType,
    sensor_id: str,
    sensor_type: SensorType,
    observed_at: datetime,
    sequence_number: int,
    provenance: Provenance,
    payload: EventPayload,
    data_state: DataState = DataState.CURRENT,
    event_id: str | None = None,
) -> SensorEvent:
    """Create a validated event while generating its identifier if needed."""

    return SensorEvent(
        event_id=str(uuid4()) if event_id is None else event_id,
        node_id=node_id,
        node_type=node_type,
        sensor_id=sensor_id,
        sensor_type=sensor_type,
        observed_at=observed_at,
        sequence_number=sequence_number,
        provenance=provenance,
        data_state=data_state,
        payload=payload,
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event_type_for_payload(payload: EventPayload) -> EventType:
    if isinstance(payload, RfDetectionPayload):
        return EventType.RF_DETECTION
    if isinstance(payload, RemoteIdObservationPayload):
        return EventType.REMOTE_ID_OBSERVATION
    if isinstance(payload, SensorHealthPayload):
        return EventType.SENSOR_HEALTH
    raise TypeError(f"unsupported payload type: {type(payload).__name__}")


def _payload_to_dict(payload: EventPayload) -> dict[str, Any]:
    data = asdict(payload)
    if isinstance(payload, SensorHealthPayload):
        data["status"] = payload.status.value
    return data


def _payload_from_dict(
    event_type: EventType,
    data: dict[str, Any],
) -> EventPayload:
    if event_type is EventType.RF_DETECTION:
        return RfDetectionPayload(**data)
    if event_type is EventType.REMOTE_ID_OBSERVATION:
        event_data = data.copy()
        event_data["position"] = GeoPosition(**event_data["position"])
        operator_position = event_data.get("operator_position")
        if operator_position is not None:
            event_data["operator_position"] = GeoPosition(**operator_position)
        return RemoteIdObservationPayload(**event_data)
    if event_type is EventType.SENSOR_HEALTH:
        event_data = data.copy()
        event_data["status"] = HealthStatus(event_data["status"])
        return SensorHealthPayload(**event_data)
    raise ValueError(f"unsupported event type: {event_type.value}")


def _validate_sensor_payload_pair(
    sensor_type: SensorType,
    payload: EventPayload,
) -> None:
    if isinstance(payload, RfDetectionPayload) and sensor_type not in {
        SensorType.SDR,
        SensorType.SIMULATOR,
    }:
        raise ValueError("RF detections require an SDR or simulator sensor")
    if (
        isinstance(payload, RemoteIdObservationPayload)
        and sensor_type not in {SensorType.REMOTE_ID, SensorType.SIMULATOR}
    ):
        raise ValueError(
            "Remote ID observations require a Remote ID or simulator sensor"
        )


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("observed_at must be a timestamp string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("observed_at must be an ISO 8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include timezone information")
    return parsed


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _require_nonnegative(name: str, value: float) -> None:
    _require_finite(name, value)
    if value < 0:
        raise ValueError(f"{name} cannot be negative")


def _require_positive(name: str, value: float) -> None:
    _require_finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _validate_optional_finite(name: str, value: float | None) -> None:
    if value is not None:
        _require_finite(name, value)


def _validate_optional_nonnegative(name: str, value: float | None) -> None:
    if value is not None:
        _require_nonnegative(name, value)
