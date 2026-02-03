"""OpenSPP DCI Core Module.

Provides core DCI (Digital Convergence Initiative) API components:
- Message envelope schemas (signature, header, message)
- HTTP Signature signing and verification
- JWKS key management
- Pydantic schemas for Person, Group, Search operations
"""

from . import models
from . import schemas
from . import services
