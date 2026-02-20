# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCIClient service"""

from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestClientService(TransactionCase):
    """Test DCIClient service"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]

    def _create_test_data_source(self, **kwargs):
        """Helper to create a test data source"""
        vals = {
            "name": "Test CRVS",
            "code": "test_crvs",
            "base_url": "https://crvs.example.org/api",
            "auth_type": "none",
            "our_sender_id": "openspp.example.org",
            "our_callback_uri": "https://openspp.example.org/callback",
            "registry_type": "ns:org:RegistryType:Civil",
        }
        vals.update(kwargs)
        return self.DataSource.create(vals)

    def test_client_initialization(self):
        """Test creating client with valid data source"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        self.assertEqual(client.data_source, ds)
        self.assertEqual(client.env, self.env)

    def test_client_initialization_missing_data_source(self):
        """Test client raises error when data_source is None"""
        from ..services.client import DCIClient

        with self.assertRaises(ValueError) as cm:
            DCIClient(None, self.env)
        self.assertIn("required", str(cm.exception))

    def test_client_missing_base_url(self):
        """Test client raises ValidationError for missing base_url"""
        from ..services.client import DCIClient

        # Create data source without base_url by bypassing constraint
        ds = self.DataSource.new(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "auth_type": "none",
                "our_sender_id": "openspp.example.org",
            }
        )
        # Force empty base_url
        ds.base_url = False

        with self.assertRaises(ValidationError) as cm:
            DCIClient(ds, self.env)
        self.assertIn("base_url", str(cm.exception))

    def test_client_missing_sender_id(self):
        """Test client raises ValidationError for missing sender_id"""
        from ..services.client import DCIClient

        # Create data source without sender_id by bypassing constraint
        ds = self.DataSource.new(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )
        # Force empty sender_id
        ds.our_sender_id = False

        with self.assertRaises(ValidationError) as cm:
            DCIClient(ds, self.env)
        self.assertIn("our_sender_id", str(cm.exception))

    def test_build_envelope_structure(self):
        """Test envelope structure matches DCI spec"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        # Build test envelope
        message = {"test": "data"}
        envelope = client._build_envelope(action="search", message=message)

        # Verify envelope structure
        self.assertIn("signature", envelope)
        self.assertIn("header", envelope)
        self.assertIn("message", envelope)

        # Verify header structure
        header = envelope["header"]
        self.assertEqual(header["version"], "1.0.0")
        self.assertIn("message_id", header)
        self.assertIn("message_ts", header)
        self.assertEqual(header["action"], "search")
        self.assertEqual(header["sender_id"], "openspp.example.org")
        self.assertEqual(header["total_count"], 1)
        self.assertEqual(header["is_msg_encrypted"], False)

        # Verify message is passed through
        self.assertEqual(envelope["message"], message)

    def test_build_envelope_receiver_id(self):
        """Test envelope uses configured receiver_id"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source(receiver_id="crvs.example.org")
        client = DCIClient(ds, self.env)

        envelope = client._build_envelope(action="search", message={})

        self.assertEqual(envelope["header"]["receiver_id"], "crvs.example.org")

    def test_build_envelope_receiver_id_default(self):
        """Test envelope defaults receiver_id to base_url"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = client._build_envelope(action="search", message={})

        # Should default to base_url without trailing slash
        self.assertEqual(envelope["header"]["receiver_id"], "https://crvs.example.org/api")

    def test_build_envelope_callback_uri(self):
        """Test envelope includes callback URI if configured"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source(our_callback_uri="https://openspp.example.org/callback")
        client = DCIClient(ds, self.env)

        envelope = client._build_envelope(action="search", message={})

        self.assertEqual(envelope["header"]["sender_uri"], "https://openspp.example.org/callback")

    def test_sign_request_no_signing_key(self):
        """Test signing without configured key produces empty signature"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        header = {"test": "header"}
        message = {"test": "message"}

        envelope = client._sign_request(header, message)

        self.assertEqual(envelope["signature"], "")
        self.assertEqual(envelope["header"], header)
        self.assertEqual(envelope["message"], message)

    @patch("odoo.addons.spp_dci_client.services.client.DCISigner")
    def test_sign_request_with_signing_key(self, mock_signer_class):
        """Test signing with configured key"""
        from ..services.client import DCIClient

        # Create signing key - must have both private and public keys to activate
        signing_key = self.env["spp.dci.signing.key"].create(
            {
                "name": "Test Key",
                "key_id": "test-key-123",
                "algorithm": "rs256",
                "state": "active",
                "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
                "public_key": "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
            }
        )

        ds = self._create_test_data_source(signing_key_id=signing_key.id)
        client = DCIClient(ds, self.env)

        # Mock signer
        mock_signer = MagicMock()
        mock_signer.sign.return_value = "test_signature_12345"
        mock_signer_class.return_value = mock_signer

        header = {"test": "header"}
        message = {"test": "message"}

        envelope = client._sign_request(header, message)

        # Verify signer was called
        mock_signer_class.assert_called_once()
        mock_signer.sign.assert_called_once_with(header, message)

        # Verify envelope has signature
        self.assertEqual(envelope["signature"], "test_signature_12345")

    def test_sign_request_inactive_signing_key(self):
        """Test signing fails with inactive key"""
        from ..services.client import DCIClient

        # Create inactive signing key
        signing_key = self.env["spp.dci.signing.key"].create(
            {
                "name": "Test Key",
                "key_id": "test-key-123",
                "algorithm": "rs256",
                "state": "draft",
                "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
            }
        )

        ds = self._create_test_data_source(signing_key_id=signing_key.id)
        client = DCIClient(ds, self.env)

        header = {"test": "header"}
        message = {"test": "message"}

        with self.assertRaises(UserError) as cm:
            client._sign_request(header, message)
        self.assertIn("not active", str(cm.exception))

    def test_search_by_id_format_parsing(self):
        """Test parsing of idtype:value format"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"status": "success"}

            client.search_by_id(
                identifier_type="UIN",
                identifier_value="12345678",
            )

            # Verify request was made
            mock_request.assert_called_once()

            # Get the envelope that was passed
            call_args = mock_request.call_args
            endpoint = call_args[0][0]
            envelope = call_args[0][1]

            # Verify endpoint
            self.assertEqual(endpoint, "/registry/sync/search")

            # Verify envelope structure
            self.assertIn("message", envelope)
            message = envelope["message"]
            self.assertIn("search_request", message)
            search_request = message["search_request"][0]
            self.assertIn("search_criteria", search_request)

            # Verify query format
            search_criteria = search_request["search_criteria"]
            self.assertEqual(search_criteria["query_type"], "idtype-value")
            self.assertEqual(search_criteria["query"]["type"], "UIN")
            self.assertEqual(search_criteria["query"]["value"], "12345678")

    def test_search_by_id_invalid_format(self):
        """Test search with invalid query format raises error"""
        from odoo.addons.spp_dci.schemas import QueryType

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        # Test idtype-value without colon
        with self.assertRaises(ValidationError) as cm:
            client.search(
                query_type=QueryType.IDTYPE_VALUE,
                query_value="12345678",  # Missing TYPE: prefix
            )
        self.assertIn("TYPE:VALUE", str(cm.exception))

    def test_search_pagination_params(self):
        """Test search with pagination parameters"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"status": "success"}

            client.search_by_id(
                identifier_type="UIN",
                identifier_value="12345678",
                page=2,
                page_size=50,
            )

            # Get the envelope
            envelope = mock_request.call_args[0][1]
            search_criteria = envelope["message"]["search_request"][0]["search_criteria"]

            # Verify pagination
            self.assertEqual(search_criteria["pagination"]["page_number"], 2)
            self.assertEqual(search_criteria["pagination"]["page_size"], 50)

    def test_search_pagination_validation(self):
        """Test search validates pagination parameters"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        # Invalid page number
        with self.assertRaises(ValidationError) as cm:
            client.search_by_id(
                identifier_type="UIN",
                identifier_value="12345678",
                page=0,
            )
        self.assertIn("Page", str(cm.exception))

        # Invalid page size (too small)
        with self.assertRaises(ValidationError) as cm:
            client.search_by_id(
                identifier_type="UIN",
                identifier_value="12345678",
                page_size=0,
            )
        self.assertIn("Page size", str(cm.exception))

        # Invalid page size (too large)
        with self.assertRaises(ValidationError) as cm:
            client.search_by_id(
                identifier_type="UIN",
                identifier_value="12345678",
                page_size=2000,
            )
        self.assertIn("Page size", str(cm.exception))

    @patch("httpx.Client")
    def test_make_request_success(self, mock_client_class):
        """Test successful HTTP request"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "header": {"status": "success"},
            "message": {"data": "test"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        # Make request
        envelope = {
            "signature": "",
            "header": {"action": "search", "message_id": "test-123"},
            "message": {"test": "data"},
        }
        result = client._make_request("/registry/sync/search", envelope)

        # Verify response
        self.assertEqual(result["header"]["status"], "success")
        self.assertEqual(result["message"]["data"], "test")

        # Verify request was made to correct URL
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        self.assertEqual(call_args[0][0], "https://crvs.example.org/api/registry/sync/search")

    @patch("httpx.Client")
    def test_make_request_http_error(self, mock_client_class):
        """Test HTTP error handling"""
        import httpx

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.return_value = {"header": {"status_reason_message": "Database connection failed"}}
        mock_request = MagicMock()

        def raise_status():
            raise httpx.HTTPStatusError("Server Error", request=mock_request, response=mock_response)

        mock_response.raise_for_status = raise_status

        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        # Make request
        envelope = {
            "signature": "",
            "header": {"action": "search", "message_id": "test-123"},
            "message": {"test": "data"},
        }

        with self.assertRaises(UserError) as cm:
            client._make_request("/registry/sync/search", envelope)

        error_msg = str(cm.exception)
        # User-friendly message should NOT expose technical details
        # Instead, it shows a generic user-friendly message
        self.assertIn("external registry encountered an error", error_msg.lower())

    @patch("httpx.Client")
    def test_make_request_with_oauth2(self, mock_client_class):
        """Test request includes OAuth2 token"""
        from ..services.client import DCIClient

        # Create data source with OAuth2
        ds = self._create_test_data_source(
            auth_type="oauth2",
            oauth2_token_url="https://auth.example.org/token",
            oauth2_client_id="client123",
            oauth2_client_secret="secret456",
        )
        client = DCIClient(ds, self.env)

        # Mock OAuth2 token response
        mock_token_response = MagicMock()
        mock_token_response.json.return_value = {
            "access_token": "test_token_12345",
            "expires_in": 3600,
        }
        mock_token_response.raise_for_status = MagicMock()

        # Mock search response
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {"status": "success"}
        mock_search_response.raise_for_status = MagicMock()

        mock_http_client = MagicMock()
        # First call is OAuth2 token request, second is search request
        mock_http_client.post.side_effect = [mock_token_response, mock_search_response]
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        # Make request
        envelope = {
            "signature": "",
            "header": {"action": "search", "message_id": "test-123"},
            "message": {"test": "data"},
        }
        client._make_request("/registry/sync/search", envelope)

        # Verify second call (search) included Authorization header
        search_call = mock_http_client.post.call_args_list[1]
        headers = search_call[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer test_token_12345")

    def test_subscribe_endpoint(self):
        """Test subscribe method builds correct request"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"ack_status": "ACK"}}

            client.subscribe(event_type="BIRTH", notify_record_type="Person")

            # Verify request was made to subscribe endpoint
            call_args = mock_request.call_args
            endpoint = call_args[0][0]
            envelope = call_args[0][1]

            self.assertEqual(endpoint, "/registry/subscribe")
            self.assertEqual(envelope["header"]["action"], "subscribe")
            self.assertIn("subscribe_request", envelope["message"])
            subscribe_req = envelope["message"]["subscribe_request"][0]
            self.assertEqual(subscribe_req["subscribe_criteria"]["reg_event_type"], "BIRTH")
            self.assertEqual(subscribe_req["subscribe_criteria"]["notify_record_type"], "Person")
            # Filter is required by OpenAPI spec
            self.assertIn("filter", subscribe_req["subscribe_criteria"])

    def test_subscribe_with_filter(self):
        """Test subscribe with filter query"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"ack_status": "ACK"}}

            filter_query = {"type": "UIN", "value": "123*"}
            client.subscribe(
                event_type="DEATH",
                filter_query=filter_query,
                notify_record_type="Person",
            )

            envelope = mock_request.call_args[0][1]
            subscribe_req = envelope["message"]["subscribe_request"][0]
            self.assertEqual(subscribe_req["subscribe_criteria"]["filter"], filter_query)

    def test_subscribe_default_filter(self):
        """Test subscribe uses default match-all filter when none provided"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"ack_status": "ACK"}}

            client.subscribe(event_type="BIRTH")

            envelope = mock_request.call_args[0][1]
            subscribe_req = envelope["message"]["subscribe_request"][0]
            # Default filter should be match-all
            self.assertEqual(subscribe_req["subscribe_criteria"]["filter"]["type"], "*")
            self.assertEqual(subscribe_req["subscribe_criteria"]["filter"]["value"], "*")

    def test_get_registry_type_from_data_source(self):
        """Test registry type is retrieved from data source"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source(registry_type="ns:org:RegistryType:Civil")
        client = DCIClient(ds, self.env)

        registry_type = client._get_registry_type()

        self.assertEqual(registry_type, "ns:org:RegistryType:Civil")

    def test_get_registry_type_default(self):
        """Test default registry type when not configured"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        ds.registry_type = False
        client = DCIClient(ds, self.env)

        registry_type = client._get_registry_type()

        self.assertEqual(registry_type, "ns:org:RegistryType:Social")

    def test_search_uses_custom_endpoint(self):
        """Test search uses custom endpoint if configured"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source(search_endpoint="/api/v2/search")
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"status": "success"}

            client.search_by_id(identifier_type="UIN", identifier_value="12345678")

            # Verify custom endpoint was used
            call_args = mock_request.call_args
            endpoint = call_args[0][0]
            self.assertEqual(endpoint, "/api/v2/search")

    def test_build_search_envelope_structure(self):
        """Test search envelope has correct structure"""
        from odoo.addons.spp_dci.schemas import QueryType

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = client._build_search_envelope(
            query_type=QueryType.IDTYPE_VALUE,
            query={"type": "UIN", "value": "12345678"},
            registry_type="ns:org:RegistryType:Civil",
            registry_event_type="BIRTH",
            record_type="PERSON",
            page=1,
            page_size=10,
        )

        # Verify envelope structure
        self.assertIn("signature", envelope)
        self.assertIn("header", envelope)
        self.assertIn("message", envelope)

        # Verify message structure
        message = envelope["message"]
        self.assertIn("transaction_id", message)
        self.assertIn("search_request", message)

        # Verify search request structure
        search_request = message["search_request"][0]
        self.assertIn("reference_id", search_request)
        self.assertIn("timestamp", search_request)
        self.assertIn("search_criteria", search_request)

        # Verify search criteria
        search_criteria = search_request["search_criteria"]
        self.assertEqual(search_criteria["version"], "1.0.0")
        self.assertEqual(search_criteria["reg_type"], "ns:org:RegistryType:Civil")
        self.assertEqual(search_criteria["reg_event_type"], "BIRTH")
        self.assertEqual(search_criteria["query_type"], QueryType.IDTYPE_VALUE)
        self.assertEqual(search_criteria["query"]["type"], "UIN")
        self.assertEqual(search_criteria["query"]["value"], "12345678")

        # Verify pagination
        pagination = search_criteria["pagination"]
        self.assertEqual(pagination["page_size"], 10)
        self.assertEqual(pagination["page_number"], 1)

    def test_search_async_uses_async_endpoint(self):
        """Test search_async uses /registry/search endpoint"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"ack_status": "ACK", "correlation_id": "test-123"}}

            result = client.search_async(
                query_type="idtype-value",
                query_value="UIN:12345678",
                record_type="PERSON",
            )

            # Verify request was made to async endpoint
            call_args = mock_request.call_args
            endpoint = call_args[0][0]
            self.assertEqual(endpoint, "/registry/search")

            # Verify ACK response
            self.assertEqual(result["message"]["ack_status"], "ACK")

    def test_search_async_vs_search_sync(self):
        """Test search_async and search use different endpoints"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"ack_status": "ACK"}}

            # Async search
            client.search_async(
                query_type="idtype-value",
                query_value="UIN:12345678",
            )
            async_endpoint = mock_request.call_args[0][0]

            # Sync search
            client.search(
                query_type="idtype-value",
                query_value="UIN:12345678",
            )
            sync_endpoint = mock_request.call_args[0][0]

            # Verify different endpoints
            self.assertEqual(async_endpoint, "/registry/search")
            self.assertEqual(sync_endpoint, "/registry/sync/search")

    def test_unsubscribe_endpoint(self):
        """Test unsubscribe method builds correct request"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"ack_status": "ACK"}}

            client.unsubscribe(subscription_codes=["sub-001", "sub-002"])

            call_args = mock_request.call_args
            endpoint = call_args[0][0]
            envelope = call_args[0][1]

            self.assertEqual(endpoint, "/registry/unsubscribe")
            self.assertEqual(envelope["header"]["action"], "unsubscribe")
            # Field is subscription_code (not subscription_codes) per DCI spec
            self.assertIn("subscription_code", envelope["message"])
            self.assertEqual(envelope["message"]["subscription_code"], ["sub-001", "sub-002"])

    def test_unsubscribe_validation(self):
        """Test unsubscribe validates subscription_codes"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with self.assertRaises(ValidationError) as cm:
            client.unsubscribe(subscription_codes=[])
        self.assertIn("subscription_code", str(cm.exception).lower())

    def test_txn_status_endpoint(self):
        """Test txn_status method builds correct request"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"ack_status": "ACK"}}

            client.txn_status(
                attribute_value="txn-12345",
                attribute_type="transaction_id",
            )

            call_args = mock_request.call_args
            endpoint = call_args[0][0]
            envelope = call_args[0][1]

            self.assertEqual(endpoint, "/registry/txn/status")
            self.assertEqual(envelope["header"]["action"], "txn_status")
            self.assertIn("txnstatus_request", envelope["message"])
            txn_req = envelope["message"]["txnstatus_request"]
            self.assertEqual(txn_req["attribute_type"], "transaction_id")
            self.assertEqual(txn_req["attribute_value"], "txn-12345")

    def test_txn_status_with_reference_id(self):
        """Test txn_status can query by reference_id"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"ack_status": "ACK"}}

            client.txn_status(
                attribute_value="ref-67890",
                attribute_type="reference_id",
            )

            envelope = mock_request.call_args[0][1]
            txn_req = envelope["message"]["txnstatus_request"]
            self.assertEqual(txn_req["attribute_type"], "reference_id")
            self.assertEqual(txn_req["attribute_value"], "ref-67890")

    def test_txn_status_invalid_attribute_type(self):
        """Test txn_status validates attribute_type"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with self.assertRaises(ValidationError) as cm:
            client.txn_status(
                attribute_value="test-123",
                attribute_type="invalid_type",
            )
        self.assertIn("attribute_type", str(cm.exception).lower())

    def test_search_by_predicate(self):
        """Test search_by_predicate sends CEL expression"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"search_response": []}}

            cel_expression = "person.age >= 18 && person.status == 'active'"
            client.search_by_predicate(
                predicate=cel_expression,
                record_type="PERSON",
            )

            call_args = mock_request.call_args
            envelope = call_args[0][1]

            search_criteria = envelope["message"]["search_request"][0]["search_criteria"]
            self.assertEqual(search_criteria["query_type"], "predicate")
            self.assertEqual(search_criteria["query"], cel_expression)

    def test_search_by_predicate_async(self):
        """Test search_by_predicate can use async mode"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"message": {"ack_status": "ACK"}}

            client.search_by_predicate(
                predicate="person.disabled == true",
                record_type="PERSON",
                async_mode=True,
            )

            endpoint = mock_request.call_args[0][0]
            self.assertEqual(endpoint, "/registry/search")

    def test_bearer_token_auth(self):
        """Test Bearer token authentication is included in headers"""
        from ..services.client import DCIClient

        # Create data source with bearer token auth
        ds = self._create_test_data_source(
            auth_type="bearer",
            bearer_token="test-bearer-token-12345",
        )
        client = DCIClient(ds, self.env)

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"message": {"status": "success"}}
            mock_response.raise_for_status = MagicMock()

            mock_http_client = MagicMock()
            mock_http_client.post.return_value = mock_response
            mock_http_client.__enter__.return_value = mock_http_client
            mock_http_client.__exit__.return_value = None
            mock_client_class.return_value = mock_http_client

            # Build a proper envelope with required fields
            envelope = client._build_envelope(action="search", message={"test": "data"})
            client._make_request("/test", envelope)

            # Verify Bearer token in headers
            call_headers = mock_http_client.post.call_args[1]["headers"]
            self.assertEqual(call_headers["Authorization"], "Bearer test-bearer-token-12345")

    def test_envelope_meta_field(self):
        """Test envelope header includes meta field per DCI spec"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = client._build_envelope(action="search", message={})

        # meta is required by DCI spec (even if empty)
        self.assertIn("meta", envelope["header"])
        self.assertEqual(envelope["header"]["meta"], {})


class TestOpenCRVSEnvelopeFormat(TransactionCase):
    """Test OpenCRVS envelope format for _build_search_envelope_opencrvs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]

    def _create_test_data_source(self, **kwargs):
        """Helper to create a test data source"""
        vals = {
            "name": "Test CRVS",
            "code": "test_crvs",
            "base_url": "https://crvs.example.org/api",
            "auth_type": "none",
            "our_sender_id": "openspp.example.org",
            "our_callback_uri": "https://openspp.example.org/callback",
            "registry_type": "ns:org:RegistryType:Civil",
        }
        vals.update(kwargs)
        return self.DataSource.create(vals)

    def _build_opencrvs_envelope(self, client, event_type=None):
        """Helper to build an OpenCRVS envelope via search_by_date_range."""
        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"status": "success"}
            client.search_by_date_range(
                start_date="2020-01-01",
                end_date="2026-02-10",
                attribute_name="dateOfEvent",
                event_type=event_type,
                use_opencrvs_format=True,
            )
            return mock_request.call_args[0][1]

    def test_opencrvs_envelope_reg_type(self):
        """reg_type must be 'ns:org:RegistryType:Civil' (not lowercase event type)."""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = self._build_opencrvs_envelope(client)
        search_criteria = envelope["message"]["search_request"][0]["search_criteria"]

        self.assertEqual(search_criteria["reg_type"], "ns:org:RegistryType:Civil")

    def test_opencrvs_envelope_reg_event_type(self):
        """reg_event_type must be present and default to 'birth' (lowercase)."""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = self._build_opencrvs_envelope(client)
        search_criteria = envelope["message"]["search_request"][0]["search_criteria"]

        self.assertIn("reg_event_type", search_criteria)
        self.assertEqual(search_criteria["reg_event_type"], "birth")

    def test_opencrvs_envelope_reg_event_type_death(self):
        """Passing event_type='DEATH' produces reg_event_type: 'death'."""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = self._build_opencrvs_envelope(client, event_type="DEATH")
        search_criteria = envelope["message"]["search_request"][0]["search_criteria"]

        self.assertEqual(search_criteria["reg_event_type"], "death")

    def test_opencrvs_envelope_expression_query_structure(self):
        """Expression query must be nested: type/value/expression/query."""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = self._build_opencrvs_envelope(client)
        search_criteria = envelope["message"]["search_request"][0]["search_criteria"]
        query = search_criteria["query"]

        # Top-level structure
        self.assertEqual(query["type"], "ns:org:QueryType:expression")
        self.assertIn("value", query)

        # value -> expression -> query -> { attribute_name: { type, gte, lte } }
        value = query["value"]
        self.assertIn("expression", value)
        self.assertIn("query", value["expression"])

        attribute_query = value["expression"]["query"]
        self.assertIn("dateOfEvent", attribute_query)
        self.assertEqual(attribute_query["dateOfEvent"]["type"], "range")
        self.assertEqual(attribute_query["dateOfEvent"]["gte"], "2020-01-01")
        self.assertEqual(attribute_query["dateOfEvent"]["lte"], "2026-02-10")

    def test_opencrvs_envelope_has_consent_and_locale(self):
        """OpenCRVS envelope must include consent and locale."""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = self._build_opencrvs_envelope(client)
        search_request_item = envelope["message"]["search_request"][0]

        self.assertIn("consent", search_request_item)
        self.assertIn("locale", search_request_item)
        self.assertEqual(search_request_item["locale"], "eng")

    def test_opencrvs_envelope_no_signature_key(self):
        """OpenCRVS envelope must not have a 'signature' key."""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = self._build_opencrvs_envelope(client)

        self.assertNotIn("signature", envelope)

    def test_search_by_expression_opencrvs_format(self):
        """search_by_expression(use_opencrvs_format=True) produces OpenCRVS envelope."""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        expression = {"birthDate": {"type": "range", "gte": "2020-01-01", "lte": "2026-12-31"}}

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"status": "success"}
            client.search_by_expression(
                expression=expression,
                use_opencrvs_format=True,
            )
            envelope = mock_request.call_args[0][1]

        # Should use OpenCRVS format (no signature, has consent/locale)
        self.assertNotIn("signature", envelope)
        search_request_item = envelope["message"]["search_request"][0]
        self.assertIn("consent", search_request_item)
        self.assertIn("locale", search_request_item)

        # Query should be wrapped in expression/query structure
        search_criteria = search_request_item["search_criteria"]
        self.assertEqual(search_criteria["reg_type"], "ns:org:RegistryType:Civil")
        query = search_criteria["query"]
        self.assertEqual(query["type"], "ns:org:QueryType:expression")
        self.assertIn("expression", query["value"])
        self.assertIn("query", query["value"]["expression"])
        self.assertEqual(query["value"]["expression"]["query"], expression)

    def test_search_by_expression_standard_unchanged(self):
        """search_by_expression() without flag still uses standard DCI path."""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        expression = [
            {
                "seq_num": 1,
                "expression1": {
                    "attribute_name": "dateOfEvent",
                    "operator": "ge",
                    "attribute_value": "2020-01-01",
                },
                "condition": "and",
                "expression2": {
                    "attribute_name": "dateOfEvent",
                    "operator": "le",
                    "attribute_value": "2026-02-10",
                },
            }
        ]

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"status": "success"}
            client.search_by_expression(expression=expression)
            envelope = mock_request.call_args[0][1]

        # Standard DCI format has signature
        self.assertIn("signature", envelope)
        # Standard DCI format uses registry type not OpenCRVS format
        search_criteria = envelope["message"]["search_request"][0]["search_criteria"]
        self.assertEqual(search_criteria["reg_type"], "ns:org:RegistryType:Civil")
