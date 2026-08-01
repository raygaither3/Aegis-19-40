from pathlib import Path

import numpy as np

from src.aegis.file_source import load_spectrum_csv
from src.aegis.signal_detector import detect_signals, display_results


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
            np.abs(
                frequencies_hz
                - signal["center_frequency_hz"]
            )
            <= signal["bandwidth_hz"] / 2
        )

        power_db[signal_bins] += signal["power_increase_db"]

    spectrum_data = np.column_stack(
        (frequencies_hz, power_db)
    )

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

    print(f"Noise floor: {noise_floor_db:.2f} dB")
    print(f"Threshold:   {threshold_db:.2f} dB")
    print(f"Detections:  {len(detections)}")

    for number, signal in enumerate(detections, start=1):
        print()
        print(f"Signal {number}")
        print(
            f"  Start:       "
            f"{signal.start_frequency_hz / 1e6:.6f} MHz"
        )
        print(
            f"  End:         "
            f"{signal.end_frequency_hz / 1e6:.6f} MHz"
        )
        print(
            f"  Center:      "
            f"{signal.center_frequency_hz / 1e6:.6f} MHz"
        )
        print(
            f"  Bandwidth:   "
            f"{signal.bandwidth_hz / 1e3:.2f} kHz"
        )
        print(
            f"  Peak power:  "
            f"{signal.peak_power_db:.2f} dB"
        )
        print(
            f"  Above noise: "
            f"{signal.power_above_noise_db:.2f} dB"
        )

    display_results(
        frequencies_hz,
        power_db,
        noise_floor_db,
        threshold_db,
        detections,
    )


if __name__ == "__main__":
    main()