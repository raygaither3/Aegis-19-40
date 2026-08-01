from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np


@dataclass
class DetectedSignal:
    start_frequency_hz: float
    end_frequency_hz: float
    center_frequency_hz: float
    bandwidth_hz: float
    peak_power_db: float
    power_above_noise_db: float


def generate_test_spectrum() -> tuple[np.ndarray, np.ndarray]:
    """
    Create a simulated spectrum from 100 MHz to 101 MHz.

    It contains:
    - random background noise
    - three simulated RF signals
    """

    start_frequency_hz = 100_000_000
    stop_frequency_hz = 101_000_000
    number_of_bins = 1024

    frequencies_hz = np.linspace(
        start_frequency_hz,
        stop_frequency_hz,
        number_of_bins,
        endpoint=False,
    )

    random_generator = np.random.default_rng(seed=19)

    power_db = random_generator.normal(
        loc=-90.0,
        scale=2.0,
        size=number_of_bins,
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

    return frequencies_hz, power_db


def estimate_noise_floor(power_db: np.ndarray) -> float:
    """
    Estimate the background power using the median.
    """

    return float(np.median(power_db))


def detect_signals(
    frequencies_hz: np.ndarray,
    power_db: np.ndarray,
    threshold_above_noise_db: float = 10.0,
) -> tuple[float, float, list[DetectedSignal]]:
    """
    Detect groups of neighboring frequency bins above the threshold.
    """

    noise_floor_db = estimate_noise_floor(power_db)
    threshold_db = noise_floor_db + threshold_above_noise_db

    active_bins = power_db > threshold_db
    bin_width_hz = frequencies_hz[1] - frequencies_hz[0]

    detections: list[DetectedSignal] = []
    region_start: int | None = None

    for index, is_active in enumerate(active_bins):
        if is_active and region_start is None:
            region_start = index

        region_has_ended = (
            region_start is not None
            and (
                not is_active
                or index == len(active_bins) - 1
            )
        )

        if not region_has_ended:
            continue

        region_end = index if is_active else index - 1

        region_power = power_db[region_start : region_end + 1]
        peak_offset = int(np.argmax(region_power))
        peak_index = region_start + peak_offset

        start_frequency_hz = frequencies_hz[region_start]
        end_frequency_hz = frequencies_hz[region_end] + bin_width_hz
        center_frequency_hz = (
            start_frequency_hz + end_frequency_hz
        ) / 2

        detections.append(
            DetectedSignal(
                start_frequency_hz=float(start_frequency_hz),
                end_frequency_hz=float(end_frequency_hz),
                center_frequency_hz=float(center_frequency_hz),
                bandwidth_hz=float(
                    end_frequency_hz - start_frequency_hz
                ),
                peak_power_db=float(power_db[peak_index]),
                power_above_noise_db=float(
                    power_db[peak_index] - noise_floor_db
                ),
            )
        )

        region_start = None

    return noise_floor_db, threshold_db, detections


def display_results(
    frequencies_hz: np.ndarray,
    power_db: np.ndarray,
    noise_floor_db: float,
    threshold_db: float,
    detections: list[DetectedSignal],
) -> None:
    frequencies_mhz = frequencies_hz / 1_000_000

    plt.figure(figsize=(12, 6))
    plt.plot(
        frequencies_mhz,
        power_db,
        label="Simulated spectrum",
    )

    plt.axhline(
        noise_floor_db,
        linestyle="--",
        label="Estimated noise floor",
    )

    plt.axhline(
        threshold_db,
        linestyle="--",
        label="Detection threshold",
    )

    for signal_number, signal in enumerate(detections, start=1):
        plt.axvspan(
            signal.start_frequency_hz / 1_000_000,
            signal.end_frequency_hz / 1_000_000,
            alpha=0.2,
            label=f"Detected signal {signal_number}",
        )

        plt.axvline(
            signal.center_frequency_hz / 1_000_000,
            linestyle=":",
        )

    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Power (simulated dB)")
    plt.title("Project Aegis — Multiple Signal Detection")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def main() -> None:
    frequencies_hz, power_db = generate_test_spectrum()

    noise_floor_db, threshold_db, detections = detect_signals(
        frequencies_hz,
        power_db,
    )

    print(f"Noise floor: {noise_floor_db:.2f} dB")
    print(f"Threshold:   {threshold_db:.2f} dB")
    print(f"Detections:  {len(detections)}")

    for signal_number, signal in enumerate(detections, start=1):
        print()
        print(f"Signal {signal_number}")
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
        print(f"  Peak power:  {signal.peak_power_db:.2f} dB")
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