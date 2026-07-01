"""
MortgageStream AI Underwriting Tests
====================================

This test module contains automated checks to verify the deterministic core
of the MortgageStream AI application. 

These tests act as critical guards to guarantee the deterministic behavior
that the whole project relies on (such as exact financial ratios, reliable
GDPR-compliant redactions, and consistent risk-routing classifications).
"""

import json
from privacy import scrub_application_data
from mortgage_agents.tools import calculate_affordability, classify_application_risk


def test_affordability_tool():
    """Guards the deterministic guarantees of the affordability calculator."""
    # Pass case (DTI < 36%): 60,000 / 12 = 5,000 monthly income. Debt 500 = 10% DTI.
    res_pass = calculate_affordability(60000, 0, 0, 0, [500])
    assert res_pass["decision"] == "Pass"

    # Review case (36% <= DTI <= 45%): 48,000 / 12 = 4,000 monthly income. Debt 1,500 = 37.5% DTI.
    res_review = calculate_affordability(48000, 0, 0, 0, [1500])
    assert res_review["decision"] == "Review"

    # Fail case (DTI > 45%): 30,000 / 12 = 2,500 monthly income. Debt 1,300 = 52% DTI.
    res_fail = calculate_affordability(30000, 0, 0, 0, [1300])
    assert res_fail["decision"] == "Fail"

    # Summation check: Income sum = 52,000, Debt sum = 500.
    res_sum = calculate_affordability(40000, 5000, 5000, 2000, [200, 300])
    assert res_sum["total_annual_income"] == 52000
    assert res_sum["total_monthly_debt"] == 500


def test_risk_routing_tool():
    """Guards the deterministic risk classification routing logic."""
    # Self-employed status must route to High-Risk
    assert classify_application_risk('Self-Employed', 0, 0, 0)["classification"] == "High-Risk"

    # Standard salaried PAYE applicant routes to Standard
    assert classify_application_risk('Employed', 0, 0, 0)["classification"] == "Standard"

    # Variable income triggers High-Risk routing
    assert classify_application_risk('Employed', 12000, 0, 0)["classification"] == "High-Risk"

    # Vulnerability flags trigger High-Risk routing
    assert classify_application_risk('Employed', 0, 1, 0)["classification"] == "High-Risk"

    # Adverse credit flags alone trigger High-Risk routing
    assert classify_application_risk('Employed', 0, 0, 1)["classification"] == "High-Risk"


def test_privacy_shield_redaction():
    """Guards the GDPR-compliant PII redaction guarantees of the Privacy Shield Gateway."""
    # Build a realistic factfind-shaped JSON string containing sensitive PII fields
    factfind_data = {
        "personal_details": {
            "title": "Mr",
            "forename": "Alexander",
            "surname": "Hamilton",
            "date_of_birth": "1990-01-11",
            "national_insurance_number": "QQ123456C"
        },
        "contact_details": {
            "email": "alex.hamilton@example.com",
            "mobile_telephone": "07700900088",
            "current_address": "10 Downing Street",
            "postcode": "SW1A 1AA"
        },
        "bank_details": {
            "account_holder_name": "Alexander Hamilton",
            "account_number": "12345678",
            "sort_code": "12-34-56"
        }
    }
    
    raw_json_str = json.dumps(factfind_data)
    
    # Run the Privacy Shield gateway to scrub all PII
    redacted_json_str = scrub_application_data(raw_json_str)
    
    # Assert that none of the raw sensitive values appear anywhere in the redacted output string
    assert "Alexander" not in redacted_json_str
    assert "Hamilton" not in redacted_json_str
    assert "QQ123456C" not in redacted_json_str
    assert "12345678" not in redacted_json_str
    assert "12-34-56" not in redacted_json_str
    assert "SW1A 1AA" not in redacted_json_str
    assert "alex.hamilton@example.com" not in redacted_json_str
