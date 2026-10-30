"""Offline tests: python -B -m unittest backend.test_resource_matcher -v"""

import json
import unittest
from unittest.mock import patch

from backend import resource_matcher as matcher


def resource(identifier="sample", **overrides):
    return dict({
        "id": identifier, "title": identifier, "provider": "Example Learning",
        "url": f"https://example.org/{identifier}", "description": "SQL practice.",
        "skill_tags": ["sql"], "audience": "Beginners",
        "access_conditions": "Free public lessons.", "verified": True,
        "verification_date": "2026-10-30",
    }, **overrides)


class ResourceMatcherTests(unittest.TestCase):
    def recommend(self, resources, skills=None, limit=5):
        with patch.object(matcher, "_load_resources", return_value=resources):
            return matcher.recommend_resources(["SQL"] if skills is None else skills, limit)

    def test_sql_catalog(self):
        results = matcher.recommend_resources([" SQL "])
        ids = [item["id"] for item in results]
        for specific in ("cs50-sql", "sqlbolt", "roadmap-sql"):
            self.assertLess(ids.index(specific), ids.index("code-crunch-catalog"))
        self.assertTrue(all(item["matched_skills"] == ["sql"] for item in results))

    def test_interview_preparation(self):
        results = matcher.recommend_resources(["Interview preparation"])
        self.assertEqual(results[0]["id"], "fiu-colorstack")
        self.assertEqual(results[0]["matched_skills"], ["interview"])

    def test_resume_writing(self):
        results = matcher.recommend_resources(["Resume writing"])
        self.assertIn("fiu-career", [item["id"] for item in results])
        self.assertEqual(results, matcher.recommend_resources(["RÉSUMÉ writing"]))

    def test_ai_and_machine_learning(self):
        for skill in ("AI", "ML", "machine-learning"):
            with self.subTest(skill=skill):
                self.assertIn("cs50-ai", [item["id"] for item in
                                         matcher.recommend_resources([skill])])

    def test_unknown_skills(self):
        self.assertEqual(matcher.recommend_resources(["underwater basket weaving"]), [])

    def test_roadmap_skills(self):
        for skill, identifier in (("Data Analyst", "roadmap-data-analyst"),
                                  ("SQL", "roadmap-sql"), ("Python", "roadmap-python"),
                                  ("Power BI", "roadmap-power-bi"), ("powerbi", "roadmap-power-bi")):
            with self.subTest(skill=skill):
                self.assertIn(identifier, [r["id"] for r in matcher.recommend_resources([skill])])

    def test_explicit_data_analyst_role(self):
        for title in ("Data Analyst Intern; SQL required", "Junior Data Analyst",
                      "Target role: Data Analyst", "Senior Data-Analyst"):
            with self.subTest(title=title):
                result = matcher.recommend_resources([], job_description=title)
                self.assertEqual([r["id"] for r in result], ["roadmap-data-analyst"])
                self.assertIn("target role", result[0]["why_it_helps"])

    def test_unrelated_roles_do_not_infer_skills(self):
        for title in ("Nursing intern", "Software engineer working with a data analyst",
                      "Database administrator: SQL and Python"):
            with self.subTest(title=title):
                self.assertEqual(matcher.recommend_resources([], job_description=title), [])
        result = matcher.recommend_resources(["SQL"], job_description="Software Engineer")
        self.assertNotIn("roadmap-data-analyst", [r["id"] for r in result])

    def test_roadmap_https_and_deduplication(self):
        result = matcher.recommend_resources(
            ["SQL", "sql", "Python", "Power BI", "data analysis"], limit=20,
            job_description="Data Analyst Intern",
        )
        urls = [r["url"] for r in result]
        self.assertEqual(len(urls), len(set(urls)))
        roadmaps = [r for r in result if r["provider"] == "roadmap.sh"]
        self.assertEqual(len(roadmaps), 4)
        self.assertTrue(all(r["verified"] and r["url"].startswith("https://roadmap.sh/")
                            for r in roadmaps))

    def test_fiu_resources_remain_relevant(self):
        result = matcher.recommend_resources(["interview", "resume"], job_description="Data Analyst")
        self.assertEqual(result[0]["id"], "fiu-colorstack")
        self.assertIn("fiu-career", [r["id"] for r in result])

    def test_invalid_role_metadata_or_input(self):
        for roles in ("data analyst", [None], [" "]):
            self.assertEqual(self.recommend([resource(role_tags=roles)]), [])
        with self.assertRaises(TypeError):
            matcher.recommend_resources([], job_description=None)

    def test_empty_input(self):
        with patch.object(matcher, "_load_resources") as loader:
            self.assertEqual(matcher.recommend_resources([]), [])
            self.assertEqual(matcher.recommend_resources([" "]), [])
            loader.assert_not_called()

    def test_duplicate_urls_keep_best_match(self):
        resources = [resource("a", url="https://EXAMPLE.org:443/lesson#intro"),
                     resource("b", url="https://example.org/lesson", skill_tags=["sql", "python"]),
                     resource("c", url="https://example.org/lesson")]
        results = self.recommend(resources, ["sql", "python"])
        self.assertEqual([item["id"] for item in results], ["b"])

    def test_unverified_entries(self):
        for flag in (False, "true", 1, None):
            with self.subTest(flag=flag):
                self.assertEqual(self.recommend([resource(verified=flag)]), [])

    def test_invalid_urls(self):
        for url in ("http://example.org", "javascript:alert(1)", "//example.org",
                    "https://", "https://bad host.org", "https://example.org:bad",
                    "https://user:password@example.org", "https://[broken",
                    "https://example.org\\evil", "https://example.org/\npath",
                    "https://-bad.org", "https://example..org"):
            with self.subTest(url=url):
                self.assertEqual(self.recommend([resource(url=url)]), [])

    def test_stable_order_relevance_then_fiu_then_title(self):
        resources = [resource("z", title="Zebra", provider="FIU"),
                     resource("a", title="Alpha", provider="FIU"),
                     resource("other", title="Aardvark"),
                     resource("best", skill_tags=["sql", "python"])]
        expected = ["best", "a", "z", "other"]
        for items in (resources, list(reversed(resources))):
            results = self.recommend(items, ["Python", "SQL"])
            self.assertEqual([item["id"] for item in results], expected)
            self.assertEqual(results[0]["matched_skills"], ["python", "sql"])

    def test_duplicate_skills_and_tags_do_not_inflate_score(self):
        results = self.recommend([resource(skill_tags=["SQL", "sql"])],
                                 ["sql", "SQL", "structured query language"])
        self.assertEqual(results[0]["relevance_score"], 1)

    def test_specificity_before_fiu_but_after_relevance(self):
        resources = [resource("catalog", provider="FIU", is_catalog=True),
                     resource("course"),
                     resource("more-relevant", is_catalog=True,
                              skill_tags=["sql", "python"])]
        for items in (resources, list(reversed(resources))):
            results = self.recommend(items, ["SQL", "Python"])
            self.assertEqual([item["id"] for item in results],
                             ["more-relevant", "course", "catalog"])

    def test_invalid_catalog_flag_is_skipped(self):
        for flag in ("false", 0, None, []):
            with self.subTest(flag=flag):
                self.assertEqual(self.recommend([resource(is_catalog=flag)]), [])

    def test_malformed_entries_are_skipped(self):
        bad = [None, [], "resource", {}, resource(skill_tags="sql"),
               resource(skill_tags=[None]), resource(skill_tags=[]),
               resource(title=" "), resource(verification_date="not-a-date")]
        for field in matcher._TEXT_FIELDS:
            item = resource()
            del item[field]
            bad.append(item)
        results = self.recommend(bad + [resource("valid")])
        self.assertEqual([item["id"] for item in results], ["valid"])

    def test_limit(self):
        items = [resource("a"), resource("b")]
        self.assertEqual(len(self.recommend(items, limit=1)), 1)
        self.assertEqual(self.recommend(items, limit=0), [])
        self.assertEqual(self.recommend(items, limit=-1), [])

    def test_argument_types(self):
        for skills in (None, "SQL", {"sql"}, [None], [1]):
            with self.assertRaises(TypeError):
                matcher.recommend_resources(skills)
        for limit in (True, "5", 1.5):
            with self.assertRaises(TypeError):
                matcher.recommend_resources(["sql"], limit)

    def test_result_structure_and_no_catalog_mutation(self):
        original = resource()
        results = self.recommend([original])
        self.assertTrue(set(original).issubset(results[0]))
        self.assertEqual(results[0]["why_it_helps"], "Matches your skill gaps: sql.")
        json.dumps(results)
        results[0]["skill_tags"].append("python")
        self.assertEqual(original["skill_tags"], ["sql"])
        self.assertNotIn("matched_skills", original)

    def test_real_catalog_integrity(self):
        resources = matcher._load_resources()
        self.assertGreaterEqual(len(resources), 8)
        self.assertLessEqual(len(resources), 12)
        self.assertTrue(all(matcher._valid_resource(item) for item in resources))
        self.assertEqual(len({item["id"] for item in resources}), len(resources))
        self.assertEqual(len({matcher._url_key(item["url"]) for item in resources}), len(resources))

    def test_catalog_path_independent_of_working_directory(self):
        self.assertEqual(matcher.CATALOG_PATH.parent, matcher.Path(matcher.__file__).parent)
        self.assertTrue(matcher.CATALOG_PATH.is_absolute())


if __name__ == "__main__":
    unittest.main()
