from odoo import models, fields


class CopilotMessage(models.Model):
    """
    A single message in a copilot session.
    role: 'user' | 'assistant' | 'system'
    """
    _name = 'copilot.message'
    _description = 'Copilot Message'
    _order = 'create_date asc, id asc'

    session_id = fields.Many2one(
        'copilot.session', string='Session',
        required=True, ondelete='cascade', index=True
    )
    role = fields.Selection([
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ], required=True, default='user')

    content = fields.Text(required=True)

    # RAG metadata — populated by copilot_rag if installed
    rag_sources = fields.Text(
        string='RAG Sources (JSON)',
        help="JSON list of document chunks used to answer this message"
    )