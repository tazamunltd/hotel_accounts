/** @odoo-module **/

import { systrayItems } from "@web/webclient/systray/systray_items";
import { Component, onMounted } from "@odoo/owl";

export class SystrayDate extends Component {
    setup() {
        this.systemDate = new Date().toLocaleDateString();
        setInterval(() => {
            this.systemDate = new Date().toLocaleDateString();
            this.render();
        }, 60000); // Update every minute
    }
}

SystrayDate.template = "custom_header_date.custom_systray_date";

// Register the component in the systray
systrayItems.push(SystrayDate);
