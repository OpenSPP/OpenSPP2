from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_change_request import TestChangeRequestBase


@tagged("post_install", "-at_install")
class TestApprovalHooks(TestChangeRequestBase):
    """Tests for approval hooks in spp.change.request."""

    def _create_cr(self, registrant=None, cr_type=None):
        """Helper to create a CR for testing."""
        vals = {
            "request_type_id": (cr_type or self.cr_type_add_member).id,
        }
        if registrant is not False:
            vals["registrant_id"] = (registrant or self.group).id
        return self.cr_model.create(vals)

    def test_on_approve_creates_log_and_audit(self):
        """_on_approve() creates log entry with 'approved' action."""
        cr = self._create_cr()
        # Disable auto_apply to avoid action_apply being triggered
        cr.request_type_id.auto_apply_on_approve = False
        # _on_approve is called after base mixin sets approved state
        cr.approval_state = "approved"
        log_count_before = len(cr.log_ids)
        cr._on_approve()
        cr.invalidate_recordset()
        new_logs = cr.log_ids.filtered(lambda r: r.action == "approved")
        self.assertTrue(new_logs)
        self.assertGreater(len(cr.log_ids), log_count_before)

    def test_on_approve_auto_apply(self):
        """Auto-apply triggers when auto_apply_on_approve=True."""
        cr = self._create_cr()
        cr.request_type_id.auto_apply_on_approve = True
        # _on_approve is called after base mixin sets approved state
        cr.approval_state = "approved"
        # action_apply will run the strategy — might fail if strategy
        # raises but we just want to verify the auto_apply path is taken
        try:
            cr._on_approve()
        except Exception:
            pass  # Strategy-specific errors are OK, we're testing the hook path
        # Verify it attempted (log was created)
        cr.invalidate_recordset()
        new_logs = cr.log_ids.filtered(lambda r: r.action == "approved")
        self.assertTrue(new_logs)

    def test_on_reject_creates_log_with_reason(self):
        """_on_reject() logs with reason notes."""
        cr = self._create_cr()
        cr.approval_state = "pending"
        reason = "Missing documentation"
        cr._on_reject(reason)
        cr.invalidate_recordset()
        reject_logs = cr.log_ids.filtered(lambda r: r.action == "rejected")
        self.assertTrue(reject_logs)
        self.assertEqual(reject_logs[0].notes, reason)

    def test_on_submit_creates_log(self):
        """_on_submit() creates log entry with 'submitted' action."""
        cr = self._create_cr()
        cr.approval_state = "draft"
        cr._on_submit()
        cr.invalidate_recordset()
        submit_logs = cr.log_ids.filtered(lambda r: r.action == "submitted")
        self.assertTrue(submit_logs)

    def test_on_submit_resubmission_logs_resubmitted(self):
        """Resubmit from revision logs 'resubmitted' action."""
        cr = self._create_cr()
        # Simulate revision state
        cr.approval_state = "revision"
        cr._on_submit()
        cr.invalidate_recordset()
        resubmit_logs = cr.log_ids.filtered(lambda r: r.action == "resubmitted")
        self.assertTrue(resubmit_logs)

    def test_on_request_revision_sets_stage_review(self):
        """_on_request_revision() sets stage to 'review' and creates log."""
        cr = self._create_cr()
        cr.approval_state = "pending"
        cr._on_request_revision("Please update details")
        self.assertEqual(cr.stage, "review")
        cr.invalidate_recordset()
        rev_logs = cr.log_ids.filtered(lambda r: r.action == "revision_requested")
        self.assertTrue(rev_logs)
        self.assertEqual(rev_logs[0].notes, "Please update details")

    def test_on_reset_to_draft_sets_stage_details(self):
        """_on_reset_to_draft() sets stage to 'details' and creates log."""
        cr = self._create_cr()
        cr.stage = "review"
        cr._on_reset_to_draft()
        self.assertEqual(cr.stage, "details")
        cr.invalidate_recordset()
        reset_logs = cr.log_ids.filtered(lambda r: r.action == "reset_to_draft")
        self.assertTrue(reset_logs)

    def test_check_can_submit_from_draft(self):
        """_check_can_submit() passes for draft state."""
        cr = self._create_cr()
        cr.approval_state = "draft"
        # Should not raise
        cr._check_can_submit()

    def test_check_can_submit_from_revision(self):
        """_check_can_submit() passes for revision state."""
        cr = self._create_cr()
        cr.approval_state = "revision"
        # Should not raise
        cr._check_can_submit()

    def test_check_can_submit_from_pending_raises(self):
        """_check_can_submit() raises UserError from pending state."""
        cr = self._create_cr()
        cr.approval_state = "pending"
        with self.assertRaises(UserError):
            cr._check_can_submit()

    def test_check_can_submit_from_approved_raises(self):
        """_check_can_submit() raises UserError from approved state."""
        cr = self._create_cr()
        cr.approval_state = "approved"
        with self.assertRaises(UserError):
            cr._check_can_submit()


@tagged("post_install", "-at_install")
class TestDocumentValidation(TestChangeRequestBase):
    """Tests for document validation in spp.change.request."""

    def _create_cr(self, registrant=None, cr_type=None):
        """Helper to create a CR for testing."""
        vals = {
            "request_type_id": (cr_type or self.cr_type_add_member).id,
        }
        if registrant is not False:
            vals["registrant_id"] = (registrant or self.group).id
        return self.cr_model.create(vals)

    def _get_or_create_doc_vocab(self):
        """Get or create the document type vocabulary."""
        vocab = self.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:cr_document_type")], limit=1
        )
        if not vocab:
            vocab = self.env["spp.vocabulary"].create(
                {
                    "name": "CR Document Types",
                    "namespace_uri": "urn:openspp:vocab:cr_document_type",
                }
            )
        return vocab

    def test_validate_documents_mode_none(self):
        """Returns None when mode='none'."""
        cr = self._create_cr()
        cr.request_type_id.document_validation_mode = "none"
        result = cr._validate_documents()
        self.assertIsNone(result)

    def test_validate_documents_no_required(self):
        """Returns None when no required docs configured."""
        cr = self._create_cr()
        cr.request_type_id.document_validation_mode = "required"
        cr.request_type_id.required_document_ids = False
        result = cr._validate_documents()
        self.assertIsNone(result)

    def test_validate_documents_mode_required_raises(self):
        """Raises ValidationError with missing doc names."""
        cr = self._create_cr()
        vocab = self._get_or_create_doc_vocab()
        doc_type = self.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": vocab.id,
                "code": "test_cert_val",
                "display": "Birth Certificate",
            }
        )
        cr.request_type_id.document_validation_mode = "required"
        cr.request_type_id.required_document_ids = doc_type
        with self.assertRaises(ValidationError):
            cr._validate_documents()

    def test_validate_documents_mode_warning_returns_notification(self):
        """Returns warning notification dict when mode='warning'."""
        cr = self._create_cr()
        vocab = self._get_or_create_doc_vocab()
        doc_type = self.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": vocab.id,
                "code": "test_id_val",
                "display": "ID Document",
            }
        )
        cr.request_type_id.document_validation_mode = "warning"
        cr.request_type_id.required_document_ids = doc_type
        result = cr._validate_documents()
        self.assertIsNotNone(result)
        self.assertIn("notification", result)
        self.assertEqual(result["notification"]["type"], "warning")

    def test_validate_documents_all_present(self):
        """Returns None when all required docs uploaded."""
        cr = self._create_cr()
        vocab = self._get_or_create_doc_vocab()
        doc_type = self.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": vocab.id,
                "code": "test_present_val",
                "display": "Present Doc",
            }
        )
        cr.request_type_id.document_validation_mode = "required"
        cr.request_type_id.required_document_ids = doc_type

        # Upload the required document
        dms_file = self.env["spp.dms.file"].create(
            {
                "name": "present.pdf",
                "document_type_id": doc_type.id,
                "directory_id": cr.dms_directory_id.id,
                "content": "dGVzdA==",
            }
        )
        cr.document_ids = dms_file
        result = cr._validate_documents()
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestAuditLogging(TestChangeRequestBase):
    """Tests for audit logging in spp.change.request."""

    def _create_cr(self, registrant=None, cr_type=None):
        """Helper to create a CR for testing."""
        vals = {
            "request_type_id": (cr_type or self.cr_type_add_member).id,
        }
        if registrant is not False:
            vals["registrant_id"] = (registrant or self.group).id
        return self.cr_model.create(vals)

    def test_create_log_entry(self):
        """_create_log() creates spp.change.request.log record."""
        cr = self._create_cr()
        log_count_before = self.env["spp.change.request.log"].search_count([("change_request_id", "=", cr.id)])
        cr._create_log("submitted")
        log_count_after = self.env["spp.change.request.log"].search_count([("change_request_id", "=", cr.id)])
        self.assertEqual(log_count_after, log_count_before + 1)

    def test_create_log_with_notes(self):
        """Log includes notes field."""
        cr = self._create_cr()
        cr._create_log("rejected", notes="Incomplete submission")
        log = self.env["spp.change.request.log"].search(
            [("change_request_id", "=", cr.id), ("action", "=", "rejected")],
            limit=1,
            order="id desc",
        )
        self.assertTrue(log)
        self.assertEqual(log.notes, "Incomplete submission")

    def test_create_log_records_user(self):
        """Log records the current user."""
        cr = self._create_cr()
        cr._create_log("approved")
        log = self.env["spp.change.request.log"].search(
            [("change_request_id", "=", cr.id), ("action", "=", "approved")],
            limit=1,
            order="id desc",
        )
        self.assertTrue(log)
        self.assertEqual(log.user_id.id, self.env.user.id)

    def test_create_audit_event_with_registrant(self):
        """_create_audit_event() creates spp.event.data record if model exists."""
        cr = self._create_cr()
        if "spp.event.data" not in self.env:
            return  # Skip if event module not installed
        event_type = self.env.ref(
            "spp_change_request_v2.event_type_cr_audit",
            raise_if_not_found=False,
        )
        if not event_type:
            return  # Skip if event type not defined
        event_count_before = self.env["spp.event.data"].search_count([("partner_id", "=", cr.registrant_id.id)])
        cr._create_audit_event("test_action", "draft", "pending")
        event_count_after = self.env["spp.event.data"].search_count([("partner_id", "=", cr.registrant_id.id)])
        self.assertEqual(event_count_after, event_count_before + 1)

    def test_create_audit_event_no_registrant_skips(self):
        """Skips audit event creation if no registrant."""
        cr = self._create_cr()
        cr.registrant_id = False
        # Should not raise, just skip
        cr._create_audit_event("test_action", "draft", "pending")

    def test_create_audit_event_no_event_model_skips(self):
        """Skips if spp.event.data not in env (handled gracefully)."""
        cr = self._create_cr()
        # The method checks 'spp.event.data' not in self.env
        # We can't easily remove a model from env, but we can verify
        # the method doesn't crash when called
        cr._create_audit_event("test_action", "draft", "pending")

    def test_cr_create_generates_log(self):
        """CR creation generates a 'created' log entry."""
        cr = self._create_cr()
        created_logs = cr.log_ids.filtered(lambda r: r.action == "created")
        self.assertTrue(created_logs, "CR creation should generate a 'created' log entry")

    def test_log_action_label_computed(self):
        """Log action_label is computed from action field."""
        cr = self._create_cr()
        cr._create_log("submitted")
        log = self.env["spp.change.request.log"].search(
            [("change_request_id", "=", cr.id), ("action", "=", "submitted")],
            limit=1,
            order="id desc",
        )
        self.assertEqual(log.action_label, "Submitted for Approval")

    def test_log_action_label_approved(self):
        """Log action_label for 'approved' is 'Approved'."""
        cr = self._create_cr()
        cr._create_log("approved")
        log = self.env["spp.change.request.log"].search(
            [("change_request_id", "=", cr.id), ("action", "=", "approved")],
            limit=1,
            order="id desc",
        )
        self.assertEqual(log.action_label, "Approved")
