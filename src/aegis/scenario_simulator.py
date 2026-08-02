from dataclasses import dataclass

from src.aegis.signal_detector import DetectedSignal
from src.aegis.tracker import SignalTracker, TrackState, TrackedSignal


@dataclass(frozen=True)
class ScenarioScan:
    """One timestamped set of detections in a simulated scenario."""

    name: str
    timestamp: float
    detections: tuple[DetectedSignal, ...]


@dataclass(frozen=True)
class ContactSnapshot:
    """Immutable contact data suitable for logs or a future GUI."""

    signal_id: int
    center_frequency_hz: float
    bandwidth_hz: float
    peak_power_db: float
    confidence: float
    state: TrackState
    detection_count: int
    missed_scans: int


@dataclass(frozen=True)
class ScanResult:
    scan_number: int
    name: str
    timestamp: float
    contacts: tuple[ContactSnapshot, ...]


def make_detection(
    center_frequency_hz: float,
    bandwidth_hz: float = 20_000,
    peak_power_db: float = -60.0,
    noise_floor_db: float = -90.0,
) -> DetectedSignal:
    """Create a deterministic detection for a simulated scan."""

    return DetectedSignal(
        start_frequency_hz=center_frequency_hz - bandwidth_hz / 2,
        end_frequency_hz=center_frequency_hz + bandwidth_hz / 2,
        center_frequency_hz=center_frequency_hz,
        bandwidth_hz=bandwidth_hz,
        peak_power_db=peak_power_db,
        power_above_noise_db=peak_power_db - noise_floor_db,
    )


def build_demo_scenario() -> tuple[ScenarioScan, ...]:
    """Build scans containing persistence, drift, noise, and dropout."""

    return (
        ScenarioScan(
            name="Initial contacts and one-scan noise",
            timestamp=0.0,
            detections=(
                make_detection(100_180_000, peak_power_db=-62.0),
                make_detection(100_520_000, peak_power_db=-55.0),
                make_detection(100_840_000, peak_power_db=-72.0),
            ),
        ),
        ScenarioScan(
            name="Persistent contacts drift; noise disappears",
            timestamp=1.0,
            detections=(
                make_detection(100_184_000, peak_power_db=-61.0),
                make_detection(100_516_000, peak_power_db=-56.0),
            ),
        ),
        ScenarioScan(
            name="Second contact drops out",
            timestamp=2.0,
            detections=(
                make_detection(100_188_000, peak_power_db=-60.0),
            ),
        ),
        ScenarioScan(
            name="Dropped contact returns within tolerance",
            timestamp=3.0,
            detections=(
                make_detection(100_192_000, peak_power_db=-59.0),
                make_detection(100_521_000, peak_power_db=-57.0),
            ),
        ),
        ScenarioScan(
            name="Both persistent contacts continue",
            timestamp=4.0,
            detections=(
                make_detection(100_196_000, peak_power_db=-58.0),
                make_detection(100_525_000, peak_power_db=-56.0),
            ),
        ),
    )


def run_scenario(
    scans: tuple[ScenarioScan, ...],
    tracker: SignalTracker | None = None,
) -> tuple[ScanResult, ...]:
    """Run a scenario and preserve the result of every individual scan."""

    active_tracker = tracker if tracker is not None else SignalTracker()
    results: list[ScanResult] = []

    for scan_number, scan in enumerate(scans, start=1):
        tracks = active_tracker.update(
            list(scan.detections),
            current_time=scan.timestamp,
        )
        contacts = tuple(
            _snapshot(track)
            for track in sorted(tracks, key=lambda item: item.signal_id)
        )
        results.append(
            ScanResult(
                scan_number=scan_number,
                name=scan.name,
                timestamp=scan.timestamp,
                contacts=contacts,
            )
        )

    return tuple(results)


def format_scan_result(result: ScanResult) -> str:
    """Format one scan as a readable contact table."""

    lines = [
        f"Scan {result.scan_number}: {result.name}",
        "ID  Frequency     Confidence  State      Seen  Missed",
        "--  ------------  ----------  ---------  ----  ------",
    ]

    if not result.contacts:
        lines.append("No active contacts")
        return "\n".join(lines)

    for contact in result.contacts:
        lines.append(
            f"{contact.signal_id:<2}  "
            f"{contact.center_frequency_hz / 1e6:>10.3f} MHz  "
            f"{contact.confidence:>8.1f}%  "
            f"{contact.state.value.upper():<9}  "
            f"{contact.detection_count:>4}  "
            f"{contact.missed_scans:>6}"
        )

    return "\n".join(lines)


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


def main() -> None:
    print("Project Aegis - Multi-Scan Contact Scenario")
    print()

    for result in run_scenario(build_demo_scenario()):
        print(format_scan_result(result))
        print()


if __name__ == "__main__":
    main()
