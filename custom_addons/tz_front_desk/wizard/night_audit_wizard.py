from odoo import models, fields, api, _
from odoo.exceptions import UserError

class NightAuditWizard(models.TransientModel):
    _name = 'night.audit.wizard'
    _description = 'Night Audit Wizard'

    progress = fields.Integer(string="Progress", default=0)

    def action_run_audit(self):
        steps = [
            self._validate_departures,
            self._mark_no_shows,
            self._post_accounting_entries,
            self._advance_system_date,
        ]

        total = len(steps)
        for idx, step in enumerate(steps, start=1):
            step()
            self.progress = int((idx / total) * 100)
            self._cr.commit()  # Optional: commit after each step for safety

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'night.audit.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _validate_departures(self):
        # Your logic here
        pass

    def _mark_no_shows(self):
        # Your logic here
        pass

    def _post_accounting_entries(self):
        # Your logic here
        pass

    def _advance_system_date(self):
        # Your logic here
        pass
