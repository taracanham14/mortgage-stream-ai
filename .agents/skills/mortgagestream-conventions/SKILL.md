---
name: mortgagestream-conventions
description: holds the build conventions for the MortgageStream AI Google ADK project and should be used whenever writing or editing code in this workspace.
---

# MortgageStream AI Build Conventions

This skill governs the development and configuration conventions for the MortgageStream AI project. Follow these conventions whenever writing, editing, or refactoring code in this workspace.

## Agent Architecture
- **Model**: Use the model `gemini-2.5-flash` for all agents.
- **Framework**: Build agents with `google-adk` using `LlmAgent` and `SequentialAgent`.
- **Top-Level Agent**: The top-level agent variable must be named `root_agent`.
- **Package structure**: The agent package must contain an `__init__.py` file containing exactly:
  ```python
  from . import agent
  ```

## Tools and Logic
- **Tool definitions**: Expose tools as plain annotated Python functions (ADK function tools), never as a class.
- **Deterministic logic location**: Keep all deterministic logic (such as risk routing, affordability maths, FCA rule lookup) inside tools and never in the model's reasoning.

## Security and Environment
- **API key usage**: Read the API key only from the environment variable `GOOGLE_API_KEY`. Never hardcode it.
- **Credentials isolation**: Keep `.env` out of Git (.gitignore) and out of the container image (.dockerignore).

## Web Application and Deployment
- **FastAPI Integration**: The FastAPI application must be asynchronous. You must `await` the ADK Runner directly.
- **Command tools**: Run the application locally with `uvicorn`. Deploy the application using `gcloud run deploy` only. Never use any `agents deploy` command.

## Code Style
- **Language**: Use UK English spelling (e.g., *minimisation*, *organisation*, *programme*).
- **Documentation**: Include extensive, professional code comments explaining architectural details, regulatory checks (GDPR, FCA), and code design decisions.
