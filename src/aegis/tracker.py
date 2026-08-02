from dataclasses import dataclass
from enum import Enum
import time

from src.aegis.signal_detector import DetectedSignal


class TrackState(str, Enum):
    """Lifecycle state for a tracked RF contact."""

    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    FADING = "fading"


@dataclass
class TrackedSignal:
    signal_id: int
    center_frequency_hz: float
    bandwidth_hz: float
    peak_power_db: float
    first_seen: float
    last_seen: float
    detection_count: int = 1
    missed_scans: int = 0
    confidence: float = 20.0
    state: TrackState = TrackState.TENTATIVE

    @property
    def age_seconds(self) -> float:
        return self.last_seen - self.first_seen


class SignalTracker:
    """Associate detections across scans and manage contact confidence."""

    def __init__(
        self,
        frequency_tolerance_hz: float = 25_000,
        initial_confidence: float = 20.0,
        confidence_gain: float = 20.0,
        confidence_decay: float = 15.0,
        confirmation_threshold: float = 60.0,
        max_missed_scans: int = 3,
    ) -> None:
        if frequency_tolerance_hz < 0:
            raise ValueError("frequency_tolerance_hz cannot be negative")
        if not 0 <= initial_confidence <= 100:
            raise ValueError("initial_confidence must be between 0 and 100")
        if confidence_gain < 0 or confidence_decay < 0:
            raise ValueError("confidence gain and decay cannot be negative")
        if not 0 <= confirmation_threshold <= 100:
            raise ValueError("confirmation_threshold must be between 0 and 100")
        if max_missed_scans < 0:
            raise ValueError("max_missed_scans cannot be negative")

        self.frequency_tolerance_hz = frequency_tolerance_hz
        self.initial_confidence = initial_confidence
        self.confidence_gain = confidence_gain
        self.confidence_decay = confidence_decay
        self.confirmation_threshold = confirmation_threshold
        self.max_missed_scans = max_missed_scans
        self._next_signal_id = 1
        self._tracks: list[TrackedSignal] = []

    @property
    def tracks(self) -> list[TrackedSignal]:
        return self._tracks.copy()

    def update(
        self,
        detections: list[DetectedSignal],
        current_time: float | None = None,
    ) -> list[TrackedSignal]:
        """Process one complete scan and return all active contacts."""

        scan_time = time.monotonic() if current_time is None else current_time
        matches = self._match_detections(detections)
        matched_track_ids = {track.signal_id for track, _ in matches}
        matched_detection_indexes = {
            detection_index for _, detection_index in matches
        }

        for track, detection_index in matches:
            self._update_track(track, detections[detection_index], scan_time)

        for track in self._tracks:
            if track.signal_id not in matched_track_ids:
                self._mark_missed(track)

        for index, detection in enumerate(detections):
            if index not in matched_detection_indexes:
                self._create_track(detection, scan_time)

        self._tracks = [
            track
            for track in self._tracks
            if track.confidence > 0
            and track.missed_scans <= self.max_missed_scans
        ]
        return self.tracks

    def _match_detections(
        self,
        detections: list[DetectedSignal],
    ) -> list[tuple[TrackedSignal, int]]:
        candidates: list[tuple[float, int, int]] = []

        for track_index, track in enumerate(self._tracks):
            for detection_index, detection in enumerate(detections):
                difference_hz = abs(
                    track.center_frequency_hz
                    - detection.center_frequency_hz
                )
                if difference_hz <= self.frequency_tolerance_hz:
                    candidates.append(
                        (difference_hz, track_index, detection_index)
                    )

        matches: list[tuple[TrackedSignal, int]] = []
        used_tracks: set[int] = set()
        used_detections: set[int] = set()

        for _, track_index, detection_index in sorted(candidates):
            if (
                track_index in used_tracks
                or detection_index in used_detections
            ):
                continue
            used_tracks.add(track_index)
            used_detections.add(detection_index)
            matches.append((self._tracks[track_index], detection_index))

        return matches

    def _create_track(
        self,
        detection: DetectedSignal,
        current_time: float,
    ) -> TrackedSignal:
        state = self._state_for_confidence(self.initial_confidence)
        track = TrackedSignal(
            signal_id=self._next_signal_id,
            center_frequency_hz=detection.center_frequency_hz,
            bandwidth_hz=detection.bandwidth_hz,
            peak_power_db=detection.peak_power_db,
            first_seen=current_time,
            last_seen=current_time,
            confidence=self.initial_confidence,
            state=state,
        )
        self._tracks.append(track)
        self._next_signal_id += 1
        return track

    def _update_track(
        self,
        track: TrackedSignal,
        detection: DetectedSignal,
        current_time: float,
    ) -> None:
        track.center_frequency_hz = detection.center_frequency_hz
        track.bandwidth_hz = detection.bandwidth_hz
        track.peak_power_db = detection.peak_power_db
        track.last_seen = current_time
        track.detection_count += 1
        track.missed_scans = 0
        track.confidence = min(
            100.0,
            track.confidence + self.confidence_gain,
        )
        track.state = self._state_for_confidence(track.confidence)

    def _mark_missed(self, track: TrackedSignal) -> None:
        track.missed_scans += 1
        track.confidence = max(
            0.0,
            track.confidence - self.confidence_decay,
        )
        track.state = TrackState.FADING

    def _state_for_confidence(self, confidence: float) -> TrackState:
        if confidence >= self.confirmation_threshold:
            return TrackState.CONFIRMED
        return TrackState.TENTATIVE
