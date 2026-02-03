import logging

from odoo.orm import domains as orm_domains

from .operators import Operator

_logger = logging.getLogger(__name__)

# GIS operators that will be recognized by the domain parser
GIS_OPERATORS = list(Operator.OPERATION_TO_RELATION.keys())

# Register GIS operators as valid condition operators (Odoo 19)
orm_domains.CONDITION_OPERATORS.update(GIS_OPERATORS)

# Add GIS operators to STANDARD_CONDITION_OPERATORS
# Since STANDARD_CONDITION_OPERATORS is a frozenset, we need to recreate it
orm_domains.STANDARD_CONDITION_OPERATORS = frozenset(list(orm_domains.STANDARD_CONDITION_OPERATORS) + GIS_OPERATORS)

_logger.info(f"Registered {len(GIS_OPERATORS)} GIS operators as standard operators: {', '.join(GIS_OPERATORS)}")

# Odoo 19 uses the Field.condition_to_sql method to handle custom operators
# The GeoField class in fields.py implements this method to handle GIS operators
_logger.info("GIS operators integrated with Odoo 19 domain system via Field.condition_to_sql")
