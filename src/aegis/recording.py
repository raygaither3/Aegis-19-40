"""Segmented recording and deterministic playback for Aegis events."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import time
from typing import Any, TextIO

from src.aegis.events import SCHEMA_VERSION, SensorEvent, utc_now


RECORDING_FORMAT_VERSION = "1.0"


class RecordingStatus(str, Enum):
    RECORDING = "recording"
    COMPLETE = "complete"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class RecordingManifest:
    format_version: str
    event_schema_version: str
    recording_id: str
    node_id: str
    created_at: datetime
    closed_at: datetime | None
    status: RecordingStatus
    event_count: int
    segments: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "event_schema_version": self.event_schema_version,
            "recording_id": self.recording_id,
            "node_id": self.node_id,
            "created_at": _format_utc(self.created_at),
            "closed_at": (
                _format_utc(self.closed_at)
                if self.closed_at is not None
                else None
            ),
            "status": self.status.value,
            "event_count": self.event_count,
            "segments": list(self.segments),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecordingManifest":
        required = {
            "format_version",
            "event_schema_version",
            "recording_id",
            "node_id",
            "created_at",
            "closed_at",
            "status",
            "event_count",
            "segments",
        }
        missing = required - data.keys()
        if missing:
            raise ValueError(f"manifest is missing fields: {sorted(missing)}")
        if data["format_version"] != RECORDING_FORMAT_VERSION:
            raise ValueError(
                "unsupported recording format version: "
                f"{data['format_version']}"
            )
        if data["event_schema_version"] != SCHEMA_VERSION:
            raise ValueError(
                "unsupported event schema version: "
                f"{data['event_schema_version']}"
            )
        if not isinstance(data["segments"], list):
            raise ValueError("manifest segments must be a list")
        if not isinstance(data["event_count"], int) or data["event_count"] < 0:
            raise ValueError("manifest event_count must be a nonnegative integer")
        return cls(
            format_version=data["format_version"],
            event_schema_version=data["event_schema_version"],
            recording_id=data["recording_id"],
            node_id=data["node_id"],
            created_at=_parse_timestamp(data["created_at"]),
            closed_at=(
                _parse_timestamp(data["closed_at"])
                if data["closed_at"] is not None
                else None
            ),
            status=RecordingStatus(data["status"]),
            event_count=data["event_count"],
            segments=tuple(data["segments"]),
        )


@dataclass(frozen=True)
class RecordingIssue:
    segment: str
    line_number: int
    message: str


@dataclass(frozen=True)
class LoadedRecording:
    manifest: RecordingManifest
    events: tuple[SensorEvent, ...]
    issues: tuple[RecordingIssue, ...]


class RecordingReadError(ValueError):
    pass


class EventRecorder:
    """Write events to bounded JSON Lines segments with an atomic manifest."""

    def __init__(
        self,
        directory: str | Path,
        *,
        recording_id: str,
        node_id: str,
        max_events_per_segment: int = 1_000,
        created_at: datetime | None = None,
        durable_writes: bool = False,
    ) -> None:
        if not recording_id.strip():
            raise ValueError("recording_id cannot be empty")
        if not node_id.strip():
            raise ValueError("node_id cannot be empty")
        if max_events_per_segment <= 0:
            raise ValueError("max_events_per_segment must be positive")

        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.recording_id = recording_id
        self.node_id = node_id
        self.max_events_per_segment = max_events_per_segment
        self.durable_writes = durable_writes
        self.created_at = created_at if created_at is not None else utc_now()
        _require_timezone("created_at", self.created_at)

        self._event_count = 0
        self._segments: list[str] = []
        self._segment_event_count = 0
        self._segment_file: TextIO | None = None
        self._closed = False
        self._write_manifest(RecordingStatus.RECORDING, closed_at=None)

    def __enter__(self) -> "EventRecorder":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        status = (
            RecordingStatus.COMPLETE
            if exc_type is None
            else RecordingStatus.INTERRUPTED
        )
        self.close(status=status)

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def is_closed(self) -> bool:
        return self._closed

    def record(self, event: SensorEvent) -> None:
        if self._closed:
            raise RuntimeError("cannot record events after recorder is closed")
        if event.node_id != self.node_id:
            raise ValueError(
                f"event node_id {event.node_id!r} does not match "
                f"recording node_id {self.node_id!r}"
            )
        if (
            self._segment_file is None
            or self._segment_event_count >= self.max_events_per_segment
        ):
            self._open_next_segment()

        assert self._segment_file is not None
        self._segment_file.write(event.to_json())
        self._segment_file.write("\n")
        self._segment_file.flush()
        if self.durable_writes:
            import os

            os.fsync(self._segment_file.fileno())
        self._segment_event_count += 1
        self._event_count += 1

    def close(
        self,
        *,
        status: RecordingStatus = RecordingStatus.COMPLETE,
        closed_at: datetime | None = None,
    ) -> None:
        if self._closed:
            return
        if status is RecordingStatus.RECORDING:
            raise ValueError("a closed recording cannot have recording status")
        if self._segment_file is not None:
            self._segment_file.flush()
            self._segment_file.close()
            self._segment_file = None
        final_time = closed_at if closed_at is not None else utc_now()
        _require_timezone("closed_at", final_time)
        self._write_manifest(status, closed_at=final_time)
        self._closed = True

    def _open_next_segment(self) -> None:
        if self._segment_file is not None:
            self._segment_file.flush()
            self._segment_file.close()
        name = f"segment-{len(self._segments) + 1:06d}.jsonl"
        self._segments.append(name)
        self._segment_event_count = 0
        self._segment_file = (self.directory / name).open(
            "x", encoding="utf-8", newline="\n"
        )
        self._write_manifest(RecordingStatus.RECORDING, closed_at=None)

    def _write_manifest(
        self,
        status: RecordingStatus,
        *,
        closed_at: datetime | None,
    ) -> None:
        manifest = RecordingManifest(
            format_version=RECORDING_FORMAT_VERSION,
            event_schema_version=SCHEMA_VERSION,
            recording_id=self.recording_id,
            node_id=self.node_id,
            created_at=self.created_at,
            closed_at=closed_at,
            status=status,
            event_count=self._event_count,
            segments=tuple(self._segments),
        )
        temporary = self.directory / "manifest.json.tmp"
        final = self.directory / "manifest.json"
        temporary.write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(final)


def load_recording(
    directory: str | Path,
    *,
    strict: bool = True,
) -> LoadedRecording:
    """Load and validate a recording, optionally recovering valid events."""

    root = Path(directory)
    manifest_path = root / "manifest.json"
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RecordingReadError(f"cannot read manifest: {error}") from error
    if not isinstance(raw_manifest, dict):
        raise RecordingReadError("manifest must contain a JSON object")
    try:
        manifest = RecordingManifest.from_dict(raw_manifest)
    except (TypeError, ValueError) as error:
        raise RecordingReadError(f"invalid manifest: {error}") from error

    events: list[SensorEvent] = []
    issues: list[RecordingIssue] = []
    for segment_name in manifest.segments:
        _validate_segment_name(segment_name)
        segment_path = root / segment_name
        try:
            lines = segment_path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            issue = RecordingIssue(segment_name, 0, f"cannot read: {error}")
            if strict:
                raise RecordingReadError(_format_issue(issue)) from error
            issues.append(issue)
            continue
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                events.append(SensorEvent.from_json(line))
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                issue = RecordingIssue(
                    segment_name,
                    line_number,
                    f"invalid event: {error}",
                )
                if strict:
                    raise RecordingReadError(_format_issue(issue)) from error
                issues.append(issue)

    if len(events) != manifest.event_count:
        issue = RecordingIssue(
            "manifest.json",
            0,
            f"event count is {len(events)}, manifest reports "
            f"{manifest.event_count}",
        )
        if strict:
            raise RecordingReadError(_format_issue(issue))
        issues.append(issue)

    return LoadedRecording(
        manifest=manifest,
        events=tuple(events),
        issues=tuple(issues),
    )


class EventReplayer:
    """Replay already-validated events in their recorded order."""

    def __init__(
        self,
        events: Iterable[SensorEvent],
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.events = tuple(events)
        self._sleep = sleep

    def replay(
        self,
        consumer: Callable[[SensorEvent], None],
        *,
        speed: float = 0.0,
    ) -> int:
        """Replay events; speed 0 disables waiting, 1 preserves event timing."""

        if speed < 0:
            raise ValueError("speed cannot be negative")
        previous_time: datetime | None = None
        for event in self.events:
            if speed > 0 and previous_time is not None:
                delay = max(
                    0.0,
                    (event.observed_at - previous_time).total_seconds() / speed,
                )
                if delay > 0:
                    self._sleep(delay)
            consumer(event)
            previous_time = event.observed_at
        return len(self.events)


def _validate_segment_name(name: str) -> None:
    path = Path(name)
    if path.name != name or path.suffix != ".jsonl":
        raise RecordingReadError(f"invalid segment name: {name!r}")


def _format_issue(issue: RecordingIssue) -> str:
    location = issue.segment
    if issue.line_number:
        location += f":{issue.line_number}"
    return f"{location}: {issue.message}"


def _require_timezone(name: str, value: datetime) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{name} must include timezone information")


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    _require_timezone("timestamp", parsed)
    return parsed
