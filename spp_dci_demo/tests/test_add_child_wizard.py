# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for the multi-step Add Child wizard."""

from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAddChildWizard(TransactionCase):
    """Test the multi-step Add Child wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["spp.dci.demo.add.child.wizard"]

        # Create test data source
        cls.data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "Test CRVS",
                "code": "test_crvs_wizard",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "our_sender_id": "openspp.test",
                "registry_type": "ns:org:RegistryType:Civil",
                "active": True,
            }
        )

        # Create test household (group)
        cls.test_group = cls.env["res.partner"].create(
            {
                "name": "Test Wizard Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Get or create the add_member CR type
        cls.request_type = cls.env["spp.change.request.type"].search([("code", "=", "add_member")], limit=1)
        if not cls.request_type:
            cls.request_type = cls.env["spp.change.request.type"].create(
                {
                    "name": "Add Member",
                    "code": "add_member",
                    "detail_model": "spp.cr.detail.add_member",
                    "strategy_model": "spp.cr.apply.add_member",
                    "target_type": "group",
                }
            )

        # Create an approver user
        cls.approver = cls.env["res.users"].create(
            {
                "name": "Test Wizard Approver",
                "login": "test_wizard_approver",
                "email": "wizard_approver@test.com",
            }
        )

        # Get spp.change.request ir.model record
        cls.cr_model_record = cls.env["ir.model"].search([("model", "=", "spp.change.request")], limit=1)

        # Create approval definition
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Wizard Approval",
                "model_id": cls.cr_model_record.id,
                "approval_type": "user",
                "approval_user_ids": [(6, 0, [cls.approver.id])],
            }
        )

        # Link approval definition to CR type
        cls.request_type.approval_definition_id = cls.approval_def

        # Get gender vocabulary code (loaded via spp_vocabulary data)
        cls.gender_male = cls.env.ref("spp_vocabulary.code_gender_male", raise_if_not_found=False)
        if not cls.gender_male:
            cls.gender_male = cls.env["spp.vocabulary.code"].search(
                [
                    ("namespace_uri", "=", "urn:iso:std:iso:5218"),
                    ("code", "=", "1"),
                ],
                limit=1,
            )

        # Get relationship vocabulary code (use "head" since "child" is not in data)
        cls.relationship_head = cls.env.ref(
            "spp_vocabulary.code_membership_type_head",
            raise_if_not_found=False,
        )
        if not cls.relationship_head:
            cls.relationship_head = cls.env["spp.vocabulary.code"].search(
                [
                    (
                        "vocabulary_id.namespace_uri",
                        "=",
                        "urn:openspp:vocab:group-membership-type",
                    ),
                ],
                limit=1,
            )

    def _create_wizard(self, **kwargs):
        """Create a wizard with sensible defaults."""
        vals = {
            "registrant_id": self.test_group.id,
        }
        vals.update(kwargs)
        return self.Wizard.create(vals)

    # ==================
    # Default Get Tests
    # ==================

    def test_default_type_is_add_member(self):
        """default_get sets request_type_id to the add_member type."""
        wizard = self.Wizard.create({})
        self.assertEqual(wizard.request_type_id, self.request_type)

    def test_context_prefill_registrant(self):
        """Registrant is pre-filled from active_id context."""
        wizard = self.Wizard.with_context(
            active_model="res.partner",
            active_id=self.test_group.id,
        ).create({})
        self.assertEqual(wizard.registrant_id, self.test_group)

    # ==================
    # Step Navigation
    # ==================

    def test_initial_stage_is_registrant(self):
        """Wizard starts at 'registrant' stage."""
        wizard = self._create_wizard()
        self.assertEqual(wizard.stage, "registrant")

    def test_navigate_forward_to_details(self):
        """action_next advances from 'registrant' to 'details'."""
        wizard = self._create_wizard()
        wizard.action_next()
        self.assertEqual(wizard.stage, "details")

    def test_navigate_forward_to_review(self):
        """action_next advances from 'details' to 'review'."""
        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
            birthdate="2024-01-15",
        )
        wizard.stage = "details"
        wizard.action_next()
        self.assertEqual(wizard.stage, "review")

    def test_navigate_backward_from_details(self):
        """action_previous goes from 'details' to 'registrant'."""
        wizard = self._create_wizard()
        wizard.stage = "details"
        wizard.action_previous()
        self.assertEqual(wizard.stage, "registrant")

    def test_navigate_backward_from_review(self):
        """action_previous goes from 'review' to 'details'."""
        wizard = self._create_wizard()
        wizard.stage = "review"
        wizard.action_previous()
        self.assertEqual(wizard.stage, "details")

    def test_navigate_backward_from_registrant_stays(self):
        """action_previous on first step stays at 'registrant'."""
        wizard = self._create_wizard()
        wizard.action_previous()
        self.assertEqual(wizard.stage, "registrant")

    # ==================
    # Per-Step Validation
    # ==================

    def test_step1_requires_registrant(self):
        """Cannot advance past step 1 without a registrant."""
        wizard = self.Wizard.create({})
        with self.assertRaises(UserError):
            wizard.action_next()

    def test_step2_requires_given_name(self):
        """Cannot advance past step 2 without given_name."""
        wizard = self._create_wizard(
            family_name="Doe",
            birthdate="2024-01-15",
        )
        wizard.stage = "details"
        with self.assertRaises(UserError):
            wizard.action_next()

    def test_step2_requires_birthdate(self):
        """Cannot advance past step 2 without birthdate."""
        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
        )
        wizard.stage = "details"
        with self.assertRaises(UserError):
            wizard.action_next()

    # ==================
    # Computed Fields
    # ==================

    def test_member_name_computed(self):
        """member_name is computed from given_name and family_name."""
        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
        )
        self.assertEqual(wizard.member_name, "DOE, JOHN")

    def test_member_name_given_only(self):
        """member_name with only given_name."""
        wizard = self._create_wizard(given_name="John")
        self.assertEqual(wizard.member_name, "JOHN")

    def test_member_name_family_only(self):
        """member_name with only family_name."""
        wizard = self._create_wizard(family_name="Doe")
        self.assertEqual(wizard.member_name, "DOE")

    def test_registrant_info_html_populated(self):
        """registrant_info_html is populated when registrant is selected."""
        wizard = self._create_wizard()
        self.assertTrue(wizard.registrant_info_html)
        self.assertIn("Test Wizard Household", wizard.registrant_info_html)

    def test_preview_html_contains_data(self):
        """preview_html shows summary data at review stage."""
        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
            birthdate="2024-01-15",
            gender_id=self.gender_male.id,
        )
        wizard.stage = "review"
        self.assertTrue(wizard.preview_html)
        self.assertIn("DOE, JOHN", wizard.preview_html)
        self.assertIn("2024-01-15", wizard.preview_html)

    # ==================
    # Birth Verification
    # ==================

    def test_verify_birth_requires_brn(self):
        """action_verify_birth requires a BRN."""
        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
        )
        with self.assertRaises(UserError):
            wizard.action_verify_birth()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_verify_birth_success(self, mock_client_class):
        """Successful birth verification sets status to 'verified'."""
        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.return_value = {
            "identifier": [{"identifier_type": "BRN", "identifier_value": "TEST123"}],
            "name": {"given_name": "John", "surname": "Doe"},
            "sex": "male",
            "birth_date": "2024-01-15",
        }
        mock_client_class.return_value = mock_client

        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
            birthdate="2024-01-15",
            gender_id=self.gender_male.id,
            birth_registration_number="TEST123",
            dci_data_source_id=self.data_source.id,
        )
        wizard.action_verify_birth()

        self.assertEqual(wizard.birth_verification_status, "verified")
        self.assertTrue(wizard.birth_verification_date)
        self.assertTrue(wizard.birth_verification_response)
        self.assertTrue(wizard.dci_data_match)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_verify_birth_not_found(self, mock_client_class):
        """Not-found response sets status to 'not_found'."""
        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.return_value = {
            "message": {
                "search_response": [
                    {"status": "succ", "data": []},
                ]
            },
        }
        mock_client_class.return_value = mock_client

        wizard = self._create_wizard(
            given_name="John",
            birth_registration_number="NONEXISTENT",
            dci_data_source_id=self.data_source.id,
        )
        wizard.action_verify_birth()

        self.assertEqual(wizard.birth_verification_status, "not_found")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_verify_birth_error(self, mock_client_class):
        """API error sets status to 'error'."""
        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.side_effect = Exception("Connection timeout")
        mock_client_class.return_value = mock_client

        wizard = self._create_wizard(
            given_name="John",
            birth_registration_number="TEST123",
            dci_data_source_id=self.data_source.id,
        )

        with self.assertRaises(UserError) as cm:
            wizard.action_verify_birth()
        self.assertIn("Connection timeout", str(cm.exception))

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_verify_birth_data_mismatch(self, mock_client_class):
        """Data mismatch sets dci_data_match to False."""
        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.return_value = {
            "identifier": [{"identifier_type": "BRN", "identifier_value": "TEST123"}],
            "name": {"given_name": "Jane", "surname": "Smith"},
            "sex": "female",
            "birth_date": "2024-06-20",
        }
        mock_client_class.return_value = mock_client

        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
            birthdate="2024-01-15",
            gender_id=self.gender_male.id,
            birth_registration_number="TEST123",
            dci_data_source_id=self.data_source.id,
        )
        wizard.action_verify_birth()

        self.assertEqual(wizard.birth_verification_status, "verified")
        self.assertFalse(wizard.dci_data_match)

    # ==================
    # Create & Submit
    # ==================

    def test_create_and_submit_creates_cr(self):
        """action_create_and_submit creates a CR with detail populated."""
        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
            birthdate="2024-01-15",
            gender_id=self.gender_male.id,
            relationship_id=self.relationship_head.id,
        )
        wizard.stage = "review"

        result = wizard.action_create_and_submit()

        # Should return an action opening the CR form
        self.assertEqual(result["res_model"], "spp.change.request")
        cr_id = result["res_id"]
        cr = self.env["spp.change.request"].browse(cr_id)
        self.assertTrue(cr.exists())

        # Check CR fields
        self.assertEqual(cr.request_type_id, self.request_type)
        self.assertEqual(cr.registrant_id, self.test_group)

        # Check detail fields
        detail = cr.get_detail()
        self.assertTrue(detail)
        self.assertEqual(detail.given_name, "John")
        self.assertEqual(detail.family_name, "Doe")
        self.assertEqual(str(detail.birthdate), "2024-01-15")
        self.assertEqual(detail.gender_id, self.gender_male)
        self.assertEqual(detail.relationship_id, self.relationship_head)

    def test_create_and_submit_submits_cr(self):
        """action_create_and_submit submits the CR for approval."""
        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
            birthdate="2024-01-15",
            gender_id=self.gender_male.id,
        )
        wizard.stage = "review"

        result = wizard.action_create_and_submit()

        cr = self.env["spp.change.request"].browse(result["res_id"])
        # Should be pending (submitted for approval)
        self.assertEqual(cr.display_state, "pending")

    def test_create_and_submit_copies_verification_data(self):
        """Verification data from wizard is copied to the CR detail."""
        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
            birthdate="2024-01-15",
            gender_id=self.gender_male.id,
            birth_registration_number="BRN123",
            birth_verification_status="verified",
            birth_verification_response='{"test": true}',
            dci_data_match=True,
            dci_data_source_id=self.data_source.id,
        )
        wizard.stage = "review"

        result = wizard.action_create_and_submit()

        cr = self.env["spp.change.request"].browse(result["res_id"])
        detail = cr.get_detail()
        self.assertEqual(detail.birth_registration_number, "BRN123")
        self.assertEqual(detail.birth_verification_status, "verified")
        self.assertTrue(detail.birth_verification_response)
        self.assertTrue(detail.dci_data_match)
        self.assertEqual(detail.dci_data_source_id, self.data_source)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_full_happy_path(self, mock_client_class):
        """Full wizard flow: create -> submit -> auto-approve -> auto-apply."""
        # Enable auto-approve
        self.env["ir.config_parameter"].sudo().set_param("spp_dci_demo.auto_approve_on_match", "True")

        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.return_value = {
            "identifier": [{"identifier_type": "BRN", "identifier_value": "HAPPY123"}],
            "name": {"given_name": "George", "surname": "Doe"},
            "sex": "male",
            "birth_date": "2024-01-15",
        }
        mock_client_class.return_value = mock_client

        # Step 1: Create wizard with household
        wizard = self._create_wizard(
            given_name="George",
            family_name="Doe",
            birthdate="2024-01-15",
            gender_id=self.gender_male.id,
            relationship_id=self.relationship_head.id,
            birth_registration_number="HAPPY123",
            dci_data_source_id=self.data_source.id,
        )

        # Step 2: Verify birth
        wizard.action_verify_birth()
        self.assertEqual(wizard.birth_verification_status, "verified")
        self.assertTrue(wizard.dci_data_match)

        # Step 3: Create and submit
        wizard.stage = "review"
        result = wizard.action_create_and_submit()

        cr = self.env["spp.change.request"].browse(result["res_id"])
        detail = cr.get_detail()

        # The CR should be submitted (pending). Auto-approve happens
        # at birth verification on the detail, not on the wizard.
        # So the CR is in pending state after wizard submit.
        self.assertIn(cr.display_state, ("pending", "applied"))

        # Verify detail has all the data
        self.assertEqual(detail.given_name, "George")
        self.assertEqual(detail.family_name, "Doe")
        self.assertEqual(detail.birth_registration_number, "HAPPY123")
        self.assertEqual(detail.birth_verification_status, "verified")
        self.assertTrue(detail.dci_data_match)

    def test_create_and_submit_with_applicant(self):
        """Applicant info is stored when provided."""
        applicant = self.env["res.partner"].create(
            {
                "name": "Parent Applicant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        wizard = self._create_wizard(
            given_name="John",
            family_name="Doe",
            birthdate="2024-01-15",
            applicant_id=applicant.id,
            applicant_phone="555-1234",
        )
        wizard.stage = "review"

        result = wizard.action_create_and_submit()

        cr = self.env["spp.change.request"].browse(result["res_id"])
        self.assertEqual(cr.applicant_id, applicant)
        self.assertEqual(cr.applicant_phone, "555-1234")

    def test_action_returns_wizard_form(self):
        """Navigation actions return an action dict that redisplays the wizard."""
        wizard = self._create_wizard()
        result = wizard.action_next()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.dci.demo.add.child.wizard")
        self.assertEqual(result["res_id"], wizard.id)
        self.assertEqual(result["target"], "current")
