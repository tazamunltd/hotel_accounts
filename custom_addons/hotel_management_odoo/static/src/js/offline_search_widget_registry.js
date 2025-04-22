/** @odoo-module **/

/**
 * Offline Search Widget Registry
 * @date 2025-01-08T23:02:44+05:00
 */

import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { OfflineSearchWidget } from "./offline_search_widget";

// Setup widget props
OfflineSearchWidget.props = {
    ...standardWidgetProps
};

// Register the widget in the view_widgets registry (Odoo 17)
registry.category("view_widgets").add("offline_search_widget", {
    component: OfflineSearchWidget,
    extractProps: ({ attrs }) => ({
        readonly: attrs.readonly === "true",
        ...attrs
    }),
});

