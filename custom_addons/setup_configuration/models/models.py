from odoo import _, api, models, fields
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class HotelDetails(models.Model):
    _name = 'system.configuration'
    _description = 'Hotel Details'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    hotel_name = fields.Char(string=_('Hotel Name'), tracking=True)
    address = fields.Char(string=_('Address'), tracking=True)
    contact_info = fields.Char(string=_('Contact Info'), tracking=True, translate=True)


class SystemConfig(models.Model):
    _name = 'system.config'
    _description = 'System Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    system_configuration_id = fields.Char(
        _('System Configuration ID'), tracking=True)
    pms_integration_id = fields.Char(_('PMS Integration ID'), tracking=True)
    accounting_integration_id = fields.Char(_('Accounting Integration ID'), tracking=True)
    booking_integration_id = fields.Char(_('Booking.com Integration ID'), tracking=True)


class SystemLanguagesUI(models.Model):
    _name = 'system.languages.ui'
    _description = 'Languages and UI'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    language_id = fields.Many2one('res.lang', string='Language', tracking=True)
    ui_theme = fields.Char('UI Theme', tracking=True)


# class SystemPaymentCurrencies(models.Model):
#     _name = 'system.payment.currencies'
#     _description = 'Payment and Currencies'

#     currency = fields.Char('Currency')
#     payment_gateway = fields.Char('Payment Gateway')

# class SystemCategories(models.Model):
#     _name = 'system.categories'
#     _description = 'Categories'

#     category_name = fields.Char('Category Name')
#     description = fields.Text('Description')

class RateCategory(models.Model):
    _name = 'rate.category'
    _description = 'Rate Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'category'
    category = fields.Char(string=_('Category'), required=True, tracking=True, translate=True)
    description = fields.Char(string=_('Description'),
                              required=True, tracking=True, translate=True)
    abbreviation = fields.Char(
        string=_('Abbreviation'), required=True, tracking=True, translate=True)
    user_sort = fields.Integer(string='User Sort', default=0, tracking=True)


class RateCode(models.Model):
    _name = 'rate.code'
    _description = 'Rate Code Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    rate_detail_ids = fields.One2many(
        'rate.detail', 'rate_code_id', string="Rate Details")

    _rec_name = 'code'
    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True)
    code = fields.Char(string=_('Rate Code'), required=True, tracking=True, translate=True)
    description = fields.Char(string=_('Description'),
                              required=True, tracking=True, translate=True)
    abbreviation = fields.Char(string=_('Abbreviation'), tracking=True, translate=True)
    arabic_desc = fields.Char(string=_('Arabic Description'), tracking=True)
    arabic_abbr = fields.Char(string=_('Arabic Abbreviation'), tracking=True)
    rate_code_category_id = fields.Many2one(
        'rate.category', string='Category', required=True, tracking=True)
    rate_posting_item = fields.Many2one(
        'posting.item', string='Rate Posting Item', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', tracking=True)
    include_meals = fields.Boolean(
        string='Include Meals in Posting Item', tracking=True)
    user_sort = fields.Integer(string='User Sort', default=0, tracking=True)
    obsolete = fields.Boolean(string='Obsolete', tracking=True)

    room_type_id = fields.Many2one(
        'room.type', string="Room Type", tracking=True)

    def name_get(self):
        result = []
        for record in self:
            # Use the 'Code' field as the display name
            name = record.code
            result.append((record.id, name))
        return result

    rhythm = fields.Selection([
        ('every_night', 'Every Night'),
        ('after_change_date', 'After Change Date'),
        ('upon_check_out', 'Upon Check Out')
    ], string="Rhythm", tracking=True)

    exchange_rate = fields.Selection([
        ('fixed', 'Fixed (As it was on arrival)'),
        ('variable', 'Variable (Evaluated daily)')
    ], string="Exchange Rate", tracking=True)

    # Date fields for rate details
    rate_details = fields.One2many(
        'rate.detail', 'rate_code_id', string="Rate Details")

    # Method for "Edit Details" button

    def action_rate_code_details(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rate Details',
            'res_model': 'rate.detail',
            # Show the tree view first, and allow form view when a record is selected
            'view_mode': 'tree,kanban,pivot,graph,calendar,form',
            'view_type': 'form',
            'target': 'current',  # Use 'current' instead of 'new' to show the full tree and form view
            'context': {
                'default_rate_code_id': self.id,
            },
            'domain': [('rate_code_id', '=', self.id)]
        }


class RateDetailLine(models.Model):
    _name = 'rate.detail.line'
    _description = 'Rate Detail Lines'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    parent_id = fields.Many2one(
        'rate.detail', string="Parent", required=True, tracking=True)
    hotel_services_config = fields.Many2one(
        'hotel.configuration', string="Hotel Service", tracking=True)
    packages_posting_item = fields.Many2one(
        'posting.item', string="Posting Item", required=True, tracking=True)
    packages_value = fields.Integer(string="Value", tracking=True, default=0)

    @api.onchange('hotel_services_config')
    def _onchange_hotel_services_config(self):
        for record in self:
            if record.hotel_services_config:
                # Fetch the price and frequency from the related service
                service = record.hotel_services_config
                # Assuming `unit_price` exists in `hotel.configuration`
                record.packages_value = service.unit_price

                if service.frequency == 'one time':
                    record.packages_rhythm = 'first_night'
                elif service.frequency == 'daily':
                    record.packages_rhythm = 'every_night'

    @api.onchange('packages_value')
    def _onchange_packages_value(self):
        for record in self:
            if record.packages_value < 0:
                raise ValidationError("Value cannot be less than zero.")

    packages_rhythm = fields.Selection([
        ('every_night', 'Every Night'),
        ('first_night', 'First Night')
    ], string="Rhythm", default='every_night', tracking=True)
    packages_value_type = fields.Selection([
        ('added_value', 'Added Value'),
        ('per_pax', 'Per Pax')
    ], string="Value Type", default='added_value', tracking=True)


class RateDetail(models.Model):
    _name = 'rate.detail'
    _description = 'Rate Details'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'rate_code_id'

    def write(self, values):
        super(RateDetail, self).write(values)
        bookings = self.env['room.booking'].search([
            ('rate_code', '<=', self.id),
            ('state', 'not in', ['done', 'cancel', 'no_show', 'check_out']),

        ])
        print("BOOKINGS", len(bookings))

        # print("BOOKINGS", bookings)

        for booking in bookings:
            # print("CHECK", booking.checkin_date, booking.checkout_date, booking.state)
            _logger.info(f"BOOKING ID {booking.id}, {booking.name}")
            booking._get_forecast_rates(from_rate_code=True)

    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True)

    def name_get(self):
        result = []
        for record in self:
            # Use the 'Code' field as the display name
            name = record.rate_code_id
            result.append((record.id, name))
        return result

    hotel_services_config = fields.Many2one(
        'hotel.configuration', string="Hotel Services", tracking=True)
    line_ids = fields.One2many('rate.detail.line', 'parent_id', string="Lines")
    parent_id = fields.Many2one('rate.detail', string="Parent", tracking=True)

    def action_add_line(self):
        """Add a line with the current field values to the table below."""
        self.write({
            'line_ids': [(0, 0, {
                'hotel_services_config': self.hotel_services_config.id,
                'packages_posting_item': self.packages_posting_item.id,
                'packages_value': self.packages_value,
                'packages_rhythm': self.packages_rhythm,
                'packages_value_type': self.packages_value_type,
            })]
        })

    # taxes = fields.Many2one('account.tax', string="Taxes")
    customize_meal = fields.Selection([
        ('meal_pattern', 'Meal Pattern'),
        ('customize', 'Customize Meal')
    ], string="Meal Option", required=True, default='meal_pattern', tracking=True)
    adult_meal_rate = fields.Float(string='Adult Rate', tracking=True)
    child_meal_rate = fields.Float(string='Child Rate', tracking=True)
    @api.constrains('adult_meal_rate', 'child_meal_rate')
    def _check_meal_rate(self):
        for record in self:
            if record.adult_meal_rate < 0:
                raise ValidationError("The Adult Rate cannot be less than 0.")
            if record.child_meal_rate < 0:
                raise ValidationError("The Child Rate cannot be less than 0.")
    infant_meal_rate = fields.Float(string='Infant Rate', tracking=True)

    packages_line_number = fields.Integer(string="Line", tracking=True)
    packages_posting_item = fields.Many2one(
        'posting.item', string="Posting Item", tracking=True)
    packages_value = fields.Integer(string="Value", tracking=True, default=0)

    @api.onchange('packages_value')
    def _onchange_packages_value(self):
        for record in self:
            if record.packages_value < 0:
                raise ValidationError("Value cannot be less than zero.")

    packages_rhythm = fields.Selection([
        ('every_night', 'Every Night'),
        ('first_night', 'First Night')
    ], string="Rhythm", default='every_night', tracking=True)

    packages_value_type = fields.Selection([
        ('added_value', 'Added Value'),
        ('per_pax', 'Per Pax')
    ], string="Value Type", default='added_value', tracking=True)

    from_date = fields.Date(string="From Date", required=True, tracking=True)
    to_date = fields.Date(string="To Date", required=True, tracking=True)

    @api.constrains('from_date', 'to_date')
    def _check_date_overlap(self):
        for record in self:
            company = self.env.user.company_id
            if company.system_date:
                # Ensure both are `date` objects
                system_date = fields.Date.to_date(company.system_date)
                print('251', system_date)
                from_date = fields.Date.to_date(record.from_date)
                if from_date < system_date:
                    raise ValidationError(
                        "The 'From Date' cannot be earlier than the system date set in the company."
                    )
            if record.to_date <= record.from_date:
                raise ValidationError(
                    "The 'To Date' must be greater than the 'From Date'.")

            # Search for overlapping records
            overlapping_records = self.search([
                # Exclude the current record (for updates)
                ('id', '!=', record.id),
                # Match the same rate_code
                ('rate_code_id', '=', record.rate_code_id.id),
                '|',
                '&', ('from_date', '<=', record.to_date), ('to_date',
                                                           '>=', record.from_date),
                '&', ('from_date', '>=', record.from_date), ('from_date',
                                                             '<=', record.to_date),
            ])
            print('187', overlapping_records)

            if overlapping_records:
                # Collect details of all overlapping records
                overlap_details = "\n".join(
                    f"From Date: {overlap.from_date}, To Date: {overlap.to_date}"
                    for overlap in overlapping_records
                )

                # Raise the validation error with all overlapping records
                raise ValidationError(
                    f"The date range from '{record.from_date}' to '{record.to_date}' overlaps with the following records:\n\n{overlap_details}"
                )

    rate_detail_dicsount = fields.Float(
        string="Discount", tracking=True, default=0)

    @api.onchange('rate_detail_dicsount')
    def _check_rate_detail_discount(self):
        for record in self:
            if record.rate_detail_dicsount < 0:
                raise ValidationError(
                    _("The Discount value cannot be negative."))

    is_amount = fields.Boolean(string="Amount", default=False, tracking=True)
    is_percentage = fields.Boolean(
        string="Percentage", default=False, tracking=True)

    # @api.constrains('from_date', 'to_date')
    # def _check_date_overlap(self):
    #     for record in self:
    #         if record.from_date > record.to_date:
    #             raise ValidationError("From Date cannot be after To Date.")

    #         # Search for any existing records with overlapping dates
    #         overlapping_records = self.env['rate.detail'].search([
    #             ('id', '!=', record.id),
    #             '|',
    #             '&', ('from_date', '<=', record.to_date.strftime('%Y-%m-%d')),
    #                  ('to_date', '>=', record.from_date.strftime('%Y-%m-%d'))
    #         ])

    #         if overlapping_records:
    #             raise ValidationError(
    #                 f"The dates overlap with an existing record (From Date: {overlapping_records[0].from_date}, "
    #                 f"To Date: {overlapping_records[0].to_date}). Please choose different dates."
    #             )

    @api.onchange('is_amount')
    def _onchange_is_amount(self):
        if self.is_amount:
            self.is_percentage = False

    @api.onchange('is_percentage')
    def _onchange_is_percentage(self):
        if self.is_percentage:
            self.is_amount = False

    # Additional radio buttons for Total and Line Wise
    amount_selection = fields.Selection([
        ('total', 'Total'),
        ('line_wise', 'Line Wise')
    ], string="Amount Selection", tracking=True)

    percentage_selection = fields.Selection([
        ('total', 'Total'),
        ('line_wise', 'Line Wise')
    ], string="Percentage Selection", tracking=True)


    posting_item = fields.Many2one(
        'posting.item', string="Posting Item", tracking=True)
    rate_code_id = fields.Many2one(
        'rate.code', string="Rate Code", tracking=True)

    # Room Prices for different configurations (1 Pax, 2 Pax, etc.,tracking=True)
    default_price = fields.Float(string="Default", tracking=True)
    monday_price = fields.Float(string="Monday", tracking=True)
    tuesday_price = fields.Float(string="Tuesday", tracking=True)
    wednesday_price = fields.Float(string="Wednesday", tracking=True)
    thursday_price = fields.Float(string="Thursday", tracking=True)
    friday_price = fields.Float(string="Friday", tracking=True)
    saturday_price = fields.Float(string="Saturday", tracking=True)
    sunday_price = fields.Float(string="Sunday", tracking=True)

    pax_1 = fields.Float(string="1 Pax", tracking=True, default=0)
    pax_2 = fields.Float(string="2 Pax", tracking=True, default=0)
    pax_3 = fields.Float(string="3 Pax", tracking=True, default=0)
    pax_4 = fields.Float(string="4 Pax", tracking=True, default=0)
    pax_5 = fields.Float(string="5 Pax", tracking=True, default=0)
    pax_6 = fields.Float(string="6 Pax", tracking=True, default=0)

    # Child Prices for different configurations (1 Child, 2 Children, etc., tracking=True)
    child_pax_1 = fields.Float(string="1 Infant", tracking=True, default=0)
    child_pax_2 = fields.Float(string="2 Children", tracking=True, default=0)
    child_pax_3 = fields.Float(string="3 Children", tracking=True, default=0)
    child_pax_4 = fields.Float(string="4 Children", tracking=True, default=0)
    child_pax_5 = fields.Float(string="5 Children", tracking=True, default=0)
    child_pax_6 = fields.Float(string="6 Children", tracking=True, default=0)

    infant_pax_1 = fields.Float(string="1 Infant", tracking=True, default=0)
    infant_pax_2 = fields.Float(string="2 Infant", tracking=True, default=0)
    infant_pax_3 = fields.Float(string="3 Infant", tracking=True, default=0)
    infant_pax_4 = fields.Float(string="4 Infant", tracking=True, default=0)
    infant_pax_5 = fields.Float(string="5 Infant", tracking=True, default=0)
    infant_pax_6 = fields.Float(string="6 Infant", tracking=True, default=0)

    extra_bed = fields.Integer(string="Extra Bed", tracking=True, default=0)
    suite_supl = fields.Integer(string="Suite Supl", tracking=True, default=0)

    @api.onchange('pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6', 'extra_bed', 'suite_supl')
    def _onchange_check_minimum_value(self):
        for field_name in ['pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6']:
            if getattr(self, field_name, 0) < 0:
                raise ValidationError(
                    _("The value for '%s' cannot be less than 0.") % self._fields[field_name].string
                )

    @api.onchange('child_pax_1', 'child_pax_2', 'child_pax_3', 'child_pax_4', 'child_pax_5', 'child_pax_6')
    def _onchange_check_minimum_child_value(self):
        for field_name in ['child_pax_1', 'child_pax_2', 'child_pax_3', 'child_pax_4', 'child_pax_5', 'child_pax_6']:
            if getattr(self, field_name, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' cannot be less than 0.") % self._fields[field_name].string
                )

    @api.onchange('infant_pax_1', 'infant_pax_2', 'infant_pax_3', 'infant_pax_4', 'infant_pax_5', 'infant_pax_6')
    def _onchange_check_minimum_infant_value(self):
        for field_name in ['infant_pax_1', 'infant_pax_2', 'infant_pax_3', 'infant_pax_4', 'infant_pax_5', 'infant_pax_6']:
            if getattr(self, field_name, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' cannot be less than 0.") % self._fields[field_name].string
                )

    @api.onchange('extra_bed', 'suite_supl')
    def _onchange_check_minimum_value_bed_suite(self):
        for field_name in ['extra_bed', 'suite_supl']:
            if getattr(self, field_name, 0) < 0:
                raise ValidationError(
                    _("The value for '%s' cannot be less than 0.") % self._fields[field_name].string
                )

    # Pax Rates for Monday
    monday_pax_1 = fields.Float(
        string="1 Pax (Monday)", tracking=True, default=0)
    monday_pax_2 = fields.Float(
        string="2 Pax (Monday)", tracking=True, default=0)
    monday_pax_3 = fields.Float(
        string="3 Pax (Monday)", tracking=True, default=0)
    monday_pax_4 = fields.Float(
        string="4 Pax (Monday)", tracking=True, default=0)
    monday_pax_5 = fields.Float(
        string="5 Pax (Monday)", tracking=True, default=0)
    monday_pax_6 = fields.Float(
        string="6 Pax (Monday)", tracking=True, default=0)

    @api.onchange('monday_pax_1', 'monday_pax_2', 'monday_pax_3', 'monday_pax_4', 'monday_pax_5', 'monday_pax_6')
    def _onchange_monday_pax(self):
        for field in ['monday_pax_1', 'monday_pax_2', 'monday_pax_3', 'monday_pax_4', 'monday_pax_5', 'monday_pax_6']:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Monday cannot be less than 0.") % self._fields[field].string)

    # Child Pax Rates for each day
    monday_child_pax_1 = fields.Float(
        string="1 Child (Monday)", tracking=True, default=0)
    monday_child_pax_2 = fields.Float(
        string="2 Children (Monday)", tracking=True, default=0)
    monday_child_pax_3 = fields.Float(
        string="3 Children (Monday)", tracking=True, default=0)
    monday_child_pax_4 = fields.Float(
        string="4 Children (Monday)", tracking=True, default=0)
    monday_child_pax_5 = fields.Float(
        string="5 Children (Monday)", tracking=True, default=0)
    monday_child_pax_6 = fields.Float(
        string="6 Children (Monday)", tracking=True, default=0)

    # Onchange for Monday child pax``

    @api.onchange('monday_child_pax_1', 'monday_child_pax_2', 'monday_child_pax_3', 'monday_child_pax_4', 'monday_child_pax_5', 'monday_child_pax_6')
    def _onchange_monday_child_pax(self):
        for field in [
            'monday_child_pax_1', 'monday_child_pax_2', 'monday_child_pax_3',
            'monday_child_pax_4', 'monday_child_pax_5', 'monday_child_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Monday cannot be less than 0.") % self._fields[field].string)

    monday_infant_pax_1 = fields.Float(
        string="1 Child (Monday)", tracking=True, default=0)
    monday_infant_pax_2 = fields.Float(
        string="2 Children (Monday)", tracking=True, default=0)
    monday_infant_pax_3 = fields.Float(
        string="3 Children (Monday)", tracking=True, default=0)
    monday_infant_pax_4 = fields.Float(
        string="4 Children (Monday)", tracking=True, default=0)
    monday_infant_pax_5 = fields.Float(
        string="5 Children (Monday)", tracking=True, default=0)
    monday_infant_pax_6 = fields.Float(
        string="6 Children (Monday)", tracking=True, default=0)

    # Onchange for Monday Infant pax
    @api.onchange('monday_infant_pax_1', 'monday_infant_pax_2', 'monday_infant_pax_3', 'monday_infant_pax_4', 'monday_infant_pax_5', 'monday_infant_pax_6')
    def _onchange_monday_infant_pax(self):
        for field in [
            'monday_infant_pax_1', 'monday_infant_pax_2', 'monday_infant_pax_3',
            'monday_infant_pax_4', 'monday_infant_pax_5', 'monday_infant_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Monday cannot be less than 0.") % self._fields[field].string)

    # Pax Rates for Tuesday
    tuesday_pax_1 = fields.Float(
        string="1 Pax (Tuesday)", tracking=True, default=0)
    tuesday_pax_2 = fields.Float(
        string="2 Pax (Tuesday)", tracking=True, default=0)
    tuesday_pax_3 = fields.Float(
        string="3 Pax (Tuesday)", tracking=True, default=0)
    tuesday_pax_4 = fields.Float(
        string="4 Pax (Tuesday)", tracking=True, default=0)
    tuesday_pax_5 = fields.Float(
        string="5 Pax (Tuesday)", tracking=True, default=0)
    tuesday_pax_6 = fields.Float(
        string="6 Pax (Tuesday)", tracking=True, default=0)

    @api.onchange('tuesday_pax_1', 'tuesday_pax_2', 'tuesday_pax_3', 'tuesday_pax_4', 'tuesday_pax_5', 'tuesday_pax_6')
    def _onchange_tuesday_pax(self):
        for field in ['tuesday_pax_1', 'tuesday_pax_2', 'tuesday_pax_3', 'tuesday_pax_4', 'tuesday_pax_5', 'tuesday_pax_6']:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Tuesday cannot be less than 0.") % self._fields[field].string)

    tuesday_child_pax_1 = fields.Float(
        string="1 Child (Tuesday)", tracking=True, default=0)
    tuesday_child_pax_2 = fields.Float(
        string="2 Children (Tuesday)", tracking=True, default=0)
    tuesday_child_pax_3 = fields.Float(
        string="3 Children (Tuesday)", tracking=True, default=0)
    tuesday_child_pax_4 = fields.Float(
        string="4 Children (Tuesday)", tracking=True, default=0)
    tuesday_child_pax_5 = fields.Float(
        string="5 Children (Tuesday)", tracking=True, default=0)
    tuesday_child_pax_6 = fields.Float(
        string="6 Children (Tuesday)", tracking=True, default=0)

    @api.onchange(
        'tuesday_child_pax_1', 'tuesday_child_pax_2', 'tuesday_child_pax_3',
        'tuesday_child_pax_4', 'tuesday_child_pax_5', 'tuesday_child_pax_6'
    )
    def _onchange_tuesday_child_pax(self):
        for field in [
            'tuesday_child_pax_1', 'tuesday_child_pax_2', 'tuesday_child_pax_3',
            'tuesday_child_pax_4', 'tuesday_child_pax_5', 'tuesday_child_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Tuesday cannot be less than 0.") % self._fields[field].string)

    tuesday_infant_pax_1 = fields.Float(
        string="1 Infant (Tuesday)", tracking=True, default=0)
    tuesday_infant_pax_2 = fields.Float(
        string="2 Infants (Tuesday)", tracking=True, default=0)
    tuesday_infant_pax_3 = fields.Float(
        string="3 Infants (Tuesday)", tracking=True, default=0)
    tuesday_infant_pax_4 = fields.Float(
        string="4 Infants (Tuesday)", tracking=True, default=0)
    tuesday_infant_pax_5 = fields.Float(
        string="5 Infants (Tuesday)", tracking=True, default=0)
    tuesday_infant_pax_6 = fields.Float(
        string="6 Infants (Tuesday)", tracking=True, default=0)

    @api.onchange(
        'tuesday_infant_pax_1', 'tuesday_infant_pax_2', 'tuesday_infant_pax_3',
        'tuesday_infant_pax_4', 'tuesday_infant_pax_5', 'tuesday_infant_pax_6'
    )
    def _onchange_tuesday_infant_pax(self):
        for field in [
            'tuesday_infant_pax_1', 'tuesday_infant_pax_2', 'tuesday_infant_pax_3',
            'tuesday_infant_pax_4', 'tuesday_infant_pax_5', 'tuesday_infant_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Tuesday cannot be less than 0.") % self._fields[field].string)

    # Pax Rates for Wednesday
    wednesday_pax_1 = fields.Float(
        string="1 Pax (Wednesday)", tracking=True, default=0)
    wednesday_pax_2 = fields.Float(
        string="2 Pax (Wednesday)", tracking=True, default=0)
    wednesday_pax_3 = fields.Float(
        string="3 Pax (Wednesday)", tracking=True, default=0)
    wednesday_pax_4 = fields.Float(
        string="4 Pax (Wednesday)", tracking=True, default=0)
    wednesday_pax_5 = fields.Float(
        string="5 Pax (Wednesday)", tracking=True, default=0)
    wednesday_pax_6 = fields.Float(
        string="6 Pax (Wednesday)", tracking=True, default=0)

    @api.onchange('wednesday_pax_1', 'wednesday_pax_2', 'wednesday_pax_3', 'wednesday_pax_4', 'wednesday_pax_5', 'wednesday_pax_6')
    def _onchange_wednesday_pax(self):
        for field in ['wednesday_pax_1', 'wednesday_pax_2', 'wednesday_pax_3', 'wednesday_pax_4', 'wednesday_pax_5', 'wednesday_pax_6']:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Wednesday cannot be less than 0.") % self._fields[field].string)

    # Child Pax Rates for Wednesday
    wednesday_child_pax_1 = fields.Float(
        string="1 Child (Wednesday)", tracking=True, default=0)
    wednesday_child_pax_2 = fields.Float(
        string="2 Children (Wednesday)", tracking=True, default=0)
    wednesday_child_pax_3 = fields.Float(
        string="3 Children (Wednesday)", tracking=True, default=0)
    wednesday_child_pax_4 = fields.Float(
        string="4 Children (Wednesday)", tracking=True, default=0)
    wednesday_child_pax_5 = fields.Float(
        string="5 Children (Wednesday)", tracking=True, default=0)
    wednesday_child_pax_6 = fields.Float(
        string="6 Children (Wednesday)", tracking=True, default=0)

    @api.onchange('wednesday_child_pax_1', 'wednesday_child_pax_2', 'wednesday_child_pax_3', 'wednesday_child_pax_4', 'wednesday_child_pax_5', 'wednesday_child_pax_6')
    def _onchange_wednesday_child_pax(self):
        for field in [
            'wednesday_child_pax_1', 'wednesday_child_pax_2', 'wednesday_child_pax_3',
            'wednesday_child_pax_4', 'wednesday_child_pax_5', 'wednesday_child_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Wednesday cannot be less than 0.") % self._fields[field].string)

    # Infant Pax Rates for Wednesday
    wednesday_infant_pax_1 = fields.Float(
        string="1 Infant (Wednesday)", tracking=True, default=0)
    wednesday_infant_pax_2 = fields.Float(
        string="2 Infants (Wednesday)", tracking=True, default=0)
    wednesday_infant_pax_3 = fields.Float(
        string="3 Infants (Wednesday)", tracking=True, default=0)
    wednesday_infant_pax_4 = fields.Float(
        string="4 Infants (Wednesday)", tracking=True, default=0)
    wednesday_infant_pax_5 = fields.Float(
        string="5 Infants (Wednesday)", tracking=True, default=0)
    wednesday_infant_pax_6 = fields.Float(
        string="6 Infants (Wednesday)", tracking=True, default=0)

    @api.onchange(
        'wednesday_infant_pax_1', 'wednesday_infant_pax_2', 'wednesday_infant_pax_3',
        'wednesday_infant_pax_4', 'wednesday_infant_pax_5', 'wednesday_infant_pax_6'
    )
    def _onchange_wednesday_infant_pax(self):
        for field in [
            'wednesday_infant_pax_1', 'wednesday_infant_pax_2', 'wednesday_infant_pax_3',
            'wednesday_infant_pax_4', 'wednesday_infant_pax_5', 'wednesday_infant_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Wednesday cannot be less than 0.") % self._fields[field].string)

    # Pax Rates for Thursday
    thursday_pax_1 = fields.Float(
        string="1 Pax (Thursday)", tracking=True, default=0)
    thursday_pax_2 = fields.Float(
        string="2 Pax (Thursday)", tracking=True, default=0)
    thursday_pax_3 = fields.Float(
        string="3 Pax (Thursday)", tracking=True, default=0)
    thursday_pax_4 = fields.Float(
        string="4 Pax (Thursday)", tracking=True, default=0)
    thursday_pax_5 = fields.Float(
        string="5 Pax (Thursday)", tracking=True, default=0)
    thursday_pax_6 = fields.Float(
        string="6 Pax (Thursday)", tracking=True, default=0)

    @api.onchange('thursday_pax_1', 'thursday_pax_2', 'thursday_pax_3', 'thursday_pax_4', 'thursday_pax_5', 'thursday_pax_6')
    def _onchange_thursday_pax(self):
        for field in ['thursday_pax_1', 'thursday_pax_2', 'thursday_pax_3', 'thursday_pax_4', 'thursday_pax_5', 'thursday_pax_6']:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Thursday cannot be less than 0.") % self._fields[field].string)

    # Child Pax Rates for Thursday
    thursday_child_pax_1 = fields.Float(
        string="1 Child (Thursday)", tracking=True, default=0)
    thursday_child_pax_2 = fields.Float(
        string="2 Children (Thursday)", tracking=True, default=0)
    thursday_child_pax_3 = fields.Float(
        string="3 Children (Thursday)", tracking=True, default=0)
    thursday_child_pax_4 = fields.Float(
        string="4 Children (Thursday)", tracking=True, default=0)
    thursday_child_pax_5 = fields.Float(
        string="5 Children (Thursday)", tracking=True, default=0)
    thursday_child_pax_6 = fields.Float(
        string="6 Children (Thursday)", tracking=True, default=0)

    @api.onchange('thursday_child_pax_1', 'thursday_child_pax_2', 'thursday_child_pax_3', 'thursday_child_pax_4', 'thursday_child_pax_5', 'thursday_child_pax_6')
    def _onchange_thursday_child_pax(self):
        for field in [
            'thursday_child_pax_1', 'thursday_child_pax_2', 'thursday_child_pax_3',
            'thursday_child_pax_4', 'thursday_child_pax_5', 'thursday_child_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Thursday cannot be less than 0.") % self._fields[field].string)

        # Infant Pax Rates for Thursday
    thursday_infant_pax_1 = fields.Float(
        string="1 Infant (Thursday)", tracking=True, default=0)
    thursday_infant_pax_2 = fields.Float(
        string="2 Infants (Thursday)", tracking=True, default=0)
    thursday_infant_pax_3 = fields.Float(
        string="3 Infants (Thursday)", tracking=True, default=0)
    thursday_infant_pax_4 = fields.Float(
        string="4 Infants (Thursday)", tracking=True, default=0)
    thursday_infant_pax_5 = fields.Float(
        string="5 Infants (Thursday)", tracking=True, default=0)
    thursday_infant_pax_6 = fields.Float(
        string="6 Infants (Thursday)", tracking=True, default=0)

    @api.onchange(
        'thursday_infant_pax_1', 'thursday_infant_pax_2', 'thursday_infant_pax_3',
        'thursday_infant_pax_4', 'thursday_infant_pax_5', 'thursday_infant_pax_6'
    )
    def _onchange_thursday_infant_pax(self):
        for field in [
            'thursday_infant_pax_1', 'thursday_infant_pax_2', 'thursday_infant_pax_3',
            'thursday_infant_pax_4', 'thursday_infant_pax_5', 'thursday_infant_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Thursday cannot be less than 0.") % self._fields[field].string)

    # Pax Rates for Friday
    friday_pax_1 = fields.Float(
        string="1 Pax (Friday)", tracking=True, default=0)
    friday_pax_2 = fields.Float(
        string="2 Pax (Friday)", tracking=True, default=0)
    friday_pax_3 = fields.Float(
        string="3 Pax (Friday)", tracking=True, default=0)
    friday_pax_4 = fields.Float(
        string="4 Pax (Friday)", tracking=True, default=0)
    friday_pax_5 = fields.Float(
        string="5 Pax (Friday)", tracking=True, default=0)
    friday_pax_6 = fields.Float(
        string="6 Pax (Friday)", tracking=True, default=0)

    @api.onchange('friday_pax_1', 'friday_pax_2', 'friday_pax_3', 'friday_pax_4', 'friday_pax_5', 'friday_pax_6')
    def _onchange_friday_pax(self):
        for field in ['friday_pax_1', 'friday_pax_2', 'friday_pax_3', 'friday_pax_4', 'friday_pax_5', 'friday_pax_6']:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Friday cannot be less than 0.") % self._fields[field].string)

    # Child Pax Rates for Friday
    friday_child_pax_1 = fields.Float(
        string="1 Child (Friday)", tracking=True, default=0)
    friday_child_pax_2 = fields.Float(
        string="2 Children (Friday)", tracking=True, default=0)
    friday_child_pax_3 = fields.Float(
        string="3 Children (Friday)", tracking=True, default=0)
    friday_child_pax_4 = fields.Float(
        string="4 Children (Friday)", tracking=True, default=0)
    friday_child_pax_5 = fields.Float(
        string="5 Children (Friday)", tracking=True, default=0)
    friday_child_pax_6 = fields.Float(
        string="6 Children (Friday)", tracking=True, default=0)

    @api.onchange(
        'friday_child_pax_1', 'friday_child_pax_2', 'friday_child_pax_3',
        'friday_child_pax_4', 'friday_child_pax_5', 'friday_child_pax_6'
    )
    def _onchange_friday_child_pax(self):
        for field in [
            'friday_child_pax_1', 'friday_child_pax_2', 'friday_child_pax_3',
            'friday_child_pax_4', 'friday_child_pax_5', 'friday_child_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Friday cannot be less than 0.") % self._fields[field].string)

    # Infant Pax Rates for Friday
    friday_infant_pax_1 = fields.Float(
        string="1 Infant (Friday)", tracking=True, default=0)
    friday_infant_pax_2 = fields.Float(
        string="2 Infants (Friday)", tracking=True, default=0)
    friday_infant_pax_3 = fields.Float(
        string="3 Infants (Friday)", tracking=True, default=0)
    friday_infant_pax_4 = fields.Float(
        string="4 Infants (Friday)", tracking=True, default=0)
    friday_infant_pax_5 = fields.Float(
        string="5 Infants (Friday)", tracking=True, default=0)
    friday_infant_pax_6 = fields.Float(
        string="6 Infants (Friday)", tracking=True, default=0)

    @api.onchange(
        'friday_infant_pax_1', 'friday_infant_pax_2', 'friday_infant_pax_3',
        'friday_infant_pax_4', 'friday_infant_pax_5', 'friday_infant_pax_6'
    )
    def _onchange_friday_infant_pax(self):
        for field in [
            'friday_infant_pax_1', 'friday_infant_pax_2', 'friday_infant_pax_3',
            'friday_infant_pax_4', 'friday_infant_pax_5', 'friday_infant_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Friday cannot be less than 0.") % self._fields[field].string)

    # Pax Rates for Saturday
    saturday_pax_1 = fields.Float(
        string="1 Pax (Saturday)", tracking=True, default=0)
    saturday_pax_2 = fields.Float(
        string="2 Pax (Saturday)", tracking=True, default=0)
    saturday_pax_3 = fields.Float(
        string="3 Pax (Saturday)", tracking=True, default=0)
    saturday_pax_4 = fields.Float(
        string="4 Pax (Saturday)", tracking=True, default=0)
    saturday_pax_5 = fields.Float(
        string="5 Pax (Saturday)", tracking=True, default=0)
    saturday_pax_6 = fields.Float(
        string="6 Pax (Saturday)", tracking=True, default=0)

    @api.onchange('saturday_pax_1', 'saturday_pax_2', 'saturday_pax_3', 'saturday_pax_4', 'saturday_pax_5', 'saturday_pax_6')
    def _onchange_saturday_pax(self):
        for field in ['saturday_pax_1', 'saturday_pax_2', 'saturday_pax_3', 'saturday_pax_4', 'saturday_pax_5', 'saturday_pax_6']:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Saturday cannot be less than 0.") % self._fields[field].string)

    # Child Pax Rates for Saturday
    saturday_child_pax_1 = fields.Float(
        string="1 Child (Saturday)", tracking=True, default=0)
    saturday_child_pax_2 = fields.Float(
        string="2 Children (Saturday)", tracking=True, default=0)
    saturday_child_pax_3 = fields.Float(
        string="3 Children (Saturday)", tracking=True, default=0)
    saturday_child_pax_4 = fields.Float(
        string="4 Children (Saturday)", tracking=True, default=0)
    saturday_child_pax_5 = fields.Float(
        string="5 Children (Saturday)", tracking=True, default=0)
    saturday_child_pax_6 = fields.Float(
        string="6 Children (Saturday)", tracking=True, default=0)

    @api.onchange(
        'saturday_child_pax_1', 'saturday_child_pax_2', 'saturday_child_pax_3',
        'saturday_child_pax_4', 'saturday_child_pax_5', 'saturday_child_pax_6'
    )
    def _onchange_saturday_child_pax(self):
        for field in [
            'saturday_child_pax_1', 'saturday_child_pax_2', 'saturday_child_pax_3',
            'saturday_child_pax_4', 'saturday_child_pax_5', 'saturday_child_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Saturday cannot be less than 0.") % self._fields[field].string)

    # Infant Pax Rates for Saturday
    saturday_infant_pax_1 = fields.Float(
        string="1 Infant (Saturday)", tracking=True, default=0)
    saturday_infant_pax_2 = fields.Float(
        string="2 Infants (Saturday)", tracking=True, default=0)
    saturday_infant_pax_3 = fields.Float(
        string="3 Infants (Saturday)", tracking=True, default=0)
    saturday_infant_pax_4 = fields.Float(
        string="4 Infants (Saturday)", tracking=True, default=0)
    saturday_infant_pax_5 = fields.Float(
        string="5 Infants (Saturday)", tracking=True, default=0)
    saturday_infant_pax_6 = fields.Float(
        string="6 Infants (Saturday)", tracking=True, default=0)

    @api.onchange(
        'saturday_infant_pax_1', 'saturday_infant_pax_2', 'saturday_infant_pax_3',
        'saturday_infant_pax_4', 'saturday_infant_pax_5', 'saturday_infant_pax_6'
    )
    def _onchange_saturday_infant_pax(self):
        for field in [
            'saturday_infant_pax_1', 'saturday_infant_pax_2', 'saturday_infant_pax_3',
            'saturday_infant_pax_4', 'saturday_infant_pax_5', 'saturday_infant_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Saturday cannot be less than 0.") % self._fields[field].string)

    # Pax Rates for Sunday
    sunday_pax_1 = fields.Float(
        string="1 Pax (Sunday)", tracking=True, default=0)
    sunday_pax_2 = fields.Float(
        string="2 Pax (Sunday)", tracking=True, default=0)
    sunday_pax_3 = fields.Float(
        string="3 Pax (Sunday)", tracking=True, default=0)
    sunday_pax_4 = fields.Float(
        string="4 Pax (Sunday)", tracking=True, default=0)
    sunday_pax_5 = fields.Float(
        string="5 Pax (Sunday)", tracking=True, default=0)
    sunday_pax_6 = fields.Float(
        string="6 Pax (Sunday)", tracking=True, default=0)

    @api.onchange('sunday_pax_1', 'sunday_pax_2', 'sunday_pax_3', 'sunday_pax_4', 'sunday_pax_5', 'sunday_pax_6')
    def _onchange_sunday_pax(self):
        for field in ['sunday_pax_1', 'sunday_pax_2', 'sunday_pax_3', 'sunday_pax_4', 'sunday_pax_5', 'sunday_pax_6']:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Sunday cannot be less than 0.") % self._fields[field].string)

    sunday_child_pax_1 = fields.Float(
        string="1 Child (Sunday)", tracking=True, default=0)
    sunday_child_pax_2 = fields.Float(
        string="2 Children (Sunday)", tracking=True, default=0)
    sunday_child_pax_3 = fields.Float(
        string="3 Children (Sunday)", tracking=True, default=0)
    sunday_child_pax_4 = fields.Float(
        string="4 Children (Sunday)", tracking=True, default=0)
    sunday_child_pax_5 = fields.Float(
        string="5 Children (Sunday)", tracking=True, default=0)
    sunday_child_pax_6 = fields.Float(
        string="6 Children (Sunday)", tracking=True, default=0)

    @api.onchange(
        'sunday_child_pax_1', 'sunday_child_pax_2', 'sunday_child_pax_3',
        'sunday_child_pax_4', 'sunday_child_pax_5', 'sunday_child_pax_6'
    )
    def _onchange_sunday_child_pax(self):
        for field in [
            'sunday_child_pax_1', 'sunday_child_pax_2', 'sunday_child_pax_3',
            'sunday_child_pax_4', 'sunday_child_pax_5', 'sunday_child_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Sunday cannot be less than 0.") % self._fields[field].string)

    # Infant Pax Rates for Sunday
    sunday_infant_pax_1 = fields.Float(
        string="1 Infant (Sunday)", tracking=True, default=0)
    sunday_infant_pax_2 = fields.Float(
        string="2 Infants (Sunday)", tracking=True, default=0)
    sunday_infant_pax_3 = fields.Float(
        string="3 Infants (Sunday)", tracking=True, default=0)
    sunday_infant_pax_4 = fields.Float(
        string="4 Infants (Sunday)", tracking=True, default=0)
    sunday_infant_pax_5 = fields.Float(
        string="5 Infants (Sunday)", tracking=True, default=0)
    sunday_infant_pax_6 = fields.Float(
        string="6 Infants (Sunday)", tracking=True, default=0)

    @api.onchange(
        'sunday_infant_pax_1', 'sunday_infant_pax_2', 'sunday_infant_pax_3',
        'sunday_infant_pax_4', 'sunday_infant_pax_5', 'sunday_infant_pax_6'
    )
    def _onchange_sunday_infant_pax(self):
        for field in [
            'sunday_infant_pax_1', 'sunday_infant_pax_2', 'sunday_infant_pax_3',
            'sunday_infant_pax_4', 'sunday_infant_pax_5', 'sunday_infant_pax_6'
        ]:
            if getattr(self, field, 1) < 0:
                raise ValidationError(
                    _("The value for '%s' on Sunday cannot be less than 0.") % self._fields[field].string)

    monday_checkbox = fields.Boolean(
        string="Apply Default for Monday", tracking=True)
    tuesday_checkbox = fields.Boolean(
        string="Apply Default for Tuesday", tracking=True)
    wednesday_checkbox = fields.Boolean(
        string="Apply Default for Wednesday", tracking=True)
    thursday_checkbox = fields.Boolean(
        string="Apply Default for Thursday", tracking=True)
    friday_checkbox = fields.Boolean(
        string="Apply Default for Friday", tracking=True)
    saturday_checkbox = fields.Boolean(
        string="Apply Default for Saturday", tracking=True)
    sunday_checkbox = fields.Boolean(
        string="Apply Default for Sunday", tracking=True)

    monday_checkbox_child = fields.Boolean(
        string="Apply Default for Monday", tracking=True)
    tuesday_checkbox_child = fields.Boolean(
        string="Apply Default for Tuesday", tracking=True)
    wednesday_checkbox_child = fields.Boolean(
        string="Apply Default for Wednesday", tracking=True)
    thursday_checkbox_child = fields.Boolean(
        string="Apply Default for Thursday", tracking=True)
    friday_checkbox_child = fields.Boolean(
        string="Apply Default for Friday", tracking=True)
    saturday_checkbox_child = fields.Boolean(
        string="Apply Default for Saturday", tracking=True)
    sunday_checkbox_child = fields.Boolean(
        string="Apply Default for Sunday", tracking=True)

    monday_checkbox_infant = fields.Boolean(
        string="Apply Default for Monday (Infant)", tracking=True)
    tuesday_checkbox_infant = fields.Boolean(
        string="Apply Default for Tuesday (Infant)", tracking=True)
    wednesday_checkbox_infant = fields.Boolean(
        string="Apply Default for Wednesday (Infant)", tracking=True)
    thursday_checkbox_infant = fields.Boolean(
        string="Apply Default for Thursday (Infant)", tracking=True)
    friday_checkbox_infant = fields.Boolean(
        string="Apply Default for Friday (Infant)", tracking=True)
    saturday_checkbox_infant = fields.Boolean(
        string="Apply Default for Saturday (Infant)", tracking=True)
    sunday_checkbox_infant = fields.Boolean(
        string="Apply Default for Sunday (Infant)", tracking=True)

    # Onchange methods for each checkbox

    @api.onchange('monday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6', 'child_pax_1', 'infant_pax_1')
    def _onchange_monday_checkbox(self):
        if self.monday_checkbox:
            print("Monday Checkbox")
            self.monday_pax_1 = self.pax_1
            self.monday_pax_2 = self.pax_2
            self.monday_pax_3 = self.pax_3
            self.monday_pax_4 = self.pax_4
            self.monday_pax_5 = self.pax_5
            self.monday_pax_6 = self.pax_6
            self.monday_child_pax_1 = self.child_pax_1
            self.monday_infant_pax_1 = self.infant_pax_1

    @api.onchange('monday_checkbox_child', 'child_pax_1', 'child_pax_2', 'child_pax_3', 'child_pax_4', 'child_pax_5', 'child_pax_6')
    def _onchange_monday_child_checkbox(self):
        if self.monday_checkbox_child:
            self.monday_child_pax_1 = self.child_pax_1
            self.monday_child_pax_2 = self.child_pax_2
            self.monday_child_pax_3 = self.child_pax_3
            self.monday_child_pax_4 = self.child_pax_4
            self.monday_child_pax_5 = self.child_pax_5
            self.monday_child_pax_6 = self.child_pax_6

    @api.onchange('tuesday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6', 'child_pax_1', 'infant_pax_1')
    def _onchange_tuesday_checkbox(self):
        if self.tuesday_checkbox:
            self.tuesday_pax_1 = self.pax_1
            self.tuesday_pax_2 = self.pax_2
            self.tuesday_pax_3 = self.pax_3
            self.tuesday_pax_4 = self.pax_4
            self.tuesday_pax_5 = self.pax_5
            self.tuesday_pax_6 = self.pax_6
            self.tuesday_child_pax_1 = self.child_pax_1
            self.tuesday_infant_pax_1 = self.infant_pax_1

    @api.onchange('tuesday_checkbox_child', 'child_pax_1', 'child_pax_2', 'child_pax_3', 'child_pax_4', 'child_pax_5', 'child_pax_6')
    def _onchange_tuesday_child_checkbox(self):
        if self.tuesday_checkbox_child:
            self.tuesday_child_pax_1 = self.child_pax_1
            self.tuesday_child_pax_2 = self.child_pax_2
            self.tuesday_child_pax_3 = self.child_pax_3
            self.tuesday_child_pax_4 = self.child_pax_4
            self.tuesday_child_pax_5 = self.child_pax_5
            self.tuesday_child_pax_6 = self.child_pax_6

    @api.onchange('wednesday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6', 'child_pax_1', 'infant_pax_1')
    def _onchange_wednesday_checkbox(self):
        if self.wednesday_checkbox:
            self.wednesday_pax_1 = self.pax_1
            self.wednesday_pax_2 = self.pax_2
            self.wednesday_pax_3 = self.pax_3
            self.wednesday_pax_4 = self.pax_4
            self.wednesday_pax_5 = self.pax_5
            self.wednesday_pax_6 = self.pax_6
            self.wednesday_child_pax_1 = self.child_pax_1
            self.wednesday_infant_pax_1 = self.infant_pax_1

    @api.onchange('wednesday_checkbox_child', 'child_pax_1', 'child_pax_2', 'child_pax_3', 'child_pax_4', 'child_pax_5', 'child_pax_6')
    def _onchange_wednesday_child_checkbox(self):
        if self.wednesday_checkbox_child:
            self.wednesday_child_pax_1 = self.child_pax_1
            self.wednesday_child_pax_2 = self.child_pax_2
            self.wednesday_child_pax_3 = self.child_pax_3
            self.wednesday_child_pax_4 = self.child_pax_4
            self.wednesday_child_pax_5 = self.child_pax_5
            self.wednesday_child_pax_6 = self.child_pax_6

    @api.onchange('thursday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6', 'child_pax_1', 'infant_pax_1')
    def _onchange_thursday_checkbox(self):
        if self.thursday_checkbox:
            self.thursday_pax_1 = self.pax_1
            self.thursday_pax_2 = self.pax_2
            self.thursday_pax_3 = self.pax_3
            self.thursday_pax_4 = self.pax_4
            self.thursday_pax_5 = self.pax_5
            self.thursday_pax_6 = self.pax_6
            self.thursday_child_pax_1 = self.child_pax_1
            self.thursday_infant_pax_1 = self.infant_pax_1

    @api.onchange('thursday_checkbox_child', 'child_pax_1', 'child_pax_2', 'child_pax_3', 'child_pax_4', 'child_pax_5', 'child_pax_6')
    def _onchange_thursday_child_checkbox(self):
        if self.thursday_checkbox_child:
            self.thursday_child_pax_1 = self.child_pax_1
            self.thursday_child_pax_2 = self.child_pax_2
            self.thursday_child_pax_3 = self.child_pax_3
            self.thursday_child_pax_4 = self.child_pax_4
            self.thursday_child_pax_5 = self.child_pax_5
            self.thursday_child_pax_6 = self.child_pax_6

    @api.onchange('friday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6', 'child_pax_1', 'infant_pax_1')
    def _onchange_friday_checkbox(self):
        if self.friday_checkbox:
            self.friday_pax_1 = self.pax_1
            self.friday_pax_2 = self.pax_2
            self.friday_pax_3 = self.pax_3
            self.friday_pax_4 = self.pax_4
            self.friday_pax_5 = self.pax_5
            self.friday_pax_6 = self.pax_6
            self.friday_child_pax_1 = self.child_pax_1
            self.friday_infant_pax_1 = self.infant_pax_1

    @api.onchange('friday_checkbox_child', 'child_pax_1', 'child_pax_2', 'child_pax_3', 'child_pax_4', 'child_pax_5', 'child_pax_6')
    def _onchange_friday_child_checkbox(self):
        if self.friday_checkbox_child:
            self.friday_child_pax_1 = self.child_pax_1
            self.friday_child_pax_2 = self.child_pax_2
            self.friday_child_pax_3 = self.child_pax_3
            self.friday_child_pax_4 = self.child_pax_4
            self.friday_child_pax_5 = self.child_pax_5
            self.friday_child_pax_6 = self.child_pax_6

    @api.onchange('saturday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6', 'child_pax_1', 'infant_pax_1')
    def _onchange_saturday_checkbox(self):
        if self.saturday_checkbox:
            self.saturday_pax_1 = self.pax_1
            self.saturday_pax_2 = self.pax_2
            self.saturday_pax_3 = self.pax_3
            self.saturday_pax_4 = self.pax_4
            self.saturday_pax_5 = self.pax_5
            self.saturday_pax_6 = self.pax_6
            self.saturday_child_pax_1 = self.child_pax_1
            self.saturday_infant_pax_1 = self.infant_pax_1

    @api.onchange('saturday_checkbox_child', 'child_pax_1', 'child_pax_2', 'child_pax_3', 'child_pax_4', 'child_pax_5', 'child_pax_6')
    def _onchange_saturday_child_checkbox(self):
        if self.saturday_checkbox_child:
            self.saturday_child_pax_1 = self.child_pax_1
            self.saturday_child_pax_2 = self.child_pax_2
            self.saturday_child_pax_3 = self.child_pax_3
            self.saturday_child_pax_4 = self.child_pax_4
            self.saturday_child_pax_5 = self.child_pax_5
            self.saturday_child_pax_6 = self.child_pax_6

    @api.onchange('sunday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6', 'child_pax_1', 'infant_pax_1')
    def _onchange_sunday_checkbox(self):
        if self.sunday_checkbox:
            self.sunday_pax_1 = self.pax_1
            self.sunday_pax_2 = self.pax_2
            self.sunday_pax_3 = self.pax_3
            self.sunday_pax_4 = self.pax_4
            self.sunday_pax_5 = self.pax_5
            self.sunday_pax_6 = self.pax_6
            self.sunday_child_pax_1 = self.child_pax_1
            self.sunday_infant_pax_1 = self.infant_pax_1

    @api.onchange('sunday_checkbox_child', 'child_pax_1', 'child_pax_2', 'child_pax_3', 'child_pax_4', 'child_pax_5', 'child_pax_6')
    def _onchange_sunday_child_checkbox(self):
        if self.sunday_checkbox_child:
            self.sunday_child_pax_1 = self.child_pax_1
            self.sunday_child_pax_2 = self.child_pax_2
            self.sunday_child_pax_3 = self.child_pax_3
            self.sunday_child_pax_4 = self.child_pax_4
            self.sunday_child_pax_5 = self.child_pax_5
            self.sunday_child_pax_6 = self.child_pax_6

    # infant onchange

    @api.onchange(
        'monday_checkbox_infant', 'infant_pax_1', 'infant_pax_2', 'infant_pax_3',
        'infant_pax_4', 'infant_pax_5', 'infant_pax_6'
    )
    def _onchange_monday_checkbox_infant(self):
        if self.monday_checkbox_infant:
            self.monday_infant_pax_1 = self.infant_pax_1
            self.monday_infant_pax_2 = self.infant_pax_2
            self.monday_infant_pax_3 = self.infant_pax_3
            self.monday_infant_pax_4 = self.infant_pax_4
            self.monday_infant_pax_5 = self.infant_pax_5
            self.monday_infant_pax_6 = self.infant_pax_6

    @api.onchange(
        'tuesday_checkbox_infant', 'infant_pax_1', 'infant_pax_2', 'infant_pax_3',
        'infant_pax_4', 'infant_pax_5', 'infant_pax_6'
    )
    def _onchange_tuesday_checkbox_infant(self):
        if self.tuesday_checkbox_infant:
            self.tuesday_infant_pax_1 = self.infant_pax_1
            self.tuesday_infant_pax_2 = self.infant_pax_2
            self.tuesday_infant_pax_3 = self.infant_pax_3
            self.tuesday_infant_pax_4 = self.infant_pax_4
            self.tuesday_infant_pax_5 = self.infant_pax_5
            self.tuesday_infant_pax_6 = self.infant_pax_6

    @api.onchange(
        'wednesday_checkbox_infant', 'infant_pax_1', 'infant_pax_2', 'infant_pax_3',
        'infant_pax_4', 'infant_pax_5', 'infant_pax_6'
    )
    def _onchange_wednesday_checkbox_infant(self):
        if self.wednesday_checkbox_infant:
            self.wednesday_infant_pax_1 = self.infant_pax_1
            self.wednesday_infant_pax_2 = self.infant_pax_2
            self.wednesday_infant_pax_3 = self.infant_pax_3
            self.wednesday_infant_pax_4 = self.infant_pax_4
            self.wednesday_infant_pax_5 = self.infant_pax_5
            self.wednesday_infant_pax_6 = self.infant_pax_6

    @api.onchange(
        'thursday_checkbox_infant', 'infant_pax_1', 'infant_pax_2', 'infant_pax_3',
        'infant_pax_4', 'infant_pax_5', 'infant_pax_6'
    )
    def _onchange_thursday_checkbox_infant(self):
        if self.thursday_checkbox_infant:
            self.thursday_infant_pax_1 = self.infant_pax_1
            self.thursday_infant_pax_2 = self.infant_pax_2
            self.thursday_infant_pax_3 = self.infant_pax_3
            self.thursday_infant_pax_4 = self.infant_pax_4
            self.thursday_infant_pax_5 = self.infant_pax_5
            self.thursday_infant_pax_6 = self.infant_pax_6

    @api.onchange(
        'friday_checkbox_infant', 'infant_pax_1', 'infant_pax_2', 'infant_pax_3',
        'infant_pax_4', 'infant_pax_5', 'infant_pax_6'
    )
    def _onchange_friday_checkbox_infant(self):
        if self.friday_checkbox_infant:
            self.friday_infant_pax_1 = self.infant_pax_1
            self.friday_infant_pax_2 = self.infant_pax_2
            self.friday_infant_pax_3 = self.infant_pax_3
            self.friday_infant_pax_4 = self.infant_pax_4
            self.friday_infant_pax_5 = self.infant_pax_5
            self.friday_infant_pax_6 = self.infant_pax_6

    @api.onchange(
        'saturday_checkbox_infant', 'infant_pax_1', 'infant_pax_2', 'infant_pax_3',
        'infant_pax_4', 'infant_pax_5', 'infant_pax_6'
    )
    def _onchange_saturday_checkbox_infant(self):
        if self.saturday_checkbox_infant:
            self.saturday_infant_pax_1 = self.infant_pax_1
            self.saturday_infant_pax_2 = self.infant_pax_2
            self.saturday_infant_pax_3 = self.infant_pax_3
            self.saturday_infant_pax_4 = self.infant_pax_4
            self.saturday_infant_pax_5 = self.infant_pax_5
            self.saturday_infant_pax_6 = self.infant_pax_6

    @api.onchange(
        'sunday_checkbox_infant', 'infant_pax_1', 'infant_pax_2', 'infant_pax_3',
        'infant_pax_4', 'infant_pax_5', 'infant_pax_6'
    )
    def _onchange_sunday_checkbox_infant(self):
        if self.sunday_checkbox_infant:
            self.sunday_infant_pax_1 = self.infant_pax_1
            self.sunday_infant_pax_2 = self.infant_pax_2
            self.sunday_infant_pax_3 = self.infant_pax_3
            self.sunday_infant_pax_4 = self.infant_pax_4
            self.sunday_infant_pax_5 = self.infant_pax_5
            self.sunday_infant_pax_6 = self.infant_pax_6

    # Price Type and Meal Pattern Fields
    price_type = fields.Selection([
        ('rate_meals', 'Rate and Meals Price'),
        ('room_only', 'Room Only')
    ], string="Price Type", required=True, tracking=True, default='room_only')

    meal_pattern_id = fields.Many2one(
        'meal.pattern', string="Meal Pattern", tracking=True)

    rate_meal_pattern = fields.Many2one(
        'meal.pattern', string="Meal Pattern", tracking=True)

    packages_line_number = fields.Integer(string="Line", tracking=True)
    packages_posting_item = fields.Many2one(
        'posting.item', string="Posting Item", tracking=True)
    packages_value = fields.Integer(string="Value", tracking=True, default=0)

    @api.onchange('packages_value')
    def _onchange_packages_value(self):
        for record in self:
            if record.packages_value < 0:
                raise ValidationError("Value cannot be less than zero.")

    packages_rhythm = fields.Selection([
        ('every_night', 'Every Night'),
        ('first_night', 'First Night')
    ], string="Rhythm", default='every_night', tracking=True)

    packages_value_type = fields.Selection([
        ('added_value', 'Added Value'),
        ('per_pax', 'Per Pax')
    ], string="Value Type", default='added_value', tracking=True)

    rate_detail_child = fields.Integer(
        string="Child", tracking=True, default=0)
    rate_detail_infant = fields.Integer(
        string="Infant", tracking=True, default=0)

    @api.onchange('rate_detail_child', 'rate_detail_infant')
    def _onchange_check_minimum_value_child_infant(self):
        for field_name in ['rate_detail_child', 'rate_detail_infant']:
            if getattr(self, field_name, 0) < 0:
                raise ValidationError(
                    _("The value for '%s' cannot be less than 0.") % self._fields[field_name].string
                )

    def action_set_room_type_rate(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Room Type Specific Rate',
            'res_model': 'room.type.specific.rate',
            # Show the tree view first, and allow form view when a record is selected
            'view_mode': 'tree,form',
            'view_type': 'form',
            'target': 'current',  # Use 'current' instead of 'new' to show the full tree and form view
            'context': {
                'default_rate_code_id': self.rate_code_id.id,
            },
            'domain': [('rate_code_id', '=', self.rate_code_id.id)]
        }

    def action_set_room_number_rate(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Room Number Specific Rate',
            'res_model': 'room.number.specific.rate',
            # Show the tree view first, and allow form view when a record is selected
            'view_mode': 'tree,form',
            'view_type': 'form',
            'target': 'current',  # Use 'current' instead of 'new' to show the full tree and form view
            'context': {
                'default_rate_code_id': self.rate_code_id.id,
            },
            'domain': [('rate_code_id', '=', self.rate_code_id.id)]
        }


class RoomTypeSpecificRate(models.Model):
    _name = 'room.type.specific.rate'
    _description = 'Room Type Specific Rate'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'room_type_id'
    # Fields for Room Type Specific Rate Model
    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True)
    rate_code_id = fields.Many2one(
        'rate.code', string="Rate Code", required=True, tracking=True)
    from_date = fields.Date(string="From Date", required=True, tracking=True)
    to_date = fields.Date(string="To Date", required=True, tracking=True)
    room_type_id = fields.Many2one(
        'room.type', string="Room Type", required=True, tracking=True)

    # Fields for Weekday Rates
    room_type_monday_pax_1 = fields.Float(string="Monday 1 Pax", tracking=True)
    room_type_monday_pax_2 = fields.Float(string="Monday 2 Pax", tracking=True)
    room_type_monday_pax_3 = fields.Float(string="Monday 3 Pax", tracking=True)
    room_type_monday_pax_4 = fields.Float(string="Monday 4 Pax", tracking=True)
    room_type_monday_pax_5 = fields.Float(string="Monday 5 Pax", tracking=True)
    room_type_monday_pax_6 = fields.Float(string="Monday 6 Pax", tracking=True)
    room_type_monday_child_pax_1 = fields.Float(
        string="Monday 1 Child", tracking=True)
    room_type_monday_infant_pax_1 = fields.Float(
        string="Monday 1 Infant", tracking=True)

    room_type_tuesday_pax_1 = fields.Float(
        string="Tuesday 1 Pax", tracking=True)
    room_type_tuesday_pax_2 = fields.Float(
        string="Tuesday 2 Pax", tracking=True)
    room_type_tuesday_pax_3 = fields.Float(
        string="Tuesday 3 Pax", tracking=True)
    room_type_tuesday_pax_4 = fields.Float(
        string="Tuesday 4 Pax", tracking=True)
    room_type_tuesday_pax_5 = fields.Float(
        string="Tuesday 5 Pax", tracking=True)
    room_type_tuesday_pax_6 = fields.Float(
        string="Tuesday 6 Pax", tracking=True)
    room_type_tuesday_child_pax_1 = fields.Float(
        string="Tuesday 1 Child", tracking=True)
    room_type_tuesday_infant_pax_1 = fields.Float(
        string="Tuesday 1 Infant", tracking=True)

    room_type_wednesday_pax_1 = fields.Float(
        string="Wednesday 1 Pax", tracking=True)
    room_type_wednesday_pax_2 = fields.Float(
        string="Wednesday 2 Pax", tracking=True)
    room_type_wednesday_pax_3 = fields.Float(
        string="Wednesday 3 Pax", tracking=True)
    room_type_wednesday_pax_4 = fields.Float(
        string="Wednesday 4 Pax", tracking=True)
    room_type_wednesday_pax_5 = fields.Float(
        string="Wednesday 5 Pax", tracking=True)
    room_type_wednesday_pax_6 = fields.Float(
        string="Wednesday 6 Pax", tracking=True)
    room_type_wednesday_child_pax_1 = fields.Float(
        string="Wednesday 1 Child", tracking=True)
    room_type_wednesday_infant_pax_1 = fields.Float(
        string="Wednesday 1 Infant", tracking=True)

    room_type_thursday_pax_1 = fields.Float(
        string="Thursday 1 Pax", tracking=True)
    room_type_thursday_pax_2 = fields.Float(
        string="Thursday 2 Pax", tracking=True)
    room_type_thursday_pax_3 = fields.Float(
        string="Thursday 3 Pax", tracking=True)
    room_type_thursday_pax_4 = fields.Float(
        string="Thursday 4 Pax", tracking=True)
    room_type_thursday_pax_5 = fields.Float(
        string="Thursday 5 Pax", tracking=True)
    room_type_thursday_pax_6 = fields.Float(
        string="Thursday 6 Pax", tracking=True)
    room_type_thursday_child_pax_1 = fields.Float(
        string="Thursday 1 Child", tracking=True)
    room_type_thursday_infant_pax_1 = fields.Float(
        string="Thursday 1 Infant", tracking=True)

    room_type_friday_pax_1 = fields.Float(string="Friday 1 Pax", tracking=True)
    room_type_friday_pax_2 = fields.Float(string="Friday 2 Pax", tracking=True)
    room_type_friday_pax_3 = fields.Float(string="Friday 3 Pax", tracking=True)
    room_type_friday_pax_4 = fields.Float(string="Friday 4 Pax", tracking=True)
    room_type_friday_pax_5 = fields.Float(string="Friday 5 Pax", tracking=True)
    room_type_friday_pax_6 = fields.Float(string="Friday 6 Pax", tracking=True)
    room_type_friday_child_pax_1 = fields.Float(
        string="Friday 1 Child", tracking=True)
    room_type_friday_infant_pax_1 = fields.Float(
        string="Friday 1 Infant", tracking=True)

    room_type_saturday_pax_1 = fields.Float(
        string="Saturday 1 Pax", tracking=True)
    room_type_saturday_pax_2 = fields.Float(
        string="Saturday 2 Pax", tracking=True)
    room_type_saturday_pax_3 = fields.Float(
        string="Saturday 3 Pax", tracking=True)
    room_type_saturday_pax_4 = fields.Float(
        string="Saturday 4 Pax", tracking=True)
    room_type_saturday_pax_5 = fields.Float(
        string="Saturday 5 Pax", tracking=True)
    room_type_saturday_pax_6 = fields.Float(
        string="Saturday 6 Pax", tracking=True)
    room_type_saturday_child_pax_1 = fields.Float(
        string="Saturday 1 Child", tracking=True)
    room_type_saturday_infant_pax_1 = fields.Float(
        string="Saturday 1 Infant", tracking=True)

    room_type_sunday_pax_1 = fields.Float(string="Sunday 1 Pax", tracking=True)
    room_type_sunday_pax_2 = fields.Float(string="Sunday 2 Pax", tracking=True)
    room_type_sunday_pax_3 = fields.Float(string="Sunday 3 Pax", tracking=True)
    room_type_sunday_pax_4 = fields.Float(string="Sunday 4 Pax", tracking=True)
    room_type_sunday_pax_5 = fields.Float(string="Sunday 5 Pax", tracking=True)
    room_type_sunday_pax_6 = fields.Float(string="Sunday 6 Pax", tracking=True)
    room_type_sunday_child_pax_1 = fields.Float(
        string="Sunday 1 Child", tracking=True)
    room_type_sunday_infant_pax_1 = fields.Float(
        string="Sunday 1 Infant", tracking=True)

    monday_checkbox_rt = fields.Boolean(
        string="Apply Default for Monday", tracking=True)
    tuesday_checkbox_rt = fields.Boolean(
        string="Apply Default for Tuesday", tracking=True)
    wednesday_checkbox_rt = fields.Boolean(
        string="Apply Default for Wednesday", tracking=True)
    thursday_checkbox_rt = fields.Boolean(
        string="Apply Default for Thursday", tracking=True)
    friday_checkbox_rt = fields.Boolean(
        string="Apply Default for Friday", tracking=True)
    saturday_checkbox_rt = fields.Boolean(
        string="Apply Default for Saturday", tracking=True)
    sunday_checkbox_rt = fields.Boolean(
        string="Apply Default for Sunday", tracking=True)

    # Room Prices for different configurations
    pax_1 = fields.Float(string="1 Pax", tracking=True)
    pax_2 = fields.Float(string="2 Pax", tracking=True)
    pax_3 = fields.Float(string="3 Pax", tracking=True)
    pax_4 = fields.Float(string="4 Pax", tracking=True)
    pax_5 = fields.Float(string="5 Pax", tracking=True)
    pax_6 = fields.Float(string="6 Pax", tracking=True)
    child_pax_1 = fields.Float(string="1 Child", tracking=True)
    infant_pax_1 = fields.Float(string="1 Infant", tracking=True)

    # Linked to rate.detail
    rate_detail_id = fields.Many2one(
        'rate.detail', string="Rate Detail", tracking=True)

    @api.model
    def default_get(self, fields_list):
        res = super(RoomTypeSpecificRate, self).default_get(fields_list)
        context = self.env.context

        # Get the rate_code_id from context if provided
        rate_code_id = context.get('default_rate_code_id')
        if rate_code_id:
            # Fetch the related rate.detail record
            rate_detail = self.env['rate.detail'].search(
                [('rate_code_id', '=', rate_code_id)], limit=1)
            if rate_detail:
                # Prefill the pax fields and weekday-specific fields with values from rate.detail
                res.update({
                    'pax_1': rate_detail.pax_1,
                    'pax_2': rate_detail.pax_2,
                    'pax_3': rate_detail.pax_3,
                    'pax_4': rate_detail.pax_4,
                    'pax_5': rate_detail.pax_5,
                    'pax_6': rate_detail.pax_6,

                    'room_type_monday_pax_1': rate_detail.monday_pax_1,
                    'room_type_monday_pax_2': rate_detail.monday_pax_2,
                    'room_type_monday_pax_3': rate_detail.monday_pax_3,
                    'room_type_monday_pax_4': rate_detail.monday_pax_4,
                    'room_type_monday_pax_5': rate_detail.monday_pax_5,
                    'room_type_monday_pax_6': rate_detail.monday_pax_6,

                    'room_type_tuesday_pax_1': rate_detail.tuesday_pax_1,
                    'room_type_tuesday_pax_2': rate_detail.tuesday_pax_2,
                    'room_type_tuesday_pax_3': rate_detail.tuesday_pax_3,
                    'room_type_tuesday_pax_4': rate_detail.tuesday_pax_4,
                    'room_type_tuesday_pax_5': rate_detail.tuesday_pax_5,
                    'room_type_tuesday_pax_6': rate_detail.tuesday_pax_6,

                    'room_type_wednesday_pax_1': rate_detail.wednesday_pax_1,
                    'room_type_wednesday_pax_2': rate_detail.wednesday_pax_2,
                    'room_type_wednesday_pax_3': rate_detail.wednesday_pax_3,
                    'room_type_wednesday_pax_4': rate_detail.wednesday_pax_4,
                    'room_type_wednesday_pax_5': rate_detail.wednesday_pax_5,
                    'room_type_wednesday_pax_6': rate_detail.wednesday_pax_6,

                    'room_type_thursday_pax_1': rate_detail.thursday_pax_1,
                    'room_type_thursday_pax_2': rate_detail.thursday_pax_2,
                    'room_type_thursday_pax_3': rate_detail.thursday_pax_3,
                    'room_type_thursday_pax_4': rate_detail.thursday_pax_4,
                    'room_type_thursday_pax_5': rate_detail.thursday_pax_5,
                    'room_type_thursday_pax_6': rate_detail.thursday_pax_6,

                    'room_type_friday_pax_1': rate_detail.friday_pax_1,
                    'room_type_friday_pax_2': rate_detail.friday_pax_2,
                    'room_type_friday_pax_3': rate_detail.friday_pax_3,
                    'room_type_friday_pax_4': rate_detail.friday_pax_4,
                    'room_type_friday_pax_5': rate_detail.friday_pax_5,
                    'room_type_friday_pax_6': rate_detail.friday_pax_6,

                    'room_type_saturday_pax_1': rate_detail.saturday_pax_1,
                    'room_type_saturday_pax_2': rate_detail.saturday_pax_2,
                    'room_type_saturday_pax_3': rate_detail.saturday_pax_3,
                    'room_type_saturday_pax_4': rate_detail.saturday_pax_4,
                    'room_type_saturday_pax_5': rate_detail.saturday_pax_5,
                    'room_type_saturday_pax_6': rate_detail.saturday_pax_6,

                    'room_type_sunday_pax_1': rate_detail.sunday_pax_1,
                    'room_type_sunday_pax_2': rate_detail.sunday_pax_2,
                    'room_type_sunday_pax_3': rate_detail.sunday_pax_3,
                    'room_type_sunday_pax_4': rate_detail.sunday_pax_4,
                    'room_type_sunday_pax_5': rate_detail.sunday_pax_5,
                    'room_type_sunday_pax_6': rate_detail.sunday_pax_6,
                })
        return res

    # Onchange methods for each checkbox

    @api.onchange('monday_checkbox_rt')
    def _onchange_monday_checkbox_rt(self):
        if self.monday_checkbox_rt:
            self.room_type_monday_pax_1 = self.pax_1
            self.room_type_monday_pax_2 = self.pax_2
            self.room_type_monday_pax_3 = self.pax_3
            self.room_type_monday_pax_4 = self.pax_4
            self.room_type_monday_pax_5 = self.pax_5
            self.room_type_monday_pax_6 = self.pax_6
            self.room_type_monday_child_pax_1 = self.child_pax_1
            self.room_type_monday_infant_pax_1 = self.infant_pax_1

    @api.onchange('tuesday_checkbox_rt')
    def _onchange_tuesday_checkbox_rt(self):
        if self.tuesday_checkbox_rt:
            self.room_type_tuesday_pax_1 = self.pax_1
            self.room_type_tuesday_pax_2 = self.pax_2
            self.room_type_tuesday_pax_3 = self.pax_3
            self.room_type_tuesday_pax_4 = self.pax_4
            self.room_type_tuesday_pax_5 = self.pax_5
            self.room_type_tuesday_pax_6 = self.pax_6
            self.room_type_tuesday_child_pax_1 = self.child_pax_1
            self.room_type_tuesday_infant_pax_1 = self.infant_pax_1

    @api.onchange('wednesday_checkbox_rt')
    def _onchange_wednesday_checkbox_rt(self):
        if self.wednesday_checkbox_rt:
            self.room_type_wednesday_pax_1 = self.pax_1
            self.room_type_wednesday_pax_2 = self.pax_2
            self.room_type_wednesday_pax_3 = self.pax_3
            self.room_type_wednesday_pax_4 = self.pax_4
            self.room_type_wednesday_pax_5 = self.pax_5
            self.room_type_wednesday_pax_6 = self.pax_6
            self.room_type_wednesday_child_pax_1 = self.child_pax_1
            self.room_type_wednesday_infant_pax_1 = self.infant_pax_1

    @api.onchange('thursday_checkbox_rt')
    def _onchange_thursday_checkbox_rt(self):
        if self.thursday_checkbox_rt:
            self.room_type_thursday_pax_1 = self.pax_1
            self.room_type_thursday_pax_2 = self.pax_2
            self.room_type_thursday_pax_3 = self.pax_3
            self.room_type_thursday_pax_4 = self.pax_4
            self.room_type_thursday_pax_5 = self.pax_5
            self.room_type_thursday_pax_6 = self.pax_6
            self.room_type_thursday_child_pax_1 = self.child_pax_1
            self.room_type_thursday_infant_pax_1 = self.infant_pax_1

    @api.onchange('friday_checkbox_rt')
    def _onchange_friday_checkbox_rt(self):
        if self.friday_checkbox_rt:
            self.room_type_friday_pax_1 = self.pax_1
            self.room_type_friday_pax_2 = self.pax_2
            self.room_type_friday_pax_3 = self.pax_3
            self.room_type_friday_pax_4 = self.pax_4
            self.room_type_friday_pax_5 = self.pax_5
            self.room_type_friday_pax_6 = self.pax_6
            self.room_type_friday_child_pax_1 = self.child_pax_1
            self.room_type_friday_infant_pax_1 = self.infant_pax_1

    @api.onchange('saturday_checkbox_rt')
    def _onchange_saturday_checkbox_rt(self):
        if self.saturday_checkbox_rt:
            self.room_type_saturday_pax_1 = self.pax_1
            self.room_type_saturday_pax_2 = self.pax_2
            self.room_type_saturday_pax_3 = self.pax_3
            self.room_type_saturday_pax_4 = self.pax_4
            self.room_type_saturday_pax_5 = self.pax_5
            self.room_type_saturday_pax_6 = self.pax_6
            self.room_type_saturday_child_pax_1 = self.child_pax_1
            self.room_type_saturday_infant_pax_1 = self.infant_pax_1

    @api.onchange('sunday_checkbox_rt')
    def _onchange_sunday_checkbox_rt(self):
        if self.sunday_checkbox_rt:
            self.room_type_sunday_pax_1 = self.pax_1
            self.room_type_sunday_pax_2 = self.pax_2
            self.room_type_sunday_pax_3 = self.pax_3
            self.room_type_sunday_pax_4 = self.pax_4
            self.room_type_sunday_pax_5 = self.pax_5
            self.room_type_sunday_pax_6 = self.pax_6
            self.room_type_sunday_child_pax_1 = self.child_pax_1
            self.room_type_sunday_infant_pax_1 = self.infant_pax_1

    extra_bed = fields.Integer(string="Extra Bed", tracking=True, default=0)
    suite_supl = fields.Integer(
        string="Suite Supplement", tracking=True, default=0)
    child = fields.Integer(string="Child", tracking=True, default=0)
    infant = fields.Integer(string="Infant", tracking=True, default=0)

    @api.onchange('extra_bed', 'suite_supl', 'child', 'infant')
    def _onchange_check_minimum_value_bed_suite(self):
        for field_name in ['extra_bed', 'suite_supl', 'child', 'infant']:
            if getattr(self, field_name, 0) < 0:
                raise ValidationError(
                    _("The value for '%s' cannot be less than 0.") % self._fields[field_name].string
                )


class RoomNumberStore(models.Model):
    _name = 'room.number.store'
    _description = 'Room Number Store'
    # _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Room Name", required=True, tracking=True)
    fsm_location = fields.Many2one(
        'fsm.location', string="Location", tracking=True)
    room_type = fields.Many2one('room.type', string="Room Type", tracking=True)


class FSMLocation(models.Model):
    _inherit = 'fsm.location'

    _rec_name = 'description'


class RoomNumberSpecificRate(models.Model):
    _name = 'room.number.specific.rate'
    _description = 'Room Number Specific Rate'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'room_number'
    # Fields for Room Type Specific Rate Model
    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True)
    rate_code_id = fields.Many2one('rate.code', string="Rate Code", required=True, tracking=True)
    from_date = fields.Date(string="From Date", tracking=True)
    to_date = fields.Date(string="To Date", tracking=True)

    room_fsm_location = fields.Many2one(
        'fsm.location',
        string="Location",
        domain=[('dynamic_selection_id', '=', 4)], tracking=True)

    room_fsm_location_id = fields.Integer(
        string="Location ID",
        compute="_compute_room_fsm_location_id",
        store=True, tracking=True)

    room_number = fields.Many2one(
        'room.number.store',
        string="Room Number",
        domain="[('fsm_location', '=', room_fsm_location)]", tracking=True)

    @api.onchange('room_fsm_location')
    def _onchange_room_fsm_location(self):
        """Reset the room number when the location changes"""
        self.room_number = False
        if self.room_fsm_location:
            # Store the rooms in a custom model if they do not already exist
            for room in self.env['hotel.room'].search([('fsm_location', '=', self.room_fsm_location.id)]):
                existing_room = self.env['room.number.store'].search(
                    [('name', '=', room.name), ('fsm_location', '=', room.fsm_location.id)], limit=1)
                if not existing_room:
                    self.env['room.number.store'].create({
                        'name': room.name,
                        'fsm_location': room.fsm_location.id, })

    room_number_default_price = fields.Float(string="Default", tracking=True)

    # Fields for Weekday Rates
    room_number_monday_pax_1 = fields.Float(
        string="Monday 1 Pax", tracking=True)
    room_number_monday_pax_2 = fields.Float(
        string="Monday 2 Pax", tracking=True)
    room_number_monday_pax_3 = fields.Float(
        string="Monday 3 Pax", tracking=True)
    room_number_monday_pax_4 = fields.Float(
        string="Monday 4 Pax", tracking=True)
    room_number_monday_pax_5 = fields.Float(
        string="Monday 5 Pax", tracking=True)
    room_number_monday_pax_6 = fields.Float(
        string="Monday 6 Pax", tracking=True)

    room_number_monday_child_pax_1 = fields.Float(
        string="Monday 1 Child", tracking=True)

    room_number_monday_infant_pax_1 = fields.Float(
        string="Monday 1 Infant", tracking=True)

    room_number_tuesday_pax_1 = fields.Float(
        string="Tuesday 1 Pax", tracking=True)
    room_number_tuesday_pax_2 = fields.Float(
        string="Tuesday 2 Pax", tracking=True)
    room_number_tuesday_pax_3 = fields.Float(
        string="Tuesday 3 Pax", tracking=True)
    room_number_tuesday_pax_4 = fields.Float(
        string="Tuesday 4 Pax", tracking=True)
    room_number_tuesday_pax_5 = fields.Float(
        string="Tuesday 5 Pax", tracking=True)
    room_number_tuesday_pax_6 = fields.Float(
        string="Tuesday 6 Pax", tracking=True)

    room_number_tuesday_child_pax_1 = fields.Float(
        string="Tuesday 1 Child", tracking=True)

    room_number_tuesday_infant_pax_1 = fields.Float(
        string="Tuesday 1 Infant", tracking=True)

    room_number_wednesday_pax_1 = fields.Float(
        string="Wednesday 1 Pax", tracking=True)
    room_number_wednesday_pax_2 = fields.Float(
        string="Wednesday 2 Pax", tracking=True)
    room_number_wednesday_pax_3 = fields.Float(
        string="Wednesday 3 Pax", tracking=True)
    room_number_wednesday_pax_4 = fields.Float(
        string="Wednesday 4 Pax", tracking=True)
    room_number_wednesday_pax_5 = fields.Float(
        string="Wednesday 5 Pax", tracking=True)
    room_number_wednesday_pax_6 = fields.Float(
        string="Wednesday 6 Pax", tracking=True)
    room_number_wednesday_child_pax_1 = fields.Float(
        string="Wednesday 1 Child", tracking=True)
    room_number_wednesday_infant_pax_1 = fields.Float(
        string="Wednesday 1 Infant", tracking=True)

    room_number_thursday_pax_1 = fields.Float(
        string="Thursday 1 Pax", tracking=True)
    room_number_thursday_pax_2 = fields.Float(
        string="Thursday 2 Pax", tracking=True)
    room_number_thursday_pax_3 = fields.Float(
        string="Thursday 3 Pax", tracking=True)
    room_number_thursday_pax_4 = fields.Float(
        string="Thursday 4 Pax", tracking=True)
    room_number_thursday_pax_5 = fields.Float(
        string="Thursday 5 Pax", tracking=True)
    room_number_thursday_pax_6 = fields.Float(
        string="Thursday 6 Pax", tracking=True)

    room_number_thursday_child_pax_1 = fields.Float(
        string="Thursday 1 Child", tracking=True)
    room_number_thursday_infant_pax_1 = fields.Float(
        string="Thursday 1 Infant", tracking=True)

    room_number_friday_pax_1 = fields.Float(
        string="Friday 1 Pax", tracking=True)
    room_number_friday_pax_2 = fields.Float(
        string="Friday 2 Pax", tracking=True)
    room_number_friday_pax_3 = fields.Float(
        string="Friday 3 Pax", tracking=True)
    room_number_friday_pax_4 = fields.Float(
        string="Friday 4 Pax", tracking=True)
    room_number_friday_pax_5 = fields.Float(
        string="Friday 5 Pax", tracking=True)
    room_number_friday_pax_6 = fields.Float(
        string="Friday 6 Pax", tracking=True)
    room_number_friday_child_pax_1 = fields.Float(
        string="Friday 1 Child", tracking=True)
    room_number_friday_infant_pax_1 = fields.Float(
        string="Friday 1 Infant", tracking=True)

    room_number_saturday_pax_1 = fields.Float(
        string="Saturday 1 Pax", tracking=True)
    room_number_saturday_pax_2 = fields.Float(
        string="Saturday 2 Pax", tracking=True)
    room_number_saturday_pax_3 = fields.Float(
        string="Saturday 3 Pax", tracking=True)
    room_number_saturday_pax_4 = fields.Float(
        string="Saturday 4 Pax", tracking=True)
    room_number_saturday_pax_5 = fields.Float(
        string="Saturday 5 Pax", tracking=True)
    room_number_saturday_pax_6 = fields.Float(
        string="Saturday 6 Pax", tracking=True)
    room_number_saturday_child_pax_1 = fields.Float(
        string="Saturday 1 Child", tracking=True)
    room_number_saturday_infant_pax_1 = fields.Float(
        string="Saturday 1 Infant", tracking=True)

    room_number_sunday_pax_1 = fields.Float(
        string="Sunday 1 Pax", tracking=True)
    room_number_sunday_pax_2 = fields.Float(
        string="Sunday 2 Pax", tracking=True)
    room_number_sunday_pax_3 = fields.Float(
        string="Sunday 3 Pax", tracking=True)
    room_number_sunday_pax_4 = fields.Float(
        string="Sunday 4 Pax", tracking=True)
    room_number_sunday_pax_5 = fields.Float(
        string="Sunday 5 Pax", tracking=True)
    room_number_sunday_pax_6 = fields.Float(
        string="Sunday 6 Pax", tracking=True)
    room_number_sunday_child_pax_1 = fields.Float(
        string="Sunday 1 Child", tracking=True)
    room_number_sunday_infant_pax_1 = fields.Float(
        string="Sunday 1 Infant", tracking=True)

    # Room Prices for different configurations
    pax_1 = fields.Float(string="1 Pax", tracking=True)
    pax_2 = fields.Float(string="2 Pax", tracking=True)
    pax_3 = fields.Float(string="3 Pax", tracking=True)
    pax_4 = fields.Float(string="4 Pax", tracking=True)
    pax_5 = fields.Float(string="5 Pax", tracking=True)
    pax_6 = fields.Float(string="6 Pax", tracking=True)

    child_pax_1 = fields.Float(string="1 Child", tracking=True)
    infant_pax_1 = fields.Float(string="1 Infant", tracking=True)

    default_checkbox_rn = fields.Boolean(string="Apply Default", tracking=True)
    monday_checkbox_rn = fields.Boolean(
        string="Apply Default for Monday", tracking=True)
    tuesday_checkbox_rn = fields.Boolean(
        string="Apply Default for Tuesday", tracking=True)
    wednesday_checkbox_rn = fields.Boolean(
        string="Apply Default for Wednesday", tracking=True)
    thursday_checkbox_rn = fields.Boolean(
        string="Apply Default for Thursday", tracking=True)
    friday_checkbox_rn = fields.Boolean(
        string="Apply Default for Friday", tracking=True)
    saturday_checkbox_rn = fields.Boolean(
        string="Apply Default for Saturday", tracking=True)
    sunday_checkbox_rn = fields.Boolean(
        string="Apply Default for Sunday", tracking=True)

    # Onchange methods for each checkbox

    @api.onchange('monday_checkbox_rn')
    def _onchange_monday_checkbox_rn(self):
        if self.monday_checkbox_rn:
            self.room_number_monday_pax_1 = self.pax_1
            self.room_number_monday_pax_2 = self.pax_2
            self.room_number_monday_pax_3 = self.pax_3
            self.room_number_monday_pax_4 = self.pax_4
            self.room_number_monday_pax_5 = self.pax_5
            self.room_number_monday_pax_6 = self.pax_6
            self.room_number_monday_child_pax_1 = self.child_pax_1
            self.room_number_monday_infant_pax_1 = self.infant_pax_1

    @api.onchange('tuesday_checkbox_rn')
    def _onchange_tuesday_checkbox_rn(self):
        if self.tuesday_checkbox_rn:
            self.room_number_tuesday_pax_1 = self.pax_1
            self.room_number_tuesday_pax_2 = self.pax_2
            self.room_number_tuesday_pax_3 = self.pax_3
            self.room_number_tuesday_pax_4 = self.pax_4
            self.room_number_tuesday_pax_5 = self.pax_5
            self.room_number_tuesday_pax_6 = self.pax_6
            self.room_number_tuesday_child_pax_1 = self.child_pax_1
            self.room_number_tuesday_infant_pax_1 = self.infant_pax_1

    @api.onchange('wednesday_checkbox_rn')
    def _onchange_wednesday_checkbox_rn(self):
        if self.wednesday_checkbox_rn:
            self.room_number_wednesday_pax_1 = self.pax_1
            self.room_number_wednesday_pax_2 = self.pax_2
            self.room_number_wednesday_pax_3 = self.pax_3
            self.room_number_wednesday_pax_4 = self.pax_4
            self.room_number_wednesday_pax_5 = self.pax_5
            self.room_number_wednesday_pax_6 = self.pax_6
            self.room_number_wednesday_child_pax_1 = self.child_pax_1
            self.room_number_wednesday_infant_pax_1 = self.infant_pax_1

    @api.onchange('thursday_checkbox_rn')
    def _onchange_thursday_checkbox_rn(self):
        if self.thursday_checkbox_rn:
            self.room_number_thursday_pax_1 = self.pax_1
            self.room_number_thursday_pax_2 = self.pax_2
            self.room_number_thursday_pax_3 = self.pax_3
            self.room_number_thursday_pax_4 = self.pax_4
            self.room_number_thursday_pax_5 = self.pax_5
            self.room_number_thursday_pax_6 = self.pax_6
            self.room_number_thursday_child_pax_1 = self.child_pax_1
            self.room_number_thursday_infant_pax_1 = self.infant_pax_1

    @api.onchange('friday_checkbox_rn')
    def _onchange_friday_checkbox_rn(self):
        if self.friday_checkbox_rn:
            self.room_number_friday_pax_1 = self.pax_1
            self.room_number_friday_pax_2 = self.pax_2
            self.room_number_friday_pax_3 = self.pax_3
            self.room_number_friday_pax_4 = self.pax_4
            self.room_number_friday_pax_5 = self.pax_5
            self.room_number_friday_pax_6 = self.pax_6
            self.room_number_friday_child_pax_1 = self.child_pax_1
            self.room_number_friday_infant_pax_1 = self.infant_pax_1

    @api.onchange('saturday_checkbox_rn')
    def _onchange_saturday_checkbox_rn(self):
        if self.saturday_checkbox_rn:
            self.room_number_saturday_pax_1 = self.pax_1
            self.room_number_saturday_pax_2 = self.pax_2
            self.room_number_saturday_pax_3 = self.pax_3
            self.room_number_saturday_pax_4 = self.pax_4
            self.room_number_saturday_pax_5 = self.pax_5
            self.room_number_saturday_pax_6 = self.pax_6
            self.room_number_saturday_child_pax_1 = self.child_pax_1
            self.room_number_saturday_infant_pax_1 = self.infant_pax_1

    @api.onchange('sunday_checkbox_rn')
    def _onchange_sunday_checkbox_rn(self):
        if self.sunday_checkbox_rn:
            self.room_number_sunday_pax_1 = self.pax_1
            self.room_number_sunday_pax_2 = self.pax_2
            self.room_number_sunday_pax_3 = self.pax_3
            self.room_number_sunday_pax_4 = self.pax_4
            self.room_number_sunday_pax_5 = self.pax_5
            self.room_number_sunday_pax_6 = self.pax_6
            self.room_number_sunday_child_pax_1 = self.child_pax_1
            self.room_number_sunday_infant_pax_1 = self.infant_pax_1

    @api.model
    def default_get(self, fields_list):
        res = super(RoomNumberSpecificRate, self).default_get(fields_list)
        context = self.env.context

        # Get the rate_code_id from context if provided
        rate_code_id = context.get('default_rate_code_id')
        if rate_code_id:
            # Fetch the related rate.detail record
            rate_detail = self.env['rate.detail'].search(
                [('rate_code_id', '=', rate_code_id)], limit=1)
            if rate_detail:
                # Prefill the pax fields and weekday-specific fields with values from rate.detail
                res.update({
                    'pax_1': rate_detail.pax_1,
                    'pax_2': rate_detail.pax_2,
                    'pax_3': rate_detail.pax_3,
                    'pax_4': rate_detail.pax_4,
                    'pax_5': rate_detail.pax_5,
                    'pax_6': rate_detail.pax_6,

                    'room_number_monday_pax_1': rate_detail.monday_pax_1,
                    'room_number_monday_pax_2': rate_detail.monday_pax_2,
                    'room_number_monday_pax_3': rate_detail.monday_pax_3,
                    'room_number_monday_pax_4': rate_detail.monday_pax_4,
                    'room_number_monday_pax_5': rate_detail.monday_pax_5,
                    'room_number_monday_pax_6': rate_detail.monday_pax_6,

                    'room_number_tuesday_pax_1': rate_detail.tuesday_pax_1,
                    'room_number_tuesday_pax_2': rate_detail.tuesday_pax_2,
                    'room_number_tuesday_pax_3': rate_detail.tuesday_pax_3,
                    'room_number_tuesday_pax_4': rate_detail.tuesday_pax_4,
                    'room_number_tuesday_pax_5': rate_detail.tuesday_pax_5,
                    'room_number_tuesday_pax_6': rate_detail.tuesday_pax_6,

                    'room_number_wednesday_pax_1': rate_detail.wednesday_pax_1,
                    'room_number_wednesday_pax_2': rate_detail.wednesday_pax_2,
                    'room_number_wednesday_pax_3': rate_detail.wednesday_pax_3,
                    'room_number_wednesday_pax_4': rate_detail.wednesday_pax_4,
                    'room_number_wednesday_pax_5': rate_detail.wednesday_pax_5,
                    'room_number_wednesday_pax_6': rate_detail.wednesday_pax_6,

                    'room_number_thursday_pax_1': rate_detail.thursday_pax_1,
                    'room_number_thursday_pax_2': rate_detail.thursday_pax_2,
                    'room_number_thursday_pax_3': rate_detail.thursday_pax_3,
                    'room_number_thursday_pax_4': rate_detail.thursday_pax_4,
                    'room_number_thursday_pax_5': rate_detail.thursday_pax_5,
                    'room_number_thursday_pax_6': rate_detail.thursday_pax_6,

                    'room_number_friday_pax_1': rate_detail.friday_pax_1,
                    'room_number_friday_pax_2': rate_detail.friday_pax_2,
                    'room_number_friday_pax_3': rate_detail.friday_pax_3,
                    'room_number_friday_pax_4': rate_detail.friday_pax_4,
                    'room_number_friday_pax_5': rate_detail.friday_pax_5,
                    'room_number_friday_pax_6': rate_detail.friday_pax_6,

                    'room_number_saturday_pax_1': rate_detail.saturday_pax_1,
                    'room_number_saturday_pax_2': rate_detail.saturday_pax_2,
                    'room_number_saturday_pax_3': rate_detail.saturday_pax_3,
                    'room_number_saturday_pax_4': rate_detail.saturday_pax_4,
                    'room_number_saturday_pax_5': rate_detail.saturday_pax_5,
                    'room_number_saturday_pax_6': rate_detail.saturday_pax_6,

                    'room_number_sunday_pax_1': rate_detail.sunday_pax_1,
                    'room_number_sunday_pax_2': rate_detail.sunday_pax_2,
                    'room_number_sunday_pax_3': rate_detail.sunday_pax_3,
                    'room_number_sunday_pax_4': rate_detail.sunday_pax_4,
                    'room_number_sunday_pax_5': rate_detail.sunday_pax_5,
                    'room_number_sunday_pax_6': rate_detail.sunday_pax_6,
                })
        return res

    extra_bed = fields.Integer(string="Extra Bed", tracking=True)
    suite_supl = fields.Integer(string="Suite Supplement", tracking=True)
    child = fields.Integer(string="Child", tracking=True)
    infant = fields.Integer(string="Infant", tracking=True)

    @api.onchange('extra_bed', 'suite_supl', 'child', 'infant')
    def _onchange_check_minimum_value_bed_suite(self):
        for field_name in ['extra_bed', 'suite_supl', 'child', 'infant']:
            if getattr(self, field_name, 0) < 0:
                raise ValidationError(
                    _("The value for '%s' cannot be less than 0.") % self._fields[field_name].string
                )


class RatePromotion(models.Model):
    _name = 'rate.promotion'
    _description = 'Rate Promotion'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    promotion_id = fields.Char(string=_("Promotion ID"), tracking=True, translate=True)
    description = fields.Char(string=_("Description"), tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"), tracking=True, translate=True)
    buy = fields.Integer(string="Buy", tracking=True)
    get = fields.Integer(string="Get", tracking=True)
    valid_from = fields.Date(string="Validity Period From", tracking=True)
    valid_to = fields.Date(string="Validity Period To", tracking=True)


class MarketCategory(models.Model):
    _name = 'market.category'
    _description = 'Market Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # category = fields.Many2one(
    #     'rate.category', string='Category', tracking=True)
    _rec_name = "market_category"
    market_category = fields.Char(
        string=_('Category'), required=True, tracking=True, translate=True)
    description = fields.Char(string=_("Description"), tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"), tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", tracking=True)


class MarketSegment(models.Model):
    _name = 'market.segment'
    _description = 'Market Segment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'market_segment'
    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True)
    market_segment = fields.Char(
        string=_("Market Segment"), required=True, tracking=True, translate=True)
    description = fields.Char(string=_("Description"), tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"), tracking=True, translate=True)
    category = fields.Many2one(
        'market.category', string='Category', required=True, tracking=True)
    user_sort = fields.Integer(string="User Sort", tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False, tracking=True)


class SourceOfBusiness(models.Model):
    _name = 'source.business'
    _description = 'Source of Business'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'source'
    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True)
    source = fields.Char(string=_("Source"), required=True, tracking=True, translate=True)
    description = fields.Char(string=_("Description"), tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"), tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False, tracking=True)


class CompanyCategory(models.Model):
    _name = 'company.category'
    _description = 'Company Category'

    category = fields.Many2one(
        'rate.category', string='Category', required=True)
    description = fields.Char(string=_("Description"), translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"), translate=True)
    user_sort = fields.Integer(string="User Sort", default=0)


class CountryRegion(models.Model):
    _name = 'country.region'
    _description = 'Country Region'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'Region'

    country_ids = fields.Many2many(
        'res.country', string="Countries", required=True, tracking=True)
    Region = fields.Char(string=_("Region"), tracking=True, required=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"), tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", default=0, tracking=True)


class ReservationStatusCode(models.Model):
    _name = 'reservation.status.code'
    _description = 'Reservation Status Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'reservation'

    reservation = fields.Char(
        string=_("Reservation Type"), required=True, tracking=True, translate=True)
    description = fields.Char(string=_("Description"), tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"), tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", default=0, tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False, tracking=True)

    count_as = fields.Selection([
        ('not_confirmed', 'Not Confirmed'),
        ('confirmed', 'Confirmed'),
        ('wait_list', 'Wait List'),
        ('tentative', 'Tentative'),
        ('release', 'Release'),
        ('cancelled', 'Cancelled'),
        ('other', 'Other')
    ], string="Count As", tracking=True)


class AllotmentCode(models.Model):
    _name = 'allotment.code'
    _description = 'Allotment Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'allotment_code'

    allotment_code = fields.Char(
        string=_("Allotment Code"), required=True, tracking=True, translate=True)
    description = fields.Char(string=_("Description"), tracking=True, translate=True)
    arabic_description = fields.Char(
        string=_("Arabic Description"), tracking=True, translate=True)
    company = fields.Char(string=_("Company"), tracking=True, translate=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    committed_reservations = fields.Boolean(
        string="Committed Reservations", tracking=True)
    from_date = fields.Date(string="From Date", tracking=True)
    to_date = fields.Date(string="To Date", tracking=True)
    release_date = fields.Date(string="Release Date", tracking=True)
    release_period = fields.Integer(string="Release Period", tracking=True)
    room_type_ids = fields.One2many(
        'allotment.room.type', 'allotment_id', string="Room Types")
    user_sort = fields.Integer(string="User Sort", default=0, tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False, tracking=True)

    def action_edit_details(self):
        # Logic for the "Edit Details" button
        return {
            'type': 'ir.actions.act_window',
            'name': 'Edit Allotment Details',
            'view_mode': 'form',
            'res_model': 'allotment.code',
            'target': 'new',
            'res_id': self.id,
        }


class AllotmentRoomType(models.Model):
    _name = 'allotment.room.type'
    _description = 'Allotment Room Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    room_type = fields.Char(string=_("Room Type"), tracking=True, translate=True)
    short_name = fields.Char(string=_("Short Name"), tracking=True, translate=True)
    no_of_rooms = fields.Integer(string="Number of Rooms", tracking=True)
    no_of_pax = fields.Integer(string="Number of Pax", tracking=True)
    allotment_id = fields.Many2one(
        'allotment.code', string="Allotment Code", tracking=True)


class CancellationCode(models.Model):
    _name = 'cancellation.code'
    _description = 'Cancellation Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'code'

    code = fields.Char(string=_("Code"), required=True, tracking=True, translate=True)
    description = fields.Char(string=_("Description"), tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"), tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", default=0, tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False, tracking=True)


class CountryCode(models.Model):
    _name = 'country.code'
    _description = 'Country Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'country_id'

    country_id = fields.Many2one(
        'res.country', string="Country", required=True, tracking=True)
    country_code = fields.Char(
        string=_("Country Code"), compute="_compute_country_code", store=True, tracking=True, translate=True)
    phone_code = fields.Char(
        string=_("Phone Code"), compute="_compute_country_code", store=True, tracking=True, translate=True)

    @api.depends('country_id')
    def _compute_country_code(self):
        for record in self:
            record.country_code = record.country_id.code if record.country_id else ''
            record.phone_code = record.country_id.phone_code if record.country_id else ''


class HotelConfiguration(models.Model):
    _name = 'hotel.configuration'
    _description = "Hotel Configuration"
    _rec_name = 'service_name'
    # _inherit = ['mail.thread', 'mail.activity.mixin']

    service_name = fields.Char(
        string=_("Service Name"), required=True, tracking=True, translate=True)
    unit_price = fields.Float(string="Service Price",
                              readonly=True, tracking=True)
    frequency = fields.Selection(
        [
            ('one time', 'One Time'),
            ('daily', 'Daily'),
        ],
        string='Frequency',
        readonly=True, tracking=True)

    @api.model
    def _sync_with_service(self, service):
        """Sync hotel configuration with hotel service"""
        config = self.search([('service_name', '=', service.name)], limit=1)
        if config:
            # Update existing configuration
            config.write({
                'unit_price': service.unit_price,
                'frequency': service.frequency,
            })
        else:
            # Create a new configuration
            self.create({
                'service_name': service.name,
                'unit_price': service.unit_price,
                'frequency': service.frequency,
            })


class Yearly_geographical_chart(models.Model):
    _name = 'yearly.geographical.chart'
    _description = 'Yearly Geographical Chart'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    report_date = fields.Date(string='Report Date',
                              required=True, tracking=True)
    client_id = fields.Many2one(
        'res.partner', string='Client', required=True, tracking=True)
    room_type = fields.Char(string=_('Room Type'), required=True, tracking=True, translate=True)
    total_rooms = fields.Integer(
        string='Total Rooms', readonly=True, tracking=True)
    available = fields.Integer(
        string='Available', readonly=True, tracking=True)
    inhouse = fields.Integer(string='In-House', readonly=True, tracking=True)
    expected_arrivals = fields.Integer(
        string='Expected Arrivals', readonly=True, tracking=True)
    expected_departures = fields.Integer(
        string='Expected Departures', readonly=True, tracking=True)
    expected_inhouse = fields.Integer(
        string='Expected In House', readonly=True, tracking=True)
    reserved = fields.Integer(string='Reserved', readonly=True, tracking=True)
    expected_occupied_rate = fields.Integer(
        string='Expected Occupied Rate (%,tracking=True)', readonly=True, tracking=True)
    out_of_order = fields.Integer(
        string='Out of Order', readonly=True, tracking=True)
    overbook = fields.Integer(string='Overbook', readonly=True, tracking=True)
    free_to_sell = fields.Integer(
        string='Free to sell', readonly=True, tracking=True)
    sort_order = fields.Integer(
        string='Sort Order', readonly=True, tracking=True)

    def action_generate_results(self):
        # Generate and update room results by client
        self.run_process_by_room_type()

    def run_process_by_room_type(self):
        # Execute the SQL query and process the results
        pass
