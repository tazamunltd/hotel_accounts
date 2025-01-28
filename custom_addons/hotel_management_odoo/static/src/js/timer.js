/** @odoo-module **/

import { Component, onWillStart, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TimerWidget extends Component {
  static props = [];

  setup() {
    // Services
    this.orm = useService("orm");
    this.userService = useService("user");
    this.companyService = useService("company");
    this.notificationService = useService("notification");

    // Initial state
    this.state = { systemDate: null };

    // Log the user ID before fetching data
    // console.log("TimerWidget: Current User ID =>", this.userService.userId);

    // Setup company change watcher using onWillStart lifecycle hook
    onWillStart(async () => {
      // Initial fetch
      await this.fetchSystemDate();

      // Show notification when the page loads
      if (this.state.systemDate) {
        this.notificationService.add(`System Date: ${this.state.systemDate}`, {
          // title: "Welcome!",
          type: "info",
        });
      }

      // Setup company change watcher
      this.companyChangedCallback = () => this.fetchSystemDate();
      this.env.bus.addEventListener(
        "COMPANY_SWITCHED",
        this.companyChangedCallback
      );
    });

    // Cleanup on component destroy
    onWillDestroy(() => {
      if (this.companyChangedCallback) {
        this.env.bus.removeEventListener(
          "COMPANY_SWITCHED",
          this.companyChangedCallback
        );
      }
    });
  }

  async fetchSystemDate() {
    try {
      // Get current company ID
      const companyId = this.companyService.currentCompany.id;
      console.log("TimerWidget: Current Company ID =>", companyId);

      if (!companyId) {
        console.warn("TimerWidget: No valid company_id found.");
        return;
      }

      // Read the system_date from the res.company record
      const [company] = await this.orm.read(
        "res.company",
        [companyId],
        ["system_date"]
      );
      console.log("TimerWidget: res.company record =>", company);

      if (company && company.system_date) {
        // Format and store the system date in component state
        const rawDateStr = company.system_date;
        const dateObj = new Date(rawDateStr + "Z"); // Force UTC interpretation
        this.state.systemDate = dateObj.toLocaleString("en-GB", {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
        });

        // Log the final formatted date
        console.log(
          "TimerWidget: Computed systemDate =>",
          this.state.systemDate
        );

        // Trigger render
        this.render();
      }
    } catch (error) {
      console.error("Error fetching system date:", error);
    }
  }
}

TimerWidget.template = "hotel_management_odoo.TimerWidget";

// Register the component in the systray registry
registry.category("systray").add("hotel_management_odoo.timer", {
  Component: TimerWidget,
  sequence: 100,
});
