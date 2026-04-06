from __future__ import annotations

import unittest

from fastapi import HTTPException

from app.routes.web import _derive_feedback_payload


class WebFeedbackPayloadTest(unittest.TestCase):
    def test_noise_feedback_allows_empty_levels(self) -> None:
        payload = _derive_feedback_payload(
            impact_level="",
            urgency_level="",
            is_relevant=False,
            is_noise=True,
            comment="noise",
        )

        self.assertEqual(payload["review_status"], "\uc7a1\uc74c")
        self.assertIsNone(payload["impact_level"])
        self.assertIsNone(payload["urgency_level"])
        self.assertEqual(payload["is_noise"], 1)
        self.assertEqual(payload["is_relevant"], 0)

    def test_relevant_feedback_requires_valid_levels(self) -> None:
        with self.assertRaises(HTTPException) as context:
            _derive_feedback_payload(
                impact_level="",
                urgency_level="",
                is_relevant=True,
                is_noise=False,
                comment=None,
            )

        self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
