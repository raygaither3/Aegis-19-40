from pathlib import Path

import numpy as np


def load_spectrum_csv(
    file_path: str | Path,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Load frequency and power values from a CSV file.

    Expected columns:
    frequency_hz,power_db
    """

    data = np.genfromtxt(
        file_path,
        delimiter=",",
        names=True,
        dtype=float,
    )

    frequencies_hz = np.asarray(
        data["frequency_hz"],
        dtype=float,
    )

    power_db = np.asarray(
        data["power_db"],
        dtype=float,
    )

    if frequencies_hz.size == 0:
        raise ValueError(
            "The spectrum file contains no data."
        )

    if frequencies_hz.shape != power_db.shape:
        raise ValueError(
            "Frequency and power columns must have equal lengths."
        )

    return frequencies_hz, power_db