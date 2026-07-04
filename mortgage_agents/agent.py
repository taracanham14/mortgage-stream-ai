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
# We set timeout=120.0 to accommodate rate-limiting delays and avoid timeouts.
connection_params = StdioConnectionParams(
    server_params=StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=dict(os.environ)
    ),
    timeout=120.0
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


# Single optimized Underwriting Agent that executes all steps and tools in a single turn.
underwriting_agent = LlmAgent(
    name="underwriting_agent",
    description="Pre-qualifies mortgage applicants, evaluates affordability, and verifies compliance against FCA rules.",
    model=MODEL_NAME,
    tools=[classify_application_risk, analyst_mcp_toolset, compliance_mcp_toolset],
    output_key="audit_log",
    instruction=(
        "You are the Underwriting Agent in the mortgage underwriting pipeline. "
        "Your task is to process the incoming REDACTED applicant JSON data. "
        "You MUST call the following three tools sequentially in a single session: "
        "1. Call `classify_application_risk`, passing: "
        "   - employment_status (from employment.employment_status) "
        "   - variable_annual_income (variable_overtime_bonus_commission from the income section) "
        "   - vulnerability_flag_count (number of items in vulnerability.vulnerability_flags) "
        "   - adverse_credit_flag_count (number of items in adverse_credit.adverse_credit_flags) "
        "2. Call `calculate_affordability` (MCP tool), passing: "
        "   - gross_basic_income (from the income section) "
        "   - guaranteed_overtime_bonus_commission (from the income section) "
        "   - variable_overtime_bonus_commission (from the income section) "
        "   - other_income (from the income section) "
        "   - monthly_commitments (the list of monthly_repayment values from monthly_commitments) "
        "3. Call `query_fca_handbook` (MCP tool), querying relevant keywords based on the applicant's risk factors (e.g. self_employed, vulnerability, affordability, consumer_duty, adverse_credit). "
        "Do not make risk routing or DTI calculations yourself. "
        "You MUST output a single structured JSON audit log containing exactly these keys: "
        "classification, dti_percent, decision, cited_rules, and a plain-English rationale. "
        "Do not wrap your output in anything other than a clean JSON block."
    )
)


# Chain the agents sequentially to form the root agent underwriting swarm.
# ADK requires the top-level variable name to be exactly root_agent.
root_agent = SequentialAgent(
    name="mortgage_underwriting_swarm",
    description="Sequential multi-agent underwriting pipeline.",
    sub_agents=[underwriting_agent]
)
