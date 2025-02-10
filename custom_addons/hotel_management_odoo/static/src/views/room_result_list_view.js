/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { RoomResultDashBoard } from "@hotel_management_odoo/views/hotel_room_result";

export class RoomResultRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.modelName = this.props.list.resModel;
    }
}

RoomResultRenderer.template = "reservation.RoomResultListView";
RoomResultRenderer.components = Object.assign({}, ListRenderer.components, { RoomResultDashBoard });

export const RoomResultDashBoardListView = {
    ...listView,
    Renderer: RoomResultRenderer,
};

// Register for both models
registry.category("views").add("hotel_room_result_filter", RoomResultDashBoardListView);
registry.category("views").add("room_result_by_client_filter", RoomResultDashBoardListView);