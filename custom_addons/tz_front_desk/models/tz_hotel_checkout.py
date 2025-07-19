import logging
from odoo import models, fields, tools, api, _
from odoo.exceptions import UserError
from datetime import date
_logger = logging.getLogger(__name__)

class HotelCheckOut(models.Model):
    _name = 'tz.hotel.checkout'
    _description = 'Hotel Checkout'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _order = 'create_date desc'
    _check_company_auto = True

    name = fields.Char('Room')
    booking_id = fields.Many2one('room.booking', string='Booking Id')
    group_booking_id = fields.Many2one('group.booking', string='Group Booking')
    dummy_id = fields.Many2one('tz.dummy.group', string='Dummy')
    room_id = fields.Many2one('hotel.room', string='Room')
    partner_id = fields.Many2one('res.partner', string='Guest')
    checkin_date = fields.Datetime('Check-in Date')
    checkout_date = fields.Datetime('Check-out Date')
    adult_count = fields.Integer('Adults')
    child_count = fields.Integer('Children')
    infant_count = fields.Integer('Infants')
    rate_code = fields.Many2one('rate.code', string='Rate Code')
    meal_pattern = fields.Many2one('meal.pattern', string='Meal Pattern')
    state = fields.Char('State')
    company_id = fields.Many2one('res.company', string='Company')
    is_cashier_checkout = fields.Boolean(string="Cashier C/O", tracking=True)
    is_suspended_manual_posting = fields.Boolean(string="Suspended MP", tracking=True)
    is_suspended_auto_posting = fields.Boolean(string="Suspended AP", tracking=True)
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('prepaid_credit', 'Pre-Paid / Credit Limit'),
        ('credit_limit', 'Credit Limit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment')
    ], string='Payment Type',
        related='booking_id.payment_type',
        store=True,
        readonly=True)

    folio_id = fields.Many2one(
        'tz.master.folio',
        string="Master Folio",
        compute='_compute_folio_id',
        store=True,
        readonly=False
    )

    group_by_category = fields.Selection([
        ('expected_dep', 'Expected Departure'),
        ('dep_with_balance', 'Departure with Balance'),
        ('dep_zero_balance', 'Zero Balance Departure'),
        ('in_with_balance', 'Checked-in with Balance'),
        ('in_checkout_today', 'Check-in & C/O Today'),
    ], string="Group By Category", compute='_compute_group_by_category', store=True)

    def _compute_group_by_category(self):
        today = self.env.user.company_id.system_date or date.today()
        for rec in self:
            # Initialize as False
            rec.group_by_category = False

            checkout = rec.checkout_date.date() if rec.checkout_date else None
            checkin = rec.checkin_date.date() if rec.checkin_date else None

            if rec.state == 'In' and checkout == today:
                rec.group_by_category = 'expected_dep'
            elif rec.folio_id and rec.folio_id.balance and checkout == today:
                rec.group_by_category = 'dep_with_balance'
            elif rec.folio_id and rec.folio_id.balance == 0 and checkout == today:
                rec.group_by_category = 'dep_zero_balance'
            elif rec.folio_id and rec.folio_id.balance:
                rec.group_by_category = 'in_with_balance'
            elif rec.state == 'In' and checkin == today:
                rec.group_by_category = 'in_checkout_today'

    show_re_checkout = fields.Boolean(compute='_compute_button_visibility')
    show_other_buttons = fields.Boolean(compute='_compute_button_visibility')

    @api.onchange('is_cashier_checkout')
    def _onchange_is_cashier_checkout(self):
        for record in self:
            if record.is_cashier_checkout:
                record.is_suspended_manual_posting = True
                record.is_suspended_auto_posting = True
            else:
                record.is_suspended_manual_posting = False
                record.is_suspended_auto_posting = False

    @api.depends('state', 'checkout_date')
    def _compute_button_visibility(self):
        for record in self:
            if record.state == 'Out':
                # raise UserError((record.checkout_date.date() == self.env.company.system_date.date()))
                record.show_re_checkout = (record.checkout_date.date() == self.env.company.system_date.date())
                record.show_other_buttons = False
            else:
                record.show_re_checkout = False
                record.show_other_buttons = True

    @api.depends('group_booking_id', 'booking_id', 'dummy_id', 'room_id', 'partner_id', 'company_id')
    def _compute_folio_id(self):
        for record in self:
            folio = False

            domain_base = [
                ('company_id', '=', record.company_id.id),
                ('guest_id', '=', record.partner_id.id)
            ]

            if record.group_booking_id:
                folio = self.env['tz.master.folio'].search(
                    domain_base + [('group_id', '=', record.group_booking_id.id)],
                    limit=1
                )

            if not folio and record.room_id and record.booking_id:
                folio = self.env['tz.master.folio'].search(
                    domain_base + [
                        ('room_id', '=', record.room_id.id),
                        ('booking_ids', 'in', record.booking_id.id)
                    ],
                    limit=1
                )

            if not folio and record.dummy_id:
                folio = self.env['tz.master.folio'].search(
                    domain_base + [('dummy_id', '=', record.dummy_id.id)],
                    limit=1
                )

            record.folio_id = folio

    def action_generate_checkout(self):
        self.ensure_one()

        # 1. Fetch all checkout records for the company
        existing_records = self.env['tz.hotel.checkout'].search([
            ('company_id', '=', self.company_id.id)
        ])

        # 2. Get all current booking IDs from the materialized view or table
        self.env.cr.execute("SELECT booking_id FROM tz_checkout WHERE booking_id IS NOT NULL")
        current_booking_ids = {r[0] for r in self.env.cr.fetchall()}

        # 3. Filter existing records to those NOT in current booking_ids
        records_to_remove = existing_records.filtered(
            lambda r: r.booking_id not in current_booking_ids
        )

        # 4. Delete these unmatched records
        records_to_remove.unlink()

        # Step 2: Rebuild the SQL view with filters
        self.generate_data()

        # Step 3: Sync from view to hotel checkout table
        self.env['tz.hotel.checkout'].sync_from_view()

        # Step 4: Redirect to the hotel checkout view
        return self.env.ref('tz_front_desk.action_hotel_checkout').read()[0]

    def generate_data(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
                CREATE OR REPLACE VIEW tz_checkout AS (
                    SELECT
                        ROW_NUMBER() OVER () AS id,
                        booking_id,
                        room_id,
                        group_booking_id,
                        dummy_id,
                        partner_id,
                        checkin_date,
                        checkout_date,
                        adult_count,
                        child_count,
                        infant_count,
                        rate_code,
                        meal_pattern,
                        state,
                        company_id,
                        name
                    FROM (
                        SELECT
                            rb.id AS booking_id,
                            hr.id AS room_id,
                            rb.group_booking_id,
                            NULL::integer AS dummy_id,
                            rb.partner_id,
                            rb.checkin_date,
                            rb.checkout_date,
                            rb.adult_count::integer,
                            rb.child_count::integer,
                            rb.infant_count::integer,
                            rb.rate_code,
                            rb.meal_pattern,
                            rb.state,
                            rb.company_id,
                            COALESCE(hr.name ->> 'en_US', 'Unnamed') AS name
                        FROM room_booking rb
                        JOIN room_booking_line rbl ON rbl.booking_id = rb.id
                        JOIN hotel_room hr ON rbl.room_id = hr.id
                        WHERE rb.state = 'check_in' AND rb.group_booking IS NULL
                
                        UNION ALL
                
                        SELECT
                            NULL AS booking_id,
                            NULL AS room_id,
                            gb.id AS group_booking_id,
                            NULL::integer AS dummy_id,
                            gb.company,
                            gb.first_visit,
                            gb.last_visit,
                            gb.total_adult_count::integer,
                            gb.total_child_count::integer,
                            gb.total_infant_count::integer,
                            gb.rate_code,
                            gb.group_meal_pattern,
                            gb.state::varchar,
                            gb.company_id,
                            COALESCE(gb.group_name ->> 'en_US', 'Unnamed')
                        FROM group_booking gb
                        WHERE gb.status_code = 'confirmed'
                          AND gb.id in (SELECT rb.group_booking from room_booking rb WHERE rb.state = 'check_in')
                
                        UNION ALL
                
                        SELECT
                            NULL AS booking_id,
                            NULL AS room_id,
                            NULL AS group_booking_id,
                            dg.id AS dummy_id,
                            NULL,
                            dg.start_date,
                            dg.end_date,
                            NULL,
                            NULL,
                            NULL,
                            NULL,
                            NULL,
                            dg.state,
                            dg.company_id,
                            dg.description::text
                        FROM tz_dummy_group dg
                        WHERE dg.obsolete = FALSE
                    ) AS unified
                );
        """)

    @api.model
    def sync_from_view(self):
        company_id = self.env.company.id
        view_model = self.env['tz.checkout']
        records = view_model.search([])
        vals = []

        for rec in records:
            # Check for existing record based on the unique key
            domain = []
            if rec.booking_id:
                domain.append(('booking_id', '=', rec.booking_id.id))
            elif rec.group_booking_id:
                domain.append(('group_booking_id', '=', rec.group_booking_id.id))
            elif rec.dummy_id:
                domain.append(('dummy_id', '=', rec.dummy_id.id))
            else:
                continue  # Skip if no identifier is found

            # Avoid duplication
            if self.search(domain, limit=1):
                continue

            vals.append({
                'name': getattr(rec, 'all_name', rec.name),
                'booking_id': rec.booking_id.id if rec.booking_id else False,
                'group_booking_id': rec.group_booking_id.id if rec.group_booking_id else False,
                'dummy_id': rec.dummy_id.id if rec.dummy_id else False,
                'room_id': rec.room_id.id if rec.room_id else False,
                'partner_id': rec.partner_id.id if rec.partner_id else False,
                'checkin_date': rec.checkin_date,
                'checkout_date': rec.checkout_date,
                'adult_count': rec.adult_count,
                'child_count': rec.child_count,
                'infant_count': rec.infant_count,
                'rate_code': rec.rate_code.id if rec.rate_code else False,
                'meal_pattern': rec.meal_pattern.id if rec.meal_pattern else False,
                'state': 'In' if rec.state == 'check_in' else rec.state.capitalize(),
                'company_id': rec.company_id.id if rec.company_id else company_id,
            })

        if vals:
            self.sudo().create(vals)
        return True

    @api.model
    def create(self, vals):
        if vals.get('is_cashier_checkout'):
            vals.update({
                'is_suspended_manual_posting': True,
                'is_suspended_auto_posting': True,
            })
        return super(HotelCheckOut, self).create(vals)

    def write(self, vals):
        if 'is_cashier_checkout' in vals:
            if vals['is_cashier_checkout']:
                vals.update({
                    'is_suspended_manual_posting': True,
                    'is_suspended_auto_posting': True,
                })
            else:
                vals.update({
                    'is_suspended_manual_posting': False,
                    'is_suspended_auto_posting': False,
                })
        for record in self:
            new_value = vals.get('is_cashier_checkout')
            if new_value is not None:  # user is trying to change the field
                if not record.folio_id:
                    raise UserError("No Master Folio linked to this checkout.")

                # User wants to check it (True)
                if new_value and record.folio_id.balance != 0.0:
                    raise UserError("The folio balance is not zero. Cannot proceed with cashier checkout.")
                # User wants to uncheck it (False) — always allowed
        return super(HotelCheckOut, self).write(vals)

    def action_checkout_room(self):
        for record in self:
            if not record.is_cashier_checkout:
                raise UserError("Cashier checkout must be completed first.")
            if record.state == 'In':
                record.state = 'Out'
                record.checkout_date = self.env.company.system_date.date()
            else:
                raise UserError("Room is already checked out.")

    def open_manual_posting(self):
        self.ensure_one()
        # Optional: Find related posting type_id if available (one way of pre-filling or filtering)
        posting_type = self.env['tz.manual.posting.type'].search([
            ('booking_id', '=', self.booking_id.id),
            ('room_id', '=', self.room_id.id),
            ('group_booking_id', '=', self.group_booking_id.id),
            ('dummy_id', '=', self.dummy_id.id)
        ], limit=1)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Manual Posting',
            'res_model': 'tz.manual.posting',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {
                'default_type_id': posting_type.id if posting_type else False,
                'search_default_type_id': posting_type.id if posting_type else False,
                'default_booking_id': self.booking_id.id,
                'default_room_id': self.room_id.id,
                'default_group_booking_id': self.group_booking_id.id,
                'default_dummy_id': self.dummy_id.id,
                'manual_creation': True
            },
            'domain': [('type_id', '=', posting_type.id)] if posting_type else []
        }

    def action_auto_posting(self):
        system_date = self.env.company.system_date.date()
        created_count = 0
        for record in self:
            if record.group_booking_id:
                # make auto posting for all rooms in checkin of the group from room.booking.line
                room_bookings = record.group_booking_id.room_booking_ids.filtered(
                    lambda r: r.state == 'check_in' and r.company_id == self.env.company
                )
                for room_booking in room_bookings:
                    booking_line = self.env['room.booking.line'].search([
                        ('current_company_id', '=', self.env.company.id),
                        ('booking_id', '=', room_booking.id),
                        ('state_', '=', 'check_in'),
                    ], limit=1)
                    folio = self._find_existing_folio(booking_line)
                    forecast = self._get_forecast_data(booking_line, system_date)
                    records_created = self._create_folio_lines(record, folio, forecast)
                    created_count += records_created
            elif record.room_id:
                # make auto posting for the room in checkin from room.booking.line
                booking_line = self.env['room.booking.line'].search([
                    ('current_company_id', '=', self.env.company.id),
                    ('room_id', '=', record.room_id.id),
                    ('state_', '=', 'check_in'),
                ], limit=1)

                folio = self._find_existing_folio(booking_line)
                forecast = self._get_forecast_data(booking_line, system_date)
                records_created = self._create_folio_lines(record, folio, forecast)
                created_count += records_created
        if created_count > 0:
            return self._show_notification(
                f"Successfully posted {created_count} charges",
                "success"
            )
        return self._show_notification("No charges available for posting", "warning")

    def _find_existing_folio(self, booking_line):
        """Find existing folio that is active during the system_date"""
        domain = [
            ('company_id', '=', self.env.company.id),
            ('state', '=', 'draft'),
        ]

        if booking_line.booking_id.group_booking:
            domain.append(('group_id', '=', booking_line.booking_id.group_booking.id))
        else:
            domain.append(('room_id', '=', booking_line.room_id.id))

        return self.env['tz.master.folio'].search(domain, limit=1)

    def _create_new_folio(self, checkout):
        """Create a new folio for the checkout"""
        folio_vals = {
            'company_id': checkout.company_id.id,
            'room_id': checkout.room_id.id if not checkout.group_booking_id else False,
            'group_id': checkout.group_booking_id.id if checkout.group_booking_id else False,
            'partner_id': checkout.partner_id.id,
            'check_in': checkout.checkin_date,
            'check_out': checkout.checkout_date,
            'state': 'draft',
        }
        return self.env['tz.master.folio'].create(folio_vals)

    def _get_forecast_data(self, booking_line, system_date):
        """Get forecast data for the checkout"""
        forecast = self.env['room.rate.forecast'].search([
            ('date', '=', system_date),
            ('room_booking_id', '=', booking_line.booking_id.id),
        ], limit=1)

        return forecast

    def _create_folio_lines(self, checkout, folio, forecast):
        """Create posting lines and return count of actually created records"""
        created_count = 0

        # Get all posting items
        rate_item = checkout.rate_code.rate_posting_item if checkout.rate_code else None
        meal_item = checkout.meal_pattern.meal_posting_item if checkout.meal_pattern else None
        package_items = checkout.rate_code.rate_detail_ids.line_ids.packages_posting_item if checkout.rate_code else None
        fixed_items = checkout.booking_id.posting_item_ids.posting_item_id if checkout.booking_id else None

        # Room Rate
        if rate_item and forecast.rate > 0:
            total_amount = forecast.rate

            if checkout.rate_code.include_meals and forecast.meals > 0:
                total_amount += forecast.meals

            if self._create_posting_line(folio, checkout, rate_item.id, rate_item.description, total_amount):
                created_count += 1

        # Meals
        if meal_item and forecast.meals > 0 and not checkout.rate_code.include_meals:
            if self._create_posting_line(folio, checkout, meal_item.id, meal_item.description, forecast.meals):
                created_count += 1

        # Packages
        if package_items and forecast.packages > 0:
            if self._create_posting_line(folio, checkout, package_items.id, package_items.description,
                                         forecast.packages):
                created_count += 1

        # Fixed Charges
        if fixed_items and forecast.fixed_post > 0:
            if self._create_posting_line(folio, checkout, fixed_items.id, fixed_items.description, forecast.fixed_post):
                created_count += 1

        return created_count

    def _create_posting_line(self, folio, checkout, item_id, description, amount):
        """Create posting line and return True if created, False if skipped"""
        system_date = self.env.company.system_date.date()

        # Check for existing postings first
        existing = self.env['tz.manual.posting'].search([
            ('company_id', '=', checkout.company_id.id),
            ('folio_id', '=', folio.id),
            ('item_id', '=', item_id),
            ('room_id', '=', checkout.room_id.id),
            ('date', '=', system_date),
            ('source_type', '=', 'auto'),
        ], limit=1)

        if existing:
            return False  # Skip if already exists

        if checkout.group_booking_id:
            post_type_domain = [('group_booking_id', '=', checkout.group_booking_id.id if checkout.group_booking_id else False)]
        else:
            post_type_domain = [
                ('room_id', '=', checkout.room_id.id if checkout.room_id else False)]

        posting_type = self.env['tz.manual.posting.type'].search(post_type_domain, limit=1)

        # raise UserError(posting_type)

        item = self.env['posting.item'].browse(item_id)
        if item.default_sign == 'main':
            raise UserError('Please note, main value for Default Sign not accepted, they must only debit or credit')

        manual_posting = f"{self.env.company.name}/{self.env['ir.sequence'].next_by_code('tz.manual.posting')}"
        vals = {
            'name': manual_posting,
            'date': system_date,
            'folio_id': folio.id,
            'item_id': item_id,
            'description': description,
            'booking_id': checkout.booking_id.id,
            'room_id': checkout.room_id.id,
            'group_booking_id': folio.group_id.id if folio.group_id else False,
            'sign': item.default_sign,
            'quantity': 1,
            'source_type': 'auto',
            'total': amount,
            'debit_amount': amount if item.default_sign == 'debit' else 0.0,
            'credit_amount': amount if item.default_sign == 'credit' else 0.0,
            'type_id': posting_type.id
        }
        self.env['tz.manual.posting'].create(vals)
        return True

    def _show_notification(self, message, type_):
        """Helper for showing notifications"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': type_,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_re_checkout_room(self):
        for rec in self:
            if rec.checkout_date.date() != self.env.company.system_date.date():
                raise UserError("You cannot back checkout room if checkout date not equal system date")
        self.write({'state': 'In'})

    def _check_suspended_manual_posting(self, room_id=None, group_id=None, dummy_id=None):
        domain = []
        if room_id:
            domain.append(('room_id', '=', room_id))
        if group_id:
            domain.append(('group_booking_id', '=', group_id))
        if dummy_id:
            domain.append(('dummy_id', '=', dummy_id))

        if domain:
            domain.append(('is_suspended_manual_posting', '=', True))
            suspended_checkouts = self.env['tz.hotel.checkout'].sudo().search(domain, limit=1)
            return bool(suspended_checkouts)
        return False

    def _check_suspended_auto_posting(self, room_id=None, group_id=None):
        domain = []
        if room_id:
            domain.append(('room_id', '=', room_id))
        if group_id:
            domain.append(('group_booking_id', '=', group_id))

        if domain:
            domain.append(('is_suspended_auto_posting', '=', True))
            suspended_checkouts = self.env['tz.hotel.checkout'].sudo().search(domain, limit=1)
            return bool(suspended_checkouts)
        return False
