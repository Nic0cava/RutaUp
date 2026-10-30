"""Offline connector tests. Model responses here are test fixtures."""
import json
import os
import unittest
from unittest.mock import patch

from backend import ai

FAKE_KEY = "fake-offline-test-key"


def valid_analysis():
    return {
        "matching_skills": ["Python", "Excel"],
        "missing_skills": ["SQL"],
        "roadmap": [
            {"title": "Learn SQL", "description": "Practice SELECT and JOIN."},
            {"title": "Analyze data", "description": "Query a public dataset."},
            {"title": "Build a project", "description": "Explain findings in a portfolio."},
        ],
        "interview_questions": [
            "How would you use SQL?", "How do you check data quality?",
            "How would you explain your findings?",
        ],
    }


class AITests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        dotenv = patch.object(ai, "load_dotenv")
        dotenv.start()
        self.addCleanup(dotenv.stop)
        client = patch.object(ai.genai, "Client")
        self.client = client.start()
        self.addCleanup(client.stop)
        self.generate = self.client.return_value.__enter__.return_value.models.generate_content
        self.generate.return_value.text = json.dumps(valid_analysis())

    def test_sdk_call_and_validated_mocked_response(self):
        self.assertEqual(ai.generate_career_response("Python", "SQL analyst"), valid_analysis())
        args = self.generate.call_args.kwargs
        self.assertEqual(args["model"], "gemma-4-26b-a4b-it")
        self.assertIn("JSON", args["contents"])
        self.assertIn("matching_skills", args["contents"])
        self.assertNotIn(FAKE_KEY, args["contents"])
        self.assertEqual(self.client.call_args.kwargs["api_key"], FAKE_KEY)

    def test_missing_key_stops_before_client(self):
        for value in ("", " "):
            with self.subTest(value=value), patch.dict(os.environ, {"GEMINI_API_KEY": value}):
                with self.assertRaisesRegex(ai.AIError, "GEMINI_API_KEY"):
                    ai.generate_career_response("Python", "SQL analyst")
        self.client.assert_not_called()

    def test_non_gemma4_override_is_rejected(self):
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-test"}):
            with self.assertRaisesRegex(ai.AIError, "Gemma 4"):
                ai.generate_career_response("Python", "SQL analyst")
        self.client.assert_not_called()

    def test_missing_fields(self):
        for field in valid_analysis():
            value = valid_analysis()
            del value[field]
            with self.subTest(field=field), self.assertRaises(ai.AIError):
                ai.validate_analysis(value)

    def test_malformed_fields(self):
        cases = [
            ("matching_skills", "Python"), ("missing_skills", [123]),
            ("missing_skills", [None]), ("missing_skills", [" "]),
            ("roadmap", ["step"] * 3),
            ("roadmap", [{"title": "Only title"}] * 3),
            ("roadmap", [{"title": "", "description": "text"}] * 3),
            ("interview_questions", ["", "Question", "Question"]),
            ("interview_questions", [1, 2, 3]),
        ]
        for field, bad in cases:
            value = valid_analysis()
            value[field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(ai.AIError):
                ai.validate_analysis(value)
        for value in (None, [], "plain text", 12):
            with self.subTest(value=value), self.assertRaises(ai.AIError):
                ai.validate_analysis(value)

    def test_exact_counts(self):
        for field in ("roadmap", "interview_questions"):
            for count in (0, 2, 4):
                value = valid_analysis()
                value[field] = [value[field][0]] * count
                with self.subTest(field=field, count=count), self.assertRaises(ai.AIError):
                    ai.validate_analysis(value)

    def test_malformed_json_is_controlled(self):
        for text in ("not JSON", "{", "[]", "null"):
            self.generate.return_value.text = text
            with self.subTest(text=text), self.assertRaises(ai.AIError):
                ai.generate_career_response("Python", "SQL analyst")

    def test_complete_json_fence_is_accepted(self):
        fence = chr(96) * 3
        self.assertEqual(ai.parse_analysis(fence + "json\n" + json.dumps(valid_analysis()) + "\n" + fence),
                         valid_analysis())

    def test_empty_response(self):
        for text in (None, "", " "):
            self.generate.return_value.text = text
            with self.subTest(text=text), self.assertRaisesRegex(ai.AIError, "no text"):
                ai.generate_career_response("Python", "SQL analyst")

    def test_provider_failures_hide_sensitive_details(self):
        for code in (400, 401, 403, 404, 429, 500):
            self.generate.side_effect = ai.errors.APIError(code, {"message": FAKE_KEY})
            with self.subTest(code=code), self.assertRaises(ai.AIError) as caught:
                ai.generate_career_response("Python", "SQL analyst")
            self.assertNotIn(FAKE_KEY, str(caught.exception))

    def test_network_failure_is_controlled(self):
        self.generate.side_effect = RuntimeError(FAKE_KEY)
        with self.assertRaises(ai.AIError) as caught:
            ai.generate_career_response("Python", "SQL analyst")
        self.assertNotIn(FAKE_KEY, str(caught.exception))

    def test_echoed_key_is_redacted(self):
        value = valid_analysis()
        value["roadmap"][0]["description"] = FAKE_KEY
        self.generate.return_value.text = json.dumps(value)
        result = ai.generate_career_response("Python", "SQL analyst")
        self.assertNotIn(FAKE_KEY, json.dumps(result))
        self.assertEqual(result["roadmap"][0]["description"], "[REDACTED]")

    def test_ai_cannot_inject_resource_fields(self):
        value = valid_analysis()
        value["resources"] = [{"url": "https://invented.example/"}]
        with self.assertRaises(ai.AIError):
            ai.validate_analysis(value)


if __name__ == "__main__":
    unittest.main()
