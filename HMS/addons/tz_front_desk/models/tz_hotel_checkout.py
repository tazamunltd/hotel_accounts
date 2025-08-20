import logging
from odoo import models, fields, tools, api, _
from odoo.exceptions import UserError
from datetime import date, datetime

_logger = logging.getLogger(__name__)

class TzCheckout(models.Model):
    _name = 'tz.checkout'
    _description = 'FrontDesk Checkout'
    _auto = False
    _check_company_auto = True

    name = fields.Char('Room')
    all_name = fields.Char('Room', compute='_compute_name', store=False)
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
    state = fields.Char('Status')
    company_id = fields.Many2one('res.company', string='Company')
    v_state = fields.Char('Status', compute='_compute_v_state', store=False)
    folio_id = fields.Many2one('tz.master.folio', string="Master Folio")

    def create_or_replace_view(self):
        self.env.cr.execute("DROP MATERIALIZED VIEW IF EXISTS tz_checkout CASCADE")

        company_id = self.env.company.id

        query = f"""
            CREATE MATERIALIZED VIEW tz_checkout AS (
                SELECT
                    id,
                    name,
                    booking_id,
                    room_id,
                    group_booking_id,
                    dummy_id,
                    folio_id,
                    partner_id,
                    checkin_date,
                    checkout_date,
                    adult_count,
                    child_count,
                    infant_count,
                    rate_code,
                    meal_pattern,
                    state,
                    company_id
                FROM (
                    -- Room Booking block (include individual bookings and group bookings that have a master folio)
                    SELECT
                        (rb.id * 10 + 1) AS id,
                        COALESCE(hr.name ->> 'en_US', 'Unnamed') AS name,
                        rb.id AS booking_id,
                        hr.id AS room_id,
                        rb.group_booking_id,
                        NULL::integer AS dummy_id,
                        folio.id AS folio_id,
                        rb.partner_id,
                        rb.checkin_date,
                        rb.checkout_date,
                        rb.adult_count::integer,
                        rb.child_count::integer,
                        rb.infant_count::integer,
                        rb.rate_code AS rate_code,  -- Removed varchar cast for Many2one
                        rb.meal_pattern AS meal_pattern,  -- Removed varchar cast for Many2one
                        rb.state::varchar AS state,
                        rb.company_id
                    FROM room_booking rb
                    JOIN room_booking_line rbl ON rbl.booking_id = rb.id
                    JOIN hotel_room hr ON rbl.room_id = hr.id
                    LEFT JOIN tz_master_folio folio ON folio.room_id = rbl.room_id
                    WHERE rb.state = 'check_in'
                      AND rb.company_id = {company_id}
                      AND (
                          rb.group_booking IS NULL
                          OR (rb.group_booking IS NOT NULL AND folio.id IS NOT NULL)
                      )

                    UNION ALL

                    -- Group Booking block (fixed to prevent duplicates)
                    SELECT DISTINCT ON (gb.id)
                        (gb.id * 10 + 2) AS id,
                        COALESCE(gb.group_name ->> 'en_US', 'Unnamed') AS name,
                        NULL::integer AS booking_id,
                        NULL::integer AS room_id,
                        gb.id AS group_booking_id,
                        NULL::integer AS dummy_id,
                        folio.id AS folio_id,
                        gb.company AS partner_id,
                        gb.first_visit AS checkin_date,
                        gb.last_visit AS checkout_date,
                        gb.total_adult_count::integer,
                        gb.total_child_count::integer,
                        gb.total_infant_count::integer,
                        gb.rate_code AS rate_code,  -- Removed varchar cast for Many2one
                        gb.group_meal_pattern AS meal_pattern,  -- Removed varchar cast for Many2one
                        gb.status_code::varchar AS state,
                        gb.company_id
                    FROM group_booking gb
                    LEFT JOIN LATERAL (
                        SELECT id 
                        FROM tz_master_folio 
                        WHERE group_id = gb.id
                        ORDER BY id
                        LIMIT 1
                    ) folio ON true
                    WHERE gb.status_code = 'confirmed'
                      AND gb.company_id = {company_id}
                      AND gb.id IN (
                          SELECT rb.group_booking FROM room_booking rb
                          WHERE rb.state = 'check_in'
                            AND rb.company_id = {company_id}
                      )

                    UNION ALL

                    -- Dummy Group block
                    SELECT
                        (dg.id * 10 + 3) AS id,
                        dg.description::text AS name,
                        NULL::integer AS booking_id,
                        NULL::integer AS room_id,
                        NULL::integer AS group_booking_id,
                        dg.id AS dummy_id,
                        folio.id AS folio_id,
                        dg.partner_id,
                        dg.start_date AS checkin_date,
                        dg.end_date AS checkout_date,
                        NULL::integer AS adult_count,
                        NULL::integer AS child_count,
                        NULL::integer AS infant_count,
                        NULL::integer AS rate_code,  -- Changed to integer for Many2one
                        NULL::integer AS meal_pattern,  -- Changed to integer for Many2one
                        dg.state::varchar AS state,
                        dg.company_id
                    FROM tz_dummy_group dg
                    LEFT JOIN tz_master_folio folio ON folio.dummy_id = dg.id
                    WHERE dg.obsolete = FALSE
                      AND dg.company_id = {company_id}
                ) AS unified
            )
        """

        self.env.cr.execute(query)
        self.env.cr.execute("REFRESH MATERIALIZED VIEW tz_checkout")

    def _setup_change_triggers(self):
        """Setup automatic refresh triggers on source tables"""
        try:
            for table in ['room_booking', 'group_booking', 'tz_dummy_group', 'hotel_room', 'tz_master_folio',
                          'rate.code', 'meal.pattern']:
                try:
                    # First drop the trigger if it exists
                    self.env.cr.execute(f"""
                        DROP TRIGGER IF EXISTS tz_checkout_refresh_trigger ON {table};
                    """)
                    # Then create the new trigger
                    self.env.cr.execute(f"""
                        CREATE TRIGGER tz_checkout_refresh_trigger
                        AFTER INSERT OR UPDATE OR DELETE ON {table}
                        FOR EACH STATEMENT EXECUTE FUNCTION tz_refresh_checkout();
                    """)
                except Exception as trigger_error:
                    _logger.warning("Failed to create trigger on %s: %s", table, str(trigger_error))
                    continue
            _logger.info("Successfully created all refresh triggers")
        except Exception as e:
            _logger.error("Failed to setup change triggers: %s", str(e))
            raise UserError(_("Failed to setup automatic refresh triggers. Check logs for details."))

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Ensure fresh data when dropdown is opened"""
        self.refresh_view()
        return super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)

    def refresh_view(self):
        """Public method to manually refresh the view"""
        self.create_or_replace_view()
        return True

    def schedule_refresh_materialized_view(self):
        """Called by scheduled action to refresh the view"""
        self.env.cr.execute("REFRESH MATERIALIZED VIEW tz_checkout")
        self.env.cr.commit()

class HotelCheckOut(models.Model):
    _name = 'tz.hotel.checkout'
    _description = 'Hotel Checkout'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _order = 'create_date desc'
    _check_company_auto = True

    source_id = fields.Integer(string="Source ID", index=True)
    name = fields.Char('Room')
    booking_id = fields.Many2one('room.booking', string='Booking Id')
    group_booking_id = fields.Many2one('group.booking', string='Group Booking')
    dummy_id = fields.Many2one('tz.dummy.group', string='Dummy')
    folio_id = fields.Many2one('tz.master.folio', string="Master Folio")
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

    # move_id = fields.Many2one('account.move', string='Invoice #')
    move_id = fields.Many2one('account.move', string='Invoice #', readonly=True)

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
                record.show_re_checkout = (record.checkout_date.date() == self.env.company.system_date.date())
                record.show_other_buttons = False
            else:
                record.show_re_checkout = False
                record.show_other_buttons = True

    @api.model
    def sync_with_materialized_view(self):
        """Sync with the materialized view using ORM with consistent field handling."""
        company_id = self.env.company.id

        # Fetch all relevant rows from the materialized view
        view_records = self.env['tz.checkout'].sudo().search([
            ('company_id', '=', company_id),
        ])

        for view in view_records:
            # Create domain based on source_id and other identifying fields
            domain = [
                ('source_id', '=', view.id),
                ('company_id', '=', company_id),
            ]

            existing = self.sudo().search(domain, limit=1)

            # Prepare values for creation or update - ensure all fields are properly formatted
            vals = {
                'source_id': view.id,
                'name': view.name,
                'booking_id': view.booking_id.id if view.booking_id else False,
                'room_id': view.room_id.id if view.room_id else False,
                'group_booking_id': view.group_booking_id.id if view.group_booking_id else False,
                'dummy_id': view.dummy_id.id if view.dummy_id else False,
                'folio_id': view.folio_id.id, # if view.folio_id else False
                'partner_id': view.partner_id.id if view.partner_id else False,
                'checkin_date': view.checkin_date,
                'checkout_date': view.checkout_date,
                'adult_count': view.adult_count,
                'child_count': view.child_count,
                'infant_count': view.infant_count,
                'rate_code': view.rate_code.id if view.rate_code else False,
                'meal_pattern': view.meal_pattern.id if view.meal_pattern else False,
                'company_id': company_id,
                'state': 'In' if view.state in ('check_in', 'confirmed') else view.state.capitalize(),
            }

            # raise UserError(str(vals))

            if existing:
                existing.sudo().write(vals)
            else:
                self.sudo().create(vals)

        _logger.info("Hotel checkout successfully synced with materialized view for company_id %s", company_id)
        return True

    @api.model
    def sync_with_materialized_viewX(self):
        company_id = self.env.company.id
        view_model = self.env['tz.checkout']
        records = view_model.search([])

        for rec in records:
            domain = []
            if rec.booking_id:
                domain.append(('booking_id', '=', rec.booking_id.id))
            if rec.room_id:
                domain.append(('room_id', '=', rec.room_id.id))
            if rec.group_booking_id:
                domain.append(('group_booking_id', '=', rec.group_booking_id.id))
            if rec.dummy_id:
                domain.append(('dummy_id', '=', rec.dummy_id.id))

            # Prepare values for creation or update
            vals = {
                'name': rec.name,
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
                'state': 'In' if rec.state in ('check_in', 'confirmed') else rec.state.capitalize(),
                'company_id': rec.company_id.id if rec.company_id else company_id,
                'folio_id': rec.folio_id.id if rec.folio_id else False,
            }

            existing = self.search(domain, limit=1)
            if existing:
                existing.write(vals)  # Update existing record
            else:
                self.sudo().create(vals)  # Create new record

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
            if new_value is not None:
                if new_value and record.folio_id.balance != 0.0:
                    raise UserError(_("The folio balance is not zero. Cannot proceed with cashier checkout."))
        return super(HotelCheckOut, self).write(vals)

    def action_checkout_room(self):
        booking = self.booking_id
        system_date = self.env.company.system_date.date()

        booking.write({
            "state": "check_out",
            "checkout_date": system_date,
        })
        booking.room_line_ids.write({"state_": "check_out"})
        self.write({"state": "Out", "checkout_date": system_date})
        self.get_partner_manual_postings()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking Checked Out Successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

        # if self.checkout_date and self.checkout_date.date() > system_date:
        #     return {
        #         'name': _('Confirm Early Check-Out'),
        #         'type': 'ir.actions.act_window',
        #         'res_model': 'confirm.early.checkout.wizard',
        #         'view_mode': 'form',
        #         'target': 'new',
        #         'context': {
        #             'default_booking_id': booking.id,
        #         },
        #     }
        # else:
        #     booking.write({
        #         "state": "check_out",
        #         "checkout_date": system_date,
        #     })
        #     booking.room_line_ids.write({"state_": "check_out"})
        #     self.write({"state": "Out", "checkout_date": system_date})
        #     self.get_partner_manual_postings()
        #     return {
        #         'type': 'ir.actions.client',
        #         'tag': 'display_notification',
        #         'params': {
        #             'type': 'success',
        #             'message': _("Booking Checked Out Successfully!"),
        #             'next': {'type': 'ir.actions.act_window_close'},
        #         }
        #     }

    def open_manual_posting(self):
        self.ensure_one()
        # Search for matching posting type
        domain = []
        if self.booking_id:
            domain.append(('booking_id', '=', self.booking_id.id))
        if self.room_id:
            domain.append(('room_id', '=', self.room_id.id))
        if self.group_booking_id:
            domain.append(('group_booking_id', '=', self.group_booking_id.id))
        if self.dummy_id:
            domain.append(('dummy_id', '=', self.dummy_id.id))

        # Find or create posting type record
        posting_type = self.env['tz.manual.posting.type'].search(domain, limit=1)

        if not posting_type:
            # Create new posting type if none exists
            posting_type = self.env['tz.manual.posting.type'].create({
                'booking_id': self.booking_id.id if self.booking_id else False,
                'room_id': self.room_id.id if self.room_id else False,
                'group_booking_id': self.group_booking_id.id if self.group_booking_id else False,
                'dummy_id': self.dummy_id.id if self.dummy_id else False,
                'company_id': self.company_id.id
            })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Manual Posting',
            'res_model': 'tz.manual.posting',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {
                'default_type_id': posting_type.id,
                'search_default_type_id': posting_type.id,
                'default_booking_id': self.booking_id.id,
                'default_room_id': self.room_id.id,
                'default_group_booking_id': self.group_booking_id.id,
                'default_dummy_id': self.dummy_id.id,
                'manual_creation': True
            },
            'domain': [('type_id', '=', posting_type.id)]
        }

    def action_auto_posting(self):
        system_date = self.env.company.system_date.date()
        created_count = 0
        for record in self:
            if record.group_booking_id:
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
        return self._show_notification(_("No charges available for posting"), "warning")

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

        if not existing:
            # Build domain to find matching posting type
            posting_type = self.env['tz.manual.posting.type'].search([
                ('company_id', '=', checkout.booking_id.company_id.id),
                ('booking_id', '=', checkout.booking_id.id),
                ('room_id', '=', checkout.room_id.id),
                ('name', '!=', False),
            ], limit=1)

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
                'type_id': posting_type.id  # Linking to posting type instead of posting room
            }
            self.env['tz.manual.posting'].create(vals)
            return True
        return False  # Skip if already exists

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
        booking = self.booking_id
        for rec in self:
            if rec.checkout_date.date() != self.env.company.system_date.date():
                raise UserError(_("You cannot back checkout room if checkout date not equal system date"))

        booking.write({
            "state": "check_in",
        })
        booking.room_line_ids.write({"state_": "check_in"})
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

    def get_partner_manual_postings(self):
        """
        Get all manual postings related to the partner_id of this checkout record.
        Consolidate postings that share the same item description and amount into a single line.
        Exclude any posting with item description 'Cash'.
        Only include postings where the related master folio has a balance of 0.
        """
        self.ensure_one()

        postings = self.env['tz.manual.posting'].search([
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', self.partner_id.id)
        ])

        # Filter only postings whose folio has a balance of 0 using sudo
        postings = postings.filtered(
            lambda p: p.folio_id and p.folio_id.sudo().balance == 0
        )

        result = {
            'partner': {
                'id': self.partner_id.id,
                'name': self.partner_id.name,
                'contact_reference': self.booking_id.reference_contact_ if self.booking_id else '',
                'hotel_booking_id': self.booking_id or '',
                'group_booking_name': self.group_booking_id.name if self.group_booking_id else '',
                'parent_booking_name': self.booking_id.parent_booking_name if self.booking_id else '',
                'room_numbers': self.booking_id.room_ids_display if self.booking_id else '',
            },
            'postings': []
        }

        consolidated = {}
        for posting in postings:
            if posting.item_id.description.strip().lower() == 'cash':
                continue

            amount = posting.debit_amount if posting.debit_amount > 0 else posting.credit_amount
            key = (posting.item_id.description, amount)

            if key in consolidated:
                consolidated[key]['quantity'] += posting.quantity
                consolidated[key]['total'] += posting.total
            else:
                consolidated[key] = {
                    'id': posting.id,
                    'item_id': posting.item_id,
                    'date': str(posting.date),
                    'time': posting.time,
                    'item': posting.item_id.description,
                    'debit': posting.debit_amount,
                    'credit': posting.credit_amount,
                    'quantity': posting.quantity,
                    'taxes': posting.taxes,
                    'total': posting.total,
                }

        result['postings'] = list(consolidated.values())

        self.create_invoice(result['partner'], result['postings'])

    def _get_default_journal(self):
        journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
        return journal

    def create_invoice(self, partner, postings):
        default_journal = self._get_default_journal()
        if not default_journal:
            raise UserError(_('No accounting journal with type "Sale" defined !'))

        # Find default income account
        income_account = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('account_type', '=', 'income'),
        ], limit=1)

        if not income_account:
            raise UserError(_('No income account found for this company.'))

        invoice_lines = []
        for line in postings:

            product = line['item_id'].product_id if line.get('item_id') else False

            if not product:
                raise UserError(
                    _('Missing Sales Product for item "%s". Please set a product_id on the Posting Item.') % (
                        line.get('item', 'Unknown')))

            invoice_lines.append((0, 0, {
                'product_id': product.id,
                'posting_item_id': line['item_id'].id if line.get('item_id') else False,
                'name': line['item'],
                'quantity': line['quantity'],
                'price_unit': line['debit'] - line['credit'],
                'posting_default_value': line['debit'] - line['credit'],
                'tax_ids': [(6, 0, [tax.id for tax in line['taxes']])] if line['taxes'] else [],
                'account_id': income_account.id,
            }))

        invoice = self.env['account.move'].sudo().create({
            'move_type': 'out_invoice',
            'journal_id': default_journal.id,
            'partner_id': partner['id'],
            'hotel_booking_id': partner['hotel_booking_id'].id if partner.get('hotel_booking_id') else False,
            'group_booking_name': partner['group_booking_name'],
            'parent_booking_name': partner['parent_booking_name'],
            'room_numbers': partner['room_numbers'],
            'invoice_date': self.env.company.system_date.date(),
            'date': self.env.company.system_date.date(),
            'ref': f"Invoice for #: {partner['name']}",
            'invoice_line_ids': invoice_lines,
        })

        self.write({'move_id': invoice.id})

        return invoice




