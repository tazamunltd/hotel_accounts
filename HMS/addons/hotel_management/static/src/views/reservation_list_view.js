/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ReservationDashBoard } from '@hotel_management/views/reservation_dashboard';

export class ReservationDashBoardRenderer extends ListRenderer {};

ReservationDashBoardRenderer.template = 'reservation.ReservationListView';
ReservationDashBoardRenderer.components= Object.assign({}, ListRenderer.components, {ReservationDashBoard})

export const ReservationDashBoardListView = {
    ...listView,
    Renderer: ReservationDashBoardRenderer,
};

registry.category("views").add("reservation_dashboard_list", ReservationDashBoardListView);
