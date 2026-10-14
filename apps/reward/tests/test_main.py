import unittest

from apps.reward.app.main import (
    MAX_TEXT_CHARS,
    levenshtein_distance,
    score_edit_similarity,
    validate_payload,
)


class RewardScoringTests(unittest.TestCase):
    def test_levenshtein_known_examples(self) -> None:
        self.assertEqual(levenshtein_distance("kitten", "sitting"), 3)
        self.assertEqual(levenshtein_distance("", "abc"), 3)
        self.assertEqual(levenshtein_distance("café", "cafe"), 1)

    def test_unchanged_text_is_one(self) -> None:
        result = score_edit_similarity("ship this draft", "ship this draft")
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["distance"], 0)

    def test_rewritten_text_is_normalized(self) -> None:
        result = score_edit_similarity("abc", "axc")
        self.assertAlmostEqual(result["score"], 2 / 3)
        self.assertEqual(result["distance"], 1)

    def test_empty_pair_is_one(self) -> None:
        self.assertEqual(score_edit_similarity("", "")["score"], 1.0)

    def test_validation_rejects_missing_unknown_and_non_string_fields(self) -> None:
        bad_payloads = [
            {"candidate": "draft"},
            {"candidate": "draft", "edited": "draft", "tenant": "acme"},
            {"candidate": True, "edited": "draft"},
            ["draft", "edit"],
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_payload(payload)

    def test_validation_rejects_oversized_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "exceeds"):
            validate_payload({"candidate": "x" * (MAX_TEXT_CHARS + 1), "edited": ""})


if __name__ == "__main__":
    unittest.main()
