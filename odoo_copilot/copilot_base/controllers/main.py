import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class CopilotController(http.Controller):
    """
    JSON-RPC endpoints consumed by the OWL frontend.

    FLOW when a user sends a message:
    1.  JS sends POST /web/copilot/chat with:
            { message, session_id, context: {model, res_id, view_type} }
    2.  _get_or_create_session() finds/creates the copilot.session record
    3.  _build_context() fetches the live record fields and builds a summary
    4.  Provider._chat(messages, context) is called → Ollama → response string
    5.  Both user msg + assistant reply are saved as copilot.message records
    6.  Response returned to JS as { reply, session_id }

    RAG slot: step 3 is where copilot_rag would intercept — it performs a
    vector similarity search on the user's message, retrieves matching chunks,
    and appends them to the context dict before the LLM call.
    """

    @http.route('/web/copilot/session', type='json', auth='user', methods=['POST'])
    def get_session(self, res_model=None, res_id=None, **kwargs):
        """
        Called when the panel opens.  Returns (or creates) the session for
        the current user + page.  The JS stores session_id and passes it
        on subsequent /chat calls.
        """
        session = request.env['copilot.session'].get_or_create_session(
            res_model=res_model,
            res_id=int(res_id) if res_id else None,
        )
        messages = session.get_messages_for_llm()
        return {
            'session_id': session.id,
            'history': [
                {'role': m['role'], 'content': m['content']}
                for m in messages
            ],
        }

    @http.route('/web/copilot/chat', type='json', auth='user', methods=['POST'])
    def chat(self, message, session_id=None, context=None, **kwargs):
        """
        Main chat endpoint.  Accepts a user message and returns the AI reply.

        `context` is a dict sent from the JS:
            {
              'model':     'sale.order',
              'res_id':    78,
              'view_type': 'form',
              'url':       '/odoo/sales/78',
            }
        """
        env = request.env
        context = context or {}

        # 1. Resolve session
        if session_id:
            session = env['copilot.session'].browse(int(session_id))
            if not session.exists() or session.user_id.id != env.uid:
                session = env['copilot.session'].get_or_create_session(
                    res_model=context.get('model'),
                    res_id=context.get('res_id'),
                )
        else:
            session = env['copilot.session'].get_or_create_session(
                res_model=context.get('model'),
                res_id=context.get('res_id'),
            )

        # 2. Save user message
        env['copilot.message'].create({
            'session_id': session.id,
            'role': 'user',
            'content': message,
        })

        # 3. Build enriched context (fetch live record fields)
        enriched_context = self._build_record_context(context)

        # === RAG HOOK ===
        # If copilot_rag is installed, it overrides _build_record_context()
        # or adds a separate _retrieve_rag_chunks() call here that appends
        # relevant document chunks to enriched_context['rag_chunks'].
        # The provider then includes those chunks in the system prompt.
        # ================

        # 4. Get message history (trimmed to max_history setting)
        max_history = int(env['ir.config_parameter'].sudo().get_param(
            'copilot.max_history', default=20
        ))
        messages = session.get_messages_for_llm()[-max_history:]

        # 5. Call the provider
        try:
            provider = env['copilot.provider'].get_active_provider()
            reply = provider._chat(messages=messages, context=enriched_context)
        except Exception as e:
            _logger.exception("Copilot provider error")
            reply = f"Sorry, I encountered an error: {str(e)}"

        # 6. Save assistant reply
        env['copilot.message'].create({
            'session_id': session.id,
            'role': 'assistant',
            'content': reply,
        })

        return {
            'reply': reply,
            'session_id': session.id,
        }

    @http.route('/web/copilot/clear', type='json', auth='user', methods=['POST'])
    def clear_session(self, session_id, **kwargs):
        """Clear message history for a session (user hits 'New chat')."""
        session = request.env['copilot.session'].browse(int(session_id))
        if session.exists() and session.user_id.id == request.env.uid:
            session.clear_history()
        return {'ok': True}

    def _build_record_context(self, context):
        """
        Given the page context from JS, fetch the actual record from the DB
        and build a human-readable summary to inject into the system prompt.

        This is the CONTEXT ENRICHMENT step — it's what makes the copilot
        aware of what the user is looking at.

        Returns a dict like:
            {
              'model': 'sale.order',
              'res_id': 78,
              'view_type': 'form',
              'record_summary': 'Sale Order S00078\nCustomer: Joel Willis\n...',
            }
        """
        enriched = dict(context)
        res_model = context.get('model')
        res_id = context.get('res_id')

        if not res_model or not res_id:
            return enriched

        try:
            record = request.env[res_model].browse(int(res_id))
            if not record.exists():
                return enriched

            # Build a text summary of the record's key fields
            summary_lines = [f"Record: {record.display_name}"]

            # Read all stored, non-binary, non-technical fields
            fields_info = record.fields_get()
            readable_types = {
                'char', 'text', 'integer', 'float', 'monetary',
                'date', 'datetime', 'boolean', 'selection', 'many2one',
            }
            field_names = [
                fname for fname, finfo in fields_info.items()
                if finfo.get('type') in readable_types
                and not fname.startswith('_')
                and fname not in ('create_uid', 'write_uid', '__last_update')
            ][:40]  # cap at 40 fields to avoid token bloat

            values = record.read(field_names)[0]
            for fname in field_names:
                val = values.get(fname)
                if val is None or val is False:
                    continue
                label = fields_info[fname].get('string', fname)
                # Many2one fields come back as (id, name) tuples
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    val = val[1]
                summary_lines.append(f"{label}: {val}")

            enriched['record_summary'] = '\n'.join(summary_lines)

        except Exception as e:
            _logger.warning("Could not build record context for %s#%s: %s",
                            res_model, res_id, e)

        return enriched