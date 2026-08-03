"""End-to-end simulated mission pipeline for Project Aegis."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import math
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from src.aegis.events import (
    GeoPosition,
    NodeType,
    Provenance,
    RemoteIdObservationPayload,
    RfDetectionPayload,
    SensorEvent,
    SensorType,
    create_sensor_event,
)
from src.aegis.recording import (
    EventRecorder,
    RecordingIssue,
    RecordingStatus,
    load_recording,
)
from src.aegis.scenario_simulator import ContactSnapshot, ScanResult
from src.aegis.signal_detector import DetectedSignal
from src.aegis.tracker import SignalTracker, TrackedSignal


SIMULATED_NODE_ID = "sentinel-sim-01"
SIMULATED_OBSERVER = GeoPosition(
    latitude_degrees=41.000000,
    longitude_degrees=-87.000000,
    altitude_m=190.0,
)


class MissionMode(str, Enum):
    READY = "ready"
    SIMULATED = "simulated"
    RECORDING = "recording"
    REPLAY = "replay"


@dataclass(frozen=True)
class MissionFrame:
    scan_result: ScanResult
    observed_at: datetime
    mode: MissionMode
    aircraft_id: str | None
    aircraft_position: GeoPosition | None
    distance_m: float | None
    bearing_degrees: float | None
    heading_degrees: float | None
    speed_mps: float | None
    events: tuple[SensorEvent, ...]


def build_simulated_drone_events() -> tuple[SensorEvent, ...]:
    """Create a fictional Remote ID trajectory and correlated RF activity."""

    start = datetime(2026, 8, 2, 2, 0, tzinfo=timezone.utc)
    events: list[SensorEvent] = []
    for index in range(10):
        observed_at = start + timedelta(seconds=index)
        aircraft_position = GeoPosition(
            latitude_degrees=41.0024 - index * 0.00018,
            longitude_degrees=-87.0020 + index * 0.00011,
            altitude_m=92.0 + index * 1.5,
            horizontal_accuracy_m=4.0,
            vertical_accuracy_m=6.0,
        )
        events.append(
            create_sensor_event(
                event_id=_simulated_event_id("remote-id", index),
                node_id=SIMULATED_NODE_ID,
                node_type=NodeType.SENTINEL,
                sensor_id="remote-id-simulator",
                sensor_type=SensorType.SIMULATOR,
                observed_at=observed_at,
                sequence_number=index,
                provenance=Provenance.SIMULATED,
                payload=RemoteIdObservationPayload(
                    aircraft_id="SIM-AEGIS-001",
                    position=aircraft_position,
                    speed_mps=12.0,
                    heading_degrees=38.0,
                ),
            )
        )

        # One missed RF observation demonstrates fading and reacquisition while
        # Remote ID remains present.
        if index == 6:
            continue
        events.append(
            create_sensor_event(
                event_id=_simulated_event_id("rf", index),
                node_id=SIMULATED_NODE_ID,
                node_type=NodeType.SENTINEL,
                sensor_id="rf-simulator",
                sensor_type=SensorType.SIMULATOR,
                observed_at=observed_at,
                sequence_number=index,
                provenance=Provenance.SIMULATED,
                payload=RfDetectionPayload(
                    center_frequency_hz=2_437_000_000 + index * 1_000,
                    bandwidth_hz=20_000_000,
                    peak_power_db=-67.0 + index * 1.2,
                    noise_floor_db=-92.0,
                ),
            )
        )
    return tuple(events)


def events_to_mission_frames(
    events: tuple[SensorEvent, ...],
    *,
    mode: MissionMode,
    observer_position: GeoPosition = SIMULATED_OBSERVER,
) -> tuple[MissionFrame, ...]:
    """Turn ordered sensor events into tracker and dashboard frames."""

    if mode is MissionMode.READY:
        raise ValueError("mission frames require an active mission mode")
    grouped = _group_events_by_timestamp(events)
    tracker = SignalTracker(frequency_tolerance_hz=25_000)
    frames: list[MissionFrame] = []
    first_time = grouped[0][0] if grouped else None

    for scan_number, (observed_at, frame_events) in enumerate(grouped, start=1):
        detections = [
            _detection_from_event(event)
            for event in frame_events
            if isinstance(event.payload, RfDetectionPayload)
        ]
        elapsed = (
            (observed_at - first_time).total_seconds()
            if first_time is not None
            else 0.0
        )
        tracks = tracker.update(detections, current_time=elapsed)
        remote_id = next(
            (
                event.payload
                for event in frame_events
                if isinstance(event.payload, RemoteIdObservationPayload)
            ),
            None,
        )
        distance: float | None = None
        bearing: float | None = None
        if remote_id is not None:
            distance, bearing = distance_and_bearing(
                observer_position,
                remote_id.position,
            )
        frames.append(
            MissionFrame(
                scan_result=ScanResult(
                    scan_number=scan_number,
                    name=_frame_name(remote_id, detections),
                    timestamp=elapsed,
                    contacts=tuple(
                        _snapshot(track)
                        for track in sorted(
                            tracks, key=lambda item: item.signal_id
                        )
                    ),
                ),
                observed_at=observed_at,
                mode=mode,
                aircraft_id=(
                    remote_id.aircraft_id if remote_id is not None else None
                ),
                aircraft_position=(
                    remote_id.position if remote_id is not None else None
                ),
                distance_m=distance,
                bearing_degrees=bearing,
                heading_degrees=(
                    remote_id.heading_degrees
                    if remote_id is not None
                    else None
                ),
                speed_mps=(
                    remote_id.speed_mps if remote_id is not None else None
                ),
                events=frame_events,
            )
        )
    return tuple(frames)


def distance_and_bearing(
    origin: GeoPosition,
    target: GeoPosition,
) -> tuple[float, float]:
    """Calculate great-circle ground distance and initial bearing."""

    earth_radius_m = 6_371_000.0
    latitude_1 = math.radians(origin.latitude_degrees)
    latitude_2 = math.radians(target.latitude_degrees)
    delta_latitude = latitude_2 - latitude_1
    delta_longitude = math.radians(
        target.longitude_degrees - origin.longitude_degrees
    )
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude_1)
        * math.cos(latitude_2)
        * math.sin(delta_longitude / 2) ** 2
    )
    distance = 2 * earth_radius_m * math.asin(math.sqrt(haversine))
    y = math.sin(delta_longitude) * math.cos(latitude_2)
    x = (
        math.cos(latitude_1) * math.sin(latitude_2)
        - math.sin(latitude_1)
        * math.cos(latitude_2)
        * math.cos(delta_longitude)
    )
    bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return distance, bearing


class MissionController:
    """Own simulation, recording, and replay state without GUI dependencies."""

    def __init__(self) -> None:
        self._frames: tuple[MissionFrame, ...] = ()
        self._index = -1
        self._mode = MissionMode.READY
        self._recorder: EventRecorder | None = None
        self._issues: tuple[RecordingIssue, ...] = ()

    @property
    def current(self) -> MissionFrame | None:
        if self._index < 0:
            return None
        return self._frames[self._index]

    @property
    def mode(self) -> MissionMode:
        return self._mode

    @property
    def issues(self) -> tuple[RecordingIssue, ...]:
        return self._issues

    @property
    def has_next(self) -> bool:
        return self._index + 1 < len(self._frames)

    @property
    def total_frames(self) -> int:
        return len(self._frames)

    def start_simulation(self, recording_directory: str | Path | None = None) -> None:
        self._finish_active_recording(RecordingStatus.INTERRUPTED)
        events = build_simulated_drone_events()
        self._mode = (
            MissionMode.RECORDING
            if recording_directory is not None
            else MissionMode.SIMULATED
        )
        self._frames = events_to_mission_frames(events, mode=self._mode)
        self._index = -1
        self._issues = ()
        if recording_directory is not None:
            path = Path(recording_directory)
            self._recorder = EventRecorder(
                path,
                recording_id=path.name,
                node_id=SIMULATED_NODE_ID,
                created_at=self._frames[0].observed_at,
            )

    def open_recording(self, directory: str | Path) -> None:
        self._finish_active_recording(RecordingStatus.INTERRUPTED)
        loaded = load_recording(directory, strict=False)
        self._mode = MissionMode.REPLAY
        self._frames = events_to_mission_frames(
            loaded.events,
            mode=MissionMode.REPLAY,
        )
        self._index = -1
        self._issues = loaded.issues

    def next_frame(self) -> MissionFrame | None:
        if not self.has_next:
            self._finish_active_recording(RecordingStatus.COMPLETE)
            return None
        self._index += 1
        frame = self._frames[self._index]
        if self._recorder is not None:
            for event in frame.events:
                self._recorder.record(event)
        if not self.has_next:
            self._finish_active_recording(RecordingStatus.COMPLETE)
        return frame

    def stop(self) -> None:
        self._finish_active_recording(RecordingStatus.COMPLETE)
        if self._frames:
            self._index = len(self._frames) - 1

    def reset(self) -> None:
        self._finish_active_recording(RecordingStatus.INTERRUPTED)
        self._frames = ()
        self._index = -1
        self._mode = MissionMode.READY
        self._issues = ()

    def _finish_active_recording(self, status: RecordingStatus) -> None:
        if self._recorder is not None:
            self._recorder.close(status=status)
            self._recorder = None


def _group_events_by_timestamp(
    events: tuple[SensorEvent, ...],
) -> list[tuple[datetime, tuple[SensorEvent, ...]]]:
    grouped: list[tuple[datetime, list[SensorEvent]]] = []
    for event in events:
        if not grouped or grouped[-1][0] != event.observed_at:
            grouped.append((event.observed_at, [event]))
        else:
            grouped[-1][1].append(event)
    return [(timestamp, tuple(items)) for timestamp, items in grouped]


def _detection_from_event(event: SensorEvent) -> DetectedSignal:
    payload = event.payload
    if not isinstance(payload, RfDetectionPayload):
        raise TypeError("event does not contain an RF detection")
    half_bandwidth = payload.bandwidth_hz / 2
    return DetectedSignal(
        start_frequency_hz=payload.center_frequency_hz - half_bandwidth,
        end_frequency_hz=payload.center_frequency_hz + half_bandwidth,
        center_frequency_hz=payload.center_frequency_hz,
        bandwidth_hz=payload.bandwidth_hz,
        peak_power_db=payload.peak_power_db,
        power_above_noise_db=payload.peak_power_db - payload.noise_floor_db,
    )


def _snapshot(track: TrackedSignal) -> ContactSnapshot:
    return ContactSnapshot(
        signal_id=track.signal_id,
        center_frequency_hz=track.center_frequency_hz,
        bandwidth_hz=track.bandwidth_hz,
        peak_power_db=track.peak_power_db,
        confidence=track.confidence,
        state=track.state,
        detection_count=track.detection_count,
        missed_scans=track.missed_scans,
    )


def _frame_name(
    remote_id: RemoteIdObservationPayload | None,
    detections: list[DetectedSignal],
) -> str:
    if remote_id is not None and detections:
        return "Remote ID and correlated RF activity"
    if remote_id is not None:
        return "Remote ID present; RF observation missed"
    if detections:
        return "RF activity without Remote ID"
    return "No observations"


def _simulated_event_id(source: str, sequence: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"aegis:{source}:{sequence}"))
