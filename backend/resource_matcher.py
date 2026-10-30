"""Offline catalog recommendations; no model calls or third-party dependencies.

Integration: recommend_resources(validated_analysis["missing_skills"]).
The current remote AI connector returns plain text, so its owner must first
provide a validated list of missing skills. Do not pass the entire AI response.
"""

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

CATALOG_PATH = Path(__file__).with_name("resources.json")
_TEXT_FIELDS = (
    "id", "title", "provider", "url", "description", "audience",
    "access_conditions", "verification_date",
)
_ALIASES = {
    "structured query language": "sql",
    "interviewing": "interview", "interviews": "interview",
    "interview preparation": "interview", "interview prep": "interview",
    "technical interview": "interview", "technical interviews": "interview",
    "resume writing": "resume", "resumes": "resume", "cv": "resume",
    "curriculum vitae": "resume",
    "ai": "artificial intelligence", "ml": "machine learning",
    "powerbi": "power bi", "microsoft power bi": "power bi",
    "data visualisation": "data visualization",
    "network building": "networking",
}


def _normalize(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = " ".join(value.replace("-", " ").split())
    return _ALIASES.get(value, value)


def _url_key(url):
    """Validate HTTPS and normalize host/default port/fragments for deduping."""
    if any(char.isspace() or ord(char) < 32 for char in url) or "\\" in url:
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname
        if (parts.scheme != "https" or not host or parts.username is not None
                or parts.password is not None or "." not in host):
            return None
        if any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?", label)
               for label in host.split(".")):
            return None
        port = parts.port
        authority = host.lower() + (f":{port}" if port not in (None, 443) else "")
        return urlunsplit(("https", authority, parts.path or "/", parts.query, ""))
    except ValueError:
        return None


def _valid_resource(resource):
    if not isinstance(resource, dict) or resource.get("verified") is not True:
        return False
    if type(resource.get("is_catalog", False)) is not bool:
        return False
    if any(not isinstance(resource.get(key), str) or not resource[key].strip()
           for key in _TEXT_FIELDS):
        return False
    tags = resource.get("skill_tags")
    if not isinstance(tags, list) or not tags or any(
        not isinstance(tag, str) or not tag.strip() for tag in tags
    ):
        return False
    try:
        date.fromisoformat(resource["verification_date"])
    except ValueError:
        return False
    return _url_key(resource["url"]) is not None


def _load_resources():
    # Missing/broken catalog is a deployment error, not a genuine no-match result.
    resources = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(resources, list):
        raise ValueError("Resource catalog must contain a JSON list.")
    return resources


def recommend_resources(missing_skills: list[str], limit: int = 5) -> list[dict]:
    """Return catalog fields plus matched_skills, relevance_score and why_it_helps.

    Rank by number of distinct matching skills, non-catalog resources first,
    FIU provider preference, then title and URL/id for deterministic ties.
    Broad catalogs must set is_catalog=True; other resources default to False.
    Exact normalized tags avoid unrelated
    substring matches. Invalid entries are skipped; catalog file errors surface.
    Empty/unknown skills or a nonpositive limit return []. Invalid argument types
    raise TypeError. This function only reads the bundled catalog.
    """
    if not isinstance(missing_skills, list) or any(
        not isinstance(skill, str) for skill in missing_skills
    ):
        raise TypeError("missing_skills must be a list of strings")
    if type(limit) is not int:
        raise TypeError("limit must be an integer")
    skills = {_normalize(skill) for skill in missing_skills if skill.strip()}
    if not skills or limit <= 0:
        return []
    ranked = []
    for resource in _load_resources():
        if not _valid_resource(resource):
            continue
        matched = sorted(skills & {_normalize(tag) for tag in resource["skill_tags"]})
        if not matched:
            continue
        result = dict(resource, skill_tags=list(resource["skill_tags"]),
                      matched_skills=matched, relevance_score=len(matched),
                      why_it_helps="Matches your skill gaps: " + ", ".join(matched) + ".")
        fiu = bool(re.search(r"\bfiu\b|florida international university",
                             resource["provider"], re.IGNORECASE))
        ranked.append(((-len(matched), resource.get("is_catalog", False),
                        not fiu, resource["title"].casefold(),
                        _url_key(resource["url"]), resource["id"]), result))
    ranked.sort(key=lambda item: item[0])
    results, seen = [], set()
    for _, result in ranked:
        key = _url_key(result["url"])
        if key not in seen:
            seen.add(key)
            results.append(result)
            if len(results) == limit:
                break
    return results
