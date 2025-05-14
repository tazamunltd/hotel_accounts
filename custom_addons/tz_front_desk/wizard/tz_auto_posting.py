from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
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

    def action_auto_posting(self):
        self.ensure_one()
        system_date = self.env.user.company_id.system_date.date()
        created_count = 0  # Track actual created records

        # 1. Get all forecasts for system_date
        forecasts = self.env['room.rate.forecast'].search([
            ('date', '=', system_date)
        ])

        if not forecasts:
            return self._show_notification("No forecast data found for selected date", "warning")

        # 2. Process each forecast
        for forecast in forecasts:
            # Get linked booking lines for this forecast
            booking_line = self.env['room.booking.line'].search([
                ('booking_id', '=', forecast.room_booking_id.id),
                ('state_', '=', 'check_in')
            ], limit=1)

            if not booking_line:
                continue

            # Apply room/group filters
            if not self.all_rooms:
                if not self.room_from or not self.room_to:
                    raise UserError(_("Please select both From and To rooms"))
                if not (self.room_from.id <= booking_line.room_id.id <= self.room_to.id):
                    continue

            if not self.all_groups:
                if not self.group_from or not self.group_to:
                    raise UserError(_("Please select both From and To groups"))
                if not (booking_line.booking_id.group_booking and
                        self.group_from.id <= booking_line.booking_id.group_booking.id <= self.group_to.id):
                    continue

            folio = self._find_existing_folio(booking_line, system_date)

            if not folio:
                continue

            # Only increment count if records were actually created
            records_created = self._create_folio_lines(booking_line, folio, forecast)
            created_count += records_created

        if created_count > 0:
            return self._show_notification(
                f"Successfully posted charges for {created_count} rooms",
                "success"
            )
        else:
            return self._show_notification(
                "No charges were posted - no valid booking lines found matching criteria",
                "warning"
            )

    def _get_filtered_booking_lines(self, system_date):
        """Get filtered booking lines based on wizard criteria"""
        domain = [
            ('checkin_date', '=', system_date),
            ('state_', '=', 'check_in')
        ]

        # Apply room range filter if specified
        if not self.all_rooms and self.room_from and self.room_to:
            domain.append(('room_id', '>=', self.room_from.id))
            domain.append(('room_id', '<=', self.room_to.id))

        # Apply group filter if specified
        if not self.all_groups and self.group_from and self.group_to:
            domain.append(('booking_id.group_booking', '>=', self.group_from.id))
            domain.append(('booking_id.group_booking', '<=', self.group_to.id))

        return self.env['room.booking.line'].search(domain)

    def _map_lines_to_folios(self, booking_lines, system_date):
        """Map booking lines to their existing folios"""
        folio_map = {}

        for line in booking_lines:
            # Find existing folio
            folio = self._find_existing_folio(line, system_date)
            # raise UserError(folio.id)
            if folio:
                folio_map.setdefault(folio.id, []).append(line)

        return folio_map

    def _find_existing_folio(self, booking_line, system_date):
        """Find existing folio that is active during the system_date"""
        domain = [
            ('check_in', '<=', fields.Datetime.to_datetime(system_date + timedelta(days=1))),
            ('check_out', '>', fields.Datetime.to_datetime(system_date)),
            ('company_id', '=', self.env.company.id)
        ]

        if booking_line.booking_id.group_booking:
            domain.append(('group_id', '=', booking_line.booking_id.group_booking.id))
        else:
            domain.append(('room_id', '=', booking_line.room_id.id))

        return self.env['tz.master.folio'].search(domain, limit=1)

    def _create_folio_lines(self, booking_line, folio, forecast):
        """Create posting lines and return count of actually created records"""
        booking = booking_line.booking_id
        created_count = 0

        # Get all posting items
        rate_item = booking.rate_code.rate_posting_item if booking.rate_code else None
        meal_item = booking.meal_pattern.meal_posting_item if booking.meal_pattern else None
        package_items = booking.posting_item_ids.filtered(lambda x: x.type == 'package')
        fixed_items = booking.posting_item_ids.filtered(lambda x: x.type == 'fixed')

        # Room Rate
        if self.include_rates and forecast.rate > 0 and rate_item:
            if self._create_posting_line(folio, booking_line, rate_item.id, rate_item.description, forecast.rate):
                created_count += 1

        # Meals
        if self.include_meals and forecast.meals > 0 and meal_item:
            if self._create_posting_line(folio, booking_line, meal_item.id, meal_item.description, forecast.meals):
                created_count += 1

        # Packages
        if self.include_packages and forecast.packages > 0 and package_items:
            for item in package_items:
                amount = item.amount if item.amount > 0 else forecast.packages
                if self._create_posting_line(folio, booking_line, item.item_id.id, item.item_id.name, amount):
                    created_count += 1

        # Fixed Charges
        if self.include_fixed and forecast.fixed_post > 0 and fixed_items:
            for item in fixed_items:
                amount = item.amount if item.amount > 0 else forecast.fixed_post
                if self._create_posting_line(folio, booking_line, item.item_id.id, item.item_id.description, amount):
                    created_count += 1

        return created_count

    def _create_posting_line(self, folio, booking_line, item_id, description, amount):
        """Create posting line and return True if created, False if skipped"""
        system_date = self.env.user.company_id.system_date.date()
        # Check for existing postings first
        existing = self.env['tz.manual.posting'].search([
            ('folio_id', '=', folio.id),
            ('item_id', '=', item_id),
            ('room_list', '=', booking_line.room_id.id),
            ('date', '>=', fields.Datetime.to_datetime(system_date)),
            ('date', '<', fields.Datetime.to_datetime(system_date + timedelta(days=1))),
        ], limit=1)

        if existing:
            return False  # Skip if already exists

        item = self.env['posting.item'].browse(item_id)
        # Initialize values dictionary
        manual_posting = f"{self.env.company.name}/{self.env['ir.sequence'].next_by_code('tz.manual.posting')}"
        vals = {
            'name': manual_posting,
            'date': system_date,
            'folio_id': folio.id,
            'item_id': item_id,
            'description': description,
            'type': 'group' if folio.group_id else 'room',
            'room_list': booking_line.room_id.id,
            'group_list': folio.group_id.id if folio.group_id else False,
            'sign': item.default_sign,
            'quantity': 1,
            'source_type': 'auto',
            'total': amount,
            'debit_amount': amount if item.default_sign == 'debit' else 0.0,
            'credit_amount': amount if item.default_sign == 'credit' else 0.0,
            'booking_id': booking_line.booking_id.id,
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

    def get_forecast_by_room(self, room_id, date=False):
        """
        Get the forecast record for a specific room
        :param room_id: ID of the hotel.room record
        :param date: Optional date filter (defaults to current system date)
        :return: Single room.rate.forecast record or False
        """
        if not date:
            date = self.env.user.company_id.system_date.date()

        return self.env['room.rate.forecast'].search([
            ('date', '=', date),
            ('booking_line_ids.room_id', '=', room_id)
        ], limit=1)
    # =============================================================================

    def _get_or_create_folio(self, booking_line):
        """Find or create folio for this booking line with proper validation"""
        if not booking_line.booking_id or not booking_line.booking_id.partner_id:
            raise UserError(_("Cannot create folio - no guest assigned to booking line ID %s") % booking_line.id)

        # Get group_id from booking if exists
        group_id = booking_line.booking_id.group_booking.id if booking_line.booking_id.group_booking else False
        master_room_id = self._get_master_room_id(booking_line) if group_id else False

        # Search domain - different logic for groups vs individual rooms
        domain = [
            ('room_id', '=', booking_line.room_id.id),
            ('guest_id', '=', booking_line.booking_id.partner_id.id),
            ('company_id', '=', self.env.company.id),
            ('check_in', '=', booking_line.checkin_date),
            ('check_out', '=', booking_line.checkout_date),
            ('group_id', '=', group_id if group_id else False),
        ]

        # Try to find existing folio
        folio = self.env['tz.master.folio'].sudo().search(domain, limit=1)

        # Create new folio if needed
        if not folio:
            folio = self._create_folio(booking_line, group_id, master_room_id)

        return folio

    def _create_folio(self, booking_line, group_id, master_room_id):
        """Helper function to create a new folio"""
        company = self.env.company
        prefix = company.name + '/' if company else ''
        folio_name = prefix + (
                self.env['ir.sequence'].with_company(company).next_by_code('tz.master.folio') or 'New')

        # For groups, always use master room. For individual rooms, use the room from booking line
        room_id = master_room_id if group_id else booking_line.room_id.id

        folio_vals = {
            'name': folio_name,
            'room_id': room_id,
            'group_id': group_id,
            'guest_id': booking_line.booking_id.partner_id.id,
            'company_id': self.env.company.id,
            'check_in': booking_line.checkin_date,
            'check_out': booking_line.checkout_date,
            'currency_id': self.env.company.currency_id.id,
        }

        folio = self.env['tz.master.folio'].sudo().create(folio_vals)
        return folio

    def _create_folio_linesX(self, booking_line, folio):
        """Create folio lines for a booking line after checking for duplicates"""
        lines_to_create = []
        posted_count = 0
        time_now = fields.Datetime.now().strftime('%H:%M %p')
        system_date = self.env.user.company_id.system_date.date()

        if not booking_line:
            raise UserError(_("No booking line provided"))

        # Get forecast specifically for this room
        forecast = self._get_forecast(booking_line)
        if not forecast:
            raise UserError(_("No forecast found for this booking line on date %s") % system_date)

        # Get posting items
        rate_posting_item = booking_line.booking_id.rate_code.rate_posting_item
        meal_posting_item = booking_line.booking_id.meal_pattern.meal_posting_item
        guest_id = booking_line.booking_id.partner_id.id
        group_id = booking_line.booking_id.group_booking.id if booking_line.booking_id.group_booking else False

        # Get or create sequence
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', 'tz.manual.posting'),
            ('company_id', '=', self.env.company.id)
        ], limit=1) or self.env['ir.sequence'].sudo().create({
            'name': f'Manual Posting Reference - {self.env.company.name}',
            'code': 'tz.manual.posting',
            'prefix': 'MP/',
            'padding': 5,
            'company_id': self.env.company.id,
        })

        def get_line_vals(posting_item, amount, description):
            """Helper to generate posting line values"""
            company = self.env.company
            return {
                'name': f"{company.name}/{sequence.next_by_id()}",
                'date': system_date,
                'time': time_now,
                'description': description,
                'item_id': posting_item.id,
                'item_description': posting_item.description,
                'room_list': booking_line.room_id.id,
                'unavailable_room_ids': [(6, 0, [booking_line.room_id.id])],
                'folio_id': folio.id,
                'source_type': 'auto',
                'company_id': company.id,
                'partner_id': guest_id,
                'sign': posting_item.default_sign,
                'group_list': group_id,
                'debit_amount': amount if posting_item.default_sign == 'debit' else 0,
                'credit_amount': amount if posting_item.default_sign == 'credit' else 0
            }

        # Process Room Rate
        if self.include_rates and forecast.rate > 0:
            if not rate_posting_item:
                raise UserError(_("No posting item configured for rate code"))

            total_amount = forecast.rate
            print('total_amount: ', total_amount)
            if forecast.room_booking_id.rate_code.include_meals and forecast.meals > 0:
                total_amount += forecast.meals

            lines_to_create.append(
                get_line_vals(rate_posting_item, total_amount, 'Room Rate')
            )
            posted_count += 1

        # Process Meals (if not included in rate)
        if (self.include_meals and forecast.meals > 0 and
                not forecast.room_booking_id.rate_code.include_meals):
            if not meal_posting_item:
                raise UserError(_("No posting item configured for meal pattern"))

            lines_to_create.append(
                get_line_vals(meal_posting_item, forecast.meals, 'Meals')
            )
            posted_count += 1

        # Process Packages
        if self.include_packages and forecast.packages > 0:
            package_item = self.env['posting.item'].search([('name', 'ilike', 'package')], limit=1)
            if not package_item:
                raise UserError(_("No posting item found for packages"))

            lines_to_create.append(
                get_line_vals(package_item, forecast.packages, 'Packages')
            )
            posted_count += 1

        # Process Fixed Posts
        if self.include_fixed and forecast.fixed_post > 0:
            fixed_item = self.env['posting.item'].search([('name', 'ilike', 'fixed')], limit=1)
            if not fixed_item:
                raise UserError(_("No posting item found for fixed posts"))

            lines_to_create.append(
                get_line_vals(fixed_item, forecast.fixed_post, 'Fixed Post')
            )
            posted_count += 1

        # Create all posting lines
        for line_vals in lines_to_create:
            try:
                self.env['tz.manual.posting'].create(line_vals)
            except Exception as e:
                raise UserError(_("Failed to create posting: %s") % str(e))

        return posted_count

    def _get_forecast(self, booking_line):
        """Get forecast for a booking line on system date"""
        system_date = self.env.user.company_id.system_date.date()
        return self.env['room.rate.forecast'].search([
            ('date', '=', system_date),
            ('state', '=', 'draft'),
            ('room_booking_id', '=', booking_line.booking_id.id),
            ('booking_line_ids.room_id', '=', booking_line.room_id.id)
        ], limit=1)

    def _show_success_message(self, posted_count, master_folios_count=0, manual_postings_count=0, is_info=False,
                              custom_message=None):
        if is_info:
            # Handle info messages (existing functionality)
            params = {
                'title': _('Information'),
                'message': custom_message if custom_message else _('Operation completed'),
                'sticky': False,
                'type': 'info'
            }
        else:
            # Enhanced success message with posting statistics
            message = _("""
                Posting completed successfully!
                Total postings: %(posted_count)d
                Master folios created: %(master_folios_count)d
                Manual postings created: %(manual_postings_count)d
            """) % {
                'posted_count': posted_count,
                'master_folios_count': master_folios_count,
                'manual_postings_count': manual_postings_count
            }

            params = {
                'title': _('Success'),
                'message': message,
                'sticky': False,
                'type': 'success'
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': params
        }

    def _get_master_room_id(self, booking_line):
        """Get master room ID for a group booking"""
        if booking_line.booking_id.group_booking:
            bookings = self.env['room.booking'].search([
                ('group_booking', '=', booking_line.booking_id.group_booking.id)
            ])
            master_booking = bookings.filtered(lambda b: not b.parent_booking_name)
            if master_booking and master_booking.room_line_ids:
                return master_booking.room_line_ids[0].room_id.id
        return False


class RoomRateForecast(models.Model):
    _inherit = 'room.rate.forecast'

    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('post', 'Post'),
    ], string='State', default='draft', tracking=True)


