/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// Configuration object for model-specific settings
const MODEL_CONFIG = {
  "hotel.room.result": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "room.result.by.client": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "room.result.by.room.type": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "yearly.geographical.chart": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms_geographical", // Corrected method name
  },
  "monthly.groups.chart": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "monthly.allotment.chart": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "reservation.status.report": {
    startDateField: "date_order",
    endDateField: "date_order",
    methodName: "search_available_rooms", // Change this to your actual method name
  },
  "deleted.reservation.report": {
    startDateField: "date_order",
    endDateField: "date_order",
    methodName: "search_available_rooms", // Change this to your actual method name
  },
  "reservation.summary.report": {
    startDateField: "first_arrival",
    endDateField: "last_departure",
    methodName: "search_available_rooms", // Change this to your actual method name
  },
  "all.reservation.status.report": {
    startDateField: "date_order",
    endDateField: "date_order",
    methodName: "search_available_rooms", // Change this to your actual method name
  },
  "meals.forecast.report": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "market.segment.forecast.report": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "source.of.buisness.forecast": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "meals.by.nationality.forecast": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "company.forecast.report": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "rooms.forecast.report": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
  "revenue.forecast": {
    startDateField: "report_date",
    endDateField: "report_date",
    methodName: "search_available_rooms",
  },
};

export class RoomResultDashBoard extends Component {
  setup() {
    this.orm = useService("orm");
    this.view = useService("view");
    this.actionService = useService("action");
    
    const fromDate = this.props.context?.from_date || "";
    const toDate = this.props.context?.to_date || "";

    this.state = useState({
      startDate: fromDate,
      endDate: toDate,
    });
    // this.state = useState({
    //   startDate: "",
    //   endDate: "",
    // });

    // Get model configuration
    this.modelConfig = MODEL_CONFIG[this.props.modelName] || {
      startDateField: "report_date",
      endDateField: "report_date",
      methodName: "search_available_rooms",
    };
  }

  onApplyFilter = async () => {
    const fromDate = this.state.startDate;
    const toDate = this.state.endDate;

    console.log("From Date:", fromDate);
    console.log("To Date:", toDate);

    if (!fromDate || !toDate) {
      console.error("Both From Date and To Date are required.");
      return;
    }

    try {
      const modelName = this.props.modelName;

      // Call the model-specific search method
      const results = await this.orm.call(
        modelName,
        this.modelConfig.methodName,
        [fromDate, toDate]
      );
      console.log(
        "Calling method:",
        this.modelConfig.methodName,
        "with params:",
        [fromDate, toDate]
      );

      console.log("Filtered Results:", results);

      // Create domain based on model configuration
      const domain = [
        [this.modelConfig.startDateField, ">=", fromDate],
        [this.modelConfig.endDateField, "<=", toDate],
      ];

      // Reload the view with the new domain
      this.actionService.doAction({
        type: "ir.actions.act_window",
        name: "Filtered Results",
        res_model: modelName,
        // view_mode: "tree,form",
        view_mode: "tree,pivot,graph",
        views: [
          [false, "tree"],
          [false, "pivot"],
          [false, "graph"],
          // [false, "form"],
        ],
        target: "current",
        domain: [
          [this.modelConfig.startDateField, ">=", fromDate],
          [this.modelConfig.endDateField, "<=", toDate],
        ],
        context: {
          from_date: fromDate,
          to_date: toDate,
        },
      });
    } catch (error) {
      console.error("Error occurred while filtering:", error);
    }
  };
}

RoomResultDashBoard.template = "hotel_management_odoo.RoomResultDashBoard";
RoomResultDashBoard.props = {
  modelName: String,
  context: { type: Object, optional: true },
};

