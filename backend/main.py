from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.ai import AIError, generate_career_response

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app = FastAPI(title="RutaUp API")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
templates = Jinja2Templates(directory=FRONTEND)


class AnalysisRequest(BaseModel):
    skills: str = Field(min_length=1, max_length=5000)
    job_description: str = Field(min_length=1, max_length=10000)

    @field_validator("skills", "job_description")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Please enter some text.")
        return value.strip()


@app.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={"skills": "", "job_description": ""},
    )


@app.post("/analyze", response_class=HTMLResponse)
def analyze_form(
    request: Request,
    skills: str = Form(default=""),
    job_description: str = Form(default=""),
):
    context = {"skills": skills, "job_description": job_description}
    try:
        payload = AnalysisRequest(skills=skills, job_description=job_description)
    except ValidationError:
        context["error"] = (
            "Enter your skills (up to 5,000 characters) and a job description "
            "(up to 10,000 characters). Neither field can be blank."
        )
        return templates.TemplateResponse(
            request=request, name="index.html", context=context, status_code=422,
        )
    try:
        context["result"] = generate_career_response(payload.skills, payload.job_description)
    except AIError as exc:
        context["error"] = str(exc)
        return templates.TemplateResponse(
            request=request, name="index.html", context=context, status_code=502,
        )
    return templates.TemplateResponse(
        request=request, name="index.html", context=context,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze(payload: AnalysisRequest):
    try:
        return generate_career_response(payload.skills, payload.job_description)
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
