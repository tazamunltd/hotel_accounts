/** @odoo-module */
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

export class ReservationDashBoard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dashboardData = useState({
            today_checkin: 0,
            today_checkout: 0,
            not_confirm: 0,
            confirmed: 0,
            waiting: 0,
            blocked: 0,
            cancelled: 0,
            checkin: 0,
            checkout: 0
        });

        onWillStart(async () => {
            const data = await this.orm.call("room.booking", "retrieve_dashboard");
            Object.assign(this.dashboardData, data);
        });
    }

    async setSearchContext(ev) {
        const filter_name = ev.currentTarget.getAttribute("filter_name");

        let domain = [];
        let actionName = '';

        if (filter_name === "today_checkin") {
            domain = [
                ['checkin_date', '>=', new Date().toISOString().slice(0, 10)], 
                ['checkin_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
                ['state', '=', 'block']
            ];
            actionName = 'Today Check-Ins';
        } else if (filter_name === "today_checkout") {
            domain = [
                ['checkout_date', '>=', new Date().toISOString().slice(0, 10)], 
                ['checkout_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
                ['state', '=', 'check_out']
            ];
            actionName = 'Today Check-Outs';
        } else if (filter_name === "not_confirm") {
            domain = [['state', '=', 'not_confirmed']];
            actionName = 'Not Confirmed';
        } else if (filter_name === "confirmed") {
            domain = [['state', '=', 'confirmed']];
            actionName = 'Confirmed';
        } else if (filter_name === "waiting") {
            domain = [['state', '=', 'waiting']];
            actionName = 'Waiting List';
        } else if (filter_name === "blocked") {
            domain = [['state', '=', 'block']];
            actionName = 'Blocked';
        } else if (filter_name === "cancelled") {
            domain = [['state', '=', 'cancel']];
            actionName = 'Cancelled';
        } else if (filter_name === "checkin") {
            domain = [['state', '=', 'check_in']];
            actionName = 'Check-In';
        } else if (filter_name === "checkout") {
            domain = [['state', '=', 'check_out']];
            actionName = 'Check-Out';
        }

        if (domain.length > 0) {
            // Get the ID of the tree view from the ORM
            const viewId = await this.orm.searchRead('ir.ui.view', [['name', '=', 'room.booking.view.tree']], ['id']);
            
            if (viewId && viewId.length) {
                // Trigger the action with the view ID
                this.action.doAction({
                    name: actionName,
                    type: 'ir.actions.act_window',
                    res_model: 'room.booking',
                    view_mode: 'tree,form',
                    views: [[viewId[0].id, 'list'], [false, 'form']],
                    domain: domain,
                    target: 'current',
                });
            } else {
                console.error("View ID not found");
            }
        }
    }
}

ReservationDashBoard.template = "reservation.ReservationDashBoard";
