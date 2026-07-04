"""
Mortgage Underwriting Tools Module
==================================

This module defines the deterministic toolset for the MortgageStream AI system.
In accordance with Google ADK conventions, these tools are defined as plain, 
type-annotated Python functions. The Google-style docstrings serve as the tool
descriptions parsed by the ADK framework to instruct the agents.

Design Philosophy & Regulatory Compliance:
1. LLM Arithmetic Unreliability:
   Large Language Models (LLMs) are probabilistic, auto-regressive token predictors. 
   They are notoriously unreliable at performing exact arithmetic calculations, 
   such as dividing large financial figures or computing precise percentages (like 
   Debt-to-Income ratios). To avoid calculation errors, all mathematical operations 
   are kept strictly in compiled, deterministic Python code.

2. Auditable Routing Logic:
   Under FCA (Financial Conduct Authority) guidelines, lending decisions must be 
   explainable, transparent, and consistent. Allowing a generative model to make 
   freeform routing decisions introduces bias and inconsistency. The risk routing tool 
   (`classify_application_risk`) uses fixed, transparent rules to generate an 
   auditable trace of why a file was categorised as High-Risk or Standard.

3. Prevention of Policy Hallucination:
   LLMs can easily hallucinate regulatory guidelines or mix up specific handbook 
   sections. The FCA Handbook query tool (`query_fca_handbook`) acts as a search index 
   providing exact, unalterable regulatory citations.
"""


def calculate_affordability(
    gross_basic_income: float, 
    guaranteed_overtime_bonus_commission: float, 
    variable_overtime_bonus_commission: float, 
    other_income: float, 
    monthly_commitments: list
) -> dict:
    """Calculates the total income, total debt, DTI percentage and provides a decision.

    This tool is used to deterministically sum incomes and commitments, calculate 
    the applicant's DTI percentage, and determine the affordability band. It ensures 
    that mathematical calculations are kept out of the LLM's non-deterministic 
    reasoning space, preventing arithmetic errors.

    Args:
        gross_basic_income: The basic gross annual income in GBP.
        guaranteed_overtime_bonus_commission: The guaranteed annual variable income in GBP.
        variable_overtime_bonus_commission: The variable annual variable income in GBP.
        other_income: Any other annual income in GBP.
        monthly_commitments: List of monthly commitments. Can be a list of numbers or 
            a list of dictionaries containing a 'monthly_repayment' key.

    Returns:
        dict: A dictionary containing:
            - 'total_annual_income' (float): Sum of all annual incomes.
            - 'total_monthly_debt' (float): Sum of all monthly commitments.
            - 'dti_percent' (float): The calculated Debt-to-Income percentage, rounded to 2 decimal places.
            - 'decision' (str): The decision recommendation ('Pass', 'Review', or 'Fail').
    """
    # Sum the four income figures
    total_annual_income = (
        gross_basic_income + 
        guaranteed_overtime_bonus_commission + 
        variable_overtime_bonus_commission + 
        other_income
    )

    # Sum the monthly commitments, handling both lists of numbers and lists of dicts
    total_monthly_debt = 0.0
    if monthly_commitments:
        for item in monthly_commitments:
            if isinstance(item, dict):
                total_monthly_debt += float(item.get("monthly_repayment", 0.0))
            elif isinstance(item, (int, float)):
                total_monthly_debt += float(item)

    # Guard against division by zero or negative total annual income
    if total_annual_income <= 0:
        return {
            "total_annual_income": total_annual_income,
            "total_monthly_debt": total_monthly_debt,
            "dti_percent": 0.0,
            "decision": "Fail",
            "error": "Total annual income must be greater than zero."
        }

    # Convert total annual income to monthly income (standard UK financial divisor)
    monthly_income = total_annual_income / 12.0
    
    # Calculate Debt-to-Income ratio as a percentage
    dti_percent = (total_monthly_debt / monthly_income) * 100.0
    dti_percent_rounded = round(dti_percent, 2)
    
    # Apply strict deterministic thresholds for affordability decisions
    # Under 36% DTI passes, 36-45% requires review, over 45% is a fail.
    if dti_percent_rounded < 36.0:
        decision = "Pass"
    elif dti_percent_rounded <= 45.0:
        decision = "Review"
    else:
        decision = "Fail"
        
    return {
        "total_annual_income": total_annual_income,
        "total_monthly_debt": total_monthly_debt,
        "dti_percent": dti_percent_rounded,
        "decision": decision
    }


def query_fca_handbook(keyword: str) -> dict:
    """Queries a mock FCA Handbook database for regulations related to a keyword.

    This tool provides a deterministic lookup of FCA (Financial Conduct Authority) 
    regulations, preventing the LLM from hallucinating or misrepresenting policy rules.

    Args:
        keyword: The search keyword (e.g., 'self_employed', 'vulnerability', 'affordability', 'consumer_duty', 'adverse_credit').

    Returns:
        dict: A dictionary containing:
            - 'keyword' (str): The keyword queried.
            - 'rule' (str): The plain-English regulatory rule text or a not-found message.
    """
    # Standardise input for case-insensitive lookup
    clean_keyword = keyword.strip().lower()
    
    # Mock FCA database mapping keywords to plain English explanations
    fca_rules = {
        "self_employed": (
            "FCA MCOB 11.6.2R: Firms must assess affordability based on the self-employed "
            "applicant's share of net profit or salary and dividends, verified using audited "
            "accounts or HMRC tax calculations (SA302)."
        ),
        "vulnerability": (
            "FCA FG21/1: Guidance on the fair treatment of vulnerable customers. Firms must "
            "identify drivers of vulnerability (health, life events, resilience, capability) "
            "and adapt underwriting processes to avoid customer detriment."
        ),
        "affordability": (
            "FCA MCOB 11.6.2R: Underwriters must assess affordability based on verified income "
            "and expenditure, ensuring the customer can sustain monthly payments without experiencing "
            "financial distress."
        ),
        "consumer_duty": (
            "FCA Principle 12: Consumer Duty. Firms must act to deliver good outcomes for retail "
            "customers, ensuring products represent fair value and support consumer understanding "
            "and financial resilience."
        ),
        "adverse_credit": (
            "FCA MCOB 11.6.3R: Firms must take appropriate account of the applicant's credit history, "
            "particularly where there is evidence of adverse credit (e.g., CCJs, defaults, or recent "
            "late payments) to ensure lending is responsible and sustainable."
        )
    }
    
    # Retrieve the rule or attempt a partial match
    rule = fca_rules.get(clean_keyword)
    if not rule:
        for key, val in fca_rules.items():
            if key in clean_keyword or clean_keyword in key:
                rule = val
                break
                
    if not rule:
        rule = f"No specific FCA handbook citation found for '{keyword}'."
        
    return {
        "keyword": keyword,
        "rule": rule
    }


def classify_application_risk(
    employment_status: str, 
    variable_annual_income: float, 
    vulnerability_flag_count: int,
    adverse_credit_flag_count: int
) -> dict:
    """Classifies the underwriting risk of the mortgage application.

    This tool deterministically routes applications to Standard or High-Risk profiles 
    based on fixed criteria, ensuring consistent and auditable routing decisions 
    independent of LLM reasoning.

    Args:
        employment_status: The employment status of the applicant (e.g., 'Employed', 'Self-Employed').
        variable_annual_income: Annual non-guaranteed variable income in GBP.
        vulnerability_flag_count: The number of active vulnerability flags on the account.
        adverse_credit_flag_count: The number of active adverse credit flags on the account.

    Returns:
        dict: A dictionary containing:
            - 'classification' (str): Either 'Standard' or 'High-Risk'.
            - 'reasons' (list of str): Detailed list of the rules that triggered the classification.
    """
    # Rate limit sleep disabled by developer request to speed up underwriting swarm.

    reasons = []
    
    # Rule 1: Self-employed status requires SA302 accounting verification
    if employment_status.strip().lower() == "self-employed":
        reasons.append("Applicant is self-employed (requires SA302 verification).")
        
    # Rule 2: Non-guaranteed variable income requires additional underwriting scrutiny
    if variable_annual_income > 0:
        reasons.append("Income pattern includes non-guaranteed variable overtime, bonus, commission or dividends.")
        
    # Rule 3: Adverse credit flags require detailed assessment of repayment history
    if adverse_credit_flag_count > 0:
        reasons.append(f"Applicant has {adverse_credit_flag_count} active adverse credit flag(s) requiring credit history assessment.")
        
    # Rule 4: Vulnerable customers require specialised, empathetic manual review
    if vulnerability_flag_count > 0:
        reasons.append(f"Applicant has {vulnerability_flag_count} active vulnerability flag(s) requiring manual review.")
        
    # Determine risk routing based on matched rules
    if reasons:
        classification = "High-Risk"
    else:
        classification = "Standard"
        reasons.append("Application meets standard PAYE salaried criteria without variable income, adverse credit, or vulnerability flags.")
        
    return {
        "classification": classification,
        "reasons": reasons
    }
