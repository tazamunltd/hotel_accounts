/** @odoo-module **/

const { Component } = require("@odoo/owl");
const { registry } = require("@web/core/registry");

class TimerWidget extends Component {
  // setup() {
  //     this.state = { currentTime: new Date().toLocaleTimeString() };
  //     this.updateTime();
  // }

  setup() {
    this.state = { currentDate: this.getCurrentDate() };
    this.updateDate();
  }

  getCurrentDate() {
    // Format date in a human-readable format
    return new Date().toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }

  getCurrentTime() {
    // Format time in 24-hour format
    return new Date().toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  //   updateTime() {
  //     setInterval(() => {
  //       this.state.currentTime = this.getCurrentTime();
  //       this.render();
  //     }, 1000);
  //   }
  // }

  updateDate() {
    setInterval(() => {
      this.state.currentDate = this.getCurrentDate();
      this.render();
    }, 60000); // Update every minute to avoid unnecessary rendering
  }
}

TimerWidget.template = "hotel_management_odoo.TimerWidget";

const systrayItem = {
  Component: TimerWidget,
  sequence: 100,
};

// Register the component in the systray registry
registry.category("systray").add("hotel_management_odoo.timer", systrayItem);
