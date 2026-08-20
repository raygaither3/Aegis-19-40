import unittest
from unittest.mock import patch

import numpy as np

from src.aegis.rf_source import RtlPowerSource, parse_rtl_power_row


class RtlPowerParsingTests(unittest.TestCase):
    def test_parse_row_builds_frequency_bins(self) -> None:
        observed, frequencies, powers = parse_rtl_power_row(
            "2026-08-20, 12:30:00, 902000000, 902300000, 100000, 10, "
            "-91.5, -73.0, -90.0"
        )
        self.assertEqual(observed.isoformat(), "2026-08-20T12:30:00+00:00")
        np.testing.assert_array_equal(
            frequencies, [902_000_000, 902_100_000, 902_200_000]
        )
        np.testing.assert_array_equal(powers, [-91.5, -73.0, -90.0])

    def test_invalid_row_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_rtl_power_row("not,a,sweep")

    @patch("src.aegis.rf_source.shutil.which", return_value=None)
    def test_missing_binary_has_actionable_error(self, _which) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "rtl_power"):
            RtlPowerSource().start()


if __name__ == "__main__":
    unittest.main()
