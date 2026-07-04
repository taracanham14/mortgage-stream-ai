"""
Privacy Shield Module using Microsoft Presidio
==============================================

This module provides a secure PII-redaction gateway (Privacy Shield) powered by
Microsoft Presidio Analyzer and Anonymizer. It anonymises sensitive personal 
identifiable information (PII) before transmission to Large Language Model agents.

Architectural and Regulatory Rationale:
---------------------------------------
1. GDPR Data Minimisation (Article 5(1)(c)):
   Organisations must only process the minimum personal data necessary. Redacting
   PII ensures compliance by design and prevents models from storing sensitive details.

2. FCA Data-Handling Guidelines:
   Protecting consumer sort codes, account numbers, and National Insurance numbers
   mitigates systemic financial crime and unauthorized consumer profiling risks.

3. Microsoft Presidio with Deterministic Fallback:
   String values are passed through NLP and regex-based engines to identify PII.
   If Presidio or its NLP model (SpaCy) fails to load, a robust deterministic 
   field-level and regex-based redaction acts as a fallback to guarantee service continuity.
"""

import copy
import json
import re
import sys

# Try to initialize Microsoft Presidio engines.
# If they fail (e.g., due to model loading issues), we mark PRESIDIO_AVAILABLE = False
# and fall back to our deterministic key-and-regex based redaction.
PRESIDIO_AVAILABLE = False
try:
    from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    # Configure the NLP engine with the downloaded large English SpaCy model.
    # We use en_core_web_lg for higher recognition accuracy of names and context.
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [
            {"lang_code": "en", "model_name": "en_core_web_lg"}
        ],
    }
    provider = NlpEngineProvider(nlp_configuration=nlp_config)
    nlp_engine = provider.create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    anonymizer = AnonymizerEngine()

    # Custom PatternRecognizer for UK Sort Codes:
    # Matches: two digits, optional hyphen, two digits, optional hyphen, two digits.
    # Examples: 12-34-56, 12 34 56, 123456
    sort_code_pattern = Pattern(
        name="uk_sort_code_pattern",
        regex=r"\b\d{2}[-\s]?\d{2}[-\s]?\d{2}\b",
        score=0.85
    )
    sort_code_recognizer = PatternRecognizer(
        supported_entity="UK_SORT_CODE",
        patterns=[sort_code_pattern],
        supported_language="en"
    )

    # Custom PatternRecognizer for UK Account Numbers:
    # Matches: exactly 8-digit numbers on word boundaries.
    account_number_pattern = Pattern(
        name="uk_account_number_pattern",
        regex=r"\b\d{8}\b",
        score=0.85
    )
    account_number_recognizer = PatternRecognizer(
        supported_entity="UK_ACCOUNT_NUMBER",
        patterns=[account_number_pattern],
        supported_language="en"
    )

    # Custom PatternRecognizer for UK National Insurance Number (NINO):
    # Matches two prefix letters (allowing test prefixes like QQ), 6 digits, and a suffix letter.
    nino_pattern = Pattern(
        name="uk_nino_pattern",
        regex=r"\b[A-CEGHJ-PQR-TW-Z][A-CEGHJ-NPQR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b",
        score=0.85
    )
    nino_recognizer = PatternRecognizer(
        supported_entity="UK_NINO",
        patterns=[nino_pattern],
        supported_language="en"
    )

    # Custom PatternRecognizer for UK Postcodes:
    postcode_pattern = Pattern(
        name="uk_postcode_pattern",
        regex=r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b",
        score=0.85
    )
    postcode_recognizer = PatternRecognizer(
        supported_entity="UK_POSTCODE",
        patterns=[postcode_pattern],
        supported_language="en"
    )

    # Register the custom recognizers with the analyzer registry
    analyzer.registry.add_recognizer(sort_code_recognizer)
    analyzer.registry.add_recognizer(account_number_recognizer)
    analyzer.registry.add_recognizer(nino_recognizer)
    analyzer.registry.add_recognizer(postcode_recognizer)

    PRESIDIO_AVAILABLE = True

except Exception as ex:
    print(
        f"Warning: Presidio initialization failed ({ex}). "
        "Falling back to deterministic redaction.",
        file=sys.stderr
    )


# =====================================================================
# Deterministic Fallback Implementation (Original Logic)
# =====================================================================

# Compile regex patterns once for fallback performance.
NINO_PATTERN = re.compile(
    r'[A-CEGHJ-PQR-TW-Z][A-CEGHJ-NPQR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]', 
    re.IGNORECASE
)
POSTCODE_PATTERN = re.compile(
    r'\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b',
    re.IGNORECASE
)
SORT_CODE_PATTERN = re.compile(r'\d{2}[-\s]?\d{2}[-\s]?\d{2}')
ACCOUNT_NUMBER_PATTERN = re.compile(r'\b\d{8}\b')
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')


def redact_string_fallback(value: str) -> str:
    """Applies regex redaction rules to a single string value as a safety backstop."""
    value = NINO_PATTERN.sub("[REDACTED_NINO]", value)
    value = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    value = POSTCODE_PATTERN.sub("[REDACTED_POSTCODE]", value)
    value = ACCOUNT_NUMBER_PATTERN.sub("[REDACTED_ACCOUNT]", value)
    value = SORT_CODE_PATTERN.sub("[REDACTED_SORTCODE]", value)
    return value


def deterministic_fallback_scrub_application_data(raw_json_string: str) -> str:
    """Parses a raw JSON string and redacts PII using the original deterministic key-and-regex rules."""
    parsed_data = json.loads(raw_json_string)
    working_copy = copy.deepcopy(parsed_data)
    
    def walk_and_redact(data):
        if isinstance(data, dict):
            redacted_dict = {}
            for key, val in data.items():
                key_lower = key.lower()
                if key_lower in ("applicant_name", "name", "full_name", "forename", "surname", "previous_name", "maiden_name", "account_holder_name"):
                    redacted_dict[key] = "[REDACTED_NAME]"
                elif key_lower == "title":
                    redacted_dict[key] = "[REDACTED_TITLE]"
                elif key_lower in ("national_insurance_number", "nino"):
                    redacted_dict[key] = "[REDACTED_NINO]"
                elif key_lower in ("bank_account", "account_number"):
                    redacted_dict[key] = "[REDACTED_ACCOUNT]"
                elif key_lower == "sort_code":
                    redacted_dict[key] = "[REDACTED_SORTCODE]"
                elif key_lower in ("date_of_birth", "dob"):
                    redacted_dict[key] = "[REDACTED_DOB]"
                elif key_lower in ("current_address", "address"):
                    redacted_dict[key] = "[REDACTED_ADDRESS]"
                elif key_lower == "postcode":
                    redacted_dict[key] = "[REDACTED_POSTCODE]"
                elif key_lower == "email":
                    redacted_dict[key] = "[REDACTED_EMAIL]"
                elif key_lower in ("mobile_telephone", "telephone", "phone"):
                    redacted_dict[key] = "[REDACTED_PHONE]"
                else:
                    redacted_dict[key] = walk_and_redact(val)
            return redacted_dict
            
        elif isinstance(data, list):
            return [walk_and_redact(item) for item in data]
            
        elif isinstance(data, str):
            return redact_string_fallback(data)
            
        else:
            return data

    redacted_data = walk_and_redact(working_copy)
    return json.dumps(redacted_data, indent=2)


# =====================================================================
# Main Scrubbing Function
# =====================================================================

def scrub_application_data(raw_json_string: str) -> str:
    """Parses a raw JSON string of applicant data and redacts all PII.

    This function attempts to use Microsoft Presidio for contextual PII 
    identification and anonymisation of string values.
    
    If Presidio is unavailable or fails during processing, it falls back to 
    the original deterministic dictionary key check and regular expression rules.

    Args:
        raw_json_string: The raw JSON string containing mortgage applicant details.

    Returns:
        A pretty-printed JSON string (indent=2) with sensitive PII scrubbed.
    """
    if PRESIDIO_AVAILABLE:
        try:
            parsed_data = json.loads(raw_json_string)

            # Define the Presidio Anonymizer replacement mapping for our target entity types
            operators = {
                "PERSON": OperatorConfig("replace", {"new_value": "[REDACTED_NAME]"}),
                "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[REDACTED_EMAIL]"}),
                "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[REDACTED_PHONE]"}),
                "UK_NINO": OperatorConfig("replace", {"new_value": "[REDACTED_NINO]"}),
                "UK_SORT_CODE": OperatorConfig("replace", {"new_value": "[REDACTED_SORTCODE]"}),
                "UK_ACCOUNT_NUMBER": OperatorConfig("replace", {"new_value": "[REDACTED_ACCOUNT]"}),
                "UK_POSTCODE": OperatorConfig("replace", {"new_value": "[REDACTED_POSTCODE]"}),
            }

            def walk_and_scrub(data):
                if isinstance(data, dict):
                    redacted_dict = {}
                    for key, val in data.items():
                        key_lower = key.lower()
                        if key_lower in ("applicant_name", "name", "full_name", "forename", "surname", "previous_name", "maiden_name", "account_holder_name"):
                            redacted_dict[key] = "[REDACTED_NAME]"
                        elif key_lower == "title":
                            redacted_dict[key] = "[REDACTED_TITLE]"
                        elif key_lower in ("national_insurance_number", "nino"):
                            redacted_dict[key] = "[REDACTED_NINO]"
                        elif key_lower in ("bank_account", "account_number"):
                            redacted_dict[key] = "[REDACTED_ACCOUNT]"
                        elif key_lower == "sort_code":
                            redacted_dict[key] = "[REDACTED_SORTCODE]"
                        elif key_lower in ("date_of_birth", "dob"):
                            redacted_dict[key] = "[REDACTED_DOB]"
                        elif key_lower in ("current_address", "address"):
                            redacted_dict[key] = "[REDACTED_ADDRESS]"
                        elif key_lower == "postcode":
                            redacted_dict[key] = "[REDACTED_POSTCODE]"
                        elif key_lower == "email":
                            redacted_dict[key] = "[REDACTED_EMAIL]"
                        elif key_lower in ("mobile_telephone", "telephone", "phone"):
                            redacted_dict[key] = "[REDACTED_PHONE]"
                        else:
                            redacted_dict[key] = walk_and_scrub(val)
                    return redacted_dict
                elif isinstance(data, list):
                    return [walk_and_scrub(item) for item in data]
                elif isinstance(data, str):
                    # Run the string through the Presidio analyzer
                    results = analyzer.analyze(
                        text=data,
                        language="en",
                        entities=["UK_NINO", "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "UK_SORT_CODE", "UK_ACCOUNT_NUMBER", "UK_POSTCODE"]
                    )
                    
                    # Anonymize using our custom operators
                    scrubbed = anonymizer.anonymize(
                        text=data,
                        analyzer_results=results,
                        operators=operators
                    )
                    return scrubbed.text
                else:
                    return data

            scrubbed_data = walk_and_scrub(parsed_data)
            return json.dumps(scrubbed_data, indent=2)

        except Exception as e:
            print(
                f"Warning: Presidio scrubbing failed ({e}). "
                "Calling fallback deterministic redaction.",
                file=sys.stderr
            )
            # Catch errors in walk/scrub and default to the fallback logic
            return deterministic_fallback_scrub_application_data(raw_json_string)

    # Default fallback when Presidio is not initialized
    return deterministic_fallback_scrub_application_data(raw_json_string)
