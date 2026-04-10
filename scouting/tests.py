from django.test import TestCase

from scouting.views import _derive_current_match_from_matches


class CurrentMatchDerivationTests(TestCase):
    def test_current_match_handles_qualification_label_variants(self):
        matches = [
            {
                "label": "Qual 14",
                "status": "In Progress",
                "times": {"actualOnFieldTime": 1000},
            }
        ]

        label, qual_match_num = _derive_current_match_from_matches(matches)

        self.assertEqual(label, "Qual 14 (In Progress)")
        self.assertEqual(qual_match_num, 14)

    def test_current_match_handles_playoff_labels(self):
        matches = [
            {
                "label": "Quarterfinal 2 Match 1",
                "status": "On Field",
                "times": {"actualOnFieldTime": 2000},
            }
        ]

        label, qual_match_num = _derive_current_match_from_matches(matches)

        self.assertEqual(label, "Quarterfinal 2 Match 1 (On Field)")
        self.assertIsNone(qual_match_num)

    def test_current_match_prefers_latest_active_time(self):
        matches = [
            {
                "label": "Qualification 10",
                "status": "On Field",
                "times": {"actualOnFieldTime": 1000},
            },
            {
                "label": "Qualification 11",
                "status": "On Field",
                "times": {"actualOnFieldTime": 2000},
            },
        ]

        label, qual_match_num = _derive_current_match_from_matches(matches)

        self.assertEqual(label, "Qualification 11 (On Field)")
        self.assertEqual(qual_match_num, 11)
