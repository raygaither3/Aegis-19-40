from dataclasses import FrozenInstanceError
import unittest

from src.aegis.scenario_simulator import (
    build_demo_scenario,
    format_scan_result,
    run_scenario,
)
from src.aegis.tracker import TrackState


class ScenarioSimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.results = run_scenario(build_demo_scenario())

    def test_demo_runs_all_scans(self) -> None:
        self.assertEqual(len(self.results), 5)
        self.assertEqual(self.results[0].scan_number, 1)
        self.assertEqual(self.results[-1].scan_number, 5)

    def test_one_scan_false_positive_expires(self) -> None:
        self.assertEqual(
            {contact.signal_id for contact in self.results[0].contacts},
            {1, 2, 3},
        )
        self.assertNotIn(
            3,
            {contact.signal_id for contact in self.results[2].contacts},
        )

    def test_dropout_reacquires_original_contact(self) -> None:
        scan_three_contact = next(
            contact
            for contact in self.results[2].contacts
            if contact.signal_id == 2
        )
        scan_four_contact = next(
            contact
            for contact in self.results[3].contacts
            if contact.signal_id == 2
        )

        self.assertEqual(scan_three_contact.state, TrackState.FADING)
        self.assertEqual(scan_three_contact.missed_scans, 1)
        self.assertEqual(scan_four_contact.missed_scans, 0)
        self.assertEqual(scan_four_contact.detection_count, 3)

    def test_persistent_drifting_contact_becomes_confirmed(self) -> None:
        final_contact = next(
            contact
            for contact in self.results[-1].contacts
            if contact.signal_id == 1
        )

        self.assertEqual(final_contact.center_frequency_hz, 100_196_000)
        self.assertEqual(final_contact.confidence, 100.0)
        self.assertEqual(final_contact.state, TrackState.CONFIRMED)
        self.assertEqual(final_contact.detection_count, 5)

    def test_scan_history_is_immutable(self) -> None:
        first_contact = self.results[0].contacts[0]
        self.assertEqual(first_contact.confidence, 20.0)

        with self.assertRaises(FrozenInstanceError):
            first_contact.confidence = 99.0  # type: ignore[misc]

    def test_table_contains_gui_relevant_fields(self) -> None:
        output = format_scan_result(self.results[2])

        self.assertIn("Confidence", output)
        self.assertIn("State", output)
        self.assertIn("Missed", output)
        self.assertIn("FADING", output)


if __name__ == "__main__":
    unittest.main()
