"""
Mortgage Underwriting Multi-Agent Swarm Configuration
=====================================================

This module constructs the multi-agent UK mortgage underwriting swarm using the 
Google Agent Development Kit (ADK). The swarm consists of three specialised agents
orchestrated sequentially to pre-qualify applicants, evaluate risk, calculate 
affordability, and perform compliance checks.

State Passing via Output Keys:
------------------------------
ADK's SequentialAgent executes sub-agents in order. Each agent's output is saved 
under a specific state key defined by the `output_key` parameter:
1. `orchestrator_agent` -> output saved to `routing`
2. `analyst_agent`      -> output saved to `analysis`
3. `compliance_agent`   -> output saved to `audit_log`

Subsequent agents in the pipeline access the outputs of previous steps by reading 
from the shared conversation state using {curly-brace} templating (e.g. `{routing}` 
and `{analysis}`).

Deterministic Tool Execution:
-----------------------------
To comply with FCA transparency rules and avoid generative errors:
- Orchestrator MUST use `classify_application_risk` to route cases, rather than 
  relying on its own heuristic assessment.
- Analyst MUST use `calculate_affordability` to obtain the total income, debt, and 
  Debt-to-Income (DTI) percentage, as LLMs are prone to arithmetic inaccuracy.
- Compliance MUST use `query_fca_handbook` to retrieve exact regulatory citations, 
  preventing hallucinated rule numbers or policies.
"""

from dotenv import load_dotenv

# Load environment variables from .env file at application startup.
# This ensures that GOOGLE_API_KEY is populated in the environment.
load_dotenv()

import sys
import os
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from .tools import classify_application_risk

# Define the shared Gemini model configuration as per project guidelines.
MODEL_NAME = "gemini-2.5-flash"

# Define the absolute path to the local mcp_server.py script
server_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server.py"))

# Setup connection parameters to launch the MCP server as a subprocess.
# We run using sys.executable (python.exe) and inherit environment variables
# so PYTHONPATH and virtual environment packages are preserved.
connection_params = StdioConnectionParams(
    server_params=StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=dict(os.environ)
    )
)

# Connect to the local MCP server, filtering tools specifically for each agent.
# McpToolset is a BaseToolset, meaning ADK automatically queries it to retrieve
# tools at runtime and handles the server subprocess lifecycle.
analyst_mcp_toolset = McpToolset(
    connection_params=connection_params,
    tool_filter=["calculate_affordability"]
)

compliance_mcp_toolset = McpToolset(
    connection_params=connection_params,
    tool_filter=["query_fca_handbook"]
)


# 1. Orchestrator Agent: Routes application and categorises initial risk.
orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    description="Routes applications based on deterministic risk categorisation rules.",
    model=MODEL_NAME,
    tools=[classify_application_risk],
    output_key="routing",
    instruction=(
        "You are the Orchestrator Agent in the mortgage underwriting pipeline. "
        "Your task is to read the incoming REDACTED applicant JSON data. "
        "You MUST call the `classify_application_risk` tool, passing: "
        "- employment_status (from employment.employment_status) "
        "- variable_annual_income (the variable_overtime_bonus_commission figure from the income section) "
        "- vulnerability_flag_count (the number of items in the vulnerability.vulnerability_flags list) "
        "- adverse_credit_flag_count (the number of items in the adverse_credit.adverse_credit_flags list) "
        "Do not make the risk classification decision yourself. "
        "Report the classification and reasons returned by the tool as a short JSON object."
    )
)


# 2. Analyst Agent: Calculates affordability metrics and evaluates financials.
analyst_agent = LlmAgent(
    name="analyst_agent",
    description="Evaluates applicant affordability using precise mathematical formulas.",
    model=MODEL_NAME,
    tools=[analyst_mcp_toolset],
    output_key="analysis",
    instruction=(
        "You are the Analyst Agent in the mortgage underwriting pipeline. "
        "You receive the applicant data and the risk routing decision as {routing}. "
        "Your task is to assess the applicant's affordability. "
        "You MUST call the `calculate_affordability` tool, passing: "
        "- gross_basic_income (from the income section) "
        "- guaranteed_overtime_bonus_commission (from the income section) "
        "- variable_overtime_bonus_commission (from the income section) "
        "- other_income (from the income section) "
        "- monthly_commitments (the list of monthly_repayment values taken from the monthly_commitments section) "
        "Do not perform any arithmetic calculations, sum any incomes, or calculate DTI yourself. "
        "Output a professional underwriting recommendation referencing the exact "
        "total_annual_income, total_monthly_debt, dti_percent and decision returned by the tool."
    )
)


# 3. Compliance Agent: Audits decisions against the FCA handbook regulations.
compliance_agent = LlmAgent(
    name="compliance_agent",
    description="Audits underwriting recommendations against official FCA regulations.",
    model=MODEL_NAME,
    tools=[compliance_mcp_toolset],
    output_key="audit_log",
    instruction=(
        "You are the Compliance Agent in the mortgage underwriting pipeline. "
        "You receive the analyst recommendation as {analysis} and the routing decision as {routing}. "
        "You MUST call the `query_fca_handbook` tool, querying relevant keywords such as "
        "self_employed, vulnerability, affordability, consumer_duty, or adverse_credit, to retrieve the "
        "official regulatory rules for the decision. "
        "Do not invent or guess any regulatory citations. "
        "Output a single structured JSON audit log containing exactly these keys: "
        "classification, dti_percent, decision, cited_rules, and a plain-English rationale."
    )
)


# Chain the agents sequentially to form the root agent underwriting swarm.
# ADK requires the top-level variable name to be exactly root_agent.
root_agent = SequentialAgent(
    name="mortgage_underwriting_swarm",
    description="Sequential multi-agent underwriting pipeline containing Orchestrator, Analyst, and Compliance agents.",
    sub_agents=[orchestrator_agent, analyst_agent, compliance_agent]
)
