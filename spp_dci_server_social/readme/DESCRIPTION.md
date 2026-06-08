Provides Social Registry search implementation for the DCI API. Converts Odoo registrants (persons and groups) to DCI-compliant Person/Group schemas and automatically queues event notifications when registrants are created, updated, or deleted.

### Key Capabilities

- **Partner-to-DCI Conversion**: Maps `res.partner` records to DCI Person and Group schemas with identifiers, names, addresses, demographics
- **CEL Expression Queries**: Parses DCI predicate queries using Common Expression Language via `spp.cel.service`
- **Automatic Event Notifications**: Triggers queue_job tasks on registrant CRUD operations, with 60-second deduplication window
- **Search Service Integration**: Provides `DCISocialSearchService` consumed by `spp_dci_server` search router
- **Consent Filtering**: Applies consent rules when available via `DCIConsentAdapter` from `spp_dci_server`

### Key Models

| Model              | Description                                                   |
| ------------------ | ------------------------------------------------------------- |
| `res.partner`      | Extended to trigger DCI notifications on create/write/unlink  |
| `fastapi.endpoint` | Inherits DCI endpoint (routers mounted by `spp_dci_server`)   |

### API Integration

This module provides the search service implementation consumed by `spp_dci_server`. The search endpoint is:

- **POST** `/fastapi/dci/v1/social/registry/sync/search` - Mounted by `spp_dci_server.fastapi_endpoint_dci`

Searches use DCI query types: `idtype-value`, `expression`, or `predicate` (CEL expressions).

### Event Notification Flow

1. Registrant created, updated (tracked fields), or deleted
2. Post-commit hook schedules queue_job with identity_key for deduplication
3. Job converts partner to DCI Person/Group schema via `DCISocialSearchService`
4. Calls `spp.dci.subscription.notify_event()` to deliver to subscribers
5. Multiple notifications within 60 seconds are collapsed by identity_key

**Tracked Fields** (20+ fields trigger update notifications):
`name`, `given_name`, `family_name`, `addl_name`, `birthdate`, `gender`, `gender_id`, `phone`, `mobile`, `email`, `street`, `street2`, `city`, `zip`, `state_id`, `country_id`, `is_group`, `active`

### Configuration

After installing:

1. Set system parameter `dci.notifications_enabled` to `true` (default) to enable event notifications
2. Configure sender registries in **Social Protection > DCI > Sender Registries**
3. Ensure the DCI queue_job cron is active under **Settings > Technical > Scheduled Actions**

### Deployment Prerequisites (read before exposing the server)

- **Endpoint user groups**: the Odoo user configured on the DCI
  `fastapi.endpoint` must belong to `spp_registry.group_registry_viewer` -
  every search fails with an access error otherwise.
- **queue_job worker**: event notifications are delivered through delayed
  jobs on channels `root.dci` and `dci`. A running queue_job worker with
  those channels configured is a hard requirement - without it,
  notifications are enqueued and silently never sent.
- **Inbound auth**: searches go through `spp_dci_server`'s authenticated
  route (bearer token per `dci.api_tokens` plus DCI envelope signature).
  This module deliberately ships no unauthenticated routes.
- **Client base URL**: DCI clients post to `{base_url}/registry/sync/search`;
  point their data source base URL at `.../api/v1/social` so requests land
  on this server's `/social/registry/sync/search` mount.

### UI Location

No standalone UI. Search functionality accessed via DCI API endpoints. Notifications triggered automatically on registrant changes.

### Security

No new access rules. Search requires the `spp_registry.group_registry_viewer` group (enforced in `DCISocialSearchService._process_search_item()`). Inherits access control from `spp_registry` and `spp_dci_server`.

Because the search runs under the DCI FastAPI endpoint's user, that user must hold `spp_registry.group_registry_viewer`. The endpoint ships as the public user, which lacks it, so Social Registry searches are rejected until a registry-viewer service user is assigned to the endpoint — see **Endpoint user (required for Social Registry search)** in the `spp_dci_server` documentation.

### Extension Points

- Override `res.partner._execute_dci_notification()` to customize notification payloads
- Modify `TRACKED_FIELDS` set in `res_partner_dci_notify.py` to change which fields trigger updates
- Extend `DCISocialSearchService._to_dci_person()` or `_to_dci_group()` for custom data mapping
- Override `DCISocialSearchService._map_gender()` for domain-specific gender mapping

### Dependencies

`spp_dci_server`, `spp_registry`, `spp_cel_domain`
