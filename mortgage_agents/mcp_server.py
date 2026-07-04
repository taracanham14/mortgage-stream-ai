"""
Model Context Protocol (MCP) Server for Mortgage Underwriting
=============================================================

This module runs a minimal MCP server over stdio, exposing the deterministic
underwriting tools (calculate_affordability and query_fca_handbook) to the
Google ADK agents.

Stdio Logging Safety:
--------------------
Because this server communicates with the client over stdout, printing anything 
directly to stdout will corrupt the JSON-RPC packet stream. All custom logging 
or debugging messages must be sent to stderr (sys.stderr) instead.
"""

import os
import sys

# Ensure the project root is in sys.path so we can import from mortgage_agents.tools
# regardless of the working directory from which this script is launched by the client.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastmcp import FastMCP
from mortgage_agents import tools

# Instantiate the FastMCP server with a descriptive name
mcp = FastMCP("MortgageUnderwritingMCPServer")


@mcp.tool()
async def calculate_affordability(
    gross_basic_income: float, 
    guaranteed_overtime_bonus_commission: float, 
    variable_overtime_bonus_commission: float, 
    other_income: float, 
    monthly_commitments: list
) -> dict:
    """Calculates total income, total debt, DTI percentage and provides a decision.

    This tool is used to deterministically sum incomes and commitments, calculate 
    the applicant's DTI percentage, and determine the affordability band.

    Args:
        gross_basic_income: The basic gross annual income in GBP.
        guaranteed_overtime_bonus_commission: The guaranteed annual variable income in GBP.
        variable_overtime_bonus_commission: The variable annual variable income in GBP.
        other_income: Any other annual income in GBP.
        monthly_commitments: List of monthly commitments. Can be a list of numbers or 
            a list of dictionaries containing a 'monthly_repayment' key.
    """
    # Rate limit sleep disabled by developer request to speed up underwriting swarm.
        
    # Execute the deterministic affordability calculation from tools.py
    return tools.calculate_affordability(
        gross_basic_income=gross_basic_income,
        guaranteed_overtime_bonus_commission=guaranteed_overtime_bonus_commission,
        variable_overtime_bonus_commission=variable_overtime_bonus_commission,
        other_income=other_income,
        monthly_commitments=monthly_commitments
    )


@mcp.tool()
async def query_fca_handbook(keyword: str) -> dict:
    """Queries a mock FCA Handbook database for regulations related to a keyword.

    This tool provides a deterministic lookup of FCA (Financial Conduct Authority) 
    regulations, preventing the LLM from hallucinating or misrepresenting policy rules.

    Args:
        keyword: The search keyword (e.g., 'self_employed', 'vulnerability', 'affordability', 'consumer_duty', 'adverse_credit').
    """
    # Rate limit sleep disabled by developer request to speed up underwriting swarm.
        
    # Execute the deterministic FCA Handbook query from tools.py
    return tools.query_fca_handbook(keyword=keyword)


if __name__ == "__main__":
    # Start the MCP server over stdio transport. Uvicorn/FastAPI or other 
    # subprocess launchers will communicate with this script using stdin/stdout.
    mcp.run()
