from odoo import models, fields, api


class CopilotSession(models.Model):
    """
    One session = one conversation thread.
    Tied to a user + optionally a specific Odoo record (res_model + res_id).
    When the user opens the copilot on Sales Order 78, we find or create a
    session for uid=X, res_model='sale.order', res_id=78.
    """
    _name = 'copilot.session'
    _description = 'Copilot Chat Session'
    _order = 'write_date desc'

    name = fields.Char(
        compute='_compute_name', store=True,
        help="Auto-generated display name"
    )
    user_id = fields.Many2one(
        'res.users', string='User',
        default=lambda self: self.env.user,
        required=True, ondelete='cascade', index=True
    )
    # The Odoo record this session is about (optional — can be a global session)
    res_model = fields.Char(string='Model', index=True)
    res_id = fields.Integer(string='Record ID', index=True)
    res_name = fields.Char(
        string='Record Name',
        help="Cached display name of the linked record"
    )

    message_ids = fields.One2many(
        'copilot.message', 'session_id',
        string='Messages'
    )
    message_count = fields.Integer(
        compute='_compute_message_count', string='Messages'
    )
    active = fields.Boolean(default=True)

    @api.depends('res_model', 'res_id', 'res_name', 'user_id')
    def _compute_name(self):
        for rec in self:
            if rec.res_name:
                rec.name = f"{rec.res_name} — {rec.user_id.name}"
            elif rec.res_model:
                rec.name = f"{rec.res_model}#{rec.res_id} — {rec.user_id.name}"
            else:
                rec.name = f"Global — {rec.user_id.name}"

    @api.depends('message_ids')
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)

    @api.model
    def get_or_create_session(self, res_model=None, res_id=None):
        """
        Find an existing open session for the current user + record,
        or create a fresh one. Called by the controller on every page load.
        """
        domain = [('user_id', '=', self.env.uid)]
        if res_model:
            domain += [('res_model', '=', res_model), ('res_id', '=', res_id or 0)]
        else:
            domain += [('res_model', '=', False)]

        session = self.search(domain, limit=1, order='write_date desc')
        if not session:
            vals = {'user_id': self.env.uid}
            if res_model:
                vals['res_model'] = res_model
                vals['res_id'] = res_id or 0
                # Try to resolve the display name
                if res_model and res_id:
                    try:
                        record = self.env[res_model].browse(res_id)
                        vals['res_name'] = record.display_name
                    except Exception:
                        pass
            session = self.create(vals)
        return session

    def get_messages_for_llm(self):
        """
        Return message history formatted for the LLM API:
        [{'role': 'user'|'assistant', 'content': '...'}]
        Excludes system messages (those are added fresh each call).
        """
        self.ensure_one()
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in self.message_ids.filtered(
                lambda m: m.role in ('user', 'assistant')
            ).sorted('create_date')
        ]

    def clear_history(self):
        """Delete all messages in this session (start fresh)."""
        self.ensure_one()
        self.message_ids.unlink()
        return True