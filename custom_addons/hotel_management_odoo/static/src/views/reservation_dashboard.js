/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useBus } from "@web/core/utils/hooks";

export class ReservationDashBoard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.parentChildMap = new Map(); // Track parent-child relationships
        this.dashboardData = useState({
            today_checkin: 0,
            today_checkout: 0,
            not_confirm: 0,
            confirmed: 0,
            waiting: 0,
            blocked: 0,
            cancelled: 0,
            checkin: 0,
            checkout: 0,
            actual_checkin_count: 0,
            actual_checkout_count: 0,
            vacant: 0,  // Add this line
            result_booking:[],
            selectedIds:[],
        });

        onWillStart(async () => {
            const data = await this.orm.call("room.booking", "retrieve_dashboard");
            Object.assign(this.dashboardData, data);
            // Ensure selected_ids is initialized
            if (!Array.isArray(this.dashboardData.selected_ids)) {
                this.dashboardData.selected_ids = [];
            }
        });

        onMounted(() => {
            this.monitorTreeViewSelection();
            this.buildParentChildMap();
        });
    }

    buildParentChildMap() {
        const rows = document.querySelectorAll("tr.o_data_row");
        this.parentChildMap.clear(); // Clear the previous map

        rows.forEach((row) => {
            const parentCell = row.querySelector("td[name='parent_booking_name']");
            const childCell = row.querySelector("td[name='name']");

            if (parentCell && childCell) {
                const parentName = parentCell.textContent.trim();
                const childName = childCell.textContent.trim();

                if (!this.parentChildMap.has(parentName)) {
                    this.parentChildMap.set(parentName, []);
                }
                this.parentChildMap.get(parentName).push(childName);
            }
        });

//        console.log("Parent-Child Map:", this.parentChildMap);
    }

    monitorTreeViewSelection() {
        const treeViewElement = document.querySelector(".o_list_view");
        if (!treeViewElement) {
            console.error("Tree view element not found");
            return;
        }
        console.log("trueview",treeViewElement);
        // Attach an event listener for checkbox changes
//        treeViewElement.addEventListener("change", (event) => {
//            const targetCheckbox = event.target;
//            console.log("targetCheckbox",targetCheckbox);
//            // Check if the event originated from a checkbox
//            if (targetCheckbox.matches(".o_list_record_selector input[type='checkbox']")) {
//                this.handleCheckboxChange(targetCheckbox);
//            }
//            console.log("this is in the target checkbox",targetCheckbox);
//        });
         // Listen for "change" events on checkboxes
        treeViewElement.addEventListener("change", (event) => {
        const checkbox = event.target;

        // Ensure the event is from a checkbox inside the tree view
        if (checkbox.matches(".o_list_record_selector input[type='checkbox']")) {
            this.processTargetRow(checkbox);
        }
    });
}

processTargetRow(checkbox) {
        // Get the row containing this checkbox
        const row = checkbox.closest("tr");
        if (!row) {
            console.error("Row not found for checkbox");
            return;
        }

        // Extract booking name or other details from cells
        const nameCell = row.querySelector('td[name="name"]');
        const parentNameCell = row.querySelector('td[name="parent_booking_name"]');

        const bookingName = nameCell ? nameCell.textContent.trim() : null;
        const parentBookingName = parentNameCell ? parentNameCell.textContent.trim() : null;

        // Print or use extracted details
        console.log("Checkbox Changed for Row:");
        console.log("Booking Name:", bookingName);
        console.log("Parent Booking Name:", parentBookingName);

        if (checkbox.checked) {
            // Add to selected
            this.addToSelected(bookingName);

            // If this is a parent booking (parentName == "" or null), select all its children
            if (!parentBookingName) {
                this.selectChildBookings(bookingName);
            }
        } else {
            // Remove from selected
            this.removeFromSelected(bookingName);

            // If this is a parent booking, deselect all its children
            if (!parentBookingName) {
                this.deselectChildBookings(bookingName);
            }
        }
    }

/**
 * Select all child bookings for a given parent
 */
selectChildBookings(parentName) {
    if (this.parentChildMap.has(parentName)) {
        console.log(`Selecting children for parent: ${parentName}`);

        const childBookings = this.parentChildMap.get(parentName);

        childBookings.forEach((childName) => {
            // Find the row and checkbox for each child
            const childRow = Array.from(document.querySelectorAll("tr.o_data_row")).find((row) => {
                const nameCell = row.querySelector('td[name="name"]');
                return nameCell && nameCell.textContent.trim() === childName;
            });

            if (childRow) {
                const childCheckbox = childRow.querySelector(".o_list_record_selector input[type='checkbox']");
                if (childCheckbox && !childCheckbox.checked) {
                    childCheckbox.checked = true;

                    // Dispatch a change event
                    const event = new Event("change", { bubbles: true });
                    childCheckbox.dispatchEvent(event);

                    console.log(`Child booking selected: ${childName}`);
                }
            }
        });
    }
}

/**
 * Deselect all child bookings for a given parent
 */
deselectChildBookings(parentName) {
    if (this.parentChildMap.has(parentName)) {
        console.log(`Deselecting children for parent: ${parentName}`);

        const childBookings = this.parentChildMap.get(parentName);

        childBookings.forEach((childName) => {
            // Find the row and checkbox for each child
            const childRow = Array.from(document.querySelectorAll("tr.o_data_row")).find((row) => {
                const nameCell = row.querySelector('td[name="name"]');
                return nameCell && nameCell.textContent.trim() === childName;
            });

            if (childRow) {
                const childCheckbox = childRow.querySelector(".o_list_record_selector input[type='checkbox']");
                if (childCheckbox && childCheckbox.checked) {
                    childCheckbox.checked = false;

                    // Dispatch a change event
                    const event = new Event("change", { bubbles: true });
                    childCheckbox.dispatchEvent(event);

                    console.log(`Child booking deselected: ${childName}`);
                }
            }
        });
    }
}



addToSelected(bookingName) {
    if (!this.dashboardData.selected_ids.includes(bookingName)) {
        this.dashboardData.selected_ids.push(bookingName);
    }
    console.log("Updated Selected IDs:", this.dashboardData.selected_ids);
}

    removeFromSelected(bookingName, parentBookingName) {
        this.dashboardData.selected_ids = this.dashboardData.selected_ids.filter((name) => name !== bookingName);

    // If a parent is unchecked, remove all child bookings
    if (this.parentChildMap.has(parentBookingName)) {
        console.log(`Removing children for parent: ${parentBookingName}`);
        this.parentChildMap.get(parentBookingName).forEach(({ checkbox: childCheckbox, row: childRow }) => {
            if (childCheckbox && childCheckbox.checked) {
                childCheckbox.checked = false;

                // Simulate event for Odoo to update UI
                const event = new Event("change", { bubbles: true });
                childCheckbox.dispatchEvent(event);

                // Remove child from selected IDs
                const childName = childRow.querySelector('td[name="name"]').textContent.trim();
                this.dashboardData.selected_ids = this.dashboardData.selected_ids.filter((name) => name !== childName);

                childRow.classList.remove("o_data_row_selected");
            }
        });
    }

    console.log("Updated Selected IDs after removal:", this.dashboardData.selected_ids);
    }


    handleCheckboxChange(checkbox) {
    const row = checkbox.closest("tr");
    if (!row) return;

    const nameCell = row.querySelector('td[name="name"]');
    if (!nameCell) return;

    const bookingName = nameCell.textContent.trim();

    if (checkbox.checked) {
        // Add the selected name
        if (!this.dashboardData.selected_ids.includes(bookingName)) {
            this.dashboardData.selected_ids.push(bookingName);
        }
    } else {
        // Remove the name when unchecked
        this.dashboardData.selected_ids = this.dashboardData.selected_ids.filter((name) => name !== bookingName);

        // If it's a parent row, uncheck all its children
        if (this.parentChildMap.has(bookingName)) {
            console.log(`Unchecking children for parent: ${bookingName}`);
            this.parentChildMap.get(bookingName).forEach(({ checkbox: childCheckbox, row: childRow }) => {
                if (childCheckbox && childCheckbox.checked) {
                    childCheckbox.checked = false;

                    // Dispatch change event to keep Odoo in sync
                    const event = new Event("change", { bubbles: true });
                    childCheckbox.dispatchEvent(event);

                    // Remove child name from the selected IDs
                    const childName = childRow.querySelector('td[name="name"]').textContent.trim();
                    this.dashboardData.selected_ids = this.dashboardData.selected_ids.filter((name) => name !== childName);

                    // Remove visual highlight
                    childRow.classList.remove("o_data_row_selected");
                }
            });
        }
    }

    console.log("Updated Selected IDs:", this.dashboardData.selected_ids);
    }


    /**
     * Method to handle filtering and trigger appropriate actions.
     * @param {Event} ev
     */
    async setSearchContext(ev) {
        const filter_name = ev.currentTarget.getAttribute("filter_name");

        let domain = [];
        let actionName = '';

        // Define filter-specific domains and action names
        if (filter_name === "today_checkin") {
            domain = [
                ['checkin_date', '>=', new Date().toISOString().slice(0, 10)],
                ['checkin_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
                ['state', '=', 'block'],
//                ['parent_booking_name', '!=', false]
            ];
            actionName = 'Today Check-Ins';
        } else if (filter_name === "today_checkout") {
            domain = [
                ['checkout_date', '>=', new Date().toISOString().slice(0, 10)],
                ['checkout_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
                ['state', '=', 'check_in'],
//                ['parent_booking_name', '!=', false]
            ];
            actionName = 'Today Check-Outs';
        }else if (filter_name === "actual_checkin") {
            domain = [
                ['checkin_date', '>=', new Date().toISOString().slice(0, 10)],
                ['checkin_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
                ['state', '=', 'check_in'],
//                ['parent_booking_name', '!=', false]
            ];
            actionName = 'Actual Check-Ins';
        }else if (filter_name === "actual_checkout") {
            domain = [
                ['checkout_date', '>=', new Date().toISOString().slice(0, 10)],
                ['checkout_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
                ['state', '=', 'check_out'],
//                ['parent_booking_name', '!=', false]
            ];
            actionName = 'Actual Check-Outs';
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
