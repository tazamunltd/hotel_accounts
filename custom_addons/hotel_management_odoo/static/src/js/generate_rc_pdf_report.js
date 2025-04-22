/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";

export class GeneratePDFButton extends ListController {
    async generatePDF() {
        const selectedRecords = this.model.root.selection;
        if (selectedRecords.length === 0) {
            this.displayNotification({ message: "Please select at least one record." });
            return;
        }

        // Get the IDs of the selected records
        const ids = selectedRecords.map(record => record.resId).join(',');

        // Redirect to the controller to generate the PDFs
        window.location.href = `/generate_rc/bookings_pdf?booking_ids=${ids}`;
    }
}

registry.category("actions").add("generate_rc_pdf_report", GeneratePDFButton);
