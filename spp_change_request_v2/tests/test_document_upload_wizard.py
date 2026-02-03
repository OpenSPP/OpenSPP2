import base64

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestDocumentUploadWizard(TransactionCase):
    """Tests for document upload wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wizard_model = cls.env["spp.cr.document.upload.wizard"]
        cls.cr_model = cls.env["spp.change.request"]
        cls.category_model = cls.env["spp.dms.category"]
        cls.file_model = cls.env["spp.dms.file"]
        cls.partner_model = cls.env["res.partner"]

        # Create test registrant
        cls.registrant = cls.partner_model.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create or find vocabulary for document types
        cls.vocab = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:cr_document_type")], limit=1
        )
        if not cls.vocab:
            cls.vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "CR Document Types",
                    "namespace_uri": "urn:openspp:vocab:cr_document_type",
                }
            )

        # Create document type vocabulary codes
        cls.doc_type_birth_cert = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.vocab.id),
                ("code", "=", "test_birth_certificate"),
            ],
            limit=1,
        )
        if not cls.doc_type_birth_cert:
            cls.doc_type_birth_cert = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.vocab.id,
                    "code": "test_birth_certificate",
                    "display": "Birth Certificate",
                }
            )

        cls.doc_type_id_card = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.vocab.id),
                ("code", "=", "test_id_card"),
            ],
            limit=1,
        )
        if not cls.doc_type_id_card:
            cls.doc_type_id_card = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.vocab.id,
                    "code": "test_id_card",
                    "display": "ID Card",
                }
            )

        # Keep category references for backward compatibility tests
        cls.category_birth_cert = cls.category_model.create({"name": "Birth Certificate"})
        cls.category_id_card = cls.category_model.create({"name": "ID Card"})

        # Get CR type by code (may be in different module)
        cls.cr_type = cls.env["spp.change.request.type"].search([("code", "=", "edit_individual")], limit=1)
        if not cls.cr_type:
            # Create a minimal test type if not installed
            cls.cr_type = cls.env["spp.change.request.type"].create(
                {
                    "name": "Test Edit Individual",
                    "code": "test_edit_individual",
                    "target_type": "individual",
                    "detail_model": "spp.cr.detail.edit_individual",
                    "apply_strategy": "field_mapping",
                }
            )
        cls.cr_type.write(
            {
                "document_validation_mode": "required",
                "available_document_ids": [(6, 0, [cls.doc_type_birth_cert.id, cls.doc_type_id_card.id])],
                "required_document_ids": [(6, 0, [cls.doc_type_birth_cert.id, cls.doc_type_id_card.id])],
            }
        )

        # Create a change request
        cls.change_request = cls.cr_model.create(
            {
                "request_type_id": cls.cr_type.id,
                "registrant_id": cls.registrant.id,
            }
        )

        # Sample file content
        cls.file_content = base64.b64encode(b"Test file content")

    def test_01_wizard_creation(self):
        """Test creating the wizard."""
        wizard = self.wizard_model.create(
            {
                "change_request_id": self.change_request.id,
                "document_type_id": self.doc_type_birth_cert.id,
                "filename": "birth_cert.pdf",
                "content": self.file_content,
            }
        )
        self.assertTrue(wizard.id)
        self.assertEqual(wizard.change_request_id, self.change_request)
        self.assertEqual(wizard.directory_id, self.change_request.dms_directory_id)

    def test_02_category_domain_with_required(self):
        """Test category domain computation with required categories."""
        wizard = self.wizard_model.create(
            {
                "change_request_id": self.change_request.id,
                "document_type_id": self.doc_type_birth_cert.id,
                "filename": "test.pdf",
                "content": self.file_content,
            }
        )
        # Should show required categories
        self.assertTrue(wizard.show_required_categories)
        self.assertIn("Birth Certificate", wizard.required_categories_text)
        self.assertIn("ID Card", wizard.required_categories_text)

    def test_03_upload_document(self):
        """Test uploading a document."""
        initial_doc_count = len(self.change_request.document_ids)

        wizard = self.wizard_model.create(
            {
                "change_request_id": self.change_request.id,
                "document_type_id": self.doc_type_birth_cert.id,
                "filename": "birth_cert.pdf",
                "content": self.file_content,
            }
        )
        result = wizard.action_upload()

        # Verify notification returned
        self.assertEqual(result.get("type"), "ir.actions.client")

        # Verify document was created
        self.assertEqual(len(self.change_request.document_ids), initial_doc_count + 1)

        # Verify document properties
        uploaded_doc = self.change_request.document_ids[-1]
        self.assertEqual(uploaded_doc.name, "birth_cert.pdf")
        self.assertEqual(uploaded_doc.document_type_id, self.doc_type_birth_cert)
        self.assertEqual(uploaded_doc.directory_id, self.change_request.dms_directory_id)

    def test_04_upload_multiple_documents(self):
        """Test uploading multiple documents with different types."""
        # Upload first document
        wizard1 = self.wizard_model.create(
            {
                "change_request_id": self.change_request.id,
                "document_type_id": self.doc_type_birth_cert.id,
                "filename": "birth_cert.pdf",
                "content": self.file_content,
            }
        )
        wizard1.action_upload()

        # Upload second document
        wizard2 = self.wizard_model.create(
            {
                "change_request_id": self.change_request.id,
                "document_type_id": self.doc_type_id_card.id,
                "filename": "id_card.jpg",
                "content": self.file_content,
            }
        )
        wizard2.action_upload()

        # Verify both documents exist
        self.assertGreaterEqual(len(self.change_request.document_ids), 2)

        # Verify document types
        doc_types = self.change_request.document_ids.mapped("document_type_id")
        self.assertIn(self.doc_type_birth_cert, doc_types)
        self.assertIn(self.doc_type_id_card, doc_types)

    def test_05_upload_without_directory_fails(self):
        """Test that upload fails if CR has no directory."""
        # Create CR without directory
        cr_no_dir = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )
        # Remove the directory (must clear FK reference before deleting)
        if cr_no_dir.dms_directory_id:
            directory = cr_no_dir.dms_directory_id
            cr_no_dir.dms_directory_id = False
            directory.unlink()

        wizard = self.wizard_model.create(
            {
                "change_request_id": cr_no_dir.id,
                "document_type_id": self.doc_type_birth_cert.id,
                "filename": "test.pdf",
                "content": self.file_content,
            }
        )

        with self.assertRaises(UserError):
            wizard.action_upload()

    def test_06_action_upload_document_from_cr(self):
        """Test opening upload wizard from change request."""
        action = self.change_request.action_upload_document()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.cr.document.upload.wizard")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_change_request_id"], self.change_request.id)

    def test_07_document_type_domain_without_required(self):
        """Test document type domain when no required document types."""
        # Create CR type without required document types
        cr_type_no_req = self.env["spp.change.request.type"].create(
            {
                "name": "Test Type No Req",
                "code": "test_no_req",
                "detail_model": "spp.cr.detail.edit_individual",
                "document_validation_mode": "none",
            }
        )

        cr = self.cr_model.create(
            {
                "request_type_id": cr_type_no_req.id,
                "registrant_id": self.registrant.id,
            }
        )

        wizard = self.wizard_model.create(
            {
                "change_request_id": cr.id,
                "document_type_id": self.doc_type_birth_cert.id,
                "filename": "test.pdf",
                "content": self.file_content,
            }
        )

        # Should not show required categories
        self.assertFalse(wizard.show_required_categories)
        # Domain should allow all document types from the vocabulary
        expected_domain = "[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:cr_document_type')]"
        self.assertEqual(wizard.document_type_domain, expected_domain)
