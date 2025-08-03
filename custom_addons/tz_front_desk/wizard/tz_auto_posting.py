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
    group_from = fields.Many2one('group.booking', domain="[('has_master_folio', '=', True)]", string="From Group")
    group_to = fields.Many2one('group.booking', domain="[('has_master_folio', '=', True)]", string="To Group")

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
        system_date = self.env.company.system_date.date()
        created_count = 0  # Track actual created records

        # 1. Get all forecasts for system_date
        forecasts = self.env['room.rate.forecast'].search([
            ('company_id', '=', self.env.company.id),
            ('date', '=', system_date)
        ])

        if not forecasts:
            return self._show_notification("No forecast data found for selected date", "warning")

        # 2. Process each forecast
        for forecast in forecasts:
            booking_line = self.env['room.booking.line'].search([
                ('current_company_id', '=', self.env.company.id),
                ('booking_id', '=', forecast.room_booking_id.id),
                ('state_', '=', 'check_in'),
            ], limit=1)

            if not booking_line:
                continue

            room_valid = True
            group_valid = True

            # Apply room filtering
            if not self.all_rooms:
                if not self.room_from or not self.room_to:
                    raise UserError(_("Please select both From and To rooms"))
                room_valid = self.room_from.id <= booking_line.room_id.id <= self.room_to.id

            # Apply group filtering
            if not self.all_groups:
                if not self.group_from or not self.group_to:
                    raise UserError(_("Please select both From and To groups"))
                group = booking_line.booking_id.group_booking
                group_valid = group and (self.group_from.id <= group.id <= self.group_to.id)

            """
            The below to suspended auto posting for groups only - rooms only inside (_create_folio_lines)
            """
            if booking_line.booking_id.group_booking:
                suspended = self.env['tz.hotel.checkout'].search([
                    '|',
                    ('room_id', '=', booking_line.room_id.id),
                    ('group_booking_id', '=',
                     booking_line.booking_id.group_booking.id if booking_line.booking_id.group_booking else False),
                    ('is_suspended_auto_posting', '=', True)
                ], limit=1)
                # raise UserError(suspended)
                if suspended:
                    continue

            # Check both room and group validity
            if (self.all_rooms or room_valid) or (self.all_groups or group_valid):
                folio = self._find_existing_folio(booking_line)

                if folio:
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

    def _create_folio_lines(self, booking_line, folio, forecast):
        """Create posting lines and return count of actually created records"""
        booking = booking_line.booking_id
        created_count = 0
        # Get all posting items
        rate_item = booking.rate_code.rate_posting_item if booking.rate_code else None
        meal_item = booking.meal_pattern.meal_posting_item if booking.meal_pattern else None
        # new_rate_code =  self.env['rate.code'].sudo().browse(62) #62
        package_items = booking.rate_code.rate_detail_ids.line_ids.packages_posting_item if booking.rate_code else None
        fixed_items = booking.posting_item_ids.posting_item_id

        # Room Rate
        if rate_item:
            if self.include_rates and forecast.rate > 0:
                total_amount = forecast.rate

                if forecast.room_booking_id.rate_code.include_meals and forecast.meals > 0:
                    total_amount += forecast.meals

                if self._create_posting_line(folio, booking_line, rate_item.id, rate_item.description, total_amount):
                    created_count += 1
        else:
            raise UserError(
                _("No posting item configured for rate code."))

        # Meals
        if meal_item:
            if self.include_meals and forecast.meals > 0 and not forecast.room_booking_id.rate_code.include_meals:
                if self._create_posting_line(folio, booking_line, meal_item.id, meal_item.description, forecast.meals):
                    created_count += 1
        else:
            raise UserError(
                _("No posting item configured for meal pattern"))

        # Packages
        if package_items:
            if self.include_packages and forecast.packages > 0:
                if self._create_posting_line(folio, booking_line, package_items.id, package_items.description, forecast.packages):
                        created_count += 1
        else:
            if self.include_packages and forecast.packages > 0:
                raise UserError(
                    _("No posting item configured for package"))

        # Fixed Charges
        if fixed_items:
            if self.include_fixed and forecast.fixed_post > 0:
                if self._create_posting_line(folio, booking_line, fixed_items.id, fixed_items.description,
                                                 forecast.fixed_post):
                        created_count += 1
        else:
            if self.include_fixed and forecast.fixed_post > 0:
                raise UserError(
                    _("No posting item configured for fixed post"))

        return created_count

    def _create_posting_line(self, folio, booking_line, item_id, description, amount):
        """Create posting line and return True if created, False if skipped"""
        system_date = self.env.company.system_date.date()

        # Check for suspended auto posting
        suspended = self.env['tz.hotel.checkout']._check_suspended_auto_posting(
            room_id=booking_line.room_id.id,
            group_id=folio.group_id.id if folio.group_id else None
        )
        if suspended:
            return False

        # Check for existing postings first
        existing = self.env['tz.manual.posting'].search([
            ('company_id', '=', booking_line.booking_id.company_id.id),
            ('folio_id', '=', folio.id),
            ('item_id', '=', item_id),
            ('date', '=', system_date),
            ('source_type', '=', 'auto'),
        ], limit=1)


        if not existing:
            # Find the correct posting type
            posting_type = self.env['tz.manual.posting.type'].search([
                ('company_id', '=', booking_line.booking_id.company_id.id),
                ('booking_id', '=', booking_line.booking_id.id),
                ('room_id', '=', booking_line.room_id.id)
            ], limit=1)

            if booking_line.booking_id.group_booking:
                posting_type = self.env['tz.manual.posting.type'].search([
                    ('company_id', '=', booking_line.booking_id.company_id.id),
                    ('group_booking_id', '=', booking_line.booking_id.group_booking.id)
                ], limit=1)

            if not posting_type:
                # Create a new posting type if none exists
                posting_type = self.env['tz.manual.posting.type'].create({
                    'company_id': booking_line.booking_id.company_id.id,
                    'booking_id': booking_line.booking_id.id,
                    'room_id': booking_line.room_id.id,
                    'group_booking_id': booking_line.booking_id.group_booking.id if booking_line.booking_id.group_booking else False
                })

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
                'booking_id': booking_line.booking_id.id,
                'room_id': booking_line.room_id.id,
                'group_booking_id': folio.group_id.id if folio.group_id else False,
                'sign': item.default_sign,
                'quantity': 1,
                'source_type': 'auto',
                'total': amount,
                'debit_amount': amount if item.default_sign == 'debit' else 0.0,
                'credit_amount': amount if item.default_sign == 'credit' else 0.0,
                'type_id': posting_type.id  # Now correctly linking to tz.manual.posting.type
            }
            self.env['tz.manual.posting'].create(vals)
            return True
        return False


    # def _create_posting_line(self, folio, booking_line, item_id, description, amount):
    #     """Create posting line and return True if created, False if skipped"""
    #     system_date = self.env.company.system_date.date()
    #     """
    #     The below to suspended auto posting for rooms only - we did for groups only inside (action_auto_posting)
    #     """
    #     suspended = self.env['tz.hotel.checkout']._check_suspended_auto_posting(
    #         room_id=booking_line.room_id.id,
    #         group_id=folio.group_id.id if folio.group_id else None
    #     )
    #     if suspended:
    #         return False  # Skip if suspended ones
    #     # Check for existing postings first
    #     existing = self.env['tz.manual.posting'].search([
    #         ('company_id', '=', booking_line.booking_id.company_id.id),
    #         ('folio_id', '=', folio.id),
    #         ('item_id', '=', item_id),
    #         ('room_id', '=', booking_line.room_id.id),
    #         ('date', '=', system_date),
    #         ('source_type', '=', 'auto'),
    #     ], limit=1)
    #
    #     if existing:
    #         return False  # Skip if already exists
    #
    #     posting_type = self.env['tz.manual.posting.type'].search([
    #         ('company_id', '=', booking_line.booking_id.company_id.id),
    #         ('group_booking_id', '=',
    #          booking_line.booking_id.group_booking.id if booking_line.booking_id.group_booking else False),
    #         ('booking_id', '=', booking_line.booking_id.id),
    #         ('room_id', '=', booking_line.room_id.id),
    #     ], limit=1)
    #
    #
    #     item = self.env['posting.item'].browse(item_id)
    #     # Initialize values dictionary
    #     manual_posting = f"{self.env.company.name}/{self.env['ir.sequence'].next_by_code('tz.manual.posting')}"
    #     if item.default_sign == 'main':
    #         raise UserError('Please note, main value for Default Sign not accepted, they must only debit or credit')
    #     vals = {
    #         'name': manual_posting,
    #         'date': system_date,
    #         'folio_id': folio.id,
    #         'item_id': item_id,
    #         'description': description,
    #         'booking_id': booking_line.booking_id.id,
    #         'room_id': booking_line.room_id.id,
    #         'group_booking_id': folio.group_id.id if folio.group_id else False,
    #         'sign': item.default_sign,
    #         'quantity': 1,
    #         'source_type': 'auto',
    #         'total': amount,
    #         'debit_amount': amount if item.default_sign == 'debit' else 0.0,
    #         'credit_amount': amount if item.default_sign == 'credit' else 0.0,
    #         'type_id': posting_type.id
    #     }
    #     self.env['tz.manual.posting'].create(vals)
    #     return True

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

class RoomRateForecast(models.Model):
    _inherit = 'room.rate.forecast'

    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('post', 'Post'),
    ], string='State', default='draft')

    company_id = fields.Many2one('res.company', string="Hotel",
                                 index=True,
                                 default=lambda self: self.env.company,
                                 readonly=True)


