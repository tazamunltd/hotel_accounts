/** @odoo-module **/

import { registry } from "@web/core/registry";
import { CompanyService } from "@web/webclient/company/company_service";
import { browser } from "@web/core/browser/browser";

const CompanySwitcherCheckout = {
    start() {
        const companyService = registry.category("services").get("company");
        this.companyChangedListener = companyService.on("COMPANY_CHANGED", this, this._onCompanyChanged);
    },

    _onCompanyChanged: async function() {
        // Only refresh if the current action is related to tz.checkout
        const currentAction = this.env.services.action.currentAction;
        if (currentAction && currentAction.res_model === 'tz.checkout') {
            await this.env.services.rpc("/web/dataset/call_kw/tz.checkout/action_refresh_checkout_view", {
                model: 'tz.checkout',
                method: 'action_refresh_checkout_view',
                args: [],
                kwargs: {},
            });
            // Reload the current view to reflect the changes
            this.env.services.action.doAction(currentAction, { replace: true });
        }
    },

    destroy() {
        if (this.companyChangedListener) {
            this.companyChangedListener(); // Unsubscribe
        }
    }
};

registry.category("web_client_components").add("CompanySwitcherCheckout", CompanySwitcherCheckout);