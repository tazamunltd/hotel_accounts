from pickle import FALSE

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class TzHotelManualPosting(models.Model):
    """
    The Manual Postings form is a crucial part of the hotel’s financial system.
    It offers accountants and Front Office staff the ability to enter or adjust financial transactions that are not automatically generated by the system’s standard processes
    (e.g., daily room charges or integrated point-of-sale sales).
    """
    _name = 'tz.manual.posting'
    _order = 'create_date asc'
    _description = 'Hotel Manual Posting'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Transaction ID",
        readonly=True,
        index=True,
        default='New',
        tracking=True
    )

    date = fields.Date(
        string="Date / Shift #",
        default=lambda self: self.env.company.system_date.replace(hour=0, minute=0, second=0, microsecond=0),
        readonly=True
    )
    time = fields.Char(
        string="Time",
        compute='_compute_current_time',
        store=True,
        default=lambda self: datetime.now().strftime('%H:%M %p')
    )

    company_id = fields.Many2one('res.company', string="Hotel",
                                 index=True,
                                 default=lambda self: self.env.company,
                                 readonly=True)

    item_id = fields.Many2one('posting.item', string="Item", index=True, required=True, tracking=True)

    description = fields.Char(string=_("Description"), required=True, readonly=False)

    voucher_number = fields.Char(string="Voucher #", index=True, tracking=True)

    type_id = fields.Many2one(
        'tz.manual.posting.type',
        string="Type",
        required=True,
        index=True,
        domain="[('company_id', '=', company_id)]"
    )

    booking_id = fields.Many2one('room.booking', compute='_compute_type_fields', store=True)
    room_id = fields.Many2one('hotel.room', compute='_compute_type_fields', store=True)
    group_booking_id = fields.Many2one('group.booking', compute='_compute_type_fields', store=True)
    dummy_id = fields.Many2one('tz.dummy.group', compute='_compute_type_fields', store=True)

    # booking_id = fields.Many2one(
    #     'room.booking',
    #     string="Room Booking",
    #     domain=lambda self: [('state', 'in', ['confirmed', 'no_show', 'block', 'check_in'])]
    # )
    #
    # room_id = fields.Many2one(
    #     'hotel.room',
    #     string="Room",
    #     domain="[('id', 'in', unavailable_room_ids)]"
    # )
    #
    unavailable_room_ids = fields.Many2many(
        comodel_name='hotel.room',
        compute='_compute_unavailable_rooms',
        store=False,
    )
    #
    # group_booking_id = fields.Many2one(
    #     'group.booking',
    #     string="Group",
    #     domain="[('status_code', '=', 'confirmed'), ('has_master_folio', '=', True)]"
    # )
    #
    # dummy_id = fields.Many2one(
    #     'tz.dummy.group',
    #     string="Dummy",
    #     domain="[('obsolete', '=', False)]"
    # )

    debit_amount = fields.Float(
        string="Debit",
        tracking=True,
        index=True,
    )
    credit_amount = fields.Float(
        string="Credit",
        tracking=True,
        index=True,
    )
    quantity = fields.Integer(string="Quantity", default=1, tracking=True, index=True)
    total = fields.Float(string="Total", tracking=True, index=True, compute='_compute_total', store=True)
    balance = fields.Float(string="Balance", compute='_compute_balance', store=True)
    formula_balance = fields.Float(string="Balance", compute='_compute_formula_balance', store=True)

    sign = fields.Selection(
        selection=[
            ('debit', 'Debit'),
            ('credit', 'Credit')
        ],
        string="Sign",
        store=True,
        tracking=True,
        compute='_compute_sign',
    )

    taxes = fields.Many2many('account.tax', compute='_compute_taxes', store=True, string="Taxes")

    partner_id = fields.Many2one(
        'res.partner',
        string="Guest",
        compute='_compute_booking_info',
        store=True
    )

    reference_contact_ = fields.Char(
        string="Contact Reference",
        compute='_compute_booking_info',
        store=True
    )
    folio_id = fields.Many2one('tz.master.folio', string="Folio", index=True, store=True)

    source_type = fields.Selection(
        [('auto', 'Auto'), ('manual', 'Manual')],
        string="Source",
        default='manual',
        tracking=True
    )

    price = fields.Float(
        string="Price",
        compute='_compute_price',
        help="Shows either debit or credit amount, whichever is non-zero"
    )

    state = fields.Selection(
        [('draft', 'Draft'), ('posted', 'Posted')],
        string="State",
        default='draft',
        tracking=True
    )

    tax_ids = fields.One2many('tz.manual.posting.tax', 'posting_id', string='Taxes')

    debit_without_vat = fields.Float(string="Debit", default=0.0, index=True)
    credit_without_vat = fields.Float(string="Credit", default=0.0, index=True)

    currency_id = fields.Many2one(related='folio_id.currency_id', store=True)
    price_subtotal = fields.Monetary(string="Untaxed", compute='_compute_amounts', store=True)
    tax_amount = fields.Monetary(string="Tax", compute='_compute_amounts', store=True)
    price_total = fields.Monetary(string="Total", compute='_compute_amounts', store=True)

    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], string="Display Type")

    # temp field for creating odoo payment
    odoo_payment = fields.Boolean()

    @api.onchange('type_id')
    def _onchange_type_id(self):
        for record in self:
            if record.type_id:
                # Update the fields with values from the selected type_id
                record.booking_id = record.type_id.booking_id
                record.room_id = record.type_id.room_id
                record.group_booking_id = record.type_id.group_booking_id
                record.dummy_id = record.type_id.dummy_id
                record.folio_id = record._get_master_folio_for_dummy(record.dummy_id.id)

    @api.depends('type_id')
    def _compute_type_fields(self):
        for record in self:
            if record.type_id:
                record.booking_id = record.type_id.booking_id
                record.room_id = record.type_id.room_id
                record.group_booking_id = record.type_id.group_booking_id
                record.dummy_id = record.type_id.dummy_id
                record.folio_id = record._get_master_folio_for_dummy(record.dummy_id.id)
            else:
                record.booking_id = False
                record.room_id = False
                record.group_booking_id = False
                record.dummy_id = False

    @api.model
    def default_get(self, fields_list):
        res = super(TzHotelManualPosting, self).default_get(fields_list)
        unavailable_rooms = self.env['room.booking.line'].search([
            ('state_', 'in', ['confirmed', 'block', 'check_in', 'no_show']),
        ]).mapped('room_id.id')
        res['unavailable_room_ids'] = [(6, 0, unavailable_rooms)]
        return res

    @api.model
    def create(self, vals):
        if vals.get('source_type') != 'auto':
            suspended = self.env['tz.hotel.checkout']._check_suspended_manual_posting(
                room_id=vals.get('room_id'),
                group_id=vals.get('group_booking_id'),
                dummy_id=vals.get('dummy_id')
            )
            if suspended:
                raise ValidationError("The Manual posting is suspended")

        booking = self.env['room.booking'].browse(vals.get('booking_id'))
        if booking and booking.state == 'cancel':
            raise ValidationError("You cannot create a manual posting for a canceled booking.")

        if not vals.get('sign'):
            raise ValidationError("You must select a Sign before creating a manual posting.")

        if vals.get('name', 'New') == 'New':
            company = self.env.company
            vals[
                'name'] = f"{company.name}/{self.env['ir.sequence'].with_company(company).next_by_code('tz.manual.posting') or '00001'}"

        record = super(TzHotelManualPosting, self).create(vals)

        if self._context.get('manual_creation'):
            if vals.get('group_booking_id', False):
                vals['room_id'] = self._get_master_room_id(vals['group_booking_id'])

            folio = False
            if record.room_id:
                folio = self._create_master_folio(record.room_id.id)
            elif record.dummy_id:
                folio = record._get_master_folio_for_dummy(record.dummy_id.id)

            if folio:
                record.folio_id = folio

        if vals.get('odoo_payment'):
            record.create_account_payment()

        vals['source_type'] = 'manual'

        if record.item_id:
            record.compute_manual_taxes()

        return record

    def write(self, vals):
        room_id = vals.get('room_id', self.room_id.id)
        group_id = vals.get('group_booking_id', self.group_booking_id.id)
        dummy_id = vals.get('dummy_id', self.dummy_id.id)

        self.env['tz.hotel.checkout']._check_suspended_manual_posting(room_id=room_id, group_id=group_id, dummy_id=dummy_id)

        if 'booking_id' in vals:
            booking = self.env['room.booking'].browse(vals['booking_id'])
            if booking.state == 'cancel':
                raise ValidationError("You cannot update manual posting to link to a canceled booking.")

        if vals.get('odoo_payment'):
            for record in self:
                record.create_account_payment()

        return super().write(vals)

    # @api.depends_context('room_id')
    def _compute_unavailable_rooms(self):
        for rec in self:
            unavailable_rooms = self.env['room.booking.line'].search([
                ('state_', 'in', ['confirmed', 'block', 'check_in', 'no_show']),
            ]).mapped('room_id.id')
            rec.unavailable_room_ids = [(6, 0, unavailable_rooms)]

    @api.depends('debit_amount', 'credit_amount', 'quantity')
    def _compute_total(self):
        for record in self:
            if record.sign == 'debit' and record.debit_amount > 0:
                record.total = record.debit_amount * record.quantity
            elif record.sign == 'credit' and record.credit_amount > 0:
                record.total = record.credit_amount * record.quantity
            else:
                record.total = 0.0

    @api.depends('folio_id', 'debit_amount', 'credit_amount')
    def _compute_balance(self):
        for folio in self.mapped('folio_id'):
            lines = folio.manual_posting_ids.sorted(key=lambda r: (r.date, r.id))
            running_balance = 0
            for line in lines:
                running_balance += line.balance + (line.debit_amount - line.credit_amount) - line.balance
                line.balance = running_balance

    @api.depends('folio_id', 'debit_without_vat', 'credit_without_vat')
    def _compute_formula_balance(self):
        for folio in self.mapped('folio_id'):
            lines = folio.manual_posting_ids.sorted(key=lambda r: (r.date, r.id))
            running_balance = 0
            for line in lines:
                running_balance += line.debit_without_vat - line.credit_without_vat
                line.formula_balance = running_balance

    @api.depends('booking_id', 'room_id', 'group_booking_id')
    def _compute_booking_info(self):
        for record in self:
            partner_id = False
            reference_contact_ = False

            # Priority 1: If booking_id is set, use its values
            if record.booking_id:
                partner_id = record.booking_id.partner_id
                reference_contact_ = record.booking_id.reference_contact_
            # Priority 2: If room_id is set, look for active booking line
            elif record.room_id:
                booking_line = self.env['room.booking.line'].search([
                    ('room_id', '=', record.room_id.id),
                    ('state_', 'in', ['confirmed', 'block', 'check_in', 'no_show'])
                ], limit=1)

                if booking_line and booking_line.booking_id:
                    partner_id = booking_line.booking_id.partner_id
                    reference_contact_ = booking_line.booking_id.reference_contact_
            # Priority 3: If group_booking_id is set, use its values
            elif record.group_booking_id:
                partner_id = record.group_booking_id.partner_id
                reference_contact_ = record.group_booking_id.reference_contact_

            record.partner_id = partner_id
            record.reference_contact_ = reference_contact_

    @api.depends()
    def _compute_current_time(self):
        """Compute current time in '%H:%M %p' format (e.g., '02:30 PM')"""
        current_time = datetime.now().strftime('%H:%M %p')
        for record in self:
            record.time = current_time

    def _get_master_room_id(self, group_id):
        if group_id:
            system_date = self.env.company.system_date.date()
            # Get all bookings for this group
            bookings = self.env['room.booking'].search([
                ('company_id', '=', self.env.company.id),
                ('group_booking', '=', group_id),
                ('checkin_date', '>=', fields.Datetime.to_datetime(system_date)),
                ('checkin_date', '<', fields.Datetime.to_datetime(system_date + timedelta(days=1))),
            ])

            # Find master bookings (where parent_booking_name is null)
            master_bookings = bookings.filtered(lambda b: not b.parent_booking_name)

            if not master_bookings:
                return False

            # Use the first master booking
            master_booking = master_bookings[0]

            # Return first room if multiple exist
            return master_booking.room_line_ids[0].room_id.id if master_booking.room_line_ids else False

    @api.depends('item_id.taxes')
    def _compute_taxes(self):
        for rec in self:
            rec.taxes = rec.item_id.taxes

    @api.depends('debit_amount', 'credit_amount')
    def _compute_price(self):
        for record in self:
            record.price = record.debit_amount or record.credit_amount

    @api.onchange('booking_id', 'room_id', 'group_booking_id')
    def _onchange_booking_room_or_group(self):
        """Automatically find and suggest folio when booking, room or group changes"""
        if self.booking_id or self.room_id or self.group_booking_id:
            self.folio_id = False
            domain = []
            if self.booking_id:
                domain.append(('booking_ids', 'in', self.booking_id.id))
            if self.room_id:
                domain.append(('room_id', '=', self.room_id.id))
            if self.group_booking_id:
                domain.append(('group_id', '=', self.group_booking_id.id))

            if self.room_id and self.group_booking_id:
                folio = self.env['tz.master.folio'].search([
                    '|',
                    ('room_id', '=', self.room_id.id),
                    ('group_id', '=', self.group_booking_id.id)
                ], limit=1, order='create_date DESC')
            elif domain:
                folio = self.env['tz.master.folio'].search(domain, limit=1, order='create_date DESC')
                # raise UserError(folio)
            else:
                folio = False
            self.folio_id = folio

    @api.onchange('item_id')
    def _onchange_item_id(self):
        if self.item_id:
            self.sign = self.item_id.default_sign

            # Set the amount based on the sign
            if self.sign == 'debit':
                self.debit_amount = self.item_id.default_value
                self.credit_amount = 0.0
            elif self.sign == 'credit':
                self.credit_amount = self.item_id.default_value
                self.debit_amount = 0.0
            self.description = self.item_id.description
            # self.taxes = self.item_id.taxes
        else:
            self.description = False
            # self.taxes = False

    def _create_master_folio(self, room_id):
        """
        Create master folio for manual posting when none exists
        Returns folio ID or raises exception
        """
        system_date = self.env.company.system_date.date()

        # check room id from
        booking_line = self.env['room.booking.line'].search([
            ('room_id', '=', room_id),
            ('checkin_date', '>=', fields.Datetime.to_datetime(system_date)),
            ('checkin_date', '<', fields.Datetime.to_datetime(system_date + timedelta(days=1))),
            ('state_', 'in', ['confirmed', 'block', 'check_in', 'no_show'])
        ], limit=1)

        domain = self._get_domain_filter(room_id)

        if booking_line.booking_id.group_booking:
            folio = self.env['tz.master.folio'].sudo().search(domain, limit=1)
            if not folio:
                company = self.env.company
                prefix = f"{company.name}/"
                folio_name = prefix + (self.env['ir.sequence'].sudo().with_company(company)
                                       .next_by_code('tz.master.folio'))

                folio_vals = {
                    'name': folio_name,
                    'guest_id': booking_line.booking_id.partner_id.id,
                    'rooming_info': booking_line.room_id.name,
                    'check_in': booking_line.checkin_date,
                    'check_out': booking_line.checkout_date,
                    'company_id': company.id,
                    'currency_id': company.currency_id.id,
                    'room_id': room_id,
                    'booking_ids': [(4, booking_line.booking_id.id)],
                }
                # raise UserError("\n".join([f"{key}: {value}" for key, value in folio_vals.items()]))
                folio = self.env['tz.master.folio'].sudo().create(folio_vals)
            return folio
        else:
            return self.env['tz.master.folio'].sudo().search(domain, limit=1)

    def _get_domain_filter(self, room_id):
        return [
            ('company_id', '=', self.env.company.id),
            ('room_id', '=', room_id),
            ('state', '=', 'draft'),
        ]

    def _get_master_folio_for_dummy(self, dummy_id):
        return self.env['tz.master.folio'].sudo().search([
            ('company_id', '=', self.env.company.id),
            ('dummy_id', '=', dummy_id),
        ], limit=1)

    @api.depends('item_id.default_sign')
    def _compute_sign(self):
        for rec in self:
            if rec.item_id.default_sign == 'debit' or rec.item_id.default_sign == 'credit':
                rec.sign = rec.item_id.default_sign

    def compute_manual_taxes(self):
        tax_model = self.env['tz.manual.posting.tax']
        for rec in self:
            taxes = rec.item_id.taxes
            total = rec.debit_amount if rec.sign == 'debit' else rec.credit_amount

            if not total or total <= 0:
                continue

            tax_lines = []
            room_charge = total  # Default if no taxes
            vat_amount = 0.0
            municipality_amount = 0.0

            if taxes:
                # Initialize variables
                vat_rate = 0.0
                municipality_rate = 0.0

                # First pass: get all tax rates
                for tax in taxes:
                    tax_description = tax.description or ""  # Handle False/None descriptions
                    if isinstance(tax_description, str):
                        if 'vat' in tax_description.lower():
                            vat_rate = tax.amount / 100.0
                        else:
                            municipality_rate = tax.amount / 100.0

                # Calculate amounts using original logic
                if vat_rate > 0:
                    vat_amount = total - (total / (1 + vat_rate))
                    room_charge = total - vat_amount

                if municipality_rate > 0:
                    municipality_amount = room_charge - (room_charge / (1 + municipality_rate))
                    room_charge = room_charge - municipality_amount

            # Always add Room Charge or item description (FIRST)
            tax_lines.append({
                'date': rec.date,
                'time': rec.time,
                'description': rec.item_id.description or 'Room Charge',
                'debit_amount': round(room_charge, 2) if rec.sign == 'debit' else 0.0,
                'credit_amount': round(room_charge, 2) if rec.sign == 'credit' else 0.0,
                'balance': round(room_charge, 2) if rec.sign == 'debit' else -round(room_charge, 2),
                'posting_id': rec.id,
                'type': 'amount',
            })

            # Add tax lines if taxes exist
            if taxes:
                for tax in taxes:
                    tax_description = tax.description or ""
                    if isinstance(tax_description, str):
                        if 'vat' in tax_description.lower():
                            tax_lines.append({
                                'date': rec.date,
                                'time': rec.time,
                                'description': tax_description or "VAT",
                                'debit_amount': round(vat_amount, 2) if rec.sign == 'debit' else 0.0,
                                'credit_amount': round(vat_amount, 2) if rec.sign == 'credit' else 0.0,
                                'balance': round(vat_amount, 2) if rec.sign == 'debit' else -round(vat_amount, 2),
                                'posting_id': rec.id,
                                'type': 'vat',
                            })
                        else:
                            tax_lines.append({
                                'date': rec.date,
                                'time': rec.time,
                                'description': tax_description or "Municipality Tax",
                                'debit_amount': round(municipality_amount, 2) if rec.sign == 'debit' else 0.0,
                                'credit_amount': round(municipality_amount, 2) if rec.sign == 'credit' else 0.0,
                                'balance': round(municipality_amount, 2) if rec.sign == 'debit' else -round(
                                    municipality_amount, 2),
                                'posting_id': rec.id,
                                'type': 'municipality',
                            })

            # Create records for non-zero lines
            for line in tax_lines:
                if line['debit_amount'] > 0 or line['credit_amount'] > 0:
                    tax_model.create(line)

            # Update net amounts
            rec.write({
                'debit_without_vat': round(room_charge, 2) if rec.sign == 'debit' else 0.0,
                'credit_without_vat': round(room_charge, 2) if rec.sign == 'credit' else 0.0,
            })

            # rec.update_folio_debit_credit_and_taxes()

    def update_folio_debit_credit_and_taxes(self):
        for rec in self:
            # Filter postings for the same folio and context
            domain = [
                ('company_id', '=', rec.company_id.id),
                ('folio_id', '=', rec.folio_id.id),
                ('date', '=', rec.date),
            ]

            postings = self.search(domain)
            total_debit = sum(post.debit_without_vat for post in postings)
            total_credit = sum(post.credit_without_vat for post in postings)

            # Tax aggregation from tax model
            tax_domain = [
                ('company_id', '=', rec.company_id.id),
                ('posting_id.folio_id', '=', rec.folio_id.id),
                ('date', '=', rec.date),
            ]

            taxes = self.env['tz.manual.posting.tax'].search(tax_domain)
            total_vat = sum(t.balance for t in taxes if t.type == 'vat')
            total_municipality = sum(t.balance for t in taxes if t.type == 'municipality')

            rec.folio_id.sudo().write({
                'total_debit': round(total_debit, 2),
                'total_credit': round(total_credit, 2),
                'value_added_tax': round(total_vat, 2),
                'municipality_tax': round(total_municipality, 2),
            })
            # Trigger the tax totals recompute
            rec.folio_id._compute_tax_totals()

    def unlink(self):
        system_date = self.env.company.system_date.date()
        yesterday = system_date - timedelta(days=1)

        for record in self:
            if record.state == 'posted':
                raise UserError(_("You cannot delete a record that is posted."))
            if record.date == yesterday:
                raise UserError(_("You cannot delete a record from yesterday's date."))

        # Store context values before deletion
        records_context = [(rec.folio_id, rec.company_id, rec.date) for rec in self]

        # Proceed with standard deletion
        res = super(TzHotelManualPosting, self).unlink()

        # Now update each affected folio after deletion
        for folio, company, date in records_context:
            # Use sudo if needed to bypass access rules
            relevant_postings = self.sudo().search([
                ('folio_id', '=', folio.id),
                ('company_id', '=', company.id),
                ('date', '=', date),
            ])

            # Use a dummy record to call your existing method
            # if relevant_postings:
            #     relevant_postings.update_folio_debit_credit_and_taxes()
            # else:
            #     # No remaining postings — reset values to zero
            #     folio.sudo().write({
            #         'total_debit': 0.0,
            #         'total_credit': 0.0,
            #         'value_added_tax': 0.0,
            #         'municipality_tax': 0.0,
            #     })

        return res

    @api.depends('debit_amount', 'credit_amount', 'quantity', 'taxes')
    def _compute_amounts(self):
        for line in self:
            price_unit = (line.debit_amount or line.credit_amount) / (line.quantity or 1)
            taxes = line.taxes.compute_all(
                price_unit,
                line.currency_id,
                line.quantity,
                product=False,
                partner=line.folio_id.guest_id if line.folio_id else None,
            )
            line.price_subtotal = taxes['total_excluded']
            line.tax_amount = taxes['total_included'] - taxes['total_excluded']
            line.price_total = taxes['total_included']

    def _convert_to_tax_base_line_dict(self):
        self.ensure_one()
        price_unit = (self.debit_amount)
        # price_unit = (self.debit_without_vat or self.credit_without_vat) / (self.quantity or 1)
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.folio_id.guest_id,
            currency=self.currency_id,
            product=None,
            taxes=self.taxes,
            price_unit=price_unit,
            quantity=self.quantity,
            discount=0.0,
            price_subtotal=self.price_subtotal,
        )

    def create_account_payment(self):
        for record in self:
            journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)

            # Find a payment method line for this journal and payment type
            payment_method_line = self.env['account.payment.method.line'].search([
                ('journal_id', '=', journal.id),
                ('payment_type', '=', 'inbound' if record.debit_amount > 0 else 'outbound')
            ], limit=1)

            if not payment_method_line:
                raise UserError("No suitable payment method line found for the selected journal.")

            payment_vals = {
                'partner_id': record.partner_id.id,
                'folio_id': record.folio_id.id,
                'amount': record.price_total,
                'date': record.date,
                # 'ref': f'Manual Posting: {record.name} - Booking: {record.booking_id.name if record.booking_id else None}',
                'currency_id': record.currency_id.id,
                'company_id': record.company_id.id,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'journal_id': journal.id,
                'payment_method_line_id': payment_method_line.id,
            }

            payment = self.env['account.payment'].create(payment_vals)
            # payment.action_post()









