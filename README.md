# OpenSPP

[![CI](https://github.com/OpenSPP/OpenSPP2/actions/workflows/ci.yml/badge.svg)](https://github.com/OpenSPP/OpenSPP2/actions/workflows/ci.yml)
[![pre-commit](https://github.com/OpenSPP/OpenSPP2/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/OpenSPP/OpenSPP2/actions/workflows/pre-commit.yml)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](LICENSE)
[![Odoo](https://img.shields.io/badge/Odoo-19.0-875A7B.svg)](https://www.odoo.com/)

**Open-source Social Protection Platform** for managing beneficiary registries, cash transfer programs, in-kind distribution, and grievance redressal at scale.

Built on [Odoo 19](https://www.odoo.com/) | [Documentation](https://docs.openspp.org) | [Website](https://openspp.org)

---

## Key Features

- **Social Registry** - Unified beneficiary database for individuals and households with deduplication
- **Program Management** - Configure eligibility rules, enrollment cycles, and benefit calculations
- **Cash & In-Kind Transfers** - Manage entitlements with payment integration and inventory tracking
- **Consent Management** - DPV-aligned consent lifecycle with GDPR-compliant audit trails
- **Approval Workflows** - Multi-tier approval chains with CEL-based business rules
- **Change Requests** - Auditable data update workflows with conflict detection
- **GIS Integration** - Geographic visualization, admin boundary management, HDX integration
- **Grievance Redressal** - Track and resolve beneficiary complaints through customizable stages
- **Disaster Response (DRIMS)** - Inventory management for emergency relief distribution
- **REST API v2** - Standards-aligned API with consent-aware data sharing
- **DCI Interoperability** - Connect to CRVS, identity systems, and other registries
- **No-Code Studio** - Configure custom fields, events, and change requests without coding
- **Audit Trail** - Comprehensive logging with tamper-resistant backends

## Quick Start

```bash
git clone https://github.com/OpenSPP/OpenSPP2.git
cd OpenSPP2
docker compose --profile ui up -d
```

Access at **http://localhost:8069** (login: `admin` / password: `admin`)

### Demo Options

| Demo | Command | Description |
|------|---------|-------------|
| **SP-MIS** | `ODOO_INIT_MODULES=spp_mis_demo_v2 docker compose --profile ui up -d` | Full social protection MIS with sample programs |
| **DRIMS** | `ODOO_INIT_MODULES=spp_drims_sl_demo docker compose --profile ui up -d` | Disaster relief inventory (Sri Lanka config) |
| **Social Registry** | `ODOO_INIT_MODULES=spp_starter_social_registry docker compose --profile ui up -d` | Social registry only |

### Reset Database

```bash
docker compose --profile ui down -v
```

## Architecture

OpenSPP follows a layered architecture:

| Layer | Modules | Purpose |
|-------|---------|---------|
| **Foundation** | `spp_registry`, `spp_security`, `spp_area` | Core data models and security |
| **Capabilities** | `spp_programs`, `spp_approval`, `spp_change_request_v2` | Business logic and workflows |
| **Integration** | `spp_api_v2`, `spp_dci_*` | External system connectivity |
| **Extensions** | `spp_drims`, `spp_grm`, `spp_gis` | Domain-specific features |

## Documentation

- **[Getting Started Guide](https://docs.openspp.org/getting-started/)**
- **[Module Reference](https://docs.openspp.org/modules/)**
- **[API Documentation](https://docs.openspp.org/api/)**
- **[Developer Guide](https://docs.openspp.org/development/)**

## External Dependencies

OpenSPP requires OCA and third-party modules listed in [EXTERNAL_DEPENDENCIES.md](EXTERNAL_DEPENDENCIES.md).
The Docker setup fetches these automatically.

## Available addons

[//]: # (addons)

Available addons
----------------
addon | version | maintainers | summary
--- | --- | --- | ---
[endpoint_route_handler](endpoint_route_handler/) | 19.0.2.0.0 | <a href='https://github.com/simahawk'><img src='https://github.com/simahawk.png' width='32' height='32' style='border-radius:50%;' alt='simahawk'/></a> | Provide mixin and tool to generate custom endpoints on the fly.
[fastapi](fastapi/) | 19.0.2.0.0 | <a href='https://github.com/lmignon'><img src='https://github.com/lmignon.png' width='32' height='32' style='border-radius:50%;' alt='lmignon'/></a> | Odoo FastAPI endpoint
[spp_alerts](spp_alerts/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/emjay0921'><img src='https://github.com/emjay0921.png' width='32' height='32' style='border-radius:50%;' alt='emjay0921'/></a> | Generic alert engine for threshold monitoring, expiry tracking, and deadline management across OpenSPP modules.
[spp_api_v2](spp_api_v2/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> <a href='https://github.com/emjay0921'><img src='https://github.com/emjay0921.png' width='32' height='32' style='border-radius:50%;' alt='emjay0921'/></a> | OpenSPP API V2 - Standards-aligned, consent-respecting API for social protection data exchange.
[spp_api_v2_change_request](spp_api_v2_change_request/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | REST API endpoints for Change Request V2.
[spp_api_v2_cycles](spp_api_v2_cycles/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | REST API endpoints for Program Cycles.
[spp_api_v2_data](spp_api_v2_data/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | REST API endpoints for Variable Data push/pull.
[spp_api_v2_entitlements](spp_api_v2_entitlements/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | REST API endpoints for Entitlements (Cash and In-Kind).
[spp_api_v2_products](spp_api_v2_products/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | REST API endpoints for Products, Categories, and Units of Measure.
[spp_api_v2_service_points](spp_api_v2_service_points/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | REST API endpoints for Service Points.
[spp_api_v2_vocabulary](spp_api_v2_vocabulary/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | REST API endpoints for Vocabulary lookup.
[spp_approval](spp_approval/) | 19.0.2.0.0 |  | Standardized approval workflows with multi-tier sequencing and CEL rules
[spp_area](spp_area/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> <a href='https://github.com/emjay0921'><img src='https://github.com/emjay0921.png' width='32' height='32' style='border-radius:50%;' alt='emjay0921'/></a> | Establishes direct associations between OpenSPP registrants, beneficiary groups, and their corresponding geographical administrative areas. It validates registrant-area linkages against official area types, ensuring data integrity and enabling targeted program delivery and analysis.
[spp_area_hdx](spp_area_hdx/) | 19.0.2.0.0 |  | HDX Common Operational Datasets (COD) integration for downloading admin boundaries with polygons. Supports humanitarian coordination with P-code standardization and GPS-based area lookup.
[spp_audit](spp_audit/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | Comprehensively tracks all data modifications and user actions across the OpenSPP platform, recording old and new values for configured data. It enhances accountability and data integrity by maintaining an immutable history of changes, crucial for internal audits, compliance, and detecting unauthorized alterations. Supports multiple backends (database, file, syslog, HTTP) with tamper-resistant configuration.
[spp_banking](spp_banking/) | 19.0.2.0.0 |  | OpenSPP Banking: Bank Details
[spp_base_common](spp_base_common/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/emjay0921'><img src='https://github.com/emjay0921.png' width='32' height='32' style='border-radius:50%;' alt='emjay0921'/></a> | The OpenSPP base module that provides the main menu, generic configuration, user role management base module, area management base module, hiding of non-openspp menus. All implementation specific base modules depends on this module. (Odoo 19 Community Edition - uses default theme)
[spp_base_setting](spp_base_setting/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> <a href='https://github.com/emjay0921'><img src='https://github.com/emjay0921.png' width='32' height='32' style='border-radius:50%;' alt='emjay0921'/></a> | OpenSPP Base Setting provides fundamental configurations for country implementations, establishing core organizational structures such as Country Offices. It also enables tailored user interface adaptations and streamlines user management by linking individuals to specific Country Offices for context-aware data access.
[spp_branding_kit](spp_branding_kit/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | Branding customization, URL routing and telemetry management for OpenSPP
[spp_cel_domain](spp_cel_domain/) | 19.0.2.0.0 |  | Write simple CEL-like expressions to filter records (OpenSPP/OpenG2P friendly)
[spp_cel_event](spp_cel_event/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/emjay0921'><img src='https://github.com/emjay0921.png' width='32' height='32' style='border-radius:50%;' alt='emjay0921'/></a> | Integrate event data with CEL expressions for eligibility and entitlement rules
[spp_cel_registry_search](spp_cel_registry_search/) | 19.0.2.0.0 |  | Search the registry using CEL expressions
[spp_cel_vocabulary](spp_cel_vocabulary/) | 19.0.2.0.0 |  | Vocabulary-aware CEL functions for robust eligibility rules
[spp_cel_widget](spp_cel_widget/) | 19.0.2.0.0 |  | Reusable CEL expression editor with syntax highlighting and autocomplete
[spp_change_request_v2](spp_change_request_v2/) | 19.0.2.0.0 |  | Configuration-driven change request system with UX improvements, conflict detection and duplicate prevention
[spp_claim_169](spp_claim_169/) | 19.0.2.0.0 | <a href='https://github.com/openspp-dev'><img src='https://github.com/openspp-dev.png' width='32' height='32' style='border-radius:50%;' alt='openspp-dev'/></a> | MOSIP Claim 169 QR code identity credentials for registrants
[spp_consent](spp_consent/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | DPV-aligned consent management for social protection programs. Implements ISO/IEC TS 27560:2023 consent record information structure using W3C Data Privacy Vocabulary (DPV) concepts. Provides GDPR-compliant consent lifecycle management with full audit trail.
[spp_cr_types_advanced](spp_cr_types_advanced/) | 19.0.2.0.0 |  | Advanced change request types with custom Python strategies
[spp_cr_types_base](spp_cr_types_base/) | 19.0.2.0.0 |  | Basic change request types with field mapping strategy
[spp_custom_field](spp_custom_field/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | The module enables administrators to define and add custom data fields directly to registrant profiles, tailoring data collection for specific social protection programs. It supports field differentiation by registrant type, integrates new data points into records, and provides dedicated sections for read-only program indicators.
[spp_dci](spp_dci/) | 19.0.2.0.0 |  | Core DCI (Digital Convergence Initiative) API components
[spp_dci_client](spp_dci_client/) | 19.0.2.0.0 |  | Base DCI client infrastructure with OAuth2 and data source management
[spp_dci_client_crvs](spp_dci_client_crvs/) | 19.0.2.0.0 |  | Connect to CRVS registries via DCI API
[spp_dci_client_dr](spp_dci_client_dr/) | 19.0.2.0.0 |  | Connect to Disability Registry via DCI API
[spp_dci_client_ibr](spp_dci_client_ibr/) | 19.0.2.0.0 |  | Connect to IBR for duplication checks via DCI API
[spp_dci_server](spp_dci_server/) | 19.0.2.0.0 |  | DCI API server infrastructure with FastAPI routers
[spp_demo](spp_demo/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> <a href='https://github.com/emjay0921'><img src='https://github.com/emjay0921.png' width='32' height='32' style='border-radius:50%;' alt='emjay0921'/></a> | Core demo module with data generator and sample data for OpenSPP
[spp_dms](spp_dms/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | The OpenSPP Dms module provides a centralized system for managing and organizing program-related documents within a structured directory tree. It facilitates efficient document retrieval through categorization and indexed storage, automatically capturing essential file metadata such as size, type, and data integrity checksums.
[spp_drims](spp_drims/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | Disaster relief inventory management for donations, requests, and distribution tracking. Links to hazard incidents with multi-tier approval workflows and warehouse operations.
[spp_drims_sl](spp_drims_sl/) | 19.0.2.0.0 |  | Sri Lanka-specific configuration for DRIMS disaster response inventory management. Includes geographic hierarchy, government agencies, and approval thresholds per DMC requirements.
[spp_drims_sl_demo](spp_drims_sl_demo/) | 19.0.2.0.0 |  | Demo data generator for DRIMS Sri Lanka implementation. Creates sample incidents, donations, requests, and stock for demonstrations.
[spp_event_data](spp_event_data/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/emjay0921'><img src='https://github.com/emjay0921.png' width='32' height='32' style='border-radius:50%;' alt='emjay0921'/></a> | Records and tracks events related to individual and group registrants from surveys, field visits, and external systems like ODK and KoBoToolbox.
[spp_gis](spp_gis/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | GIS core plus area geo fields and importer extensions (points/polygons, layers, spatial queries).
[spp_gis_report](spp_gis_report/) | 19.0.2.0.0 |  | Geographic visualization and reporting for social protection data
[spp_gis_report_programs](spp_gis_report_programs/) | 19.0.2.0.0 |  | Add program context filtering to GIS reports
[spp_grm](spp_grm/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | Provides a centralized Grievance Redress Mechanism for receiving, tracking, and resolving beneficiary complaints and feedback. It supports multi-channel submission, manages resolution workflows through customizable stages, and links grievances directly to individual or group registrants.
[spp_grm_demo](spp_grm_demo/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | Demo data generator for Grievance Redress Mechanism
[spp_hazard](spp_hazard/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | Provides hazard classification, incident recording, and impact assessment for emergency response. Links registrants to disaster events with geographic scope and severity tracking to enable targeted humanitarian assistance.
[spp_hide_menus_base](spp_hide_menus_base/) | 19.0.2.0.0 | <a href='https://github.com/emjay0921'><img src='https://github.com/emjay0921.png' width='32' height='32' style='border-radius:50%;' alt='emjay0921'/></a> <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> | Administrators can manage the visibility of OpenSPP navigation menus, streamlining the user interface for specific user groups. The module modifies ir.ui.menu records to control menu visibility, providing a foundation for other modules to selectively hide non-essential navigation items.
[spp_key_management](spp_key_management/) | 19.0.2.0.0 | <a href='https://github.com/openspp-dev'><img src='https://github.com/openspp-dev.png' width='32' height='32' style='border-radius:50%;' alt='openspp-dev'/></a> | Centralized cryptographic key management with pluggable providers
[spp_mis_demo_v2](spp_mis_demo_v2/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | Demo Generator V2 for SP-MIS programs with fixed stories and volume generation
[spp_programs](spp_programs/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> <a href='https://github.com/reichie020212'><img src='https://github.com/reichie020212.png' width='32' height='32' style='border-radius:50%;' alt='reichie020212'/></a> | Manage cash and in-kind entitlements, integrate with inventory, and enhance program management features for comprehensive social protection and agricultural support.
[spp_registry](spp_registry/) | 19.0.2.0.0 |  | Consolidated registry management for individuals, groups, and membership
[spp_registry_search](spp_registry_search/) | 19.0.2.0.0 |  | Search-first registry interface for privacy protection
[spp_security](spp_security/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | Central security definitions for OpenSPP modules
[spp_service_points](spp_service_points/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | The OpenSPP Service Points module manages physical or virtual locations for social protection service delivery, establishing and categorizing operational service points. It links these points to hierarchical geographical areas, company entities, and user accounts, integrating with spp_area and g2p_registry_base for comprehensive organizational and location management.
[spp_source_tracking](spp_source_tracking/) | 19.0.2.0.0 | <a href='https://github.com/OpenSPP'><img src='https://github.com/OpenSPP.png' width='32' height='32' style='border-radius:50%;' alt='OpenSPP'/></a> | Track data provenance and source information for registrants
[spp_starter_social_registry](spp_starter_social_registry/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | Complete Social Registry bundle with API, DCI, and Change Request support
[spp_starter_sp_mis](spp_starter_sp_mis/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | Complete SP-MIS bundle with Social Registry, Programs, and Service Points
[spp_studio](spp_studio/) | 19.0.2.0.0 |  | No-code customization interface for OpenSPP
[spp_studio_api_v2](spp_studio_api_v2/) | 19.0.2.0.0 |  | Bridge Studio custom fields and variables with API v2
[spp_studio_change_requests](spp_studio_change_requests/) | 19.0.2.0.0 |  | No-code change request type builder
[spp_studio_events](spp_studio_events/) | 19.0.2.0.0 |  | No-code event type designer for data collection
[spp_user_roles](spp_user_roles/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | The OpenSPP User Roles module defines and manages distinct user roles, categorizing them as global or local, to implement area-based access control. It restricts user access to specific geographical areas by leveraging the spp_area module and automates underlying system permission assignments.
[spp_versioning](spp_versioning/) | 19.0.2.0.0 |  | Artifact versioning with scheduled activation
[spp_vocabulary](spp_vocabulary/) | 19.0.2.0.0 |  | OpenSPP: Vocabulary
[theme_openspp_muk](theme_openspp_muk/) | 19.0.2.0.0 | <a href='https://github.com/jeremi'><img src='https://github.com/jeremi.png' width='32' height='32' style='border-radius:50%;' alt='jeremi'/></a> <a href='https://github.com/gonzalesedwin1123'><img src='https://github.com/gonzalesedwin1123.png' width='32' height='32' style='border-radius:50%;' alt='gonzalesedwin1123'/></a> | OpenSPP Theme

[//]: # (end addons)

## Contributing

We welcome contributions! Please see our [Contributing Guide](https://docs.openspp.org/contributing/) for details.

- **Report bugs** - [Open an issue](https://github.com/OpenSPP/OpenSPP2/issues/new)
- **Request features** - [Start a discussion](https://github.com/OpenSPP/OpenSPP2/discussions)
- **Submit PRs** - Fork, branch, and open a pull request

## Acknowledgments

OpenSPP includes code originally developed by the [OpenG2P](https://openg2p.org/) project. We thank all contributors to both projects.
See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the full list.

## License

[LGPL-3.0](LICENSE) - This is free and open-source software.
