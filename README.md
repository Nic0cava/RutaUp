# RutaUp

## Run Locally (Git Bash)

From the project root:

```bash
uv sync
uv run uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000. FastAPI serves the frontend and API together; no separate frontend server is needed.

Jinja2 renders the page and results on the server. The form posts to `/analyze` and reloads the page with the results, keeping your inputs. No JavaScript is required. `/api/analyze` remains available for JSON API requests.

### Quick Test

1. Enter `Python, HTML` as your skills and `Backend internship using Python and SQL` as the job description.
2. Click **Test my career roadmap**. You should see **Connected!** and three demo steps.
3. Open http://127.0.0.1:8000/api/health to see `{"status":"ok"}`.
4. Open http://127.0.0.1:8000/docs to try the API directly.
5. Press `Ctrl+C` in the terminal to stop the server.

### Google API Connection Test

With `GEMINI_API_KEY` set in `.env`, run:

```bash
uv run python -m backend.test_connection
```

Type your prompt when asked, or pass it directly:

```bash
uv run python -m backend.test_connection "Suggest three skills for a Python backend internship."
```

Each run sends one prompt and prints the response, keeping the key private. It discovers an available Gemma model (preferring Gemma 4 if listed). To choose a specific model, add `GEMINI_MODEL=your-model-id` to `.env`. Check the printed model name: success confirms access to that model, not necessarily Gemma 4. This test does not change the web form's demo behavior.

This starter returns demo data. Gemma, real skill analysis, resource recommendations, and interview questions are not connected yet.

### Project Layout

```text
backend/
  __init__.py
  main.py          # FastAPI routes and frontend serving
frontend/
  index.html       # Jinja2 template for the form and results
  styles.css       # Styling
```

RutaUp is an AI-powered career assistant for FIU students. Students enter their current skills and a job description, and the app helps them understand what to improve to prepare for that job.

## Main Features

- **Skill Gap Analysis:** Compare the student's skills with the job requirements.
- **Learning Roadmap:** Create three steps to develop missing skills.
- **Free Resources:** Recommend relevant free resources from FIU, Hack University, Code Crunch, and other learning platforms.
- **Interview Practice:** Generate three interview questions for the target position.

## Planned Tech Stack

- **Backend:** Python and FastAPI.
- **Frontend:** HTML with Jinja2 templates and CSS; JavaScript only if needed for visual enhancements.
- **AI:** Google Gemma 4 through the Google GenAI SDK.
- **Resources:** JSON files.
- **Development:** VS Code with the Codex extension, a uv environment, Git, and GitHub workflows.

## Hackathon Goals

We plan to compete in the main Devpost challenge, Best Use of Gemma 4, and DigitalOcean's open-source AI challenge.

The goal is to finish a working demo, test it, and submit everything today. This is a simple prototype with no database, login system, or unnecessary features. The plan is a rough draft and may evolve during development.
