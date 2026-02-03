from odoo import models


class SPPCRStrategyBase(models.AbstractModel):
    """Base class for CR apply strategies."""

    _name = "spp.cr.strategy.base"
    _description = "CR Apply Strategy Base"

    def apply(self, change_request):
        """Apply the change request to the registrant.

        Override in subclasses to implement specific apply logic.

        Args:
            change_request: The spp.change.request record to apply

        Returns:
            True on success

        Raises:
            UserError: If apply fails
        """
        raise NotImplementedError("Subclasses must implement apply()")

    def preview(self, change_request):
        """Preview changes that would be applied.

        Returns a dict of field changes:
        {
            'field_name': {
                'old': current_value,
                'new': new_value,
            },
            ...
        }
        """
        return {}

    def validate(self, change_request):
        """Validate the change request before apply.

        Override to add custom validation logic.

        Raises:
            ValidationError: If validation fails
        """
        pass
