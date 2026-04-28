/** @odoo-module **/

import { Component, useState, useRef, onMounted, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * CopilotPanel
 *
 * The floating chat window that slides up from the bottom-right.
 * It renders messages, an input box, a send button, and a clear button.
 *
 * This component is injected into the web client's main layout via the
 * "main_components" registry — it's always in the DOM but hidden via CSS
 * when isOpen=false.
 */
export class CopilotPanel extends Component {
    static template = "copilot_base.CopilotPanel";
    static props = {};

    setup() {
        this.copilot = useService("copilot");
        this.inputRef = useRef("messageInput");
        this.messagesRef = useRef("messagesList");

        // Scroll to bottom whenever messages change
        onPatched(() => {
            this._scrollToBottom();
        });
    }

    get state() {
        return this.copilot.state;
    }

    get isOpen() {
        return this.copilot.state.isOpen;
    }

    get messages() {
        return this.copilot.state.messages;
    }

    get isLoading() {
        return this.copilot.state.isLoading;
    }

    get error() {
        return this.copilot.state.error;
    }

    get contextLabel() {
        const ctx = this.copilot.state.currentContext;
        if (ctx.model && ctx.res_id) {
            // Convert 'sale.order' → 'Sale Order'
            const modelLabel = ctx.model
                .split('.')
                .map(p => p.charAt(0).toUpperCase() + p.slice(1))
                .join(' ');
            return `${modelLabel} #${ctx.res_id}`;
        }
        if (ctx.model) {
            return ctx.model.split('.').map(p =>
                p.charAt(0).toUpperCase() + p.slice(1)
            ).join(' ');
        }
        return 'Global';
    }

    onClose() {
        this.copilot.close();
    }

    onClear() {
        this.copilot.clearHistory();
    }

    async onSend() {
        const input = this.inputRef.el;
        if (!input) return;
        const content = input.value.trim();
        if (!content || this.isLoading) return;
        input.value = '';
        input.style.height = 'auto';
        await this.copilot.sendMessage(content);
    }

    onKeyDown(ev) {
        // Send on Enter, new line on Shift+Enter
        if (ev.key === 'Enter' && !ev.shiftKey) {
            ev.preventDefault();
            this.onSend();
        }
    }

    onInputResize(ev) {
        // Auto-grow textarea
        const el = ev.target;
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    }

    _scrollToBottom() {
        const el = this.messagesRef.el;
        if (el) {
            el.scrollTop = el.scrollHeight;
        }
    }

    /**
     * Markdown-lite renderer for assistant messages.
     * Handles **bold**, `code`, and code blocks.
     * In production you'd use a proper markdown lib.
     */
    formatMessage(content) {
        if (!content) return '';
        return content
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            // code blocks ```...```
            .replace(/```([\s\S]*?)```/g, '<pre class="cop-code-block">$1</pre>')
            // inline code `...`
            .replace(/`([^`]+)`/g, '<code class="cop-inline-code">$1</code>')
            // **bold**
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            // newlines
            .replace(/\n/g, '<br>');
    }
}

// Register as a main component — always present in the DOM
registry.category("main_components").add("copilot_base.CopilotPanel", {
    Component: CopilotPanel,
    props: {},
});