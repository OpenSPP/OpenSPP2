# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Standalone DCI verification utility functions.

These functions extract, parse, and compare DCI response data without
depending on Odoo models. Both the wizard and the detail model call
these functions instead of implementing their own logic.
"""

import logging

_logger = logging.getLogger(__name__)


def parse_dci_response(response):
    """Parse DCI response to determine verification status.

    Args:
        response: Dict response from DCI search

    Returns:
        Verification status string: 'verified', 'not_found', or 'error'
    """
    # Check for error status in header
    if "header" in response:
        header = response["header"]
        if header.get("status") == "rjct":
            return "error"

    # Check for search_response in message
    if "message" in response:
        message = response["message"]
        if "search_response" in message:
            search_responses = message["search_response"]
            if search_responses:
                # Check first response item
                first_response = search_responses[0]
                if first_response.get("status") == "succ":
                    # Check if we have data
                    data = first_response.get("data", [])
                    if data:
                        return "verified"
                    return "not_found"
                elif first_response.get("status") == "rjct":
                    return "error"
            return "not_found"

    # OpenCRVS direct response format (record directly in response)
    if "identifier" in response or "name" in response:
        return "verified"

    # Unexpected response format
    _logger.warning(
        "Unexpected DCI response structure, treating as not found. Keys: %s",
        list(response.keys()) if isinstance(response, dict) else type(response),
    )
    return "not_found"


def extract_person_from_dci_response(response):
    """Extract normalized person data from DCI response.

    Args:
        response: Dict response from DCI search

    Returns:
        Dict with normalized person data or None if not found.
        Keys: given_name, family_name, birth_date, sex (all uppercase names,
        lowercase sex).
    """
    person_data = None

    # Check for search_response in message (standard DCI format)
    if "message" in response:
        message = response["message"]
        if "search_response" in message:
            search_responses = message["search_response"]
            if search_responses:
                first_response = search_responses[0]
                data = first_response.get("data", {})
                if data:
                    # Data can be a list or a dict depending on registry
                    if isinstance(data, list):
                        person_data = data[0]  # First matching record
                    elif isinstance(data, dict):
                        # Check for reg_records (OpenCRVS SPDCI format)
                        if "reg_records" in data and data["reg_records"]:
                            person_data = data["reg_records"][0]
                        else:
                            person_data = data  # Direct dict response

    # OpenCRVS direct response format
    if not person_data and ("identifier" in response or "name" in response):
        person_data = response

    if not person_data:
        return None

    # Normalize the person data
    normalized = {}

    # Extract name
    if "name" in person_data:
        name = person_data["name"]
        if isinstance(name, dict):
            normalized["given_name"] = name.get("given_name", "").strip().upper()
            normalized["family_name"] = name.get("surname", "").strip().upper()
        elif isinstance(name, str):
            normalized["given_name"] = name.strip().upper()

    # Extract birth date
    if "birth_date" in person_data:
        normalized["birth_date"] = person_data["birth_date"]
    elif "birthdate" in person_data:
        normalized["birth_date"] = person_data["birthdate"]

    # Extract sex/gender
    if "sex" in person_data:
        normalized["sex"] = person_data["sex"].lower()
    elif "gender" in person_data:
        normalized["sex"] = person_data["gender"].lower()

    return normalized


def check_data_matches(person_data, given_name, family_name, birthdate, gender_display):
    """Check if DCI data matches provided fields.

    Args:
        person_data: Dict from extract_person_from_dci_response
        given_name: Given name string from CR/wizard
        family_name: Family name string from CR/wizard
        birthdate: date object or None from CR/wizard
        gender_display: Gender display string (e.g., "Male") or None

    Returns:
        Tuple of (matches: bool, mismatches: list[str])
    """
    mismatches = []

    # Compare given name
    if person_data.get("given_name"):
        cr_given_name = (given_name or "").strip().upper()
        dci_given_name = person_data["given_name"]
        if cr_given_name != dci_given_name:
            mismatches.append(f"given_name: CR='{cr_given_name}' vs DCI='{dci_given_name}'")

    # Compare family name
    if person_data.get("family_name"):
        cr_family_name = (family_name or "").strip().upper()
        dci_family_name = person_data["family_name"]
        if cr_family_name != dci_family_name:
            mismatches.append(f"family_name: CR='{cr_family_name}' vs DCI='{dci_family_name}'")

    # Compare birth date
    if person_data.get("birth_date") and birthdate:
        cr_birthdate = str(birthdate)
        dci_birthdate = person_data["birth_date"]
        # Handle different date formats (YYYY-MM-DD)
        if cr_birthdate[:10] != dci_birthdate[:10]:
            mismatches.append(f"birthdate: CR='{cr_birthdate}' vs DCI='{dci_birthdate}'")

    # Compare gender/sex
    if person_data.get("sex") and gender_display:
        cr_gender = gender_display.lower()
        dci_sex = person_data["sex"].lower()
        if cr_gender != dci_sex:
            mismatches.append(f"gender: CR='{cr_gender}' vs DCI='{dci_sex}'")

    return (len(mismatches) == 0, mismatches)
