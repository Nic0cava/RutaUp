"""Offline catalog recommendations; no model calls or third-party dependencies.

Integration: recommend_resources(validated_analysis["missing_skills"],
                                 job_description=job_description).
Job context matches only explicitly supported role titles; no model calls.
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
    "data analytics": "data analysis",
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
    roles = resource.get("role_tags", [])
    if not isinstance(roles, list) or any(
        not isinstance(role, str) or not role.strip() for role in roles
    ):
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


def recommend_resources(
    missing_skills: list[str], limit: int = 5, *, job_description: str = ""
) -> list[dict]:
    """Return catalog fields plus matched_skills, relevance_score and why_it_helps.

    Rank by distinct matching skills plus explicit role match, non-catalog resources first,
    FIU provider preference, then title and URL/id for deterministic ties.
    Broad catalogs must set is_catalog=True; other resources default to False.
    Exact normalized tags avoid unrelated
    substring matches. Invalid entries are skipped; catalog file errors surface.
    Optional job context recognizes a Data Analyst title at the start of the
    description, optionally after Job title/Target role and a seniority prefix.
    Empty/unknown skills without a role match or a nonpositive limit return [].
    Invalid argument types
    raise TypeError. This function only reads the bundled catalog.
    """
    if not isinstance(missing_skills, list) or any(
        not isinstance(skill, str) for skill in missing_skills
    ):
        raise TypeError("missing_skills must be a list of strings")
    if type(limit) is not int:
        raise TypeError("limit must be an integer")
    if not isinstance(job_description, str):
        raise TypeError("job_description must be a string")
    # Anchor to the title, so incidental mentions of another team's role do not
    # recommend that career path. Only this curated role is supported for MVP.
    title = _normalize(job_description)
    role_match = re.match(
        r"^(?:(?:job title|target role)\s*:\s*)?"
        r"(?:(?:junior|senior|entry level|lead)\s+)?data analyst\b", title
    )
    target_roles = {"data analyst"} if role_match else set()
    skills = {_normalize(skill) for skill in missing_skills if skill.strip()}
    if (not skills and not target_roles) or limit <= 0:
        return []
    ranked = []
    for resource in _load_resources():
        if not _valid_resource(resource):
            continue
        matched = sorted(skills & {_normalize(tag) for tag in resource["skill_tags"]})
        matched_roles = sorted(target_roles & {
            _normalize(role) for role in resource.get("role_tags", [])
        })
        if not matched and not matched_roles:
            continue
        score = len(matched) + len(matched_roles)
        reasons = []
        if matched:
            reasons.append("Matches your skill gaps: " + ", ".join(matched) + ".")
        if matched_roles:
            reasons.append("Supports your target role: " + ", ".join(matched_roles) + ".")
        result = dict(resource, skill_tags=list(resource["skill_tags"]),
                      matched_skills=matched, matched_roles=matched_roles,
                      relevance_score=score, why_it_helps=" ".join(reasons))
        fiu = bool(re.search(r"\bfiu\b|florida international university",
                             resource["provider"], re.IGNORECASE))
        ranked.append(((-score, resource.get("is_catalog", False),
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
