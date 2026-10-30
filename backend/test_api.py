"""Offline tests through FastAPI, Jinja2, the connector and the real catalog."""
import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import ai, main
from backend.resource_matcher import CATALOG_PATH
from backend.test_ai import valid_analysis, FAKE_KEY


class APITests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        dotenv = patch.object(ai, "load_dotenv")
        dotenv.start()
        self.addCleanup(dotenv.stop)
        client = patch.object(ai.genai, "Client")
        self.sdk = client.start()
        self.addCleanup(client.stop)
        self.generate = self.sdk.return_value.__enter__.return_value.models.generate_content
        self.generate.return_value.text = json.dumps(valid_analysis())
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.inputs = {"skills": "Python, Excel", "job_description": "SQL analyst"}

    def post(self, path, payload=None):
        values = self.inputs if payload is None else payload
        return self.client.post(path, **({"json": values} if path == "/api/analyze" else {"data": values}))

    def test_json_contract_and_real_catalog_matching(self):
        response = self.post("/api/analyze")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(set(result), set(valid_analysis()) | {"resources"})
        self.assertEqual(len(result["roadmap"]), 3)
        self.assertEqual(len(result["interview_questions"]), 3)
        self.assertEqual(result["resources"][0]["id"], "cs50-sql")
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        allowed = {r["url"] for r in catalog if r["verified"]}
        urls = [r["url"] for r in result["resources"]]
        self.assertTrue(set(urls).issubset(allowed))
        self.assertTrue(all(url.startswith("https://") for url in urls))
        self.assertEqual(len(urls), len(set(urls)))

    def test_html_displays_all_four_features(self):
        response = self.post("/analyze")
        self.assertEqual(response.status_code, 200)
        for text in ("Skill gap analysis", "Three-step learning roadmap",
                     "Verified learning and career resources", "Interview practice",
                     "Learn SQL", "How would you use SQL?", "Harvard CS50",
                     "https://cs50.harvard.edu/sql/", "OpenCourseWare is free."):
            self.assertIn(text, response.text)
        self.assertNotIn('"matching_skills":', response.text)

    def test_both_routes_use_shared_analysis(self):
        with patch.object(main, "analyze_student", wraps=main.analyze_student) as shared:
            self.assertEqual(self.post("/analyze").status_code, 200)
            self.assertEqual(self.post("/api/analyze").status_code, 200)
            self.assertEqual(shared.call_count, 2)

    def test_empty_and_oversized_inputs(self):
        for path in ("/analyze", "/api/analyze"):
            for field in self.inputs:
                for bad in ("", " ", "x" * 10001):
                    payload = dict(self.inputs, **{field: bad})
                    with self.subTest(path=path, field=field, size=len(bad)):
                        self.assertEqual(self.post(path, payload).status_code, 422)
        self.sdk.assert_not_called()

    def test_missing_key_both_routes(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            for path in ("/analyze", "/api/analyze"):
                response = self.post(path)
                self.assertEqual(response.status_code, 502)
                self.assertIn("GEMINI_API_KEY", response.text)
        self.sdk.assert_not_called()

    def test_provider_error_both_routes(self):
        self.generate.side_effect = ai.errors.APIError(429, {"message": FAKE_KEY})
        for path in ("/analyze", "/api/analyze"):
            response = self.post(path)
            self.assertEqual(response.status_code, 502)
            self.assertIn("quota", response.text)
            self.assertNotIn(FAKE_KEY, response.text)

    def test_malformed_ai_output_both_routes(self):
        self.generate.return_value.text = '{"missing_skills": ["SQL"]}'
        for path in ("/analyze", "/api/analyze"):
            response = self.post(path)
            self.assertEqual(response.status_code, 502)
            self.assertIn("invalid analysis", response.text)

    def test_route_boundary_revalidates_connector(self):
        with patch.object(main, "generate_career_response", return_value={"missing_skills": "SQL"}):
            with patch.object(main, "recommend_resources") as matcher:
                self.assertEqual(self.post("/api/analyze").status_code, 502)
                matcher.assert_not_called()

    def test_safe_html_escaping(self):
        attack = '<script>alert("x")</script>'
        value = valid_analysis()
        value["roadmap"][0]["title"] = attack
        value["interview_questions"][0] = attack
        self.generate.return_value.text = json.dumps(value)
        response = self.post("/analyze", dict(self.inputs, skills=attack))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(attack, response.text)
        self.assertIn("&lt;script&gt;", response.text)

    def test_empty_recommendations(self):
        value = valid_analysis()
        value["missing_skills"] = ["unknown skill"]
        self.generate.return_value.text = json.dumps(value)
        self.assertEqual(self.post("/api/analyze").json()["resources"], [])
        self.assertIn("No curated resource match yet.", self.post("/analyze").text)

    def test_model_resource_urls_cannot_reach_response(self):
        value = valid_analysis()
        value["resources"] = [{"url": "https://invented.example/"}]
        self.generate.return_value.text = json.dumps(value)
        response = self.post("/api/analyze")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("invented.example", response.text)

    def test_catalog_failure_is_controlled(self):
        with patch.object(main, "recommend_resources", side_effect=OSError("internal path")):
            for path in ("/analyze", "/api/analyze"):
                response = self.post(path)
                self.assertEqual(response.status_code, 502)
                self.assertIn("temporarily unavailable", response.text)
                self.assertNotIn("internal path", response.text)

    def test_home_sample_loading_and_health(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sample inputs: Data Analyst internship", response.text)
        self.assertIn("/static/loading.js", response.text)
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.sdk.assert_not_called()

    def test_role_roadmap_uses_job_context(self):
        value = valid_analysis()
        value["missing_skills"] = ["Power BI"]
        self.generate.return_value.text = json.dumps(value)
        payload = dict(self.inputs, job_description="Data Analyst Intern")
        result = self.post("/api/analyze", payload).json()
        ids = [r["id"] for r in result["resources"]]
        self.assertIn("roadmap-data-analyst", ids)
        self.assertIn("roadmap-power-bi", ids)
        self.assertEqual(result["roadmap"], value["roadmap"])
        html = self.post("/analyze", payload)
        self.assertIn("https://roadmap.sh/power-bi", html.text)
        self.assertIn("https://roadmap.sh/data-analyst", html.text)

    def test_consecutive_requests(self):
        for _ in range(2):
            self.assertEqual(self.post("/analyze").status_code, 200)
            self.assertEqual(self.post("/api/analyze").status_code, 200)


if __name__ == "__main__":
    unittest.main()
