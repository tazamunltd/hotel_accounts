/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useBus } from "@web/core/utils/hooks";


export class ReservationDashBoard extends Component {
  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.parentChildMap = new Map(); // Track parent-child relationships
    this.companyService = useService("company");
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
      vacant: 0, // Add this line
      result_booking: [],
      selectedIds: [],
    });

    // onWillStart(async () => {
    //   const data = await this.orm.call("room.booking", "retrieve_dashboard");
    //   Object.assign(this.dashboardData, data);
    //   // Ensure selectedIds is initialized
    //   if (!Array.isArray(this.dashboardData.selectedIds)) {
    //     this.dashboardData.selectedIds = [];
    //   }
    // });

    // onWillStart(async () => {
    //   await this.fetchDashboardData();
    // });
     onWillStart(async () => {
       const data = await this.orm.call("room.booking", "retrieve_dashboard");

       // Make sure selectedIds exists in data
       Object.assign(this.dashboardData, data);

       // Ensure selectedIds is an array
       if (!Array.isArray(this.dashboardData.selectedIds)) {
         this.dashboardData.selectedIds = [];
       }
     });

    onMounted(() => {
      this.monitorTreeViewSelection();
      this.buildParentChildMap();
      // this.fetchDashboardData();
      this.observeDataChanges();
      // setInterval(() => {
      //   this.fetchDashboardData();
      // }, 1000); // 10,000ms = 10 seconds
    });

    // onWillUnmount(() => {
    //   if (this.intervalId) {
    //     clearInterval(this.intervalId); // Clear the interval when the component is destroyed
    //   }
    // });
  }
  async fetchSystemDate() {
    try {
      const companyId = this.companyService.currentCompany.id; // Get current company ID
      if (!companyId) {
        console.warn("No valid company_id found.");
        return null;
      }

      const [company] = await this.orm.read(
        "res.company",
        [companyId],
        ["system_date"]
      );
      if (company && company.system_date) {
        const rawDateStr = company.system_date;
        console.log(rawDateStr);
        const dateObj = new Date(rawDateStr + "Z"); // Force UTC interpretation
        // const dateObj = new Date(rawDateStr + "T00:00:00Z");
        const systemDate1 = dateObj.toLocaleString("en-GB", {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
        });
        console.log("65", systemDate1);
        return systemDate1;
      } else {
        console.warn("No system_date found for the company.");
        return null;
      }
    } catch (error) {
      console.error("Error fetching system date:", error);
      return null;
    }
  }

  async fetchDashboardData() {
    try {
      console.log("Fetching updated dashboard data...");
      const data = await this.orm.call("room.booking", "retrieve_dashboard");
      Object.assign(this.dashboardData, data);
    } catch (error) {
      console.error("Error fetching dashboard data:", error);
    }
  }

  observeDataChanges() {
    const observer = new MutationObserver(() => {
      this.fetchDashboardData();
    });

    // Observe the tree view for any changes
    const treeViewElement = document.querySelector(".o_list_view");
    if (treeViewElement) {
      observer.observe(treeViewElement, { childList: true, subtree: true });
    }
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
    if (!Array.isArray(this.dashboardData.selectedIds)) {
      this.dashboardData.selectedIds = []; // Ensure it's an array
    }
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
    const parentBookingName = parentNameCell
      ? parentNameCell.textContent.trim()
      : null;

    // Print or use extracted details
    // console.log("Checkbox Changed for Row:");
    // console.log("Booking Name:", bookingName);
    // console.log("Parent Booking Name:", parentBookingName);

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
      

      const childBookings = this.parentChildMap.get(parentName);

      childBookings.forEach((childName) => {
        // Find the row and checkbox for each child
        const childRow = Array.from(
          document.querySelectorAll("tr.o_data_row")
        ).find((row) => {
          const nameCell = row.querySelector('td[name="name"]');
          return nameCell && nameCell.textContent.trim() === childName;
        });

        if (childRow) {
          const childCheckbox = childRow.querySelector(
            ".o_list_record_selector input[type='checkbox']"
          );
          if (childCheckbox && !childCheckbox.checked) {
            childCheckbox.checked = true;

            // Dispatch a change event
            const event = new Event("change", { bubbles: true });
            childCheckbox.dispatchEvent(event);

            
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
      

      const childBookings = this.parentChildMap.get(parentName);

      childBookings.forEach((childName) => {
        // Find the row and checkbox for each child
        const childRow = Array.from(
          document.querySelectorAll("tr.o_data_row")
        ).find((row) => {
          const nameCell = row.querySelector('td[name="name"]');
          return nameCell && nameCell.textContent.trim() === childName;
        });

        if (childRow) {
          const childCheckbox = childRow.querySelector(
            ".o_list_record_selector input[type='checkbox']"
          );
          if (childCheckbox && childCheckbox.checked) {
            childCheckbox.checked = false;

            // Dispatch a change event
            const event = new Event("change", { bubbles: true });
            childCheckbox.dispatchEvent(event);

            
          }
        }
      });
    }
  }

  addToSelected(bookingName) {
    if (!Array.isArray(this.dashboardData.selectedIds)) {
      this.dashboardData.selectedIds = []; // Ensure it's an array
    }

    if (!this.dashboardData.selectedIds.includes(bookingName)) {
      this.dashboardData.selectedIds.push(bookingName);
    }
  }

  removeFromSelected(bookingName, parentBookingName) {
    this.dashboardData.selectedIds = this.dashboardData.selectedIds.filter(
      (name) => name !== bookingName
    );

    // If a parent is unchecked, remove all child bookings
    if (this.parentChildMap.has(parentBookingName)) {
      
      this.parentChildMap
        .get(parentBookingName)
        .forEach(({ checkbox: childCheckbox, row: childRow }) => {
          if (childCheckbox && childCheckbox.checked) {
            childCheckbox.checked = false;

            // Simulate event for Odoo to update UI
            const event = new Event("change", { bubbles: true });
            childCheckbox.dispatchEvent(event);

            // Remove child from selected IDs
            const childName = childRow
              .querySelector('td[name="name"]')
              .textContent.trim();
            this.dashboardData.selectedIds =
              this.dashboardData.selectedIds.filter(
                (name) => name !== childName
              );

            childRow.classList.remove("o_data_row_selected");
          }
        });
    }

  }

  handleCheckboxChange(checkbox) {
    const row = checkbox.closest("tr");
    if (!row) return;

    const nameCell = row.querySelector('td[name="name"]');
    if (!nameCell) return;

    const bookingName = nameCell.textContent.trim();

    if (checkbox.checked) {
      // Add the selected name
      if (!this.dashboardData.selectedIds.includes(bookingName)) {
        this.dashboardData.selectedIds.push(bookingName);
      }
    } else {
      // Remove the name when unchecked
      this.dashboardData.selectedIds = this.dashboardData.selectedIds.filter(
        (name) => name !== bookingName
      );

      // If it's a parent row, uncheck all its children
      if (this.parentChildMap.has(bookingName)) {
        // console.log(Unchecking children for parent: ${bookingName});
        this.parentChildMap
          .get(bookingName)
          .forEach(({ checkbox: childCheckbox, row: childRow }) => {
            if (childCheckbox && childCheckbox.checked) {
              childCheckbox.checked = false;

              // Dispatch change event to keep Odoo in sync
              const event = new Event("change", { bubbles: true });
              childCheckbox.dispatchEvent(event);

              // Remove child name from the selected IDs
              const childName = childRow
                .querySelector('td[name="name"]')
                .textContent.trim();
              this.dashboardData.selectedIds =
                this.dashboardData.selectedIds.filter(
                  (name) => name !== childName
                );

              // Remove visual highlight
              childRow.classList.remove("o_data_row_selected");
            }
          });
      }
    }

  }

  /**
   * Method to handle filtering and trigger appropriate actions.
   * @param {Event} ev
   */
  async setSearchContext(ev) {
    const filter_name = ev.currentTarget.getAttribute("filter_name");

    let domain = [];
    let actionName = "";

    // const systemDate = await this.fetchSystemDate();
    // console.log('system date:', systemDate, 'type:', typeof systemDate);

    const systemDateString = await this.fetchSystemDate();

    // Convert the string to a Date object
    const [day, month, year] = systemDateString.split("/").map(Number);
    const systemDate = new Date(year, month - 1, day); // Month is 0-based in JavaScript

    // Ensure systemDate has time set to 00:00:00
    systemDate.setHours(0, 0, 0, 0);
    // systemDate.setHours(0, 0, 0, 0); // Ensure system_date has time set to 00:00:00

    // Calculate the next day based on system_date
    const nextDate = new Date(systemDate);
    nextDate.setDate(systemDate.getDate() + 1);

    // function convertToISOFormat(dateString) {
    //     const [day, month, year] = dateString.split('/'); // Split the input string
    //     return ${year}-${month}-${day}; // Rearrange into YYYY-MM-DD format
    // }

    // // Convert and log the result
    // const systemDate = convertToISOFormat(systemDate2);
    // console.log('Formatted Date:', systemDate);
    // Define filter-specific domains and action names
    if (filter_name === "today_checkin") {
      domain = [
        ["checkin_date", ">=", nextDate.toISOString().slice(0, 10)],
        ["checkin_date", "<=", nextDate.toISOString().slice(0, 10)],
        // ['checkin_date', '>=', new Date().toISOString().slice(0, 10)],
        // ['checkin_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
        ["state", "=", "block"],
        //                ['parent_booking_name', '!=', false]
      ];
      actionName = "Today Check-Ins";
    } else if (filter_name === "today_checkout") {
      domain = [
        ["checkout_date", ">=", nextDate.toISOString().slice(0, 10)],
        ["checkout_date", "<=", nextDate.toISOString().slice(0, 10)],
        // ['checkout_date', '>=', new Date().toISOString().slice(0, 10)],
        // ['checkout_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
        ["state", "=", "check_in"],
        //                ['parent_booking_name', '!=', false]
      ];
      console.log("Domain :", domain);
      actionName = "Today Check-Outs";
    } else if (filter_name === "actual_checkin") {
      domain = [
        ["checkin_date", ">=", nextDate.toISOString().slice(0, 10)],
        ["checkin_date", "<=", nextDate.toISOString().slice(0, 10)],
        // ['checkin_date', '>=', new Date().toISOString().slice(0, 10)],
        // ['checkin_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
        ["state", "=", "check_in"],
        //                ['parent_booking_name', '!=', false]
      ];
      actionName = "Actual Check-Ins";
    } else if (filter_name === "actual_checkout") {
      domain = [
        ["checkout_date", ">=", nextDate.toISOString().slice(0, 10)],
        ["checkout_date", "<=", nextDate.toISOString().slice(0, 10)],
        // ['checkout_date', '>=', new Date().toISOString().slice(0, 10)],
        // ['checkout_date', '<', new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().slice(0, 10)],
        ["state", "=", "check_out"],
        //                ['parent_booking_name', '!=', false]
      ];
      console.log("Domain departure:", domain);
      actionName = "Actual Check-Outs";
    } else if (filter_name === "not_confirm") {
      domain = [["state", "=", "not_confirmed"]];
      actionName = "Not Confirmed";
    } else if (filter_name === "confirmed") {
      domain = [["state", "=", "confirmed"]];
      actionName = "Confirmed";
    } else if (filter_name === "waiting") {
      domain = [["state", "=", "waiting"]];
      actionName = "Waiting List";
    } else if (filter_name === "blocked") {
      domain = [["state", "=", "block"]];
      actionName = "Blocked";
    } else if (filter_name === "cancelled") {
      domain = [["state", "=", "cancel"]];
      actionName = "Cancelled";
    } else if (filter_name === "checkin") {
      domain = [["state", "=", "check_in"]];
      actionName = "Check-In";
    } else if (filter_name === "checkout") {
      domain = [["state", "=", "check_out"]];
      actionName = "Check-Out";
    } else if (filter_name === "vacant") {
      domain = [
        [
          "state",
          "in",
          ["confirmed", "not_confirmed", "waiting", "check_in", "check_out"],
        ],
      ];
      actionName = "Default";
      // this.action.doAction({
      //   type: "ir.actions.act_window",
      //   name: "Room Booking",
      //   res_model: "room.booking",
      //   view_mode: "list",
      //   views: [[false, "list"]],
      //   target: "current",
      // });
      // return;
      // // Redirect to the specific URL
      // window.location.href =
      //   "/web#action=425&model=room.booking&view_type=list";
      // return; // Exit after redirection
    }

    //     if (filter_name === "vacant") {
    //     // Redirect to the specific action without filtering by state
    //     this.action.doAction({
    //         type: "ir.actions.act_window",
    //         res_model: "room.booking",
    //         view_mode: "list",
    //         name: "Default",
    //         target: "current",
    //         domain: [
    //             ['company_id', '=', this.companyService.currentCompany.id] // Only filter by company
    //         ],
    //         context: { debug: 1 },
    //         views: [[false, "list"]],
    //         action: 425, // Use the specific action ID
    //     });
    //     return; // Exit the method since we handled the Vacant button
    // }

    if (domain.length > 0) {
      // Get the ID of the tree view from the ORM
      const viewId = await this.orm.searchRead(
        "ir.ui.view",
        [["name", "=", "room.booking.view.tree"]],
        ["id"]
      );

      if (viewId && viewId.length) {
        // Trigger the action with the view ID
        this.action.doAction({
          name: actionName,
          type: "ir.actions.act_window",
          res_model: "room.booking",
          view_mode: "tree,form",
          views: [
            [viewId[0].id, "list"],
            [false, "form"],
          ],
          domain: domain,
          target: "current",
        });
      } else {
        console.error("View ID not found");
      }
    }
  }
}

ReservationDashBoard.template = "reservation.ReservationDashBoard";