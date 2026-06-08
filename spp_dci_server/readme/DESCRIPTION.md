DCI API server infrastructure for receiving and processing Digital Convergence Initiative (DCI) requests. Provides FastAPI endpoints for registry search, subscriptions, and event notifications with HTTP signature verification, asynchronous processing via queue_job, and JWKS-based public key distribution.

### Key Capabilities

- **FastAPI Endpoints**: Exposes DCI-compliant REST API at `/dci_api/v1` with automatic OpenAPI documentation
- **HTTP Signature Verification**: Validates inbound requests using Ed25519/RSA signatures against sender public keys
- **Bearer Authentication**: Accepts either a static token (system parameter `dci.api_tokens`) or an OAuth2 client-credentials access token (a JWT issued by `spp_api_v2` at `POST /api_v2/oauth/token`, validated against an active `spp.api.client`)
- **Async Transaction Processing**: Queues search, subscribe, and unsubscribe operations for background processing with automatic callbacks
- **Event Subscriptions**: Manages external system subscriptions to registry events (registration, update, delete) with notification delivery
- **JWKS Distribution**: Publishes server public keys at `/.well-known/jwks.json` for signature verification by clients
- **Rate Limiting**: Enforces per-sender request limits (per-minute and per-day) with automatic counter resets
- **Callback Retry**: Retries failed callbacks with exponential backoff (3 attempts) and SSRF protection

### Key Models

| Model                       | Description                                                     |
| --------------------------- | --------------------------------------------------------------- |
| `spp.dci.sender.registry`   | External DCI senders with public keys for signature verification |
| `spp.dci.transaction`       | Async DCI request tracking (search, subscribe, unsubscribe)     |
| `spp.dci.subscription`      | Event subscriptions with callback URIs and filter expressions   |
| `spp.dci.notification.log`  | Audit trail of sent notifications with receipt tracking         |
| `spp.dci.server.key`        | Server signing keys for outbound responses and notifications    |

### Configuration

After installing:

1. Navigate to **Settings > DCI > Configuration > Sender Registry**
2. Create external sender records with their DCI sender IDs
3. Fetch sender public keys from their JWKS endpoints using the "Fetch Public Key" button
4. Verify the scheduled action **DCI: Reset Daily Rate Limit Counters** is active

Server signing keys are automatically generated and activated on installation. To manage keys manually, use the technical interface for `spp.dci.server.key`.

### UI Location

- **Menu**: Settings > DCI > Configuration > Sender Registry
- **Menu**: Settings > DCI > Configuration > Transactions
- **Menu**: Settings > DCI > Configuration > Subscriptions
- **API**: `/dci_api/v1` (OpenAPI docs at `/dci_api/v1/docs`)
- **JWKS**: `/dci_api/v1/.well-known/jwks.json`

### Security

| Group               | Access                         |
| ------------------- | ------------------------------ |
| `base.group_system` | Full CRUD on all models        |
| `base.group_user`   | Read-only on all models        |

API authentication uses HTTP signatures verified against sender registry public keys.

### Extension Points

- Override `DCIErrorResponseMiddleware.dispatch()` to customize error response formatting
- Inherit `fastapi.endpoint` with `app='dci_api'` to add custom routers via `_get_fastapi_routers()`
- Override `spp.dci.transaction.process_async_*()` methods to customize async processing logic
- Inherit `spp.dci.subscription._build_notification()` to add custom notification fields

### Dependencies

`base`, `fastapi`, `queue_job`, `spp_dci`, `spp_dci_client`, `spp_api_v2`
