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
    startDateField: "checkin_date",
    endDateField: "checkout_date",
    methodName: "search_available_rooms", // Change this to your actual method name
  },
  "deleted.reservation.report": {
    startDateField: "checkin_date",
    endDateField: "checkout_date",
    methodName: "search_available_rooms", // Change this to your actual method name
  },
  "reservation.summary.report": {
    startDateField: "first_arrival",
    endDateField: "last_departure",
    methodName: "search_available_rooms", // Change this to your actual method name
  },
  "all.reservation.status.report": {
    startDateField: "checkin_date",
    endDateField: "checkout_date",
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
    this.state = useState({
      startDate: "",
      endDate: "",
    });

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
      console.log("Model Name:", modelName);

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
        view_mode: "tree,form",
        views: [
          [false, "tree"],
          [false, "form"],
        ],
        target: "current",
        domain: domain,
      });
    } catch (error) {
      console.error("Error occurred while filtering:", error);
    }
  };
}

RoomResultDashBoard.template = "hotel_management_odoo.RoomResultDashBoard";
RoomResultDashBoard.props = {
  modelName: String,
};

// import { Component, useState } from "@odoo/owl";
// import { useService } from "@web/core/utils/hooks";

// // Configuration object for model-specific settings
// const MODEL_CONFIG = {
//   "hotel.room.result": {
//     startDateField: "report_date",
//     endDateField: "report_date",
//     methodName: "search_available_rooms",
//   },
//   "room.result.by.client": {
//     startDateField: "report_date",
//     endDateField: "report_date",
//     methodName: "search_available_rooms",
//   },
//   "room.result.by.room.type": {
//     startDateField: "report_date",
//     endDateField: "report_date",
//     methodName: "search_available_rooms",
//     },
//     "yearly.geographical.chart": {
//     startDateField: "report_date",
//     endDateField: "report_date",
//     methodName: "search_available_rooms",
//     },
//     "monthly.groups.chart": {
//     startDateField: "report_date",
//     endDateField: "report_date",
//     methodName: "search_available_rooms",
//     },
//     "monthly.allotment.chart": {
//     startDateField: "report_date",
//     endDateField: "report_date",
//     methodName: "search_available_rooms",
//     },
//   "reservation.status.report": {
//     startDateField: "checkin_date",
//     endDateField: "checkout_date",
//     methodName: "search_available_rooms", // Change this to your actual method name
//   },
// };

// export class RoomResultDashBoard extends Component {
//   setup() {
//     this.orm = useService("orm");
//     this.view = useService("view");
//     this.actionService = useService("action");
//     this.state = useState({
//       startDate: "",
//       endDate: "",
//     });

//     // Get model configuration
//     this.modelConfig = MODEL_CONFIG[this.props.modelName] || {
//       startDateField: "report_date",
//       endDateField: "report_date",
//       methodName: "search_available_rooms",
//     };
//   }

//   onApplyFilter = async () => {
//     const fromDate = this.state.startDate;
//     const toDate = this.state.endDate;

//     if (!fromDate || !toDate) {
//       console.error("Both From Date and To Date are required.");
//       return;
//     }

//     try {
//       const modelName = this.props.modelName;

//       // Call the model-specific search method
//       const results = await this.orm.call(
//         modelName,
//         this.modelConfig.methodName,
//         [fromDate, toDate]
//       );

//       console.log("Filtered Results:", results);

//       // Create domain based on model configuration
//       const domain = [
//         [this.modelConfig.startDateField, ">=", fromDate],
//         [this.modelConfig.endDateField, "<=", toDate],
//       ];

//       // Reload the view with the new domain
//       this.actionService.doAction({
//         type: "ir.actions.act_window",
//         name: "Filtered Results",
//         res_model: modelName,
//         view_mode: "tree,form",
//         views: [
//           [false, "tree"],
//           [false, "form"],
//         ],
//         target: "current",
//         domain: domain,
//       });
//     } catch (error) {
//       console.error("Error occurred while filtering:", error);
//     }
//   };
// }

// RoomResultDashBoard.template = "hotel_management_odoo.RoomResultDashBoard";
// RoomResultDashBoard.props = {
//   modelName: String,
// };

// /** @odoo-module **/

// import { Component, useState } from "@odoo/owl";
// import { useService } from "@web/core/utils/hooks";

// export class RoomResultDashBoard extends Component {
//     setup() {
//         this.orm = useService("orm");
//         this.view = useService("view");
//         this.actionService = useService("action");
//         this.state = useState({
//             startDate: "",
//             endDate: "",
//         });
//     }

//     onApplyFilter = async () => {
//         const fromDate = this.state.startDate;
//         const toDate = this.state.endDate;

//         if (!fromDate || !toDate) {
//             console.error("Both From Date and To Date are required.");
//             return;
//         }

//         try {
//             // Get the model name from props
//             const modelName = this.props.modelName;

//             // Call the ORM method to verify data (optional step)
//             const results = await this.orm.call(
//                 modelName,
//                 "search_available_rooms",
//                 [fromDate, toDate]
//             );

//             console.log("Filtered Results:", results);

//             // Reload the view with a new domain
//             this.actionService.doAction({
//                 type: "ir.actions.act_window",
//                 name: "Filtered Room Results",
//                 res_model: modelName,
//                 view_mode: "tree,form",
//                 views: [[false, "tree"]],
//                 target: "current",
//                 domain: [
//                     ["report_date", ">=", fromDate],
//                     ["report_date", "<=", toDate],
//                 ],
//             });
//         } catch (error) {
//             console.error("Error occurred while filtering:", error);
//         }
//     };
// }

// RoomResultDashBoard.template = "hotel_management_odoo.RoomResultDashBoard";
// RoomResultDashBoard.props = {
//     modelName: String,
// };
