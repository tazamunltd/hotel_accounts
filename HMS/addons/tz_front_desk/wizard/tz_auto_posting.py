from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, time
import logging
_logger = logging.getLogger(__name__)

class AutoPostingWizard(models.TransientModel):
    _name = 'auto.posting.wizard'
    _description = 'Auto Posting Wizard'

    # Room selection fields
    all_rooms = fields.Boolean(string="All Rooms", default=True)
    room_from = fields.Many2one('hotel.room', string="From Room")
    room_to = fields.Many2one('hotel.room', string="To Room")

    # Group selection fields
    all_groups = fields.Boolean(string="All Groups", default=True)
    group_from = fields.Many2one('group.booking', string="From Group")
    group_to = fields.Many2one('group.booking', string="To Group")

    # Charge type selection
    include_rates = fields.Boolean(string="Room Rates", default=True)
    include_meals = fields.Boolean(string="Meals", default=True)
    include_packages = fields.Boolean(string="Packages", default=True)
    include_fixed = fields.Boolean(string="Fixed Post", default=True)

    @api.onchange('all_rooms')
    def _onchange_all_rooms(self):
        if self.all_rooms:
            self.room_from = False
            self.room_to = False

    @api.onchange('all_groups')
    def _onchange_all_groups(self):
        if self.all_groups:
            self.group_from = False
            self.group_to = False

    @api.onchange('all_groups')
    def _onchange_all_groups(self):
        if self.all_groups:
            self.group_from = False
            self.group_to = False

    def _find_existing_folio(self, booking_line):
        """Find existing folio - optimized version"""
        domain = [
            ('company_id', '=', self.env.company.id),
            ('state', '=', 'draft'),
        ]

        if booking_line.booking_id.group_booking:
            # For group bookings, find the master folio for the group
            domain.extend([
                ('group_id', '=', booking_line.booking_id.group_booking.id),
                ('room_id', '=', False)  # Master folio has no room assigned
            ])
        else:
            # For individual bookings, find folio by room
            domain.append(('room_id', '=', booking_line.room_id.id))

        return self.env['tz.master.folio'].search(domain, limit=1)

    def action_auto_postingXX(self):
        global total_created
        self.ensure_one()
        system_date = self.env.company.system_date.date()
        start_datetime = datetime.combine(system_date, time.min)
        end_datetime = datetime.combine(system_date, time.max)

        # print('start_datetime', start_datetime)
        # print('end_datetime', end_datetime)

        booking_lines = self.env['room.booking.line'].search([
            ('current_company_id', '=', self.env.company.id),
            ('checkin_date', '>=', start_datetime),
            ('checkin_date', '<=', end_datetime),
            ('state_', '=', 'check_in'),
        ])

        total_created = 0

        for booking_line in booking_lines:
            forecast = self.get_forecast(system_date, booking_line.booking_id.id)
            if not forecast:
                raise UserError(_('No forecast data found for selected date'))


            # Group booking vs. Room booking
            if booking_line.booking_id.group_booking:
                folio = self._find_existing_folio(booking_line)

                created_count = self._create_folio_lines(booking_line, folio, forecast)
                _logger.info("Group booking posting created for Room %s in Group %s",
                             booking_line.room_id.display_name,
                             booking_line.booking_id.group_booking.name)
            else:
                folio = self._find_existing_folio(booking_line)
                # print(folio)

                created_count = self._create_folio_lines(booking_line, folio, forecast)
                _logger.info("Room booking posting created for Room %s (Booking %s)",
                             booking_line.room_id.display_name,
                             booking_line.booking_id.name)

            total_created += created_count

        # Final notification
        if total_created > 0:
            return self._show_notification(
                f"Successfully posted charges for {total_created} rooms",
                "success"
            )
        else:
            return self._show_notification(
                "No charges were posted - no valid booking lines found matching criteria",
                "warning"
            )

        # print(booking_lines)

        # Fetch forecasts for today and this company
        # forecasts = self.env['room.rate.forecast'].search([
        #     ('company_id', '=', self.env.company.id),
        #     ('date', '=', system_date),
        #     ('state', '=', 'draft'),
        # ])
        #
        # if not forecasts:
        #     raise UserError(_('No forecast data found for selected date'))
        #
        # total_created = 0
        #
        # for forecast in forecasts:
        #     booking_line = self.env['room.booking.line'].search([
        #         ('current_company_id', '=', self.env.company.id),
        #         ('booking_id', '=', forecast.room_booking_id.id),
        #         ('state_', '=', 'check_in'),
        #     ], limit=1)
        #
        #     print(booking_line)
        #
        #     if not booking_line:
        #         continue
        #
        #     # Group booking vs. Room booking
        #     if booking_line.booking_id.group_booking:
        #         folio = self._find_existing_folio(booking_line)
        #
        #         created_count = self._create_folio_lines(booking_line, folio, forecast)
        #         _logger.info("Group booking posting created for Room %s in Group %s",
        #                      booking_line.room_id.display_name,
        #                      booking_line.booking_id.group_booking.name)
        #     else:
        #         folio = self._find_existing_folio(booking_line)
        #
        #         created_count = self._create_folio_lines(booking_line, folio, forecast)
        #         _logger.info("Room booking posting created for Room %s (Booking %s)",
        #                      booking_line.room_id.display_name,
        #                      booking_line.booking_id.name)
        #
        #     total_created += created_count
        #
        # # Final notification
        # if total_created > 0:
        #     return self._show_notification(
        #         f"Successfully posted charges for {total_created} rooms",
        #         "success"
        #     )
        # else:
        #     return self._show_notification(
        #         "No charges were posted - no valid booking lines found matching criteria",
        #         "warning"
        #     )

    def action_auto_posting(self):
        self.ensure_one()
        system_date = self.env.company.system_date.date()

        # Fetch forecasts for today and this company
        forecasts = self.env['room.rate.forecast'].search([
            ('date', '=', system_date),
            # ('company_id', '=', self.env.company.id),
        ])

        print(forecasts)

        if not forecasts:
            raise UserError(_('No forecast data found for selected date'))

        total_created = 0

        for forecast in forecasts:
            booking_line = self.env['room.booking.line'].search([
                ('current_company_id', '=', self.env.company.id),
                ('booking_id', '=', forecast.room_booking_id.id),
                ('state_', '=', 'check_in'),
            ], limit=1)

            if booking_line:
                # Group booking vs. Room booking
                if booking_line.booking_id.group_booking:
                    folio = self._find_existing_folio(booking_line)

                    created_count = self._create_folio_lines(booking_line, folio, forecast)
                    _logger.info("Group booking posting created for Room %s in Group %s",
                                 booking_line.room_id.display_name,
                                 booking_line.booking_id.group_booking.name)
                else:
                    folio = self._find_existing_folio(booking_line)

                    created_count = self._create_folio_lines(booking_line, folio, forecast)
                    _logger.info("Room booking posting created for Room %s (Booking %s)",
                                 booking_line.room_id.display_name,
                                 booking_line.booking_id.name)

                total_created += created_count

        # Final notification
        if total_created > 0:
            return self._show_notification(
                f"Successfully posted charges for {total_created} rooms",
                "success"
            )
        else:
            return self._show_notification(
                "No charges were posted - no valid booking lines found matching criteria",
                "warning"
            )

    def action_auto_postingX(self):
        self.ensure_one()
        system_date = self.env.company.system_date.date()

        # Fetch forecasts for today and this company
        forecasts = self.env['room.rate.forecast'].search([
            ('date', '=', system_date),
            ('company_id', '=', self.env.company.id),
        ])

        if not forecasts:
            return self._show_notification(
                "No forecasts found for today's system date",
                "warning"
            )

        total_created = 0

        for forecast in forecasts:
            for booking_line in forecast.booking_line_ids:
                if booking_line.state_ != 'check_in':
                    continue

                # Group booking vs. Room booking
                if booking_line.booking_id.group_booking:
                    folio = self._find_existing_folio(booking_line)

                    created_count = self._create_folio_lines(booking_line, folio, forecast)
                    _logger.info("Group booking posting created for Room %s in Group %s",
                                 booking_line.room_id.display_name,
                                 booking_line.booking_id.group_booking.name)
                else:
                    folio = self._find_existing_folio(booking_line)

                    created_count = self._create_folio_lines(booking_line, folio, forecast)
                    _logger.info("Room booking posting created for Room %s (Booking %s)",
                                 booking_line.room_id.display_name,
                                 booking_line.booking_id.name)

                total_created += created_count

        # Final notification
        if total_created > 0:
            return self._show_notification(
                f"Successfully posted charges for {total_created} rooms",
                "success"
            )
        else:
            return self._show_notification(
                "No charges were posted - no valid booking lines found matching criteria",
                "warning"
            )

    def _find_existing_folioX(self, booking_line):
        """Find existing folio - for group bookings, use the group's master folio"""
        domain = [
            ('company_id', '=', self.env.company.id),
            ('state', '=', 'draft'),
        ]

        if booking_line.booking_id.group_booking:
            # For group bookings, find the master folio for the group
            domain.append(('group_id', '=', booking_line.booking_id.group_booking.id))
            domain.append(('room_id', '=', False))  # Master folio has no room assigned
            return self.env['tz.master.folio'].search(domain, limit=1)
        else:
            # For individual bookings, find folio by room
            domain.append(('room_id', '=', booking_line.room_id.id))
            return self.env['tz.master.folio'].search(domain, limit=1)

    def _create_folio_lines(self, booking_line, folio, forecast):
        """Create posting lines and return count of actually created records"""
        booking = booking_line.booking_id
        created_count = 0

        # Get all posting items
        rate_item = booking.rate_code.rate_posting_item if booking.rate_code else None
        meal_item = booking.meal_pattern.meal_posting_item if booking.meal_pattern else None
        package_items = booking.rate_code.rate_detail_ids.line_ids.packages_posting_item if booking.rate_code else None
        fixed_items = booking.posting_item_ids.posting_item_id

        # Room Rate
        if rate_item and self.include_rates and forecast.rate > 0:
            total_amount = forecast.rate
            if forecast.room_booking_id.rate_code.include_meals and forecast.meals > 0:
                total_amount += forecast.meals

            if self._create_posting_line(folio, booking_line, rate_item.id, rate_item.description, total_amount):
                created_count += 1
        elif self.include_rates and forecast.rate > 0 and not rate_item:
            raise UserError(_("No posting item configured for rate code."))

        # Meals
        if meal_item and self.include_meals and forecast.meals > 0 and not forecast.room_booking_id.rate_code.include_meals:
            if self._create_posting_line(folio, booking_line, meal_item.id, meal_item.description, forecast.meals):
                created_count += 1
        elif self.include_meals and forecast.meals > 0 and not forecast.room_booking_id.rate_code.include_meals and not meal_item:
            raise UserError(_("No posting item configured for meal pattern"))

        # Packages
        if package_items and self.include_packages and forecast.packages > 0:
            if self._create_posting_line(folio, booking_line, package_items.id, package_items.description,
                                         forecast.packages):
                created_count += 1
        elif self.include_packages and forecast.packages > 0 and not package_items:
            raise UserError(_("No posting item configured for package"))

        # Fixed Charges
        if fixed_items and self.include_fixed and forecast.fixed_post > 0:
            if self._create_posting_line(folio, booking_line, fixed_items.id, fixed_items.description,
                                         forecast.fixed_post):
                created_count += 1
        elif self.include_fixed and forecast.fixed_post > 0 and not fixed_items:
            raise UserError(_("No posting item configured for fixed post"))

        return created_count

    def _create_posting_line(self, folio, booking_line, item_id, description, amount):
        """Create posting line and return True if created, False if skipped"""
        system_date = self.env.company.system_date.date()

        # Check for existing postings first
        existing_domain = [
            ('company_id', '=', booking_line.booking_id.company_id.id),
            ('folio_id', '=', folio.id),
            ('item_id', '=', item_id),
            ('date', '=', system_date),
            ('source_type', '=', 'auto'),
            ('room_id', '=', booking_line.room_id.id),
        ]

        existing = self.env['tz.manual.posting'].search(existing_domain, limit=1)

        if not existing:
            # Find the correct posting type - CRITICAL FIX: Always include room_id
            if booking_line.booking_id.group_booking:
                # For group bookings, search with BOTH group_booking_id AND room_id
                posting_type = self.env['tz.manual.posting.type'].search([
                    ('company_id', '=', booking_line.booking_id.company_id.id),
                    ('group_booking_id', '=', booking_line.booking_id.group_booking.id),
                    ('room_id', '=', booking_line.room_id.id),  # MUST include room_id
                ], limit=1)

                # If not found, try to find any posting type for this group and room
                if not posting_type:
                    posting_type = self.env['tz.manual.posting.type'].search([
                        ('company_id', '=', booking_line.booking_id.company_id.id),
                        ('room_id', '=', booking_line.room_id.id),
                    ], limit=1)
            else:
                # For individual bookings
                posting_type = self.env['tz.manual.posting.type'].search([
                    ('company_id', '=', booking_line.booking_id.company_id.id),
                    ('booking_id', '=', booking_line.booking_id.id),
                    ('room_id', '=', booking_line.room_id.id),
                ], limit=1)

            item = self.env['posting.item'].browse(item_id)
            if item.default_sign == 'main':
                raise UserError('Please note, main value for Default Sign not accepted, they must only debit or credit')

            manual_posting = f"{self.env.company.name}/{self.env['ir.sequence'].next_by_code('tz.manual.posting')}"

            # Create with only type_id - computed fields will be set automatically
            vals = {
                'name': manual_posting,
                'date': system_date,
                'folio_id': folio.id,
                'item_id': item_id,
                'description': description,
                'sign': item.default_sign,
                'quantity': 1,
                'source_type': 'auto',
                'total': amount,
                'debit_amount': amount if item.default_sign == 'debit' else 0.0,
                'credit_amount': amount if item.default_sign == 'credit' else 0.0,
                'type_id': posting_type.id if posting_type else False
            }

            # Debug: Check what posting_type we found
            _logger.info("Creating posting with type_id: %s, room_id on type: %s",
                         posting_type.id if posting_type else 'None',
                         posting_type.room_id.id if posting_type and posting_type.room_id else 'None')

            posting_record = self.env['tz.manual.posting'].create(vals)

            # Verify the computed fields were set correctly
            _logger.info("Created posting ID %s - room_id: %s, booking_id: %s, group_booking_id: %s",
                         posting_record.id,
                         posting_record.room_id.id if posting_record.room_id else 'None',
                         posting_record.booking_id.id if posting_record.booking_id else 'None',
                         posting_record.group_booking_id.id if posting_record.group_booking_id else 'None')

            return True
        return False

    def _create_posting_lineX(self, folio, booking_line, item_id, description, amount):
        """Create posting line and return True if created, False if skipped"""
        system_date = self.env.company.system_date.date()

        # Check for existing postings first
        existing_domain = [
            ('company_id', '=', booking_line.booking_id.company_id.id),
            ('folio_id', '=', folio.id),
            ('item_id', '=', item_id),
            ('date', '=', system_date),
            ('source_type', '=', 'auto'),
            ('room_id', '=', booking_line.room_id.id),  # Check for same room in same folio
        ]

        existing = self.env['tz.manual.posting'].search(existing_domain, limit=1)

        if not existing:
            # Find the correct posting type
            if booking_line.booking_id.group_booking:
                # For group bookings, use the group's posting type
                posting_type = self.env['tz.manual.posting.type'].search([
                    ('company_id', '=', booking_line.booking_id.company_id.id),
                    ('group_booking_id', '=', booking_line.booking_id.group_booking.id)
                ], limit=1)
            else:
                # For individual bookings, use room-specific posting type
                posting_type = self.env['tz.manual.posting.type'].search([
                    ('company_id', '=', booking_line.booking_id.company_id.id),
                    ('booking_id', '=', booking_line.booking_id.id),
                    ('room_id', '=', booking_line.room_id.id),
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
                # 'booking_id': booking_line.booking_id.id,
                # 'room_id': booking_line.room_id.id,
                # 'group_booking_id': booking_line.booking_id.group_booking.id if booking_line.booking_id.group_booking else False,
                'sign': item.default_sign,
                'quantity': 1,
                'source_type': 'auto',
                'total': amount,
                'debit_amount': amount if item.default_sign == 'debit' else 0.0,
                'credit_amount': amount if item.default_sign == 'credit' else 0.0,
                'type_id': posting_type.id if posting_type else False
            }
            self.env['tz.manual.posting'].create(vals)
            return True
        return False

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

    def get_forecast(self, system_date, booking_id):
        """Return a single draft forecast for this booking line and system_date."""
        self.ensure_one()

        forecast = self.env['room.rate.forecast'].search([
            # ('company_id', '=', self.env.company.id),
            # ('state', '=', 'draft'),
            ('room_booking_id', '=', booking_id),
            ('date', '=', system_date),
        ], limit=1)

        return forecast

class RoomRateForecast(models.Model):
    _inherit = 'room.rate.forecast'

    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('post', 'Post'),
    ], string='State', default='draft')

    company_id = fields.Many2one('res.company', string="Hotel",
                                 index=True,
                                 default=lambda self: self.env.company)


