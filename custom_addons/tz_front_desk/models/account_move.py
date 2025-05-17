from odoo import fields, models, api


class AccountMove(models.Model):
    """Inherited account. move for adding hotel booking reference field to
        invoicing model."""
    _inherit = "account.move"

    no_account_entry = fields.Boolean(string='HotelInvoice', default=False)
    folio_id = fields.Many2one(
        'tz.master.folio',
        string='Master Folio',
        readonly=True,
        copy=False
    )

    # def action_post(self):
    #     if self.no_account_entry:
    #         self.write({'state': 'posted'})
    #         return True
    #     else:
    #         return super(AccountMove, self).action_post

