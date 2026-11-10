"""HTTP API for the CaringBridge first-post flow.
This is what the front end talks to.

    python -m pip install -r requirements-local.txt
    uvicorn app:app --reload

Nothing is stored on the server.
The front end keeps the author's answers and sends them with each request, so a request is all the server ever knows.
The AI key stays here and never goes to the browser.
There is no login yet, so put real authentication in front of this before it is exposed anywhere public.
"""
import importlib.util
from pathlib import Path
from typing import List

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend import ai, flow, speech, writer
from backend.config import setting

app = FastAPI(title="CaringBridge first-post backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in setting("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
api = APIRouter(prefix="/api/v1")


class Answers(BaseModel):
    what_happened: str = Field("", max_length=writer.MAX_TEXT)
    what_next: str = Field("", max_length=writer.MAX_TEXT)
    help: List[str] = []
    help_other: str = Field("", max_length=writer.MAX_TEXT)
    update_frequency: str = ""
    reach_out: str = ""


class Draft(BaseModel):
    title: str = Field("", max_length=300)
    post: str = Field(..., max_length=20000)


class Adjustments(BaseModel):
    length: int = Field(flow.SLIDER_DEFAULT, ge=1, le=5)
    tone: int = Field(flow.SLIDER_DEFAULT, ge=1, le=5)
    wording: int = Field(flow.SLIDER_DEFAULT, ge=1, le=5)
    extra: str = Field("", max_length=writer.MAX_EXTRA)


class RegenerateRequest(BaseModel):
    answers: Answers
    draft: Draft  # as the author has it now, hand edits included
    adjustments: Adjustments = Field(default_factory=Adjustments)


# Credit to the D2 team for this shape, which comes from d2-team/app.py.
# Bad input is a 400, and a failing AI or speech service is a 502 with a message a person can read.
def run(work):
    """Turn our plain errors into HTTP ones: 400 for bad input, 502 when a service we call fails."""
    try:
        return work()
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except (ai.AIError, speech.SpeechError) as err:
        raise HTTPException(status_code=502, detail=str(err))


@api.get("/flow")
def get_flow():
    """The questions, options and sliders, so the front end draws them from here."""
    return {"questions": flow.QUESTIONS, "sliders": flow.SLIDERS,
            "slider_default": flow.SLIDER_DEFAULT, "ai_notice": flow.AI_NOTICE}


@api.post("/draft")
def make_draft(answers: Answers):
    return run(lambda: writer.first_draft(answers.model_dump()))


@api.post("/regenerate")
def make_new_draft(request: RegenerateRequest):
    return run(lambda: writer.regenerate(
        request.answers.model_dump(), request.draft.model_dump(), request.adjustments.model_dump()))


if importlib.util.find_spec("python_multipart") or importlib.util.find_spec("multipart"):
    from fastapi import File, UploadFile

    @api.post("/transcribe")
    def transcribe(audio: UploadFile = File(...)):
        data = audio.file.read(speech.MAX_AUDIO_BYTES + 1)
        return {"text": run(lambda: speech.transcribe(data, audio.filename or "voice.webm"))}
else:
    @api.post("/transcribe")
    def transcribe_needs_install():
        raise HTTPException(status_code=501, detail="Voice upload needs python-multipart: python -m pip install python-multipart")


@api.get("/health")
def health():
    # Vercel fills in the environment and commit, which shows which deployment is answering.
    # Only whether a key is set is reported, never the key itself.
    return {"status": "ok", "environment": setting("VERCEL_ENV"), "commit": setting("VERCEL_GIT_COMMIT_SHA")[:7],
            "ai_key_set": bool(ai.api_key())}


@api.get("/check")
def check():
    return {"ai": ai.check()}


app.include_router(api)

PAGE = Path(__file__).parent / "public" / "index.html"


@app.get("/", include_in_schema=False)
def home():
    # On Vercel the files in public/ are served for us, so this only matters when running on your own computer.
    if PAGE.exists():
        return FileResponse(PAGE)
    return {"status": "ok", "api": "/api/v1/health"}
