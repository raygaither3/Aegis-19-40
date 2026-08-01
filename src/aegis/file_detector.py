from pathlib import Path
import time

import numpy as np

from src.aegis.file_source import load_spectrum_csv
from src.aegis.signal_detector import detect_signals, display_results
from src.aegis.tracker import SignalTracker


def create_sample_spectrum_csv(file_path: str | Path) -> None:
    """
    Create a sample recorded spectrum and save it as a CSV file.
    """

    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frequencies_hz = np.linspace(
        100_000_000,
        101_000_000,
        1024,
        endpoint=False,
    )

    random_generator = np.random.default_rng(seed=19)

    power_db = random_generator.normal(
        loc=-90.0,
        scale=2.0,
        size=len(frequencies_hz),
    )

    simulated_signals = [
        {
            "center_frequency_hz": 100_180_000,
            "bandwidth_hz": 60_000,
            "power_increase_db": 22.0,
        },
        {
            "center_frequency_hz": 100_520_000,
            "bandwidth_hz": 180_000,
            "power_increase_db": 35.0,
        },
        {
            "center_frequency_hz": 100_840_000,
            "bandwidth_hz": 90_000,
            "power_increase_db": 27.0,
        },
    ]

    for signal in simulated_signals:
        signal_bins = (
            np.abs(frequencies_hz - signal["center_frequency_hz"])
            <= signal["bandwidth_hz"] / 2
        )

        power_db[signal_bins] += signal["power_increase_db"]

    spectrum_data = np.column_stack((frequencies_hz, power_db))

    np.savetxt(
        output_path,
        spectrum_data,
        delimiter=",",
        header="frequency_hz,power_db",
        comments="",
        fmt=["%.2f", "%.4f"],
    )

    print(f"Created spectrum file: {output_path}")


def main() -> None:
    print("Project Aegis — File Spectrum Detector")
    print()

    file_path = Path("data/sample_spectrum.csv")

    create_sample_spectrum_csv(file_path)

    print("Loading spectrum file...")

    frequencies_hz, power_db = load_spectrum_csv(file_path)

    print(f"Loaded {len(frequencies_hz)} frequency bins.")
    print()

    noise_floor_db, threshold_db, detections = detect_signals(
        frequencies_hz,
        power_db,
        threshold_above_noise_db=10.0,
    )

    tracker = SignalTracker(
        frequency_tolerance_hz=25_000,
    )

    print()
    print("Tracker scan 1")

    tracked_signals = tracker.update(detections)

    for track in tracked_signals:
        print(f"Track #{track.signal_id}")
        print(
            f"  Frequency:   "
            f"{track.center_frequency_hz / 1e6:.6f} MHz"
        )
        print(
            f"  Seen:        "
            f"{track.detection_count} time(s)"
        )
        print(
            f"  Age:         "
            f"{track.age_seconds:.2f} seconds"
        )
        print(
            f"  Confidence:  "
            f"{track.confidence:.1f}%"
        )
        print()

    time.sleep(1.0)

    print()
    print("Tracker scan 2")

    second_scan_detections = []

    for detection in detections:
        shifted_detection = type(detection)(
            start_frequency_hz=(
                detection.start_frequency_hz + 5_000
            ),
            end_frequency_hz=(
                detection.end_frequency_hz + 5_000
            ),
            center_frequency_hz=(
                detection.center_frequency_hz + 5_000
            ),
            bandwidth_hz=detection.bandwidth_hz,
            peak_power_db=detection.peak_power_db - 1.0,
            power_above_noise_db=(
                detection.power_above_noise_db - 1.0
            ),
        )

        second_scan_detections.append(shifted_detection)

    tracked_signals = tracker.update(
        second_scan_detections
    )

    for track in tracked_signals:
        print(
            f"Track #{track.signal_id}: "
            f"{track.center_frequency_hz / 1e6:.6f} MHz, "
            f"seen {track.detection_count} time(s), "
            f"age {track.age_seconds:.2f} seconds"
        )

    print(f"Noise floor: {noise_floor_db:.2f} dB")
    print(f"Threshold:   {threshold_db:.2f} dB")
    print()
    print(f"Detected {len(detections)} signals:")

    # Display the strongest signals first.
    sorted_detections = sorted(
        detections,
        key=lambda signal: signal.peak_power_db,
        reverse=True,
    )

    for number, signal in enumerate(sorted_detections, start=1):
        print()
        print(f"Signal {number}")
        print(f"  Center:      " f"{signal.center_frequency_hz / 1e6:.6f} MHz")
        print(
            f"  Range:       "
            f"{signal.start_frequency_hz / 1e6:.6f}–"
            f"{signal.end_frequency_hz / 1e6:.6f} MHz"
        )
        print(f"  Bandwidth:   " f"{signal.bandwidth_hz / 1e3:.2f} kHz")
        print(f"  Peak power:  " f"{signal.peak_power_db:.2f} dB")
        print(f"  SNR:         " f"{signal.power_above_noise_db:.2f} dB")

    try:    
            display_results(
                frequencies_hz,
                power_db,
                noise_floor_db,
                threshold_db,
                detections,
            )
    except KeyboardInterrupt:
        print()
        print("Project Aegis stopped by user.")


if __name__ == "__main__":
    main()
