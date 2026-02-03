Client infrastructure for connecting to external DCI-compliant registries. Handles OAuth2 authentication, token caching, request signing, and HTTP communication with CRVS, IBR, Social Registry, and other DCI endpoints. Provides a reusable data source configuration model and Python service class for search, subscribe, and status operations.

### Key Capabilities

- Configure external DCI registry endpoints with OAuth2 or Bearer token authentication
- Cache OAuth2 tokens with automatic refresh to minimize token requests
- Sign outgoing DCI requests using JWK keys from `spp_dci`
- Execute synchronous and asynchronous search operations (by ID, predicate, expression, date range)
- Subscribe to and unsubscribe from registry event notifications
- Check transaction status for asynchronous operations
- Test connection with one-click validation and error diagnostics
- Format HTTP and connection errors into user-friendly messages

### Key Models

| Model                  | Description                                           |
| ---------------------- | ----------------------------------------------------- |
| `spp.dci.data.source`  | Connection configuration for external DCI registries  |

### Python Service Classes

- **`DCIClient(data_source, env)`**: Main API client for executing DCI protocol operations (search, subscribe, txn_status). Instantiate with a data source record and environment.

### Configuration

After installing:

1. Navigate to **Settings > Technical > DCI > Configuration > Data Sources**
2. Create a new data source with name, code, base URL, and registry type
3. Configure authentication (OAuth2 token URL, client ID, client secret, scope)
4. Set sender ID and callback URI for DCI protocol headers
5. Optionally configure a signing key for request signatures
6. Click **Test Connection** to verify configuration

### UI Location

- **Menu**: Settings > Technical > DCI > Configuration > Data Sources
- **Form**: Includes connection test button in header, configuration groups, and two notebook tabs ("Connection Status" and "Notes")

### Security

| Group                  | Access                        |
| ---------------------- | ----------------------------- |
| `base.group_system`    | Full CRUD, view secrets       |
| `base.group_user`      | Read-only (secrets hidden)    |

### Extension Points

- Inherit `spp.dci.data.source` to add registry-specific configuration fields
- Instantiate `DCIClient(data_source, env)` from custom code to execute DCI operations
- Override `_get_registry_type()` or `_get_receiver_id()` for custom registry routing
- Use `format_http_error()` and `format_connection_error()` for consistent error handling

### Usage Example

```python
# Get data source and create client
data_source = env['spp.dci.data.source'].get_by_code('crvs_main')
client = DCIClient(data_source, env)

# Execute synchronous search by identifier
response = client.search_by_id('UIN', '123456789', record_type='PERSON')

# Execute asynchronous search with callback
response = client.search_by_id('BRN', '987654321', async_mode=True)

# Search by date range
response = client.search_by_date_range('2024-01-01', '2024-12-31', event_type='BIRTH')

# Subscribe to registry events
response = client.subscribe(event_type='REGISTER', notify_record_type='Person')
```

### Dependencies

`base`, `spp_dci` (Python: `httpx`)
