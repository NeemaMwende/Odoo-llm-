/** @odoo-module **/

import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";

/**
 * CopilotService
 *
 * A singleton OWL service registered in the global service registry.
 * It owns:
 *   - the open/closed state of the panel
 *   - the current session_id
 *   - the message list (local copy for rendering)
 *   - all RPC calls to /web/copilot/*
 *
 * Any component (the button, the panel) accesses this via:
 *   const copilot = useService("copilot");
 */

export const copilotService = {
    name: "copilot",
    dependencies: ["rpc", "action"],

    start(env, { rpc, action }) {
        const state = reactive({
            isOpen: false,
            isLoading: false,
            sessionId: null,
            messages: [],       // [{ role: 'user'|'assistant', content: '' }]
            currentContext: {}, // { model, res_id, view_type }
            error: null,
        });

        /**
         * Capture what page the user is currently on.
         * We read from the Odoo action service which holds the active controller.
         * Falls back to URL parsing if needed.
         */
        function captureContext() {
            const ctx = {};
            try {
                // Odoo 17 stores the current action controller in the action service
                const currentController = action.currentController;
                if (currentController) {
                    const actionDef = currentController.action;
                    if (actionDef) {
                        ctx.model = actionDef.res_model || null;
                        ctx.view_type = currentController.view?.type || null;
                    }
                    // For form views, res_id is in the props
                    const props = currentController.props;
                    if (props && props.resId) {
                        ctx.res_id = props.resId;
                    }
                }
            } catch (e) {
                // Graceful fallback: parse from URL
                const match = window.location.pathname.match(/\/(\d+)$/);
                if (match) ctx.res_id = parseInt(match[1]);
            }
            ctx.url = window.location.href;
            return ctx;
        }

        /**
         * Open the panel. If the context has changed (user navigated to a
         * different record), start a new session for that record.
         */
        async function open() {
            const ctx = captureContext();
            state.currentContext = ctx;
            state.isOpen = true;

            // If we already have a session for this exact record, keep using it.
            // Otherwise fetch/create one from the server.
            const contextChanged = (
                !state.sessionId ||
                ctx.model !== state.lastModel ||
                ctx.res_id !== state.lastResId
            );

            if (contextChanged) {
                state.isLoading = true;
                try {
                    const result = await rpc("/web/copilot/session", {
                        res_model: ctx.model || null,
                        res_id: ctx.res_id || null,
                    });
                    state.sessionId = result.session_id;
                    // Restore history from server (for page refresh persistence)
                    state.messages = result.history || [];
                    state.lastModel = ctx.model;
                    state.lastResId = ctx.res_id;
                } catch (e) {
                    state.error = "Could not connect to copilot backend.";
                    console.error("[Copilot] session init error:", e);
                } finally {
                    state.isLoading = false;
                }
            }
        }

        function close() {
            state.isOpen = false;
        }

        function toggle() {
            if (state.isOpen) {
                close();
            } else {
                open();
            }
        }

        /**
         * Send a user message.  Adds it to local state immediately (optimistic),
         * then POSTs to /web/copilot/chat and appends the assistant reply.
         */
        async function sendMessage(content) {
            if (!content.trim()) return;

            // Optimistic: show user message right away
            state.messages = [
                ...state.messages,
                { role: "user", content: content.trim() }
            ];
            state.isLoading = true;
            state.error = null;

            try {
                const result = await rpc("/web/copilot/chat", {
                    message: content.trim(),
                    session_id: state.sessionId,
                    context: state.currentContext,
                });
                state.sessionId = result.session_id;
                state.messages = [
                    ...state.messages,
                    { role: "assistant", content: result.reply }
                ];
            } catch (e) {
                state.error = "Request failed. Is Ollama running?";
                console.error("[Copilot] chat error:", e);
            } finally {
                state.isLoading = false;
            }
        }

        async function clearHistory() {
            if (!state.sessionId) return;
            try {
                await rpc("/web/copilot/clear", { session_id: state.sessionId });
                state.messages = [];
            } catch (e) {
                console.error("[Copilot] clear error:", e);
            }
        }

        return {
            state,
            open,
            close,
            toggle,
            sendMessage,
            clearHistory,
            captureContext,
        };
    },
};

registry.category("services").add("copilot", copilotService);