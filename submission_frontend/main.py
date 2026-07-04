"""
FastAPI Dashboard Backend
=========================

This module implements the FastAPI web server for the MortgageStream AI dashboard.
It exposes endpoints to:
1. Serve the frontend HTML dashboard.
2. Run the deterministic Privacy Shield (scrub_application_data) on uploaded applicant files.
3. Asynchronously run the mortgage underwriting multi-agent swarm via Google ADK.

Regulatory and Architectural Principles:
1. Privacy Shield Gateway (/api/redact):
   In compliance with GDPR (data minimisation) and FCA guidelines, the Privacy Shield 
   gateway scrubs all personal data (names, National Insurance numbers, bank accounts, 
   sort codes, etc.) before the payload is sent to the underwriting agents.
   
2. Asynchronous Execution model:
   FastAPI's async/await model integrates natively with Google ADK's `Runner.run_async`, 
   allowing the server to process multiple simultaneous requests without blocking 
   the event loop while waiting for Gemini API responses.

3. Output Validation & Fail-Safe Parsing:
   The Compliance Agent outputs a JSON-structured audit log. To prevent model 
   formatting issues from crashing the server, we attempt to validate the output 
   against a Pydantic `AuditLog` schema. If validation fails, we capture the raw 
   text and return it gracefully with a `validated: False` flag.
"""

import json
import pathlib
import uuid
from dotenv import load_dotenv

# Load environment variables at application startup to fetch GOOGLE_API_KEY.
load_dotenv()

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from privacy import scrub_application_data
from mortgage_agents.agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Initialize the FastAPI application
app = FastAPI(
    title="MortgageStream AI Underwriting Dashboard",
    description="Underwriting pre-qualification dashboard powered by Google ADK multi-agent swarm."
)

# Session Service and Runner are instantiated locally per request to guarantee isolation.

# Mount the static files directory containing dashboard assets (CSS, JS, index.html)
app.mount("/static", StaticFiles(directory="submission_frontend/static"), name="static")


class UnderwriteRequest(BaseModel):
    """Pydantic model representing the underwriting request body."""
    redacted_json: str


class AuditLog(BaseModel):
    """Pydantic model representing the validated compliance audit log."""
    classification: str
    dti_percent: float
    decision: str
    cited_rules: list[str]
    rationale: str


@app.get("/", response_class=HTMLResponse)
async def read_index():
    """Serves the dashboard home page from index.html."""
    index_path = pathlib.Path("submission_frontend/static/index.html")
    if not index_path.exists():
        return HTMLResponse(
            content="<h1>Index page not found. Please scaffold submission_frontend/static/index.html</h1>",
            status_code=404
        )
    html_content = index_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html_content)


@app.post("/api/redact")
async def redact_file(file: UploadFile = File(...)):
    """Accepts an uploaded JSON applicant file and returns redacted JSON.
    
    This endpoint executes the Privacy Shield BEFORE the data is exposed 
    to the AI agents, ensuring GDPR compliance.
    """
    content_bytes = await file.read()
    content_text = content_bytes.decode("utf-8")
    
    # Run the deterministic Privacy Shield
    redacted_json_str = scrub_application_data(content_text)
    
    # Load back into python structures to return as a structured JSON response
    redacted_data = json.loads(redacted_json_str)
    return JSONResponse(content=redacted_data)


@app.post("/api/underwrite")
async def run_underwriting(req: UnderwriteRequest):
    """Executes the sequential agent swarm on the redacted applicant data.
    
    This endpoint runs asynchronously, streaming events from the ADK Runner, 
    and returns a validated or raw compliance audit log.
    """
    session_id = str(uuid.uuid4())
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="mortgagestream",
        session_service=session_service
    )
    
    # Create a fresh agent session for the underwriter persona
    await session_service.create_session(
        app_name="mortgagestream",
        user_id="underwriter",
        session_id=session_id
    )
    
    # Construct the user message using Google GenAI types
    new_message = types.Content(
        role="user",
        parts=[types.Part(text=req.redacted_json)]
    )
    
    final_text = ""
    try:
        # Let's run the agent swarm asynchronously
        async for event in runner.run_async(
            user_id="underwriter",
            session_id=session_id,
            new_message=new_message
        ):
            # Retrieve the final response from each agent. Since the pipeline 
            # is sequential, the last final response will be the compliance agent's output.
            if event.is_final_response():
                if event.message and event.message.parts:
                    parts_text = [p.text for p in event.message.parts if p.text]
                    final_text = "".join(parts_text)
                    
        # Validate the final output produced by the compliance agent
        # Strip markdown json codeblock wrapping if returned by the LLM
        clean_text = final_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()
        
        parsed_json = json.loads(clean_text)
        validated_log = AuditLog.model_validate(parsed_json)
        return validated_log
        
    except Exception as e:
        # Return fallback output to prevent the server from crashing on parsing or model api errors
        return JSONResponse(
            status_code=200,
            content={
                "validated": False,
                "raw_output": final_text,
                "error": str(e)
            }
        )
