# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Field filtering utility for sparse fieldsets (_elements parameter)"""

from typing import Any

# Fields that are always included regardless of _elements
ALWAYS_INCLUDE_FIELDS = {"type", "identifier"}


def filter_fields(data: dict[str, Any], elements: str | None) -> dict[str, Any]:
    """
    Filter resource fields based on _elements parameter.

    The _elements parameter allows clients to request sparse fieldsets,
    reducing response size and improving performance.

    Args:
        data: Resource dictionary to filter
        elements: Comma-separated list of field names to include, or None for all fields

    Returns:
        Filtered dictionary with only requested fields

    Example:
        >>> data = {"type": "Individual", "identifier": [...], "name": {...}, "birthDate": "1990-01-01"}
        >>> filter_fields(data, "name,birthDate")
        {"type": "Individual", "identifier": [...], "name": {...}, "birthDate": "1990-01-01"}

    Note:
        - "type" and "identifier" are always included (required by API spec)
        - Unknown field names are silently ignored
        - Nested fields can be specified with dot notation (e.g., "name.family")
    """
    if not elements:
        return data

    # Parse requested fields
    requested_fields = {field.strip() for field in elements.split(",")}

    # Build filtered result
    result = {}

    # Always include required fields
    for field in ALWAYS_INCLUDE_FIELDS:
        if field in data:
            result[field] = data[field]

    # Include requested fields
    for field in requested_fields:
        if "." in field:
            # Handle nested field selection (e.g., "name.family")
            result = _add_nested_field(result, data, field)
        elif field in data and field not in ALWAYS_INCLUDE_FIELDS:
            result[field] = data[field]

    return result


def _add_nested_field(result: dict, source: dict, dotted_path: str) -> dict:
    """
    Add a nested field to the result based on dot notation.

    Args:
        result: Result dictionary being built
        source: Source data dictionary
        dotted_path: Field path like "name.family"

    Returns:
        Updated result dictionary
    """
    parts = dotted_path.split(".", 1)
    parent_field = parts[0]

    if parent_field not in source:
        return result

    parent_value = source[parent_field]

    # If requesting specific nested field
    if len(parts) > 1:
        child_path = parts[1]

        # Handle dict parent
        if isinstance(parent_value, dict):
            if parent_field not in result:
                result[parent_field] = {}
            if child_path in parent_value:
                result[parent_field][child_path] = parent_value[child_path]

        # Handle list of dicts
        elif isinstance(parent_value, list):
            if parent_field not in result:
                result[parent_field] = []
            for item in parent_value:
                if isinstance(item, dict) and child_path in item:
                    result[parent_field].append({child_path: item[child_path]})
    else:
        # Include entire parent field
        result[parent_field] = parent_value

    return result


def filter_list(data_list: list[dict[str, Any]], elements: str | None) -> list[dict[str, Any]]:
    """
    Filter a list of resources based on _elements parameter.

    Args:
        data_list: List of resource dictionaries
        elements: Comma-separated list of field names to include

    Returns:
        List of filtered dictionaries
    """
    if not elements:
        return data_list

    return [filter_fields(item, elements) for item in data_list]
