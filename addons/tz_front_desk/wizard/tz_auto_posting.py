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

        # 1. Build domain for booking lines
        booking_line_domain = [
            ('checkin_date', '>=', fields.Datetime.to_datetime(system_date)),
            ('checkin_date', '<', fields.Datetime.to_datetime(system_date + timedelta(days=1))),
            ('state_', '=', 'check_in')
        ]

        # Apply room/group filters
        if not self.all_rooms:
            if not self.room_from or not self.room_to:
                raise UserError(_("Please select both From and To rooms"))
            booking_line_domain.extend([
                ('room_id', '>=', self.room_from.id),
                ('room_id', '<=', self.room_to.id)
            ])

        if not self.all_groups:
            if not self.group_from or not self.group_to:
                raise UserError(_("Please select both From and To groups"))
            booking_line_domain.extend([
                ('booking_id.group_booking', '>=', self.group_from.id),
                ('booking_id.group_booking', '<=', self.group_to.id)
            ])

        # 2. Get booking lines and prepare forecasts
        booking_lines = self.env['room.booking.line'].search(booking_line_domain)
        if not booking_lines:
            return self._show_notification("No checked-in rooms found", "warning")

        # Get ALL forecasts for these booking lines
        all_forecasts = self.env['room.rate.forecast'].search([
            ('date', '=', system_date),
            ('booking_line_ids', 'in', booking_lines.ids)
        ])

        # Create mapping {booking_line_id: forecast}
        forecast_map = {}
        for forecast in all_forecasts:
            for booking_line in forecast.booking_line_ids:
                if booking_line.id not in forecast_map:
                    forecast_map[booking_line.id] = forecast

        # 3. Process each booking line with its specific forecast
        processed_rooms = set()
        for booking_line in booking_lines:
            if booking_line.room_id.id in processed_rooms:
                continue

            folio = self._find_existing_folio(booking_line, system_date)
            if not folio:
                continue

            forecast = forecast_map.get(booking_line.id)
            # raise UserError(forecast.rate)
            if not forecast:
                _logger.warning(f"No forecast found for booking line {booking_line.id}")
                continue

            self._create_folio_lines(booking_line, folio, forecast)
            processed_rooms.add(booking_line.room_id.id)

        return self._show_notification(f"Posted charges for {len(processed_rooms)} rooms", "success")

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
        """Find existing folio for a booking line"""
        domain = [
            ('check_in', '>=', fields.Datetime.to_datetime(system_date)),  # Day start
            ('check_in', '<', fields.Datetime.to_datetime(system_date + timedelta(days=1))),  # Next day start
            ('company_id', '=', self.env.company.id)
        ]

        if booking_line.booking_id.group_booking:
            domain.append(('group_id', '=', booking_line.booking_id.group_booking.id))
        else:
            domain.append(('room_id', '=', booking_line.room_id.id))

        return self.env['tz.master.folio'].search(domain, limit=1)

    def _create_folio_lines(self, booking_line, folio, forecast):
        """Create posting lines for a single forecast"""
        booking = booking_line.booking_id

        # Get posting items
        rate_item = booking.rate_code.rate_posting_item if booking.rate_code else None
        meal_item = booking.meal_pattern.meal_posting_item if booking.meal_pattern else None
        package_items = booking.posting_item_ids.filtered(lambda x: x.type == 'package')
        fixed_items = booking.posting_item_ids.filtered(lambda x: x.type == 'fixed')

        # Room Rate
        if self.include_rates and forecast.rate > 0 and rate_item:
            self._create_posting_line(
                folio=folio,
                booking_line=booking_line,  # Added missing argument
                item_id=rate_item.id,
                description=rate_item.description,
                amount=forecast.rate
            )

        # Meals
        if self.include_meals and forecast.meals > 0 and meal_item:
            self._create_posting_line(
                folio=folio,
                booking_line=booking_line,  # Added missing argument
                item_id=meal_item.id,
                description=meal_item.description,
                amount=forecast.meals
            )

        # Packages
        if self.include_packages and forecast.packages > 0 and package_items:
            for item in package_items:
                self._create_posting_line(
                    folio=folio,
                    booking_line=booking_line,  # Added missing argument
                    item_id=item.item_id.id,
                    description=item.item_id.name,
                    amount=item.amount if item.amount > 0 else forecast.packages
                )

        # Fixed Charges
        if self.include_fixed and forecast.fixed_post > 0 and fixed_items:
            for item in fixed_items:
                self._create_posting_line(
                    folio=folio,
                    booking_line=booking_line,  # Added missing argument
                    item_id=item.item_id.id,
                    description=item.item_id.description,
                    amount=item.amount if item.amount > 0 else forecast.fixed_post
                )

    def _create_posting_line(self, folio, booking_line, item_id, description, amount):
        """Create individual posting line with duplicate check"""
        system_date = self.env.user.company_id.system_date.date()

        existing_posting = self.env['tz.manual.posting'].search([
            ('folio_id', '=', folio.id),
            ('item_id', '=', item_id),
            ('room_list', '=', booking_line.room_id.id),
            ('date', '>=', fields.Datetime.to_datetime(system_date)),
            # ('date', '<', fields.Datetime.to_datetime(system_date + timedelta(days=1)))
        ], limit=1)

        # raise UserError(existing_posting)

        if existing_posting:
            _logger.info(f"Duplicate posting prevented for item {item_id} in folio {folio.id}")
            return existing_posting

        # Create sequence if not exists
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

        # Create new posting
        return self.env['tz.manual.posting'].create({
            'name': f"{self.env.company.name}/{sequence.next_by_id()}",
            'date': fields.Datetime.now(),
            'folio_id': folio.id,
            'item_id': item_id,
            'description': description,
            'type': 'group' if folio.group_id else 'room',
            'room_list': booking_line.room_id.id,
            'group_list': folio.group_id.id if folio.group_id else False,
            'sign': 'debit',
            'total': amount,
            'quantity': 1,
            'source_type': 'auto',
        })

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

    def action_auto_postingX(self):
        self.ensure_one()
        system_date = self.env.user.company_id.system_date.date()

        # Domain setup
        booking_line_domain = [('state_', '=', 'check_in')]

        # Room filters
        if not self.all_rooms:
            if not self.room_from or not self.room_to:
                raise UserError(_("Please select both From and To rooms"))
            booking_line_domain.extend([
                ('room_id', '>=', self.room_from.id),
                ('room_id', '<=', self.room_to.id)
            ])

        # Group filters
        if not self.all_groups:
            if not self.group_from or not self.group_to:
                raise UserError(_("Please select both From and To groups"))
            booking_line_domain.extend([
                ('group_id', '>=', self.group_from.id),
                ('group_id', '<=', self.group_to.id)
            ])

        # Get booking lines
        booking_lines = self.env['room.booking.line'].search(booking_line_domain)
        if not booking_lines:
            raise UserError(_("No rooms in Check-In state matching your criteria"))

        posted_count = 0
        master_folios_count = 0
        manual_postings_count = 0

        # Process GROUP bookings - ALL rooms in each group
        grouped_bookings = booking_lines.mapped('booking_id').filtered('group_booking')

        for group in grouped_bookings.mapped('group_booking'):
            group_booking_lines = booking_lines.filtered(
                lambda bl: bl.booking_id.group_booking == group)

            if group_booking_lines:
                # Create ONE master folio for the entire group
                folio = self._get_or_create_folio(group_booking_lines[0])
                master_folios_count += 1

                # Process EVERY room in the group
                for booking_line in group_booking_lines:
                    existing_posting = self.env['tz.manual.posting'].search([
                        ('date', '=', system_date),
                        ('room_list', '=', booking_line.room_id.id),
                        ('folio_id', '=', folio.id)
                    ], limit=1)
                    if existing_posting:
                        self.env.user.notify_warning(
                            _("Posting already exists for room %s on %s") %
                            (booking_line.room_id.name, system_date))
                        continue  # Skip this room but continue with others

                    count = self._create_folio_lines(booking_line, folio)
                    posted_count += count

        # Process INDIVIDUAL bookings (non-group)
        individual_bookings = booking_lines.filtered(
            lambda bl: bl.booking_id not in grouped_bookings)

        for booking_line in individual_bookings:
            # Create individual folio for this booking
            folio = self._get_or_create_folio(booking_line)
            manual_postings_count += 1

            existing_posting = self.env['tz.manual.posting'].search([
                ('date', '=', system_date),
                ('room_list', '=', booking_line.room_id.id),
                ('folio_id', '=', folio.id)
            ], limit=1)

            if existing_posting:
                self.env.user.notify_warning(
                    _("Posting already exists for room %s on %s") %
                    (booking_line.room_id.name, system_date))
                continue  # Skip this room but continue with others

            count = self._create_folio_lines(booking_line, folio)
            posted_count += count

        return self._show_success_message(
            posted_count=posted_count,
            master_folios_count=master_folios_count,
            manual_postings_count=manual_postings_count
        )

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


# self._show_success_message(0, is_info=True, custom_message="Your info message here")