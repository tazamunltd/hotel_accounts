/** @odoo-module **/

import { registry } from "@web/core/registry";
import { OfflineSearchWidget } from "./offline_search_widget";

// Register the widget in the field registry
registry.category("view_widgets").add("offline_search_widget", {
    component: OfflineSearchWidget,
    supportedTypes: ["form"],
});
