from dataclasses import dataclass
import time

from src.aegis.signal_detector import DetectedSignal


@dataclass
class TrackedSignal:

    signal_id: int

    center_frequency_hz: float
    bandwidth_hz: float
    peak_power_db: float

    first_seen: float
    last_seen: float

    detection_count: int = 1

    confidence: float = 10.0

    @property
    def age_seconds(self) -> float:
        return self.last_seen - self.first_seen


class SignalTracker:
    def __init__(
        self,
        frequency_tolerance_hz: float = 25_000,
    ) -> None:
        self.frequency_tolerance_hz = frequency_tolerance_hz
        self._next_signal_id = 1
        self._tracks: list[TrackedSignal] = []

    @property
    def tracks(self) -> list[TrackedSignal]:
        return self._tracks.copy()

    def update(
        self,
        detections: list[DetectedSignal],
    ) -> list[TrackedSignal]:
        current_time = time.monotonic()

        for detection in detections:
            matching_track = self._find_matching_track(detection)

            if matching_track is None:
                self._create_track(
                    detection,
                    current_time,
                )
            else:
                self._update_track(
                    matching_track,
                    detection,
                    current_time,
                )

        return self.tracks

    def _find_matching_track(
        self,
        detection: DetectedSignal,
    ) -> TrackedSignal | None:
        closest_track: TrackedSignal | None = None
        smallest_difference_hz = float("inf")

        for track in self._tracks:
            frequency_difference_hz = abs(
                track.center_frequency_hz
                - detection.center_frequency_hz
            )

            if (
                frequency_difference_hz
                <= self.frequency_tolerance_hz
                and frequency_difference_hz
                < smallest_difference_hz
            ):
                closest_track = track
                smallest_difference_hz = frequency_difference_hz

        return closest_track

    def _create_track(
        self,
        detection: DetectedSignal,
        current_time: float,
    ) -> TrackedSignal:
        track = TrackedSignal(
            signal_id=self._next_signal_id,
            center_frequency_hz=detection.center_frequency_hz,
            bandwidth_hz=detection.bandwidth_hz,
            peak_power_db=detection.peak_power_db,
            first_seen=current_time,
            last_seen=current_time,
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
        track.confidence = min(
        100.0,
        track.confidence + 5.0,
    )