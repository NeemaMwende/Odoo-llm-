/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * CopilotButton
 *
 * The icon that lives in the Odoo top navbar systray (top-right icon area).
 * Clicking it opens/closes the copilot panel.
 *
 * Registered in the systray registry with sequence=1 so it sits near the
 * right side of the systray.
 */
export class CopilotButton extends Component {
    static template = "copilot_base.CopilotButton";
    static props = {};

    setup() {
        this.copilot = useService("copilot");
    }

    get isOpen() {
        return this.copilot.state.isOpen;
    }

    onClick() {
        this.copilot.toggle();
    }
}

// Register in systray — this is what puts it in the navbar
registry.category("systray").add("copilot_base.CopilotButton", {
    Component: CopilotButton,
    sequence: 1,
});