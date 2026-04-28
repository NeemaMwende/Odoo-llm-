from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    copilot_provider_type = fields.Selection([
        ('ollama', 'Ollama (local)'),
        ('openai', 'OpenAI'),
    ], string='Copilot Provider',
       config_parameter='copilot.provider_type',
       default='ollama')

    copilot_system_prompt = fields.Text(
        string='System Prompt',
        config_parameter='copilot.system_prompt',
        default=(
            "You are a helpful AI copilot integrated into Odoo ERP. "
            "Answer questions about the current page, records, and business data. "
            "Be concise and precise."
        )
    )

    copilot_max_history = fields.Integer(
        string='Max History Messages',
        config_parameter='copilot.max_history',
        default=20,
        help="Maximum number of past messages to include per LLM call"
    )