/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";

class ManualPostingController extends FormController {
    setup() {
    super.setup();
    const rpc = useService("rpc");

    const modelName = this.props?.model?.config?.modelName;
    const resId = this.props?.resId;

    if (modelName === "tz.manual.posting" && resId) {
        rpc.call("tz.manual.posting", "execute_on_form_open", [[resId]])
            .then(() => {
                console.log("Executed Python method on form open.");
            })
            .catch((err) => {
                console.error("RPC failed on form open:", err);
            });
        }
    }
}

registry.category("views").add("tz_manual_posting_form", {
    ...registry.category("views").get("form"),
    Controller: ManualPostingController,
});
