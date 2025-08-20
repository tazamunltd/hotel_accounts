/** @odoo-module **/
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

class DeleteWithNotification extends Component {
    setup() {
        this.notification = useService("notification");
        this.action = useService("action");
        this.rpc = useService("rpc"); // ✅ Odoo 17-compatible, returns a service object
        this.deleteReservations();
    }

    async deleteReservations() {
        const recordIds = this.props.action?.params?.record_ids || [];

        console.log("✅ Record IDs received:", recordIds);

        if (!recordIds.length) {
            this.notification.add("No records selected.", {
                type: "warning",
            });
            return;
        }

        try {
            
            await this.rpc('/delete_reservations', {
                record_ids: recordIds,
            });

            this.notification.add(_t("Reservation(s) deleted successfully!"), {
                type: "success",
                sticky: false,
            });

            this.action.doAction("hotel_management.room_booking_action", { clearBreadcrumbs: true });

        }
        catch (error) {
            console.error("❌ Delete failed:", error);

            // ✅ Extract exact validation message
            let message = "An unexpected error occurred.";

            if (error?.data?.message) {
                message = error.data.message;
            } else if (error?.message) {
                message = error.message;
            }

            // ✅ Show your custom message instead of generic "Failed"
            this.notification.add(message, {
                type: "danger",
                sticky: true,
            });
        }
            this.action.doAction("hotel_management.room_booking_action", {
                    clearBreadcrumbs: true,
                });


        // catch (error) {
        //     console.error("❌ Delete failed:", error);
        //     this.notification.add("Failed to delete reservation(s).", {
        //         type: "danger",
        //         sticky: true,
        //     });
        // }
    }
}

DeleteWithNotification.template = "hotel_management.DeleteWithNotification";

registry.category("actions").add("delete_with_notification_js", DeleteWithNotification);

