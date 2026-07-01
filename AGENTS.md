# MortgageStream AI Agent Conventions

This document defines the standing developer and configuration conventions for the MortgageStream AI project. These rules must be strictly followed on every coding task.

## Core Rules

1. **Model Selection**: Use the model `gemini-2.5-flash` for all agents.
2. **Framework & Architecture**: Build agents using `google-adk` with `LlmAgent` and `SequentialAgent`.
3. **Variable Naming**: The top-level agent variable must be named `root_agent`.
4. **Package Initialization**: The file `mortgage_agents/__init__.py` must contain exactly:
   ```python
   from . import agent
   ```
5. **Tool Definition Style**: Expose tools as plain annotated Python functions (ADK function tools). Never wrap them inside a class.
6. **Separation of Concerns**: Keep all deterministic logic (such as risk routing, affordability maths, and FCA rule lookups) inside tools, and never in the model's reasoning.
7. **Security**: Read the API key only from the environment variable `GOOGLE_API_KEY`. Never hardcode it.
8. **Credentials Isolation**: Keep `.env` out of Git (`.gitignore`) and out of the container image (`.dockerignore`).
9. **FastAPI Integration**: The FastAPI application must be asynchronous. You must `await` the ADK Runner directly.
10. **Language & Comments**: Write code, documentation, and user interfaces in UK English, and include professional, detailed code comments.
11. **Runtime & Deployment**: Run the application locally with `uvicorn` and deploy with `gcloud run deploy`. Never use any `agents deploy` command.
