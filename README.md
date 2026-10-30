# RutaUp

RutaUp is an FIU-first career readiness assistant built by Nicolas Cava and Oliver Hernandez. It compares a student's skills with a target job using Google Gemma 4, then connects identified gaps to a locally curated resource library.

## Four MVP features

1. Matching and missing skills from a real Gemma request.
2. Exactly three personalized learning steps, each with a title and description.
3. Relevant verified HTTPS learning/career resources selected by deterministic Python matching, never model-generated links.
4. Exactly three interview practice questions.

FastAPI serves a Jinja2 HTML/CSS frontend. Both the form and JSON API use the same validated analysis pipeline. Invalid model output produces an error; no canned AI results are substituted.

## Setup and run

Requires Python 3.12+ and uv. From the integration worktree root:

    uv sync

Create a local ignored .env file in this worktree (Git worktrees do not share .env files):

    GEMINI_API_KEY=your_google_ai_studio_key
    GEMINI_MODEL=gemma-4-26b-a4b-it

GEMINI_API_KEY is required. GEMINI_MODEL is optional and defaults to the shown model; an override must identify an available Gemma 4 model. Account access to the model must be confirmed separately. Environment variables can also be supplied to the process. Never commit a key.

    uv run uvicorn backend.main:app --reload

Open http://127.0.0.1:8000. Submitting either analysis route sends student inputs to Google. Requests may take up to a minute. Restart after changing API configuration.

For this machine, the existing sibling environment can be reused without installation in PowerShell:

    & '..\RutaUp\.venv\Scripts\python.exe' -B -m uvicorn backend.main:app --reload

The integration worktree still needs its own API configuration; the sibling .env is not read.

## Demo

The page labels sample inputs to copy into the form:

- Skills: Python, Pandas, Excel
- Job: Data Analyst Intern; SQL querying, Python, dashboarding, and clear communication preferred.

The result displays skills, a three-step roadmap, resource links with access conditions, and interview questions. Unknown resource tags show "No curated resource match yet." The existing loading animation and input preservation are retained.

## API and validation

POST /api/analyze accepts skills and job_description strings. POST /analyze accepts the same fields as form data. GET /api/health is an offline health check.

The response contains matching_skills, missing_skills, roadmap, interview_questions, and resources. Skills and questions must be nonblank strings; roadmap must contain exactly three title/description objects; questions must number exactly three. Unexpected model fields are rejected. JSON is requested via the prompt and validated locally, without relying on provider-side structured-output support.

The resource catalog includes verified roadmap.sh guides for Data Analyst, SQL, Python and Power BI. Missing skills select subject roadmaps; an explicit Data Analyst title at the start of the job description also selects the role roadmap. Job title/Target role labels and common seniority prefixes are supported; arbitrary prose is not interpreted as a role. These are curated links, not another AI-generated roadmap.

The resource matcher ranks matching skill count plus an explicit role match first, specific resources before catalogs, then FIU preference and stable title order. Only verified catalog entries with valid HTTPS URLs can be recommended.

## Offline testing

    uv run python -B -m unittest backend.test_resource_matcher backend.test_ai backend.test_api -v
    git diff --check

Without installing a new environment on this machine, use PowerShell:

    & '..\RutaUp\.venv\Scripts\python.exe' -B -m unittest backend.test_resource_matcher backend.test_ai backend.test_api -v

Connector and route tests mock the Google SDK. No real keys, provider requests, or network calls are used. Fixture responses exist only in tests. Successful offline tests do not prove live model availability.

## Known limitations

- Live Gemma 4 verification passed with two real requests through the JSON and HTML routes before the roadmap.sh addition. The roadmap.sh extension is verified offline and makes no additional AI request.
- Model output can be malformed, truncated or factually wrong; local validation checks structure, not factual correctness. There is no automatic retry or synthetic fallback.
- Resource tags and synonyms are intentionally limited; no live web search is performed.
- Verification notes describe checks made on October 30, 2026. Links and access conditions can change. Catalog verification does not mean every course is complete or every event is free.
- FIU services may require eligibility/sign-in; CS50 feedback may require an account and paid credentials are separate. Read each resource's access conditions.
- API/configuration failures return controlled HTTP 502 errors; invalid inputs return 422.
- The installed Starlette test client warns that its httpx adapter is deprecated; the offline tests still pass. No dependency upgrade was made for this prototype.
- No database, authentication, uploads or exports are included.

## Credits and ownership

- Nicolas Cava: Gemma integration, FastAPI and frontend foundation.
- Oliver Hernandez: curated resources, deterministic matching and resource tests.
- Google Gemma 4 and Google GenAI SDK: model inference.
- FIU Career and Talent Development, ColorStack at FIU, Google Developer Group at FIU, Code Crunch Worldwide, SQLBolt, Harvard CS50 and roadmap.sh: linked learning and community resources. Inclusion does not imply endorsement.
- Hack University is acknowledged as a candidate community source; its unavailable resource page was excluded from the verified catalog.
