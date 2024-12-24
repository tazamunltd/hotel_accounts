/** @odoo-module **/

import { registry } from "@web/core/registry";
import { AbstractField } from "@web/views/fields/abstract_field/abstract_field";

class PercentageWidget extends AbstractField {
    supportedTypes = ["float"];

    setup() {
        super.setup();
    }

    _render() {
        const value = this.props.value || 0;
        const isPercentage = this.props.record.data.room_is_percentage;
        this.el.textContent = isPercentage ? `${value}%` : `${value}`;
    }
}

registry.category("fields").add("percentage_widget", PercentageWidget);
