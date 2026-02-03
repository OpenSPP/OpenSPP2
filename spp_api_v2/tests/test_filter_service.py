# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for FilterService"""

from odoo.exceptions import ValidationError

from ..services.filter_service import FilterService
from .common import ApiV2TestCase


class TestFilterService(ApiV2TestCase):
    """Test FilterService functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test API path configuration (or use existing)
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        # Check if Individual path already exists (from demo/test data)
        cls.api_path = cls.env["spp.api.path"].search([("name", "=", "Individual")], limit=1)
        if not cls.api_path:
            cls.api_path = cls.env["spp.api.path"].create(
                {
                    "name": "Individual",
                    "model_id": cls.partner_model.id,
                    "filter_domain": "[('is_registrant', '=', True), ('is_group', '=', False)]",
                    "allow_custom_filters": False,
                    "max_filter_complexity": 10,
                }
            )

        # Create or find filter configurations
        def get_or_create_filter(name, field_path, filter_type, allowed_operators, label, **extra):
            """Helper to create or find existing filter."""
            existing = cls.env["spp.api.path.filter"].search(
                [("path_id", "=", cls.api_path.id), ("name", "=", name)], limit=1
            )
            if existing:
                return existing
            return cls.env["spp.api.path.filter"].create(
                {
                    "path_id": cls.api_path.id,
                    "name": name,
                    "field_path": field_path,
                    "filter_type": filter_type,
                    "allowed_operators": allowed_operators,
                    "label": label,
                    **extra,
                }
            )

        cls.filter_name = get_or_create_filter(
            name="name",
            field_path="name",
            filter_type="contains",
            allowed_operators="ilike,like",
            label="Name",
        )

        cls.filter_city = get_or_create_filter(
            name="city",
            field_path="city",
            filter_type="contains",
            allowed_operators="ilike",
            label="City",
        )

        cls.filter_active = get_or_create_filter(
            name="active",
            field_path="active",
            filter_type="boolean",
            allowed_operators="eq",
            label="Active",
        )

        cls.filter_state_id = get_or_create_filter(
            name="state_id",
            field_path="state_id",
            filter_type="in",
            allowed_operators="in",
            label="State",
            max_values=10,
        )

        cls.filter_write_date = get_or_create_filter(
            name="write_date",
            field_path="write_date",
            filter_type="range",
            allowed_operators="gt,gte,lt,lte",
            label="Last Updated",
        )

        cls.filter_phone = get_or_create_filter(
            name="phone_exists",
            field_path="phone",
            filter_type="null",
            allowed_operators="null",
            label="Has Phone",
        )

    def setUp(self):
        super().setUp()
        self.service = FilterService(self.env)

        # Create test individuals
        self.ind1 = self.create_test_individual(
            name="Alice Johnson",
            identifier_value="FILTER-001",
            city="New York",
            phone="+1234567890",
        )
        self.ind2 = self.create_test_individual(
            name="Bob Smith",
            identifier_value="FILTER-002",
            city="Los Angeles",
        )
        self.ind3 = self.create_test_individual(
            name="Alice Brown",
            identifier_value="FILTER-003",
            city="New York",
            phone="+0987654321",
        )

    def test_get_path_config(self):
        """get_path_config returns correct path configuration"""
        config = self.service.get_path_config("Individual")

        # Verify we got a path with the correct name and model
        self.assertTrue(config)
        self.assertEqual(config.name, "Individual")
        self.assertEqual(config.model_id.model, "res.partner")

    def test_get_path_config_not_found(self):
        """get_path_config returns None for unknown resource"""
        config = self.service.get_path_config("Unknown")

        self.assertFalse(config)

    def test_parse_query_params_simple(self):
        """parse_query_params handles simple field=value syntax"""
        domain = self.service.parse_query_params(
            {"name": "Alice"},
            "Individual",
        )

        # Should create ilike domain (default for contains type)
        self.assertIn(("name", "ilike", "Alice"), domain)

    def test_parse_query_params_with_operator(self):
        """parse_query_params handles field[operator]=value syntax"""
        domain = self.service.parse_query_params(
            {"name[like]": "Alice"},
            "Individual",
        )

        self.assertIn(("name", "like", "Alice"), domain)

    def test_parse_query_params_ignores_reserved(self):
        """parse_query_params ignores reserved parameters"""
        domain = self.service.parse_query_params(
            {
                "name": "Alice",
                "_count": 10,
                "_offset": 0,
                "_sort": "name",
            },
            "Individual",
        )

        # Only name filter, not pagination params
        self.assertEqual(len(domain), 1)
        self.assertIn(("name", "ilike", "Alice"), domain)

    def test_parse_query_params_unknown_filter(self):
        """parse_query_params ignores unknown filters when custom filters disabled"""
        domain = self.service.parse_query_params(
            {"unknown_field": "value"},
            "Individual",
        )

        self.assertEqual(len(domain), 0)

    def test_parse_query_params_boolean_filter(self):
        """parse_query_params handles boolean filter type"""
        domain = self.service.parse_query_params(
            {"active": "true"},
            "Individual",
        )

        self.assertIn(("active", "=", True), domain)

        domain = self.service.parse_query_params(
            {"active": "false"},
            "Individual",
        )

        self.assertIn(("active", "=", False), domain)

    def test_parse_query_params_null_filter(self):
        """parse_query_params handles null filter type"""
        domain = self.service.parse_query_params(
            {"phone_exists[null]": "true"},
            "Individual",
        )

        self.assertIn(("phone", "=", False), domain)

        domain = self.service.parse_query_params(
            {"phone_exists[null]": "false"},
            "Individual",
        )

        self.assertIn(("phone", "!=", False), domain)

    def test_parse_json_filters_simple(self):
        """parse_json_filters handles simple filter conditions"""
        filters = [
            {"field": "name", "operator": "ilike", "value": "Alice"},
            {"field": "city", "operator": "ilike", "value": "New York"},
        ]

        domain = self.service.parse_json_filters(filters, "Individual")

        self.assertIn(("name", "ilike", "Alice"), domain)
        self.assertIn(("city", "ilike", "New York"), domain)

    def test_parse_json_filters_compound_or(self):
        """parse_json_filters handles OR compound conditions"""
        filters = [
            {
                "logic": "OR",
                "conditions": [
                    {"field": "city", "operator": "ilike", "value": "New York"},
                    {"field": "city", "operator": "ilike", "value": "Los Angeles"},
                ],
            },
        ]

        domain = self.service.parse_json_filters(filters, "Individual")

        # Flatten domain if nested (OR conditions may be returned as nested list)
        flat_domain = []
        for item in domain:
            if isinstance(item, list):
                flat_domain.extend(item)
            else:
                flat_domain.append(item)

        # Domain should have OR operator
        self.assertIn("|", flat_domain)
        # Should contain both city conditions
        self.assertIn(("city", "ilike", "New York"), flat_domain)
        self.assertIn(("city", "ilike", "Los Angeles"), flat_domain)

    def test_validate_filter_complexity_within_limit(self):
        """validate_filter_complexity accepts valid complexity"""
        filters = [
            {"field": "name", "operator": "ilike", "value": "Alice"},
            {"field": "city", "operator": "ilike", "value": "New York"},
        ]

        is_valid, error = self.service.validate_filter_complexity(filters, "Individual")

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_filter_complexity_exceeds_limit(self):
        """validate_filter_complexity rejects excessive complexity"""
        # Create 15 filters to exceed limit of 10
        filters = [{"field": "name", "operator": "ilike", "value": f"test{i}"} for i in range(15)]

        is_valid, error = self.service.validate_filter_complexity(filters, "Individual")

        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum", error)

    def test_get_filter_metadata(self):
        """get_filter_metadata returns correct structure"""
        metadata = self.service.get_filter_metadata("Individual")

        self.assertEqual(metadata["resource"], "Individual")
        self.assertFalse(metadata["allow_custom_filters"])
        self.assertEqual(metadata["max_filter_complexity"], 10)
        self.assertIsInstance(metadata["filters"], list)
        self.assertIsInstance(metadata["presets"], list)

        # Check filter metadata
        filter_names = [f["name"] for f in metadata["filters"]]
        self.assertIn("name", filter_names)
        self.assertIn("city", filter_names)

    def test_get_filter_metadata_unknown_resource(self):
        """get_filter_metadata handles unknown resource"""
        metadata = self.service.get_filter_metadata("Unknown")

        self.assertEqual(metadata["resource"], "Unknown")
        self.assertEqual(metadata["filters"], [])
        self.assertEqual(metadata["presets"], [])


class TestApiPathFilter(ApiV2TestCase):
    """Test spp.api.path.filter model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        cls.api_path = cls.env["spp.api.path"].create(
            {
                "name": "TestPath",
                "model_id": cls.partner_model.id,
            }
        )

    def test_filter_get_operators(self):
        """get_operators returns configured operators"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_filter",
                "field_path": "name",
                "filter_type": "range",
                "allowed_operators": "gt,gte,lt,lte",
            }
        )

        operators = filter_rec.get_operators()

        self.assertEqual(operators, ["gt", "gte", "lt", "lte"])

    def test_filter_get_default_operator(self):
        """get_default_operator returns first allowed operator"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_filter2",
                "field_path": "name",
                "filter_type": "range",
                "allowed_operators": "gte,lte",
            }
        )

        default_op = filter_rec.get_default_operator()

        self.assertEqual(default_op, "gte")

    def test_filter_validate_value_success(self):
        """validate_value accepts valid values"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_filter3",
                "field_path": "name",
                "filter_type": "contains",
                "allowed_operators": "ilike",
            }
        )

        is_valid, error = filter_rec.validate_value("test", "ilike")

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_filter_validate_value_invalid_operator(self):
        """validate_value rejects invalid operators"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_filter4",
                "field_path": "name",
                "filter_type": "contains",
                "allowed_operators": "ilike",
            }
        )

        is_valid, error = filter_rec.validate_value("test", "eq")

        self.assertFalse(is_valid)
        self.assertIn("not allowed", error)

    def test_filter_validate_value_max_values(self):
        """validate_value enforces max_values for in/nin"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_filter5",
                "field_path": "state_id",
                "filter_type": "in",
                "allowed_operators": "in",
                "max_values": 3,
            }
        )

        # 3 values is OK
        is_valid, _ = filter_rec.validate_value("1,2,3", "in")
        self.assertTrue(is_valid)

        # 5 values exceeds limit
        is_valid, error = filter_rec.validate_value("1,2,3,4,5", "in")
        self.assertFalse(is_valid)
        self.assertIn("Too many values", error)

    def test_filter_to_domain_exact(self):
        """to_domain generates correct domain for exact filter"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_exact",
                "field_path": "name",
                "filter_type": "exact",
                "allowed_operators": "eq,ne",
            }
        )

        domain = filter_rec.to_domain("John", "eq")

        self.assertEqual(domain, [("name", "=", "John")])

    def test_filter_to_domain_contains(self):
        """to_domain generates correct domain for contains filter"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_contains",
                "field_path": "name",
                "filter_type": "contains",
                "allowed_operators": "ilike",
            }
        )

        domain = filter_rec.to_domain("John", "ilike")

        self.assertEqual(domain, [("name", "ilike", "John")])

    def test_filter_to_domain_in(self):
        """to_domain generates correct domain for in filter"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_in",
                "field_path": "city",
                "filter_type": "in",
                "allowed_operators": "in",
                "max_values": 10,
            }
        )

        domain = filter_rec.to_domain("New York,Los Angeles", "in")

        self.assertEqual(domain, [("city", "in", ["New York", "Los Angeles"])])

    def test_filter_to_domain_null_true(self):
        """to_domain generates correct domain for null=true"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_null",
                "field_path": "phone",
                "filter_type": "null",
                "allowed_operators": "null",
            }
        )

        domain = filter_rec.to_domain("true", "null")

        self.assertEqual(domain, [("phone", "=", False)])

    def test_filter_to_domain_null_false(self):
        """to_domain generates correct domain for null=false"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_null2",
                "field_path": "phone",
                "filter_type": "null",
                "allowed_operators": "null",
            }
        )

        domain = filter_rec.to_domain("false", "null")

        self.assertEqual(domain, [("phone", "!=", False)])

    def test_filter_to_domain_boolean(self):
        """to_domain generates correct domain for boolean filter"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_bool",
                "field_path": "active",
                "filter_type": "boolean",
                "allowed_operators": "eq",
            }
        )

        domain = filter_rec.to_domain("true")

        self.assertEqual(domain, [("active", "=", True)])

        domain = filter_rec.to_domain("0")

        self.assertEqual(domain, [("active", "=", False)])

    def test_filter_to_metadata(self):
        """to_metadata returns correct structure"""
        filter_rec = self.env["spp.api.path.filter"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_meta",
                "field_path": "name",
                "filter_type": "contains",
                "label": "Name Filter",
                "description": "Filter by name",
                "allowed_operators": "ilike,like",
                "required": True,
                "is_indexed": True,
            }
        )

        metadata = filter_rec.to_metadata()

        self.assertEqual(metadata["name"], "test_meta")
        self.assertEqual(metadata["field_path"], "name")
        self.assertEqual(metadata["filter_type"], "contains")
        self.assertEqual(metadata["label"], "Name Filter")
        self.assertEqual(metadata["description"], "Filter by name")
        self.assertEqual(metadata["allowed_operators"], ["ilike", "like"])
        self.assertTrue(metadata["required"])
        self.assertTrue(metadata["is_indexed"])

    def test_filter_field_path_validation(self):
        """field_path must reference valid model fields"""
        with self.assertRaises(ValidationError) as ctx:
            self.env["spp.api.path.filter"].create(
                {
                    "path_id": self.api_path.id,
                    "name": "invalid_path",
                    "field_path": "nonexistent_field",
                    "filter_type": "exact",
                }
            )

        self.assertIn("does not exist", str(ctx.exception))

    def test_filter_allowed_operators_validation(self):
        """allowed_operators must be valid for filter_type"""
        with self.assertRaises(ValidationError) as ctx:
            self.env["spp.api.path.filter"].create(
                {
                    "path_id": self.api_path.id,
                    "name": "invalid_ops",
                    "field_path": "name",
                    "filter_type": "boolean",
                    "allowed_operators": "ilike,gt",  # Invalid for boolean
                }
            )

        self.assertIn("not valid for filter type", str(ctx.exception))


class TestApiFilterPreset(ApiV2TestCase):
    """Test spp.api.filter.preset model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        cls.api_path = cls.env["spp.api.path"].create(
            {
                "name": "PresetTestPath",
                "model_id": cls.partner_model.id,
            }
        )

    def test_preset_get_filters(self):
        """get_filters parses filter_json correctly"""
        preset = self.env["spp.api.filter.preset"].create(
            {
                "path_id": self.api_path.id,
                "name": "test_preset",
                "filter_json": '[{"field": "name", "operator": "ilike", "value": "John"}]',
            }
        )

        filters = preset.get_filters()

        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0]["field"], "name")
        self.assertEqual(filters[0]["operator"], "ilike")
        self.assertEqual(filters[0]["value"], "John")

    def test_preset_name_validation(self):
        """preset name must follow valid format"""
        # Valid name
        preset = self.env["spp.api.filter.preset"].create(
            {
                "path_id": self.api_path.id,
                "name": "valid_preset_name",
                "filter_json": "[]",
            }
        )
        self.assertTrue(preset)

        # Invalid name (starts with number)
        with self.assertRaises(ValidationError):
            self.env["spp.api.filter.preset"].create(
                {
                    "path_id": self.api_path.id,
                    "name": "123invalid",
                    "filter_json": "[]",
                }
            )

        # Invalid name (uppercase)
        with self.assertRaises(ValidationError):
            self.env["spp.api.filter.preset"].create(
                {
                    "path_id": self.api_path.id,
                    "name": "Invalid_Name",
                    "filter_json": "[]",
                }
            )

    def test_preset_filter_json_validation(self):
        """filter_json must be valid JSON array"""
        # Invalid JSON
        with self.assertRaises(ValidationError):
            self.env["spp.api.filter.preset"].create(
                {
                    "path_id": self.api_path.id,
                    "name": "invalid_json",
                    "filter_json": "not json",
                }
            )

        # Valid JSON but not array
        with self.assertRaises(ValidationError):
            self.env["spp.api.filter.preset"].create(
                {
                    "path_id": self.api_path.id,
                    "name": "not_array",
                    "filter_json": '{"field": "name"}',
                }
            )

    def test_preset_to_metadata(self):
        """to_metadata returns correct structure"""
        preset = self.env["spp.api.filter.preset"].create(
            {
                "path_id": self.api_path.id,
                "name": "meta_preset",
                "description": "Test preset description",
                "filter_json": "[]",
            }
        )

        metadata = preset.to_metadata()

        self.assertEqual(metadata["name"], "meta_preset")
        self.assertEqual(metadata["description"], "Test preset description")


class TestApiPath(ApiV2TestCase):
    """Test spp.api.path model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def test_path_eval_domain(self):
        """eval_domain evaluates static domain"""
        path = self.env["spp.api.path"].create(
            {
                "name": "EvalDomainTest",
                "model_id": self.partner_model.id,
                "filter_domain": "[('is_registrant', '=', True)]",
            }
        )

        domain = path.eval_domain()

        self.assertEqual(domain, [("is_registrant", "=", True)])

    def test_path_eval_domain_with_additional(self):
        """eval_domain combines static and additional domain"""
        path = self.env["spp.api.path"].create(
            {
                "name": "CombinedDomainTest",
                "model_id": self.partner_model.id,
                "filter_domain": "[('is_registrant', '=', True)]",
            }
        )

        additional = [("is_group", "=", False)]
        domain = path.eval_domain(additional)

        self.assertIn(("is_registrant", "=", True), domain)
        self.assertIn(("is_group", "=", False), domain)

    def test_path_get_available_filters(self):
        """get_available_filters returns active filters only"""
        path = self.env["spp.api.path"].create(
            {
                "name": "AvailableFiltersTest",
                "model_id": self.partner_model.id,
            }
        )

        # Create active and inactive filters
        self.env["spp.api.path.filter"].create(
            {
                "path_id": path.id,
                "name": "active_filter",
                "field_path": "name",
                "filter_type": "exact",
                "active": True,
            }
        )
        self.env["spp.api.path.filter"].create(
            {
                "path_id": path.id,
                "name": "inactive_filter",
                "field_path": "city",
                "filter_type": "exact",
                "active": False,
            }
        )

        filters = path.get_available_filters()

        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].name, "active_filter")

    def test_path_get_available_presets(self):
        """get_available_presets returns public presets only by default"""
        path = self.env["spp.api.path"].create(
            {
                "name": "PresetsTest",
                "model_id": self.partner_model.id,
            }
        )

        # Create public and private presets
        self.env["spp.api.filter.preset"].create(
            {
                "path_id": path.id,
                "name": "public_preset",
                "filter_json": "[]",
                "is_public": True,
            }
        )
        self.env["spp.api.filter.preset"].create(
            {
                "path_id": path.id,
                "name": "private_preset",
                "filter_json": "[]",
                "is_public": False,
            }
        )

        presets = path.get_available_presets()

        self.assertEqual(len(presets), 1)
        self.assertEqual(presets[0].name, "public_preset")

        # With include_private=True
        all_presets = path.get_available_presets(include_private=True)

        self.assertEqual(len(all_presets), 2)

    def test_path_filter_count(self):
        """filter_count computes correctly"""
        path = self.env["spp.api.path"].create(
            {
                "name": "FilterCountTest",
                "model_id": self.partner_model.id,
            }
        )

        self.assertEqual(path.filter_count, 0)

        self.env["spp.api.path.filter"].create(
            {
                "path_id": path.id,
                "name": "filter1",
                "field_path": "name",
                "filter_type": "exact",
            }
        )
        self.env["spp.api.path.filter"].create(
            {
                "path_id": path.id,
                "name": "filter2",
                "field_path": "city",
                "filter_type": "exact",
            }
        )

        # Refresh to get updated count
        path.invalidate_recordset()
        self.assertEqual(path.filter_count, 2)


class TestFilterServiceSecurity(ApiV2TestCase):
    """Security tests for FilterService"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        cls.api_path = cls.env["spp.api.path"].create(
            {
                "name": "SecureIndividual",
                "model_id": cls.partner_model.id,
                "allow_custom_filters": True,  # Enable for testing validation
                "max_filter_complexity": 5,
            }
        )

        cls.filter_name = cls.env["spp.api.path.filter"].create(
            {
                "path_id": cls.api_path.id,
                "name": "name",
                "field_path": "name",
                "filter_type": "contains",
                "allowed_operators": "ilike",
                "requires_scope": "individual:read",  # Scope requirement (lowercase)
            }
        )

    def setUp(self):
        super().setUp()
        self.service = FilterService(self.env)

    def test_field_path_validation_rejects_invalid_characters(self):
        """Custom filter field paths must contain only valid characters"""
        # Create path with custom filters enabled
        domain = self.service._build_custom_domain(
            "'; DROP TABLE res_partner; --",  # SQL injection attempt
            "eq",
            "test",
            "res.partner",
        )

        # Should return empty domain (rejected)
        self.assertEqual(domain, [])

    def test_field_path_validation_rejects_nonexistent_field(self):
        """Custom filter rejects non-existent fields"""
        domain = self.service._build_custom_domain(
            "nonexistent_field",
            "eq",
            "test",
            "res.partner",
        )

        self.assertEqual(domain, [])

    def test_field_path_validation_accepts_valid_field(self):
        """Custom filter accepts valid model fields"""
        domain = self.service._build_custom_domain(
            "name",
            "eq",
            "test",
            "res.partner",
        )

        self.assertEqual(domain, [("name", "=", "test")])

    def test_field_path_validation_nested_field(self):
        """Custom filter validates nested field paths"""
        # Valid nested path: state_id.name
        domain = self.service._build_custom_domain(
            "state_id.name",
            "eq",
            "California",
            "res.partner",
        )

        self.assertEqual(domain, [("state_id.name", "=", "California")])

    def test_field_path_validation_rejects_invalid_nested_path(self):
        """Custom filter rejects invalid nested paths"""
        # Invalid: trying to traverse through a non-relational field
        domain = self.service._build_custom_domain(
            "name.invalid",  # name is a char, not relational
            "eq",
            "test",
            "res.partner",
        )

        self.assertEqual(domain, [])

    def test_scope_filtered_filters(self):
        """Filters with scope requirements are filtered by client permissions"""
        # Create API client with individual:read scope (lowercase to match model)
        client_with_scope = self.create_api_client(
            name="Client With Scope",
            scopes=[{"resource": "individual", "action": "read"}],
        )

        # Create API client without the required scope
        client_without_scope = self.create_api_client(
            name="Client Without Scope",
            scopes=[{"resource": "group", "action": "read"}],
        )

        # Client with scope should see the filter
        filters_with = self.api_path.get_available_filters(client_with_scope)
        filter_names_with = [f.name for f in filters_with]
        self.assertIn("name", filter_names_with)

        # Client without scope should not see the filter
        filters_without = self.api_path.get_available_filters(client_without_scope)
        filter_names_without = [f.name for f in filters_without]
        self.assertNotIn("name", filter_names_without)


class TestOrDomainGeneration(ApiV2TestCase):
    """Tests for OR domain generation (Polish notation)"""

    def setUp(self):
        super().setUp()
        self.service = FilterService(self.env)

    def test_combine_with_or_single_condition(self):
        """Single condition returns unchanged"""
        domain = self.service._combine_with_or([("name", "=", "test")])

        self.assertEqual(domain, [("name", "=", "test")])

    def test_combine_with_or_two_conditions(self):
        """Two conditions get one OR operator"""
        domain = self.service._combine_with_or(
            [
                ("name", "=", "test1"),
                ("name", "=", "test2"),
            ]
        )

        self.assertEqual(len(domain), 3)
        self.assertEqual(domain[0], "|")
        self.assertEqual(domain[1], ("name", "=", "test1"))
        self.assertEqual(domain[2], ("name", "=", "test2"))

    def test_combine_with_or_three_conditions(self):
        """Three conditions get two OR operators"""
        domain = self.service._combine_with_or(
            [
                ("name", "=", "a"),
                ("name", "=", "b"),
                ("name", "=", "c"),
            ]
        )

        self.assertEqual(len(domain), 5)
        self.assertEqual(domain[0], "|")
        self.assertEqual(domain[1], "|")
        self.assertIn(("name", "=", "a"), domain)
        self.assertIn(("name", "=", "b"), domain)
        self.assertIn(("name", "=", "c"), domain)

    def test_combine_with_or_empty_list(self):
        """Empty list returns empty"""
        domain = self.service._combine_with_or([])

        self.assertEqual(domain, [])

    def test_combine_with_or_nested_domains(self):
        """Handles already-combined nested domains"""
        # Simulate a nested OR that was already combined
        nested = ["|", ("city", "=", "NY"), ("city", "=", "LA")]
        domain = self.service._combine_with_or(
            [
                ("name", "=", "test"),
                nested,
            ]
        )

        # Should combine the tuple and the nested list with OR
        self.assertIn("|", domain)
        self.assertIn(("name", "=", "test"), domain)


class TestPresetApplication(ApiV2TestCase):
    """Tests for filter preset application"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        cls.api_path = cls.env["spp.api.path"].create(
            {
                "name": "PresetApplyTest",
                "model_id": cls.partner_model.id,
            }
        )

        cls.filter_name = cls.env["spp.api.path.filter"].create(
            {
                "path_id": cls.api_path.id,
                "name": "name",
                "field_path": "name",
                "filter_type": "contains",
                "allowed_operators": "ilike",
            }
        )

        cls.filter_city = cls.env["spp.api.path.filter"].create(
            {
                "path_id": cls.api_path.id,
                "name": "city",
                "field_path": "city",
                "filter_type": "contains",
                "allowed_operators": "ilike",
            }
        )

        # Create presets
        cls.public_preset = cls.env["spp.api.filter.preset"].create(
            {
                "path_id": cls.api_path.id,
                "name": "active_users",
                "filter_json": '[{"field": "name", "operator": "ilike", "value": "active"}]',
                "is_public": True,
            }
        )

        cls.private_preset = cls.env["spp.api.filter.preset"].create(
            {
                "path_id": cls.api_path.id,
                "name": "private_filter",
                "filter_json": '[{"field": "city", "operator": "ilike", "value": "private"}]',
                "is_public": False,
            }
        )

    def setUp(self):
        super().setUp()
        self.service = FilterService(self.env)

    def test_apply_preset_success(self):
        """apply_preset returns domain from preset filters"""
        domain = self.service.apply_preset(
            "active_users",
            "PresetApplyTest",
        )

        self.assertIn(("name", "ilike", "active"), domain)

    def test_apply_preset_not_found(self):
        """apply_preset returns empty for unknown preset"""
        domain = self.service.apply_preset(
            "nonexistent_preset",
            "PresetApplyTest",
        )

        self.assertEqual(domain, [])

    def test_apply_preset_private_rejected(self):
        """apply_preset rejects non-public presets"""
        domain = self.service.apply_preset(
            "private_filter",
            "PresetApplyTest",
        )

        # Private preset should not be accessible
        self.assertEqual(domain, [])

    def test_apply_preset_with_additional_filters(self):
        """apply_preset combines preset with additional filters"""
        additional = [{"field": "city", "operator": "ilike", "value": "New York"}]

        domain = self.service.apply_preset(
            "active_users",
            "PresetApplyTest",
            additional_filters=additional,
        )

        self.assertIn(("name", "ilike", "active"), domain)
        self.assertIn(("city", "ilike", "New York"), domain)


class TestApiClientScopeString(ApiV2TestCase):
    """Tests for has_scope_string method"""

    def setUp(self):
        super().setUp()
        # Note: resource values must be lowercase (as defined in model selection)
        self.client = self.create_api_client(
            name="Scope Test Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "individual", "action": "update"},
                {"resource": "group", "action": "read"},
            ],
        )

    def test_has_scope_string_resource_action(self):
        """has_scope_string works with resource:action format"""
        self.assertTrue(self.client.has_scope_string("individual:read"))
        self.assertTrue(self.client.has_scope_string("individual:update"))
        self.assertTrue(self.client.has_scope_string("group:read"))

        self.assertFalse(self.client.has_scope_string("group:update"))
        self.assertFalse(self.client.has_scope_string("program:read"))

    def test_has_scope_string_wildcard(self):
        """has_scope_string supports wildcard action"""
        # individual:* should match any action on individual
        self.assertTrue(self.client.has_scope_string("individual:*"))
        self.assertTrue(self.client.has_scope_string("group:*"))

        # program:* should fail (no program scopes)
        self.assertFalse(self.client.has_scope_string("program:*"))

    def test_has_scope_string_resource_only(self):
        """has_scope_string with resource only implies wildcard"""
        self.assertTrue(self.client.has_scope_string("individual"))
        self.assertTrue(self.client.has_scope_string("group"))
        self.assertFalse(self.client.has_scope_string("program"))

    def test_has_scope_string_empty(self):
        """has_scope_string returns False for empty/None scope"""
        self.assertFalse(self.client.has_scope_string(""))
        self.assertFalse(self.client.has_scope_string(None))


class TestFilterComplexityValidation(ApiV2TestCase):
    """Tests for filter complexity validation"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        cls.api_path = cls.env["spp.api.path"].create(
            {
                "name": "ComplexityTest",
                "model_id": cls.partner_model.id,
                "max_filter_complexity": 5,
            }
        )

    def setUp(self):
        super().setUp()
        self.service = FilterService(self.env)

    def test_nested_compound_complexity_counted(self):
        """Nested compound conditions are counted correctly"""
        # This has 4 conditions in total
        filters = [
            {
                "logic": "OR",
                "conditions": [
                    {"field": "name", "operator": "ilike", "value": "a"},
                    {"field": "name", "operator": "ilike", "value": "b"},
                    {
                        "logic": "AND",
                        "conditions": [
                            {"field": "city", "operator": "eq", "value": "x"},
                            {"field": "active", "operator": "eq", "value": True},
                        ],
                    },
                ],
            },
        ]

        is_valid, error = self.service.validate_filter_complexity(
            filters,
            "ComplexityTest",
        )

        self.assertTrue(is_valid)  # 4 conditions < 5 max

    def test_nested_complexity_exceeded(self):
        """Deeply nested conditions exceed limit"""
        # 6 conditions total
        filters = [
            {"field": "name", "operator": "ilike", "value": "a"},
            {"field": "name", "operator": "ilike", "value": "b"},
            {"field": "name", "operator": "ilike", "value": "c"},
            {"field": "name", "operator": "ilike", "value": "d"},
            {"field": "name", "operator": "ilike", "value": "e"},
            {"field": "name", "operator": "ilike", "value": "f"},
        ]

        is_valid, error = self.service.validate_filter_complexity(
            filters,
            "ComplexityTest",
        )

        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum", error)


class TestAstLiteralEvalDomain(ApiV2TestCase):
    """Tests for safe domain evaluation using ast.literal_eval"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def test_eval_domain_valid_expression(self):
        """eval_domain handles valid literal expressions"""
        path = self.env["spp.api.path"].create(
            {
                "name": "LiteralEvalTest1",
                "model_id": self.partner_model.id,
                "filter_domain": "[('active', '=', True), ('is_group', '=', False)]",
            }
        )

        domain = path.eval_domain()

        self.assertEqual(len(domain), 2)
        self.assertIn(("active", "=", True), domain)
        self.assertIn(("is_group", "=", False), domain)

    def test_eval_domain_rejects_function_calls(self):
        """eval_domain rejects expressions with function calls"""
        path = self.env["spp.api.path"].create(
            {
                "name": "LiteralEvalTest2",
                "model_id": self.partner_model.id,
                # This would be dangerous with eval() but safe with ast.literal_eval
                "filter_domain": "[('id', '=', __import__('os').system('rm -rf /'))]",
            }
        )

        # Should return empty domain (rejected by ast.literal_eval)
        domain = path.eval_domain()

        self.assertEqual(domain, [])

    def test_eval_domain_none_value(self):
        """eval_domain handles None values correctly"""
        path = self.env["spp.api.path"].create(
            {
                "name": "LiteralEvalTest3",
                "model_id": self.partner_model.id,
                "filter_domain": "[('parent_id', '=', None)]",
            }
        )

        domain = path.eval_domain()

        # ast.literal_eval parses None correctly
        self.assertIn(("parent_id", "=", None), domain)

    def test_eval_domain_empty(self):
        """eval_domain handles empty/no domain"""
        path = self.env["spp.api.path"].create(
            {
                "name": "LiteralEvalTest4",
                "model_id": self.partner_model.id,
            }
        )

        domain = path.eval_domain()

        self.assertEqual(domain, [])

    def test_eval_domain_with_additional(self):
        """eval_domain combines static and additional domains"""
        path = self.env["spp.api.path"].create(
            {
                "name": "LiteralEvalTest5",
                "model_id": self.partner_model.id,
                "filter_domain": "[('active', '=', True)]",
            }
        )

        additional = [("is_registrant", "=", True)]
        domain = path.eval_domain(additional)

        self.assertEqual(len(domain), 2)
        self.assertIn(("active", "=", True), domain)
        self.assertIn(("is_registrant", "=", True), domain)
