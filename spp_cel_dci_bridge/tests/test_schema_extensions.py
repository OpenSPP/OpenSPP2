from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSchemaExtensions(TransactionCase):
    """Verify the additive schema extensions to spp.data.provider and spp.cel.variable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Provider = cls.env["spp.data.provider"]
        cls.Variable = cls.env["spp.cel.variable"]
        cls.DCISource = cls.env["spp.dci.data.source"]

        cls.dci_source = cls.DCISource.create(
            {
                "name": "Test DR Source",
                "code": "test_dr_source",
                "registry_type": "DR",
                "base_url": "https://example.invalid/api",
                "auth_type": "none",
                "our_sender_id": "test.openspp.example.org",
            }
        )

    def test_provider_dci_data_source_field_exists(self):
        provider = self.Provider.create(
            {"name": "Plain Provider", "code": "plain_provider"}
        )
        self.assertFalse(provider.dci_data_source_id)
        self.assertFalse(provider.is_dci_backed)

    def test_provider_is_dci_backed_reflects_link(self):
        provider = self.Provider.create(
            {
                "name": "DR Provider",
                "code": "dr_provider",
                "dci_data_source_id": self.dci_source.id,
            }
        )
        self.assertTrue(provider.is_dci_backed)

        provider.dci_data_source_id = False
        self.assertFalse(provider.is_dci_backed)

    def test_variable_dci_attribute_path_required_when_dci_backed(self):
        provider = self.Provider.create(
            {
                "name": "DR Provider 2",
                "code": "dr_provider_2",
                "dci_data_source_id": self.dci_source.id,
            }
        )

        with self.assertRaises(ValidationError):
            self.Variable.create(
                {
                    "name": "var_no_path",
                    "cel_accessor": "var_no_path",
                    "source_type": "external",
                    "value_type": "boolean",
                    "external_provider_id": provider.id,
                    # missing dci_attribute_path
                }
            )

    def test_variable_dci_attribute_path_accepted(self):
        provider = self.Provider.create(
            {
                "name": "DR Provider 3",
                "code": "dr_provider_3",
                "dci_data_source_id": self.dci_source.id,
            }
        )
        var = self.Variable.create(
            {
                "name": "var_ok",
                "cel_accessor": "var_ok",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": provider.id,
                "dci_attribute_path": "has_disability",
            }
        )
        self.assertEqual(var.dci_attribute_path, "has_disability")
        self.assertEqual(var.external_failure_policy, "null")

    def test_variable_attribute_path_not_required_for_non_dci_provider(self):
        provider = self.Provider.create(
            {"name": "REST Provider", "code": "rest_provider"}
        )
        var = self.Variable.create(
            {
                "name": "var_rest",
                "cel_accessor": "var_rest",
                "source_type": "external",
                "value_type": "number",
                "external_provider_id": provider.id,
            }
        )
        self.assertFalse(var.dci_attribute_path)

    def test_failure_policy_default_is_null(self):
        provider = self.Provider.create(
            {
                "name": "DR Provider 4",
                "code": "dr_provider_4",
                "dci_data_source_id": self.dci_source.id,
            }
        )
        var = self.Variable.create(
            {
                "name": "var_default_policy",
                "cel_accessor": "var_default_policy",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": provider.id,
                "dci_attribute_path": "x",
            }
        )
        self.assertEqual(var.external_failure_policy, "null")

    def test_failure_policy_accepts_other_values(self):
        provider = self.Provider.create(
            {
                "name": "DR Provider 5",
                "code": "dr_provider_5",
                "dci_data_source_id": self.dci_source.id,
            }
        )
        for policy in ("null", "last_known", "fail"):
            var = self.Variable.create(
                {
                    "name": f"var_{policy}",
                    "cel_accessor": f"var_{policy}",
                    "source_type": "external",
                    "value_type": "boolean",
                    "external_provider_id": provider.id,
                    "dci_attribute_path": "x",
                    "external_failure_policy": policy,
                }
            )
            self.assertEqual(var.external_failure_policy, policy)
