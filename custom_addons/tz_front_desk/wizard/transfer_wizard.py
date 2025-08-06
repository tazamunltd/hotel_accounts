from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TransferChargeWizard(models.TransientModel):
    _name = 'tz.transfer.charge.wizard'
    _description = 'Transfer Wizard'

    item_id = fields.Many2one(
        'posting.item',
        string="Item",
        required=True,
        domain="[('main_department.adjustment', '=', 'transfer_charge')]"
    )
    current_date = fields.Date(
        string="Current Date",
        compute='_compute_current_date',
        store=False
    )

    type_id = fields.Many2one(
        'tz.manual.posting.type',
        string="From Room",
        required=True,
        index=True,
        domain="[('company_id', '=', company_id)]", #, ('folio_id', '!=', False), ('checkin_date', '=', current_date)
        ondelete="restrict"
    )

    amount = fields.Float(string="Amount", required=True)
    description = fields.Char(string="Description")
    to_description = fields.Char(string="Description")
    to_type_id = fields.Many2one(
        'tz.manual.posting.type',
        string="To Room",
        required=True,
        index=True,
        domain="[('company_id', '=', company_id)]", #, ('folio_id', '!=', False), ('checkin_date', '=', current_date)
        ondelete="restrict"
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        self.env['tz.manual.posting.type'].sync_with_materialized_view()
        return res

    def _compute_current_date(self):
        for record in self:
            record.current_date = fields.Date.context_today(record)

    @api.onchange('type_id')
    def _onchange_type_id(self):
        for record in self:
            if not record.type_id:
                record.description = False
                continue

            src = record.type_id
            if src.room_id:
                room_info = f"Room {src.room_id.name}"
            elif src.booking_id:
                room_info = f"Booking {src.booking_id.name}"
            elif src.group_booking_id:
                room_info = f"Group Booking {src.group_booking_id.group_name}"
            elif src.dummy_id:
                room_info = f"Dummy Group {src.dummy_id.description}"
            else:
                room_info = "Unknown source"

            record.description = _(f"Transfer from {room_info}")

    @api.onchange('to_type_id')
    def _onchange_to_type_id(self):
        for record in self:
            if not record.to_type_id:
                record.to_description = False
                continue

            dst = record.to_type_id
            if dst.room_id:
                target_info = f"Room {dst.room_id.name}"
            elif dst.booking_id:
                target_info = f"Booking {dst.booking_id.name}"
            elif dst.group_booking_id:
                target_info = f"Group Booking {dst.group_booking_id.group_name}"
            elif dst.dummy_id:
                target_info = f"Dummy Group {dst.dummy_id.description}"
            else:
                target_info = "Unknown target"

            record.to_description = _(f"Transfer to {target_info}")

    def action_transfer(self):
        self.ensure_one()

        folio_id = self._get_master_folio(self.type_id.room_id.id, self.type_id.dummy_id.id)

        manual_posting = f"{self.env.company.name}/{self.env['ir.sequence'].next_by_code('tz.manual.posting')}"
        system_date = self.env.company.system_date.date()

        first_record_vals = {
            'name': str(manual_posting),
            'date': str(system_date),
            'folio_id': folio_id.id,
            'item_id': self.item_id.id,
            'type_id': self.type_id.id,
            'description': self.to_description,
            'booking_id': self.type_id.booking_id.id,
            'room_id': self.type_id.room_id.id,
            'group_booking_id': self.type_id.group_booking_id.id,
            'quantity': 1,
            'debit_amount': 0.0,
            'credit_amount': self.amount,
            'source_type': 'manual',
            'sign': 'credit',
        }

        credit_posting = self.env['tz.manual.posting'].create(first_record_vals)

        to_folio_id = self._get_master_folio(self.to_type_id.room_id.id, self.to_type_id.dummy_id.id)

        second_record_vals = {
            'name': str(manual_posting),
            'date': str(system_date),
            'folio_id': to_folio_id.id,
            'item_id': self.item_id.id,
            'type_id': self.to_type_id.id,
            'description': self.description,
            'booking_id': self.to_type_id.booking_id.id,
            'room_id': self.to_type_id.room_id.id,
            'group_booking_id': self.to_type_id.group_booking_id.id,
            'quantity': 1,
            'debit_amount': self.amount,
            'credit_amount': 0.0,
            'source_type': 'manual',
            'sign': 'debit',
            'master_id': credit_posting.id,
        }

        debit_posting = self.env['tz.manual.posting'].create(second_record_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Manual Postings',
            'res_model': 'tz.manual.posting',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('id', 'in', [credit_posting.id, debit_posting.id])],
        }

        # return {
        #     'type': 'ir.actions.act_window',
        #     'res_model': 'tz.manual.posting',
        #     'view_mode': 'tree,form',
        #     # 'res_id': credit_posting.id,
        #     'target': 'current',
        # }

    def _get_master_folio(self, room_id, dummy_id):
        folio_id = self.env['tz.manual.posting']._get_or_create_master_folio(room_id)
        if dummy_id:
            folio_id = self.env['tz.manual.posting']._get_master_folio_for_dummy(dummy_id)
        return folio_id
