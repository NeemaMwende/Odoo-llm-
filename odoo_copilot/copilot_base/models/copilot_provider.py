from odoo import models, fields, api
from odoo.exceptions import UserError


class CopilotProvider(models.AbstractModel):
    """
    Abstract base for all copilot AI providers.
    Concrete providers (e.g. copilot_ollama) inherit this and override _chat().

    The only method you MUST implement in a subclass is _chat(messages, context).
    Everything else (session management, context building) lives here or in the
    controller.
    """
    _name = 'copilot.provider'
    _description = 'Copilot AI Provider (abstract)'

    _provider_type = None

    @api.model
    def get_active_provider(self):
        """
        Return whichever concrete provider record is configured and active.
        Providers store their config in ir.config_parameter (via res.config.settings).
        """
        provider_type = self.env['ir.config_parameter'].sudo().get_param(
            'copilot.provider_type', default='ollama'
        )
        # Each provider module registers itself under its _provider_type name.
        # We find the right model by searching registered subclasses.
        for model_name in self.env:
            model = self.env[model_name]
            if (
                hasattr(model, '_provider_type')
                and model._provider_type == provider_type
                and not model._abstract
            ):
                return model
        raise UserError(
            f"No copilot provider found for type '{provider_type}'. "
            "Please install a provider module (e.g. copilot_ollama) and configure it."
        )

    def _chat(self, messages, context=None):
        """
        Override in subclass. Must return a string (the assistant reply).

        Args:
            messages: list of dicts [{'role': 'user'|'assistant'|'system', 'content': str}]
            context:  dict with page context, e.g.:
                      {'model': 'sale.order', 'res_id': 78, 'record_summary': '...'}
        Returns:
            str: the LLM's response text
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _chat(messages, context)"
        )

    def _build_system_prompt(self, context=None):
        """
        Build the system prompt. Includes the base instruction plus any
        record context injected by copilot_context (if installed).
        """
        base_prompt = self.env['ir.config_parameter'].sudo().get_param(
            'copilot.system_prompt',
            default=(
                "You are a helpful AI copilot integrated into Odoo ERP. "
                "You have access to information about the current page the user is viewing. "
                "Be concise, accurate, and helpful. When you reference data, "
                "be specific about field names and values."
            )
        )

        if context and context.get('record_summary'):
            base_prompt += (
                f"\n\nThe user is currently viewing:\n{context['record_summary']}"
            )

        if context and context.get('model'):
            base_prompt += (
                f"\n\nCurrent Odoo model: {context['model']}"
            )
            if context.get('view_type'):
                base_prompt += f" ({context['view_type']} view)"

        return base_prompt