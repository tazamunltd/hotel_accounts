from odoo.exceptions import UserError
from odoo import api, fields, models, _
from odoo import exceptions
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import pytz
import bcrypt
import convertdate.islamic as hijri
import datetime
# from ummalqura import umalqura
from hijri_converter import Gregorian
import logging
from datetime import datetime, timedelta, date, time
from odoo.models import NewId

_logger = logging.getLogger(__name__)


class RoomBooking(models.Model):
    """Model that handles the hotel room booking and all operations related
     to booking"""
    _name = "room.booking"
    _order = 'create_date desc'
    _description = "Waiting List Room Availability"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # package_ids = fields.One2many('hotel.package_handling', 'booking_id', string="Packages")

    def generateRcPDF(self):
        # Redirect to the controller to generate the PDFs
        booking_ids = ','.join(map(str, self.ids))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/generate_rc/bookings_pdf?booking_ids={booking_ids}',
            'target': 'self',
        }

    def generateRcGuestPDF(self):
        # Redirect to the controller to generate the PDFs
        booking_ids = ','.join(map(str, self.ids))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/generate_rc+guest/bookings_pdf?booking_ids={booking_ids}',
            'target': 'self',
        }

    hide_unconfirm_button = fields.Boolean(
        compute="_compute_hide_unconfirm_button",
        string="Hide Unconfirm Button",
        store=False
    )

    @api.depends('state')
    def _compute_hide_unconfirm_button(self):
        crs_user_group = self.env.ref('hotel_management_odoo.crs_user_group')
        for record in self:
            record.hide_unconfirm_button = (
                record.state == 'confirmed' and crs_user_group in self.env.user.groups_id
            )

    hide_confirm_button = fields.Boolean(
        compute="_compute_hide_confirm_button",
        string="Hide confirm Button",
        store=False
    )

    @api.depends('state')
    def _compute_hide_confirm_button(self):
        crs_user_group = self.env.ref('hotel_management_odoo.crs_user_group')
        for record in self:
            record.hide_confirm_button = (
                record.state == 'block' and crs_user_group in self.env.user.groups_id
            )

    hide_admin_buttons = fields.Boolean(
        compute="_compute_hide_admin_buttons",
        string="Hide Admin Buttons",
        store=False
    )

    @api.depends('state')
    def _compute_hide_admin_buttons(self):
        crs_admin_group = self.env.ref('hotel_management_odoo.crs_admin_group')
        for record in self:
            record.hide_admin_buttons = (
                record.state == 'block' and crs_admin_group in self.env.user.groups_id
            )

    hide_buttons_front_desk = fields.Boolean(
        compute="_compute_hide_buttons_front_desk",
        string="Hide Buttons for Front Desk",
        store=False
    )

    @api.depends('state')
    def _compute_hide_buttons_front_desk(self):
        front_desk_group = self.env.ref(
            'hotel_management_odoo.front_desk_user_group')
        for record in self:
            record.hide_buttons_front_desk = (
                record.state == 'block' and front_desk_group in self.env.user.groups_id
            )

    is_checkout_in_past = fields.Boolean(
        string="Is Checkout in Past",
        compute="_compute_is_checkout_in_past",
        store=True
    )

    @api.depends('checkout_date')
    def _compute_is_checkout_in_past(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.checkout_date:
                checkout_date = (
                    record.checkout_date.date()
                    if isinstance(record.checkout_date, datetime)
                    else record.checkout_date
                )
                record.is_checkout_in_past = checkout_date < today
            else:
                record.is_checkout_in_past = False

    notification_sent = fields.Boolean(
        string="Notification Sent", default=False)

    @api.model
    def check_waiting_list_and_notify(self):
        # Get today's date
        today = datetime.now().date()

        # Step 1: Search for bookings in the 'cancel' state for today
        canceled_bookings = self.env['room.booking'].search([
            ('state', '=', 'cancel'),
            ('checkin_date', '>=', today),
            ('checkout_date', '>=', today),
            ('notification_sent', '=', False)
        ])

        if not canceled_bookings:
            _logger.info("No canceled bookings found for today.")
            return

        _logger.info(
            f"Found {len(canceled_bookings)} canceled bookings for today.")

        for canceled_booking in canceled_bookings:
            _logger.info(
                f"Check-In: {canceled_booking.checkin_date}, Check-Out: {canceled_booking.checkout_date}")

            # Step 2: Search for bookings in the 'waiting' state with matching dates
            waiting_bookings = self.env['room.booking'].search([
                ('state', '=', 'waiting'),
                ('checkin_date', '>=', datetime.combine(
                    today, datetime.min.time())),
                ('checkout_date', '<=', canceled_booking.checkout_date.date()),
                ('company_id', '=', self.env.company.id)
            ], order='create_date asc')

            _logger.info(
                f"Found {len(waiting_bookings)} waiting bookings for canceled booking '{canceled_booking.name}'.")

            cumulative_room_count = 0
            selected_bookings = []  # To store the bookings that satisfy the criteria

            for booking in waiting_bookings:
                # Check if the booking already has a notification activity
                existing_activity = self.env['mail.activity'].search([
                    ('res_id', '=', booking.id),
                    ('res_model', '=', 'room.booking'),
                    ('summary', '=', "Room Availability Notification"),
                    # Ensure it is linked to the current canceled booking
                    ('note', 'ilike', canceled_booking.name)
                ], limit=1)

                if existing_activity:
                    _logger.info(
                        f"Booking '{booking.name}' already has a notification for canceled booking '{canceled_booking.name}'. Skipping.")
                    continue

                cumulative_room_count += booking.room_count
                selected_bookings.append(booking)

                # Stop when the cumulative room count matches or exceeds the canceled booking's room count
                if cumulative_room_count >= canceled_booking.room_count:
                    break

            # Notify about the selected bookings
            if selected_bookings:
                _logger.info(
                    f"Selected bookings for notification: {[b.name for b in selected_bookings]}")

                for booking in selected_bookings:
                    message = f"Booking '{booking.name}' is now available for the canceled booking '{canceled_booking.name}'."
                    _logger.info(
                        f"Sending notification for booking: {booking.name}")

                    # Create a scheduled activity if not already created
                    self.env['mail.activity'].create({
                        'res_id': booking.id,
                        'res_model_id': self.env['ir.model']._get('room.booking').id,
                        'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                        'summary': "Room Availability Notification",
                        'note': message,
                        'user_id': booking.create_uid.id,
                        'date_deadline': fields.Date.today(),
                    })

                    # Send real-time notification (optional)
                    self.env['bus.bus']._sendone(
                        'res.partner',
                        booking.create_uid.partner_id.id,
                        {'type': 'simple_notification', 'message': message}
                    )
                canceled_booking.notification_sent = True
            else:
                _logger.info(
                    f"No suitable bookings found for canceled booking '{canceled_booking.name}'.")

    # Working
    # @api.model
    # def check_waiting_list_and_notify(self):
    #     # Get today's date
    #     today = datetime.now().date()
    #     print(f"Today's date: {today}")

    #     # Search for bookings in the 'waiting' state where the date part of checkin_date matches today
    #     waiting_bookings = self.env['room.booking'].search([
    #         ('state', '=', 'waiting'),
    #         ('checkin_date', '>=', today),
    #         ('checkin_date', '<', today + timedelta(days=1))  # Ensures only today's bookings
    #     ])

    #     print(f"Running cron job: Found {len(waiting_bookings)} bookings to update to notification")

    #     for booking in waiting_bookings:
    #         print(f"Processing booking: {booking.name}")
    #         print(f"Check-In Date: {booking.checkin_date}")
    #         print(f"Check-Out Date: {booking.checkout_date}")

    #         # Check room availability
    #         room_availability = booking.check_room_availability_all_hotels_split_across_type(
    #             checkin_date=booking.checkin_date,
    #             checkout_date=booking.checkout_date,
    #             room_count=booking.room_count,
    #             adult_count=booking.adult_count,
    #             hotel_room_type_id=booking.hotel_room_type.id
    #         )

    #         print(f"Room Availability Found: {room_availability}")

    #         # If rooms are available, send notification
    #         if room_availability:
    #             message = f"Booking '{booking.name}' is now available!"
    #             print(f"Sending notification: {message}")

    #             # Check if an activity already exists for this booking
    #             existing_activity = self.env['mail.activity'].search([
    #                 ('res_id', '=', booking.id),  # Booking ID
    #                 ('res_model', '=', 'room.booking'),  # Model name
    #                 ('user_id', '=', booking.create_uid.id),  # Target user
    #                 ('summary', '=', "Room Availability Notification")  # Specific summary
    #             ], limit=1)

    #             if not existing_activity:
    #                 # Create a scheduled activity if not already created
    #                 self.env['mail.activity'].create({
    #                     'res_id': booking.id,
    #                     'res_model_id': self.env['ir.model']._get('room.booking').id,
    #                     'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
    #                     'summary': "Room Availability Notification",
    #                     'note': message,
    #                     'user_id': booking.create_uid.id,
    #                     'date_deadline': fields.Date.today(),
    #                 })

    #                 # Send real-time notification (optional)
    #                 self.env['bus.bus']._sendone(
    #                     'res.partner',
    #                     booking.create_uid.partner_id.id,
    #                     {'type': 'simple_notification', 'message': message}
    #                 )
    #             else:
    #                 print(f"Notification activity already exists for booking '{booking.name}'.")

    #         # if room_availability:
    #         #     message = f"Booking '{booking.name}' is now available!"
    #         #     print(f"Sending notification: {message}")

    #         #     self.env['bus.bus']._sendone(
    #         #         'res.partner',  # Channel to notify
    #         #         booking.create_uid.partner_id.id,  # Recipient user
    #         #         {'type': 'simple_notification', 'message': message}  # Message content
    #         #     )
    #         # else:
    #         #     print(f"No rooms available for booking '{booking.name}'")

    @api.model
    def action_send_pre_reminder_emails(self):
        today = datetime.now().date()

        # Step 1: Search all companies with a notification configuration
        companies = self.env['res.company'].search(
            [('reminder_days_before', '>', 0), ('template_id', '!=', False)])

        for company in companies:
            notification_days = company.reminder_days_before
            start_datetime = datetime.combine(
                (datetime.today() + timedelta(days=notification_days)).date(), time.min)
            end_datetime = datetime.combine(
                (datetime.today() + timedelta(days=notification_days)).date(), time.max)
            # Step 2: Search for bookings in the current company that meet the criteria
            bookings = self.search([
                ('checkin_date', '<=', end_datetime),
                ('company_id', '=', company.id),
                ('checkin_date', '>=', start_datetime),
            ])
            for booking in bookings:
                # Step 3: Send the email using the company's mail template
                mail_template = company.template_id
                if mail_template:
                    mail_template.send_mail(booking.id, force_send=True)

    @api.model
    def action_send_pre_arrival_emails(self):
        today = datetime.now().date()

        # Step 1: Search all companies with a notification configuration
        companies = self.env['res.company'].search(
            [('pre_arrival_days_before', '>', 0), ('pre_template_id', '!=', False)])

        for company in companies:
            notification_days = company.pre_arrival_days_before
            start_datetime = datetime.combine(
                (datetime.today() + timedelta(days=notification_days)).date(), time.min)
            end_datetime = datetime.combine(
                (datetime.today() + timedelta(days=notification_days)).date(), time.max)
            # Step 2: Search for bookings in the current company that meet the criteria
            bookings = self.search([
                ('checkin_date', '<=', end_datetime),
                ('company_id', '=', company.id),
                ('checkin_date', '>=', start_datetime),
            ])
            for booking in bookings:
                # Step 3: Send the email using the company's mail template
                mail_template = company.pre_template_id
                if mail_template:
                    mail_template.send_mail(booking.id, force_send=True)

    # @api.model
    # def _calculate_average_rate(self, rate_field, records):
    #     """
    #     Helper function to calculate the average of rates in the given records.
    #     """
    #     rates = [getattr(record, rate_field, 0) for record in records if getattr(record, rate_field, 0)]
    #     return sum(rates) / len(rates) if rates else 0

    # working
    # def _get_report_values(self, docids, data=None):
    #     """
    #     This method processes each record separately for the report.
    #     """
    #     docs = self.env['room.booking'].browse(docids)
    #     report_data = []
    #     for doc in docs:
    #         forecast_records = self.env['room.rate.forecast'].search([('room_booking_id', '=', doc.id)])
    #         rate_avg = self._calculate_average_rate('rate', forecast_records)
    #         meals_avg = self._calculate_average_rate('meals', forecast_records)

    #     booking_details = [{
    #         'room_id': doc.room_id.id if doc.room_id else None,
    #         'room_number': doc.room_id.name if doc.room_id else 'N/A',
    #         'hotel_room_name': doc.room_id.name if doc.room_id else 'N/A',
    #         'adults': [{
    #             'Nationality': adult.nationality.name,
    #             'Passport NO.': adult.passport_number,
    #             'Tel no.': adult.phone_number,
    #             'ID Number': adult.id_number,
    #         } for adult in doc.adult_ids],
    #         'children': [{
    #             'Nationality': child.nationality.name,
    #             'Passport NO.': child.passport_number,
    #             'Tel no.': child.phone_number,
    #             'ID Number': child.id_number,
    #         } for child in doc.child_ids],
    #     }]

    #     report_data.append({
    #         'doc_ids': [doc.id],
    #         'doc_model': 'room.booking',
    #         'docs': doc,
    #         'booking_details': booking_details,
    #         'rate_avg': rate_avg,
    #         'meals_avg': meals_avg,
    #     })

    #     return report_data

    # def _get_report_values(self, docids, data=None):
    #     """
    #     This method generates a report for each selected record in room.booking.
    #     """
    #     # Fetch the records based on the selected docids
    #     print(f"Doc IDs: {docids}")
    #     docs = self.env['room.booking'].browse(docids)
    #     report_data = []

    #     for doc in docs:
    #         # Fetch room rate forecast data related to this booking
    #         forecast_records = self.env['room.rate.forecast'].search([('room_booking_id', '=', doc.id)])
    #         rate_avg = self._calculate_average_rate('rate', forecast_records)
    #         meals_avg = self._calculate_average_rate('meals', forecast_records)

    #         # Prepare booking details for the current record
    #         booking_details = {
    #             'room_id': doc.room_id.id if doc.room_id else None,
    #             'room_number': doc.room_id.name if doc.room_id else 'N/A',
    #             'hotel_room_name': doc.room_id.name if doc.room_id else 'N/A',
    #             'adults': [{
    #                 'Nationality': adult.nationality.name,
    #                 'Passport NO.': adult.passport_number,
    #                 'Tel no.': adult.phone_number,
    #                 'ID Number': adult.id_number,
    #             } for adult in doc.adult_ids],
    #             'children': [{
    #                 'Nationality': child.nationality.name,
    #                 'Passport NO.': child.passport_number,
    #                 'Tel no.': child.phone_number,
    #                 'ID Number': child.id_number,
    #             } for child in doc.child_ids],
    #             'rate_average': rate_avg,
    #             'meals_average': meals_avg,
    #         }

    #         # Append details to report_data
    #         report_data.append({
    #             'doc_ids': [doc.id],
    #             'doc_model': 'room.booking',
    #             'booking_details': booking_details
    #         })

    #     return {
    #         'docs': docs,
    #         'report_data': report_data,
    #     }

    def generatePDF(self):
        # Redirect to the controller to generate the PDFs
        booking_ids = ','.join(map(str, self.ids))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/generate/bookings_pdf?booking_ids={booking_ids}',
            'target': 'self',
        }

    previous_state = fields.Char(string="Previous State")

    is_checkin_in_past = fields.Boolean(
        string="Is Check-in in Past",
        compute="_compute_is_checkin_in_past",
        store=True
    )
    active = fields.Boolean(string="Active", default=True)

    def action_archive_as_delete(self):
        """Validate states and archive records."""
        # Define allowed states
        allowed_states = ['cancel', 'no_show', 'not_confirmed']

        # Check if all records are in allowed states
        invalid_records = self.filtered(
            lambda r: r.state not in allowed_states)

        if invalid_records:
            raise exceptions.ValidationError(
                "You can only delete bookings in the following states: Cancel, No Show, or Not Confirmed.\n"
                "The following bookings are in invalid states:\n"
                + "\n".join(f"Booking ID: {rec.id}, State: {rec.state}" for rec in invalid_records)
            )

        # Archive all records in valid states
        for record in self:
            record.active = False

    @api.depends('checkin_date')
    def _compute_is_checkin_in_past(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.checkin_date:
                checkin_date = record.checkin_date.date() if isinstance(record.checkin_date,
                                                                        datetime) else record.checkin_date
                record.is_checkin_in_past = checkin_date < today
            else:
                record.is_checkin_in_past = False

    # def action_back(self):
    #     # Ensure there is a previous state to revert to
    #     if not self.previous_state:
    #         raise UserError("No previous state found for this booking.")

    #     current_state = self.state

    #     # Revert the booking's state to the previous state
    #     self.write({'state': self.previous_state})

    #     # Update previous_state to the state before the change
    #     self.previous_state = current_state

    def move_to_no_show(self):
        # Get the current date and subtract one day to get yesterday's date
        yesterday = datetime.combine(
            (datetime.now() - timedelta(days=1)).date(), time.max)

        # Find bookings with checkin_date equal to yesterday and in the specified states
        bookings = self.search([
            ('state', 'in', ['not_confirmed', 'confirmed', 'block']),
            ('checkin_date', '<=', yesterday),
        ])

        # Update the state to 'no_show' using the no_show method
        for booking in bookings:
            try:
                # Call the no_show method
                booking.no_show()
                _logger.info(
                    f"Successfully processed booking ID {booking.id} as 'no_show'.")
            except Exception as e:
                # Log or print the exception to handle any issues
                _logger.info(f"Failed to process booking ID {booking.id}: {e}")

        # working
        # def move_to_no_show(self):
        #     # Get the current date and subtract one day to get yesterday's date
        #     # yesterday = (datetime.now() - timedelta(days=1)).date()
        #     yesterday = datetime.combine((datetime.now() - timedelta(days=1)).date(), time.max)

        #     # Find bookings with checkin_date equal to yesterday and in the specified states
        #     bookings = self.search([
        #         ('state', 'in', ['not_confirmed', 'confirmed', 'block']),
        #         ('checkin_date', '<=', yesterday),
        #     ])

        # print(f"Running cron job: Found {len(bookings)} bookings to update to 'no_show'")

        # Update the state to 'no_show'
        for booking in bookings:
            booking.write({'state': 'no_show'})
            _logger.info(f"Updated booking ID {booking.id} to 'no_show'")

    # working
    # def move_to_no_show(self):
    #     # Get current datetime
    #     now = datetime.now()

    #     # Find bookings with checkin_date before now and in the specified states
    #     bookings = self.search([
    #         ('state', 'in', ['not_confirmed', 'confirmed', 'block']),
    #         ('checkin_date', '<', now),
    #     ])
    #     print(f"Running cron job: Found {len(bookings)} bookings to update to 'no_show'")

    #     # Update the state to 'no_show'
    #     for booking in bookings:
    #         booking.write({'state': 'no_show'})
    #         print(f"Updated booking ID {booking.id} to 'no_show'")

    start_line = fields.Integer(string="Start Record", default=1)
    end_line = fields.Integer(string="End Record", default=1)

    notes = fields.Text(string="Notes", tracking=True)
    room_booking_id = fields.Many2one(
        'report.model',
        string="Report Model",
        help="Reference to the consolidated report model",
    )
    name = fields.Char(string="Room Number", tracking=True)
    adult_ids = fields.One2many(
        'room.booking.adult', 'booking_id', string="Adults")  #
    child_ids = fields.One2many(
        'room.booking.child', 'booking_id', string="Children")  #
    infant_ids = fields.One2many(
        'room.booking.infant', 'booking_id', string="Infant")  #
    web_cancel = fields.Boolean(string="Web cancel", default=False, help="Reservation cancelled by website",
                                tracking=True)
    web_cancel_time = fields.Datetime(string="Web Cancel Time", compute="_compute_web_cancel_time", store=True,
                                      readonly=True, tracking=True)
    ref_id_bk = fields.Char(string="Ref. ID(booking.com)", tracking=True)

    @api.depends('web_cancel')
    def _compute_web_cancel_time(self):
        for record in self:
            if record.web_cancel and not record.web_cancel_time:
                record.web_cancel_time = datetime.now()

    hotel_id = fields.Many2one('res.company', string="Hotel", tracking=True)
    # company_address_id = fields.Many2one(
    #     'res.company',
    #     string='Company Address',
    #     help="Select the address from the company model"
    # )
    address_id = fields.Many2one(
        'res.partner', string="Address", tracking=True)
    phone = fields.Char(related='address_id.phone',
                        string="Phone Number", tracking=True)
    room_booking_line_id = fields.Many2one(
        'room.booking.line', string="Room Line", tracking=True)
    room_id = fields.Many2one(
        'room.booking.line', string="Room Line", tracking=True)
    room_type = fields.Many2one('room.type', string="Room Type", tracking=True)

    no_of_nights = fields.Integer(
        string="Number of Nights",
        compute="_compute_no_of_nights",
        store=True,
        help="Computed field to calculate the number of nights based on check-in and check-out dates.",
        tracking=True
    )

    phone_number = fields.Char(
        related='adult_id.phone_number', string='Phone Number', store=True, tracking=True)
    # passport_number = fields.Char(related='adult_id.passport_number', string='Passport No.', store=True)
    # id_number = fields.Char(related='adult_id.id_number', string='ID Number', store=True)
    adult_id = fields.Many2one(
        "reservation.adult",
        string="Full Name",
    )
    # hijri_date = fields.Char(
    #     string="Hijri Date",
    #     default=lambda self: self._get_default_hijri_date
    # )
    # gregorian_date = fields.Date(
    #     string="Gregorian Date",
    #     default=fields.Date.context_today
    # )
    hijri_checkin_date = fields.Char(
        string="Hijri Check-In Date",
        compute='_compute_hijri_dates',
        store=False
    )
    hijri_checkout_date = fields.Char(
        string="Hijri Check-Out Date",
        compute='_compute_hijri_dates',
        store=False,
    )
    number_of_pax = fields.Integer(string="Number of Pax", tracking=True)
    number_of_children = fields.Integer(
        string="Number of Children", tracking=True)
    number_of_infants = fields.Integer(
        string="Number of Infants", tracking=True)

    # Tax and Municipality
    vat = fields.Float(string="VAT (%)", tracking=True)
    municipality = fields.Float(string="Municipality (%)", tracking=True)
    vat_id = fields.Char(string="VAT ID", tracking=True)

    # Rates
    daily_room_rate = fields.Float(string="Daily Room Rate", tracking=True)
    daily_meals_rate = fields.Float(string="Daily Meals Rate", tracking=True)

    # Payments
    payments = fields.Float(string="Payments", tracking=True)
    remaining = fields.Float(string="Remaining", tracking=True)
    hijri_date = fields.Char(
        string="Hijri Date", compute="_compute_dates", store=True, tracking=True)
    gregorian_date = fields.Char(
        string="Gregorian Date", compute="_compute_dates", store=True, tracking=True)

    def _compute_dates(self):
        for record in self:
            today = date.today()
            # Gregorian date as string
            record.gregorian_date = today.strftime('%Y-%m-%d')

            # Convert to Hijri
            hijri_date = Gregorian(
                today.year, today.month, today.day).to_hijri()
            record.hijri_date = f"{hijri_date.year}-{hijri_date.month:02d}-{hijri_date.day:02d}"

    # def _get_default_hijri_date(self):
    #     # Get today's date in Gregorian
    #     today = date.today()
    #
    #     # Convert to Hijri using hijri-converter
    #     hijri_date = Gregorian(today.year, today.month, today.day).to_hijri()
    #
    #     hijri_date_str = f"{hijri_date.year}-{hijri_date.month:02d}-{hijri_date.day:02d}"  # Format as 'YYYY-MM-DD'
    #     print(f"Calculated Hijri Date: {hijri_date_str}")
    #     return hijri_date_str
    @api.depends('checkin_date', 'checkout_date')
    def _compute_hijri_dates(self):
        for record in self:
            # Convert Check-In Date to Hijri
            if record.checkin_date:
                record.hijri_checkin_date = self._convert_to_hijri(
                    record.checkin_date)
            else:
                record.hijri_checkin_date = False

            # Convert Check-Out Date to Hijri
            if record.checkout_date:
                record.hijri_checkout_date = self._convert_to_hijri(
                    record.checkout_date)
            else:
                record.hijri_checkout_date = False

    def _convert_to_hijri(self, gregorian_date):
        """Convert a Gregorian date to Hijri date."""
        try:
            if isinstance(gregorian_date, str):
                gregorian_date = datetime.datetime.strptime(
                    gregorian_date, '%Y-%m-%d').date()
            hijri_date = hijri.from_gregorian(
                gregorian_date.year, gregorian_date.month, gregorian_date.day)
            return f"{hijri_date[0]}-{hijri_date[1]:02d}-{hijri_date[2]:02d}"
        except Exception as e:
            return False

    def get_report_data(self):
        # Fetch the active_id from the context
        active_id = self.env.context.get('active_id')
        if active_id:
            # Fetch the specific record using active_id
            record = self.browse(active_id)
            # Perform any operations with the record
            return record
        else:
            # Handle case where active_id is not found
            raise ValueError("No active_id found in the context")

    @api.depends('checkin_date', 'checkout_date')
    def _compute_no_of_nights(self):
        for record in self:
            if record.checkin_date and record.checkout_date:
                delta = record.checkout_date.date() - record.checkin_date.date()
                record.no_of_nights = delta.days
                if record.no_of_nights > 999:
                    raise ValidationError(
                        "Number of nights cannot exceed 999. Please adjust the check-in or check-out dates.")
            else:
                record.no_of_nights = 0

    def action_delete_lines(self):
        for record in self:
            # Validate that the record has valid start_line and end_line
            if not record.start_line or not record.end_line:
                raise ValueError("Start Line and End Line must be provided.")

            # Fetch all lines for the current booking, ordered by ID
            booking_lines = self.env['room.booking.line'].search(
                [('booking_id', '=', record.id)],
                order="id"
            )
            total_lines = len(booking_lines)

            # Validate the range of start_line and end_line
            if not (1 <= record.start_line <= total_lines and 1 <= record.end_line <= total_lines):
                raise ValueError(
                    f"Invalid range: start_line={record.start_line}, end_line={record.end_line}, total_lines={total_lines}")

            if record.start_line > record.end_line:
                raise ValueError("Start Line cannot be greater than End Line.")

            # Select lines to delete based on start_line and end_line
            lines_to_delete = booking_lines[record.start_line -
                                            1:record.end_line]
            lines_to_delete.unlink()

    # posting_item_ids = fields.Many2many(
    #     'posting.item',
    #     string="Posting Items",
    #     help="Select posting items for this booking."
    # )

    posting_item_ids = fields.One2many(
        'room.booking.posting.item',
        'booking_id',
        string="Posting Items",
        help="Select posting items for this booking uniquely."
    )

    booking_posting_item_ids = fields.One2many(
        'booking.posting.item', 'booking_id', string="Booking Posting Items"
    )

    show_in_tree = fields.Boolean(
        compute='_compute_show_in_tree',
        store=True,  # Computed dynamically, not stored in the database
    )

    # @api.depends('parent_booking_id', 'room_count', 'room_line_ids')
    # def _compute_show_in_tree(self):
    #     for record in self:
    #         record.show_in_tree = not (
    #                 not record.parent_booking_id
    #                 and record.room_count > 1
    #                 and all(line.room_id for line in record.room_line_ids)
    #         )

    @api.depends('parent_booking_id', 'room_count', 'room_line_ids')
    def _compute_show_in_tree(self):
        for record in self:
            # record.show_in_tree = not (
            #         not record.parent_booking_id
            #         and record.room_count > 1
            #         and all(line.room_id for line in record.room_line_ids)
            # )
            if not record.room_line_ids:
                record.show_in_tree = True
            else:
                # Otherwise, apply the original logic
                record.show_in_tree = not (
                    not record.parent_booking_id
                    and record.room_count > 1
                    and all(line.room_id for line in record.room_line_ids)
                )

    no_show_ = fields.Boolean(string="No Show", help="Mark booking as No Show")

    is_room_line_readonly = fields.Boolean(
        string="Room Line Readonly", default=False)

    availability_results = fields.One2many(
        'room.availability.result', 'room_booking_id', string="Availability Results", readonly=True
    )

    @api.model
    def get_today_checkin_domain(self):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        print("this is calling")
        return [
            ('checkin_date', '>=', today),
            ('checkin_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_in')
        ]

    @api.model
    def get_today_checkout_domain(self):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            ('checkout_date', '>=', today),
            ('checkout_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_out')
        ]

    @api.model
    def retrieve_dashboard(self):
        company = self.env.company  # This fetches the current company
        system_date = company.system_date or fields.Date.context_today(self)  
        # self.delete_zero_room_count_records()
        self.env.cr.commit()
        # Today's check-in and check-out counts
        # today = fields.Date.context_today(self)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Get tomorrow's date with time 00:00:00 (end of today)
        # today_end = today + timedelta(days=1)
        # today = datetime.now()
        actual_checkin_count = self.search_count([
            # ('checkin_date', '>=', today),
            ('checkin_date', '=', system_date),
            # ('checkin_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_in'),
            # ('parent_booking_name', '!=', False)

        ])

        actual_checkout_count = self.search_count([
            # ('checkout_date', '>=', today),
            ('checkout_date', '=', system_date),
            # ('checkout_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_out'),
            # ('parent_booking_name', '!=', False)

        ])

        today_checkin_count = self.search_count([
            # ('checkin_date', '>=', today),
            ('checkin_date', '=', system_date),
            # ('checkin_date', '<', today + timedelta(days=1)),
            ('state', '=', 'block'),
            # ('parent_booking_name', '!=', False)

        ])
        today_checkout_count = self.search_count([
            # ('checkout_date', '>=', today),
            ('checkout_date', '=', system_date),
            # ('checkout_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_in'),
            # ('parent_booking_name', '!=', False)

        ])

        # Counts for each specific booking state
        not_confirm_count = self.env['room.booking'].search_count(
            [('state', '=', 'not_confirmed')])
        confirmed_count = self.env['room.booking'].search_count(
            [('state', '=', 'confirmed')])
        waiting_count = self.env['room.booking'].search_count(
            [('state', '=', 'waiting')])
        blocked_count = self.env['room.booking'].search_count(
            [('state', '=', 'block')])
        cancelled_count = self.env['room.booking'].search_count(
            [('state', '=', 'cancel')])
        checkin_count = self.search_count([('state', '=', 'check_in')])
        checkout_count = self.search_count([('state', '=', 'check_out')])

        total_rooms_count = self.env['hotel.room'].search_count([])

        # Calculate vacant count
        vacant_count = total_rooms_count - actual_checkin_count
        # Return all counts
        result = {
            'today_checkin': today_checkin_count,
            'today_checkout': today_checkout_count,
            'not_confirm': not_confirm_count,
            'confirmed': confirmed_count,
            'waiting': waiting_count,
            'blocked': blocked_count,
            'cancelled': cancelled_count,
            'checkin': checkin_count,
            'checkout': checkout_count,
            'actual_checkin_count': actual_checkin_count,
            'actual_checkout_count': actual_checkout_count,
            'vacant': vacant_count
        }
        return result

    # @api.model
    # def retrieve_dashboard(self):
    #     result = {
    #         'all_to_send': 0,
    #         'today_checkin': self.search_count(self.get_today_checkin_domain()),
    #     }
    #     return result

    adult_ids = fields.One2many(
        'reservation.adult', 'reservation_id', string='Adults')  #
    child_ids = fields.One2many(
        'reservation.child', 'reservation_id', string='Children')  #

    infant_ids = fields.One2many(
        'reservation.infant', 'reservation_id', string='Infant')  #

    meal_pattern = fields.Many2one(
        'meal.pattern', string="Meal Pattern", tracking=True)
    group_booking_id = fields.Many2one(
        'group.booking',  # The source model (group bookings)
        string='Group Booking',
        ondelete='cascade',
        tracking=True
    )

    name = fields.Char(string="Booking ID", readonly=True, index=True,
                       default="New", help="Name of Folio", tracking=True)

    rate_forecast_ids = fields.One2many(
        'room.rate.forecast',
        'room_booking_id',
        compute='_get_forecast_rates',
        store=True,
        # string='Rate Forecasts'
    )  #

    total_rate_forecast = fields.Float(
        string='Total Rate',
        compute='_compute_total_rate_forecast',
        tracking=True
    )

    @api.depends('rate_forecast_ids.rate')
    def _compute_total_rate_forecast(self):
        for record in self:
            if record.use_price:
                if record.room_amount_selection.lower() == "total":
                    total = sum(line.rate for line in record.rate_forecast_ids)
                    if record.room_is_amount:
                        record.total_rate_forecast = total - record.room_discount
                    else:
                        record.total_rate_forecast = sum(
                            line.rate for line in record.rate_forecast_ids)
                else:
                    record.total_rate_forecast = sum(
                        line.rate for line in record.rate_forecast_ids)
            else:
                record.total_rate_forecast = sum(
                    line.rate for line in record.rate_forecast_ids)

    total_meal_forecast = fields.Float(
        string='Total Meals',
        compute='_compute_total_meal_forecast',
        tracking=True
    )

    @api.depends('rate_forecast_ids.meals')
    def _compute_total_meal_forecast(self):
        for record in self:
            if record.use_meal_price:
                if record.meal_amount_selection.lower() == "total":
                    total = sum(
                        line.meals for line in record.rate_forecast_ids)
                    if record.meal_is_amount:
                        # record.total_meal_forecast = total - (record.meal_discount * record.adult_count)
                        record.total_meal_forecast = total - \
                            (record.meal_discount)
                    else:
                        record.total_meal_forecast = sum(
                            line.meals for line in record.rate_forecast_ids)
                else:
                    record.total_meal_forecast = sum(
                        line.meals for line in record.rate_forecast_ids)
            else:
                record.total_meal_forecast = sum(
                    line.meals for line in record.rate_forecast_ids)

    total_package_forecast = fields.Float(
        string='Total Packages',
        compute='_compute_total_package_forecast',
        tracking=True
    )

    @api.depends('rate_forecast_ids.packages')
    def _compute_total_package_forecast(self):
        for record in self:
            record.total_package_forecast = sum(
                line.packages for line in record.rate_forecast_ids)

    total_fixed_post_forecast = fields.Float(
        string='Total Fixed Pst.',
        compute='_compute_total_fixed_post_forecast',
        tracking=True
    )

    @api.depends('rate_forecast_ids.fixed_post')
    def _compute_total_fixed_post_forecast(self):
        for record in self:
            record.total_fixed_post_forecast = sum(
                line.fixed_post for line in record.rate_forecast_ids)

    total_total_forecast = fields.Float(
        string='Grand Total',
        compute='_compute_total_total_forecast',
        tracking=True
    )

    # @api.depends('rate_forecast_ids.total')
    # def _compute_total_total_forecast(self):
    #     for record in self:
    #         record.total_total_forecast = sum(line.total for line in record.rate_forecast_ids)

    @api.depends('rate_forecast_ids.total',
                 'room_is_amount', 'room_amount_selection',
                 'meal_is_amount', 'meal_amount_selection')
    def _compute_total_total_forecast(self):
        for record in self:
            # Fetch rate details for the record's rate code
            checkin_date = fields.Date.from_string(record.checkin_date)

            checkin_date = fields.Date.from_string(record.checkin_date)
            checkout_date = fields.Date.from_string(record.checkout_date)
            total_days = (checkout_date - checkin_date).days
            _logger.info(f"Total days {total_days}")
            if total_days == 0:
                total_days = 1

            rate_details = self.env['rate.detail'].search([
                ('rate_code_id', '=', record.rate_code.id),
                ('from_date', '<=', checkin_date),
                ('to_date', '>=', checkin_date)
            ], limit=1)

            # Initialize discount-related variables
            is_amount_value = rate_details.is_amount if rate_details else None
            is_percentage_value = rate_details.is_percentage if rate_details else None
            amount_selection_value = rate_details.amount_selection if rate_details else None
            rate_detail_discount_value = int(
                rate_details.rate_detail_dicsount) if rate_details else 0

            # print(f'Rate Details -> Is Amount: {is_amount_value}, Is Percentage: {is_percentage_value}, '
            #       f'Amount Selection: {amount_selection_value}, Discount: {rate_detail_discount_value}')

            # Calculate total_total_forecast
            # total_sum = sum(line.total for line in record.rate_forecast_ids)
            total_sum = record.total_before_discount_forecast
            _logger.info(
                f"Initial Total Sum: {total_sum}, amount {is_amount_value}, percent {is_percentage_value}, amount selection {amount_selection_value}, discount {rate_detail_discount_value}")
            if is_amount_value and amount_selection_value == 'total':
                # record.total_total_forecast = total_sum - rate_detail_discount_value
                total_sum -= rate_detail_discount_value
                _logger.info(
                    f"After Rate Discount ({rate_detail_discount_value}): {total_sum}")

            for day in range(total_days):
                if is_amount_value and amount_selection_value == 'line_wise':
                    # record.total_total_forecast = total_sum - rate_detail_discount_value
                    total_sum -= rate_detail_discount_value
                    _logger.info(
                        f"After Rate Discount Line ({rate_detail_discount_value}): {total_sum}")

            if is_percentage_value and not record.use_price:
                # record.total_total_forecast = total_sum - rate_detail_discount_value
                percentage_discount = (
                    total_sum * rate_detail_discount_value) / 100
                total_sum -= percentage_discount
                _logger.info(
                    f"After Rate Discount ({rate_detail_discount_value}): {total_sum}")

            # Apply discount if room_is_percentage is True for room_price
            if record.room_is_percentage and record.use_price:
                # record.total_total_forecast = total_sum - record.room_discount
                percentage_discount = (
                    record.room_price * record.room_discount * record.room_count * record.no_of_nights)
                total_sum -= percentage_discount
                _logger.info(
                    f"After Percent Room Discount ({record.room_discount}): {total_sum}")

            # Apply discount if is_amount is True and amount_selection_value is 'total' for room_price
            if record.room_is_amount and record.room_amount_selection == 'total' and record.use_price:
                # record.total_total_forecast = total_sum - record.room_discount
                total_sum -= record.room_discount
                _logger.info(
                    f"After Total Room Discount ({record.room_discount}): {total_sum}")

            # Apply discount if is_amount is True and amount_selection_value is 'line_wise' for room_price
            if record.room_is_amount and record.room_amount_selection == 'line_wise' and record.use_price:
                # record.total_total_forecast = total_sum - record.room_discount
                total_sum -= record.room_discount * record.no_of_nights
                _logger.info(
                    f"After Line wise Room Discount ({record.room_discount}): {total_sum}")

            # Apply discount if meal_is_percentage is True for room_price
            if record.meal_is_percentage and record.use_meal_price:
                # record.total_total_forecast = total_sum - record.room_discount
                percentage_discount = (
                    record.meal_price * record.meal_discount * record.adult_count * record.no_of_nights * record.room_count)
                percentage_discount += (
                    record.meal_child_price * record.meal_discount * record.child_count * record.no_of_nights * record.room_count)
                total_sum -= percentage_discount
                _logger.info(
                    f"After Percent Meal Discount ({record.meal_discount}): {total_sum}")

            # Apply discount if is_amount is True and amount_selection_value is 'total' for meal_price
            if record.meal_is_amount and record.meal_amount_selection == 'total' and record.use_meal_price:
                # record.total_total_forecast = total_sum - record.meal_discount
                total_sum -= record.meal_discount
                _logger.info(
                    f"After Total Meal Discount ({record.meal_discount}): {total_sum}")

            # Apply discount if is_amount is True and amount_selection_value is 'line_wise' for meal_price
            if record.meal_is_amount and record.meal_amount_selection == 'line_wise' and record.use_meal_price:
                # record.total_total_forecast = total_sum - record.meal_discount
                total_sum -= record.meal_discount * record.no_of_nights
                _logger.info(
                    f"After Line wise Meal Discount ({record.meal_discount}): {total_sum}")

                # Ensure the total doesn't go below zero
            record.total_total_forecast = total_sum

    #
    #         # working
    #         # if is_amount_value and amount_selection_value == 'total':
    #         #     # Apply discount if is_amount is True and amount_selection_value is 'total'
    #         #     record.total_total_forecast = total_sum - rate_detail_discount_value
    #         # else:
    #         #     # Default behavior without discount
    #         #     record.total_total_forecast = total_sum
    #
    #     # for record in self:
    #     #     record.total_total_forecast = sum(line.total for line in record.rate_forecast_ids)

    total_before_discount_forecast = fields.Float(
        string='Grand Total Before Discount',
        compute='_compute_total_before_discount_forecast'
    )

    @api.depends('rate_forecast_ids.before_discount')
    def _compute_total_before_discount_forecast(self):
        for record in self:
            # record.total_before_discount_forecast = record.total_rate_forecast + record.total_meal_forecast + record.total_package_forecast + record.total_fixed_post_forecast
            record.total_before_discount_forecast = sum(
                line.before_discount for line in record.rate_forecast_ids)

    def get_meal_rates(self, id):
        meal_rate_pax = 0
        meal_rate_child = 0
        meal_rate_infant = 0
        posting_item_id = None

        meal_pattern = self.env['meal.pattern'].search([('id', '=', id)])
        if meal_pattern:
            posting_item_id = meal_pattern.meal_posting_item.id
            # print(f"Posting Item ID meal: {posting_item_id}")
            # print("Meal pattern found", meal_pattern)
            # print("Meal pattern found", meal_pattern.meals_list_ids)

            for meal_code in meal_pattern.meals_list_ids:
                # print("MEAL CODE", meal_code.meal_code)
                meal_rate_pax += meal_code.meal_code.price_pax
                meal_rate_child += meal_code.meal_code.price_child
                meal_rate_infant += meal_code.meal_code.price_infant

        return posting_item_id, meal_rate_pax, meal_rate_child, meal_rate_infant

    # def get_meal_rates(self, id):
    #     meal_rate_pax = 0
    #     meal_rate_child = 0
    #     meal_rate_infant = 0

    #     meal_pattern = self.env['meal.pattern'].search([('id', '=', id)])
    #     if meal_pattern:
    #         # print("Meal pattern found", meal_pattern)
    #         # print("Meal pattern found", meal_pattern.meals_list_ids)

    #         for meal_code in meal_pattern.meals_list_ids:
    #             # print("MEAL CODE", meal_code.meal_code)
    #             meal_rate_pax += meal_code.meal_code.price_pax
    #             meal_rate_child += meal_code.meal_code.price_child
    #             meal_rate_infant += meal_code.meal_code.price_infant

    #     return meal_rate_pax, meal_rate_child, meal_rate_infant

    def get_all_prices(self, forecast_date, record):
        meal_price = 0
        room_price = 0
        package_price = 0
        take_meal_price = True
        take_room_price = True
        # To store the posting item ID from rate_code[0]
        posting_item_value = None
        line_posting_items = []

        rate_details = self.env['rate.detail'].search([
            ('rate_code_id', '=', record.rate_code.id),
            ('from_date', '<=', forecast_date),
            ('to_date', '>=', forecast_date)
        ], limit=1)

        if not record.use_meal_price:
            if rate_details.price_type == "room_only":
                print("ROOM ONLY")
                take_meal_price = False

        if take_meal_price:
            if not record.use_meal_price:
                _1, meal_rate_pax, meal_rate_child, meal_rate_infant = self.get_meal_rates(
                    record.meal_pattern.id)

                if meal_rate_pax == 0:
                    if rate_details:
                        if rate_details.customize_meal == 'meal_pattern':
                            _1, meal_rate_pax, meal_rate_child, meal_rate_infant = self.get_meal_rates(
                                rate_details[0].meal_pattern_id.id)
                        elif rate_details.customize_meal == 'customize':
                            meal_rate_pax = rate_details.adult_meal_rate
                            meal_rate_child = rate_details.child_meal_rate
                            meal_rate_infant = rate_details.infant_meal_rate

                # meal_rate_pax_price = meal_rate_pax * record.adult_count
                meal_rate_pax_price = meal_rate_pax * record.adult_count * record.room_count
                # print("MEAL PRICE ADULT", meal_rate_pax_price)
                # meal_rate_child_price = meal_rate_child * record.child_count
                meal_rate_child_price = meal_rate_child * \
                    record.child_count * record.room_count
                # print("MEAL PRICE CHILD", meal_rate_child_price)
                meal_rate_infant_price = meal_rate_infant * \
                    record.infant_count * record.room_count
                # print("MEAL PRICE INFANT", meal_rate_infant_price)
                meal_price += (meal_rate_pax_price +
                               meal_rate_child_price + meal_rate_infant_price)
                # print("MEAL PRICE FINAL", meal_price)
                # meal_price += record.meal_price * record.adult_count * record.room_count
            else:
                meal_price += record.meal_price * record.adult_count * record.room_count
                meal_price += record.meal_child_price * record.child_count * record.room_count
                meal_price += record.meal_infant_price * \
                    record.infant_count * record.room_count

        if record.adult_count > 0:
            _day = forecast_date.strftime('%A').lower()
            _var = f"{_day}_pax_{record.adult_count}"
            _var_child = f"{_day}_child_pax_1"
            _var_infant = f"{_day}_infant_pax_1"
            _adult_count = 1
            if record.adult_count > 6:
                _var = f"{_day}_pax_1"
                _adult_count = record.adult_count

            if record.rate_code.id and not record.use_price:
                # rate_details = self.env['rate.detail'].search([('rate_code_id', '=', record.rate_code.id)])
                if rate_details:
                    posting_item_value = rate_details[0].posting_item.id
                    # print(f"Posting Item Value rate: {posting_item_value}")
                    room_price += rate_details[0][_var] * \
                        record.room_count * _adult_count
                    # print("ROOM PRICE ADULT", room_price)
                    room_price += rate_details[0][_var_child] * \
                        record.room_count * record.child_count
                    # print("ROOM PRICE CHILD", room_price)
                    room_price += rate_details[0][_var_infant] * \
                        record.room_count * record.infant_count
                    # print("ROOM PRICE INFANT", room_price)
                # else:
                #     room_price += 0
                # if len(rate_details) == 1:
                #     room_price += rate_details[_var] * record.room_count

                elif len(rate_details) > 1:
                    room_price += rate_details[0][_var] * record.room_count
                    # print("ROOM PRICE ADULT 1", room_price)
                    room_price += rate_details[0][_var_child] * \
                        record.room_count
                    # print("ROOM PRICE CHILD 1", room_price)
                    room_price += rate_details[0][_var_infant] * \
                        record.room_count
                    # print("ROOM PRICE INFANT 1", room_price)

                else:
                    room_price += 0

            elif record.use_price:
                room_price += record.room_price * record.room_count
                room_price += record.room_child_price * record.room_count
                room_price += record.room_infant_price * record.room_count

        if record.rate_code.id:
            for line in rate_details.line_ids:
                posting_item_id = line.packages_posting_item.id
                line_posting_items.append(posting_item_id)
                print(f"Posting Item ID lne: {posting_item_id}")
                if line.packages_rhythm == "every_night" and line.packages_value_type == "added_value":
                    package_price += line.packages_value

                if line.packages_rhythm == "every_night" and line.packages_value_type == "per_pax":
                    package_price += line.packages_value * record.adult_count

                if line.packages_rhythm == "first_night" and line.packages_value_type == "added_value":
                    package_price += line.packages_value

                if line.packages_rhythm == "first_night" and line.packages_value_type == "per_pax":
                    package_price += line.packages_value * record.adult_count

        return meal_price, room_price, package_price, posting_item_value, line_posting_items

    # Working 04/01/2025
    # def get_all_prices(self, forecast_date, record):
    #     meal_price = 0
    #     room_price = 0
    #     package_price = 0
    #     take_meal_price = True
    #     take_room_price = True

    #     rate_details = self.env['rate.detail'].search([
    #         ('rate_code_id', '=', record.rate_code.id),
    #         ('from_date', '<=', forecast_date),
    #         ('to_date', '>=', forecast_date)
    #     ], limit=1)

    #     if not record.use_meal_price:
    #         if rate_details.price_type == "room_only":
    #             print("ROOM ONLY")
    #             take_meal_price = False

    #     if take_meal_price:
    #         if not record.use_meal_price:
    #             meal_rate_pax, meal_rate_child, meal_rate_infant = self.get_meal_rates(record.meal_pattern.id)

    #             if meal_rate_pax == 0:
    #                 if rate_details:
    #                     meal_rate_pax, meal_rate_child, meal_rate_infant = self.get_meal_rates(
    #                         rate_details[0].meal_pattern_id.id)

    #             # meal_rate_pax_price = meal_rate_pax * record.adult_count
    #             meal_rate_pax_price = meal_rate_pax * record.adult_count * record.room_count
    #             # meal_rate_child_price = meal_rate_child * record.child_count
    #             meal_rate_child_price = meal_rate_child * record.child_count * record.room_count
    #             meal_rate_infant_price = meal_rate_infant * record.infant_count * record.room_count
    #             meal_price += (meal_rate_pax_price + meal_rate_child_price + meal_rate_infant_price)
    #             # meal_price += record.meal_price * record.adult_count * record.room_count
    #         else:
    #             meal_price += record.meal_price * record.adult_count * record.room_count
    #             meal_price += record.meal_child_price * record.child_count * record.room_count
    #             meal_price += record.meal_infant_price * record.infant_count * record.room_count

    #     if record.adult_count > 0:
    #         _day = forecast_date.strftime('%A').lower()
    #         _var = f"{_day}_pax_{record.adult_count}"
    #         if record.adult_count > 6:
    #             _var = f"{_day}_pax_1"

    #         if record.rate_code.id and not record.use_price:
    #             # rate_details = self.env['rate.detail'].search([('rate_code_id', '=', record.rate_code.id)])
    #             if rate_details:
    #                 room_price += rate_details[0][_var] * record.room_count
    #             # else:
    #             #     room_price += 0
    #             # if len(rate_details) == 1:
    #             #     room_price += rate_details[_var] * record.room_count

    #             elif len(rate_details) > 1:
    #                 room_price += rate_details[0][_var] * record.room_count

    #             else:
    #                 room_price += 0

    #         elif record.use_price:
    #             room_price += record.room_price * record.room_count
    #             room_price += record.room_child_price * record.room_count
    #             room_price += record.room_infant_price * record.room_count

    #     if record.rate_code.id:
    #         for line in rate_details.line_ids:
    #             if line.packages_rhythm == "every_night" and line.packages_value_type == "added_value":
    #                 package_price += line.packages_value

    #             if line.packages_rhythm == "every_night" and line.packages_value_type == "per_pax":
    #                 package_price += line.packages_value * record.adult_count

    #             if line.packages_rhythm == "first_night" and line.packages_value_type == "added_value":
    #                 package_price += line.packages_value

    #             if line.packages_rhythm == "first_night" and line.packages_value_type == "per_pax":
    #                 package_price += line.packages_value * record.adult_count

    #     return meal_price, room_price, package_price

    @api.model
    def calculate_total(self, price, discount, is_percentage, is_amount, amount_selection, condition):
        if condition:
            if is_percentage:
                total = (price * discount)
                # total = price - (price * discount)
                # print('754', total)
            elif is_amount and amount_selection == 'line_wise':
                # total = price - discount
                total = discount
                # print('757', total)
            else:
                # total = price
                total = 0

        else:
            # total = price
            total = 0
            # print('760', total)

        return total  # Ensure the total doesn't go below zero

    # working
    # def calculate_total_discount(self, before_discount, rate_detail_discount_value, is_percentage_value, is_amount_value, amount_selection_value):
    #     if is_percentage_value:
    #         total = before_discount - ((before_discount / 100) * rate_detail_discount_value)
    #         # print(f'Condition: Percentage applied. Total: {total}')
    #     elif is_amount_value and amount_selection_value == 'line_wise':
    #         total = before_discount - rate_detail_discount_value
    #         # print(f'Condition: Line Wise amount applied. Total: {total}')
    #     else:
    #         total = before_discount
    #         # print(f'Condition: No discount applied. Total: {total}')
    #     return total

    @api.model
    def calculate_meal_rates(self, rate_details):
        total_default_value = 0

        # Retrieve the posting item from rate details
        rate_detail_posting_item = rate_details.posting_item if rate_details else 0
        if rate_detail_posting_item:
            # Get the default value of the posting item
            default_value = getattr(
                rate_detail_posting_item, 'default_value', 0)
            print(f"Default Value (Posting Item): {default_value}")

            # Add this default value to the total
            total_default_value += default_value
        else:
            print("No Posting Item found. Default Value: 0")

        # Retrieve the meal pattern from rate details
        rate_detail_meal_pattern = rate_details.meal_pattern_id if rate_details else 0
        if rate_detail_meal_pattern:
            # Get the default value of meal_posting_item
            meal_posting_item = rate_detail_meal_pattern.meal_posting_item
            meal_posting_item_default_value = getattr(
                meal_posting_item, 'default_value', 0)
            print(
                f"Meal Posting Item Default Value: {meal_posting_item_default_value}")

            # Add this default value to the total
            total_default_value += meal_posting_item_default_value

            # Loop through meal codes and calculate their default values
            for meal_code in rate_detail_meal_pattern.meals_list_ids:
                # Access the posting_item of each meal_code
                posting_item = meal_code.meal_code.posting_item

                # Get the default value of the posting_item
                meal_code_default_value = getattr(
                    posting_item, 'default_value', 0)
                print(
                    f"Posting Item Default Value (Meal Code): {meal_code_default_value}")

                # Add this default value to the total
                total_default_value += meal_code_default_value
        else:
            print("No Meal Pattern found.")

        # Print the final total default value
        return total_default_value

    @api.depends('adult_count', 'room_count', 'child_count', 'infant_count', 'checkin_date', 'checkout_date',
                 'meal_pattern', 'rate_code', 'room_price', 'room_child_price', 'room_infant_price', 'meal_price',
                 'meal_child_price', 'meal_infant_price', 'posting_item_ids', 'room_discount', 'room_is_percentage',
                 'room_is_amount', 'room_amount_selection', 'meal_discount', 'meal_is_percentage', 'meal_is_amount',
                 'meal_amount_selection', 'use_price', 'use_meal_price')
    def _get_forecast_rates(self):
        _logger.info("GET FORECAST RATES")
        print("GET FORECAST RATES")
        for record in self:
            for rate_forecast in record.rate_forecast_ids:
                if rate_forecast:
                    if isinstance(rate_forecast.room_booking_id, NewId):
                        # print("Skipping NewId", rate_forecast.room_booking_id)
                        continue
                    rate_forecast.room_booking_id = None
            if not record.checkin_date or not record.checkout_date:
                record.rate_forecast_ids = []
                continue
            checkin_date = fields.Date.from_string(record.checkin_date)
            checkout_date = fields.Date.from_string(record.checkout_date)
            total_days = (checkout_date - checkin_date).days
            _logger.info(f"Total days {total_days}")
            if total_days == 0:
                total_days = 1

            # rate_code_posting_item = record.rate_code
            # print('361', rate_code_posting_item, flush=True)
            # rate_code_meal_pattern_posting_item = record.meal_pattern
            # print('363', rate_code_meal_pattern_posting_item)

            posting_items = record.posting_item_ids

            # custom_date_ranges = []
            # custom_date_value = 0
            # for line in posting_items:
            #     if line.posting_item_selection == 'custom_date':

            #         if not line.from_date or not line.to_date:
            #             print(f"Skipping validation for line {line.item_code} as dates are not yet filled.")
            #             continue
            #         from_date = fields.Date.from_string(line.from_date)
            #         to_date = fields.Date.from_string(line.to_date)
            #         print('627',line.from_date, line.to_date, type(line.from_date),type(line.to_date))

            #         # Check if custom_date is within the booking period
            #         if from_date < checkin_date:
            #             raise ValidationError(f"'From Date' for posting item '{line.item_code}' cannot be earlier than the Check-In date.")

            #         if from_date > checkout_date:
            #             raise ValidationError(f"'From Date' for posting item '{line.item_code}' cannot be later than the Check-Out date.")

            #         if to_date <= from_date:
            #             raise ValidationError(f"'To Date' for posting item '{line.item_code}' must be greater than 'From Date'.")

            #         if to_date > checkout_date:
            #             raise ValidationError(f"'To Date' for posting item '{line.item_code}' cannot be later than the Check-Out date.")

            #         # custom_date_ranges.append({
            #         #     'from_date': from_date,
            #         #     'to_date': to_date,
            #         #     'default_value': line.default_value
            #         # })

            #         # Sum the default value for the custom_date item
            #         custom_date_value += line.default_value

            # Initialize variables for calculation
            first_night_value = sum(
                line.default_value for line in posting_items if line.posting_item_selection == 'first_night')
            every_night_value = sum(
                line.default_value for line in posting_items if line.posting_item_selection == 'every_night')

            # Get all rate detail records for the booking
            posting_items_ = self.env['room.rate.forecast'].search(
                [('room_booking_id', '=', record.id)])

            total_lines = len(posting_items_)
            # print(f"Total lines in rate details: {total_lines}")

            fixed_post_value = 0

            # Fetch rate details for the record's rate code
            rate_details = self.env['rate.detail'].search([
                ('rate_code_id', '=', record.rate_code.id),
                ('from_date', '<=', checkin_date),
                ('to_date', '>=', checkin_date)
            ], limit=1)

            # Initialize discount-related variables
            is_amount_value = rate_details.is_amount if rate_details else None
            is_percentage_value = rate_details.is_percentage if rate_details else None
            amount_selection_value = rate_details.amount_selection if rate_details else None
            if is_amount_value:
                rate_detail_discount_value = int(
                    rate_details.rate_detail_dicsount) if rate_details else 0
            else:
                rate_detail_discount_value = int(
                    rate_details.rate_detail_dicsount) / 100 if rate_details else 0

            # Prepare forecast rates
            forecast_lines = []

            for day in range(total_days):
                forecast_date = checkin_date + timedelta(days=day)
                # Fetch prices for the day
                meal_price, room_price, package_price, _1, _2 = self.get_all_prices(
                    forecast_date, record)

                # Calculate total before discount
                # before_discount = room_price + meal_price + package_price
                _logger.info(
                    f"Meal: {meal_price}, Room: {room_price}, Package {package_price}")

                if day == 0:  # First day logic
                    if every_night_value is None:
                        # Adjusted for room_count
                        fixed_post_value = (
                            first_night_value or 0) * record.room_count
                    elif first_night_value is None:
                        # Adjusted for room_count
                        fixed_post_value = (
                            every_night_value or 0) * record.room_count
                    else:
                        fixed_post_value = (
                            first_night_value + every_night_value) * record.room_count
                else:  # Other days
                    if every_night_value is None:
                        # Adjusted for room_count
                        fixed_post_value = (
                            first_night_value or 0) * record.room_count
                    else:
                        fixed_post_value = every_night_value * record.room_count

                # Add custom date values if the forecast_date falls within any custom date ranges
                for line in posting_items:
                    if line.posting_item_selection == 'custom_date' and line.from_date and line.to_date:
                        from_date = fields.Date.from_string(line.from_date)
                        to_date = fields.Date.from_string(line.to_date)
                        checkin_date = fields.Date.from_string(
                            record.checkin_date)
                        checkout_date = fields.Date.from_string(
                            record.checkout_date)
                        print('696', from_date, to_date,
                              checkin_date, checkout_date)
                        # Check if current forecast_date falls within the custom date range
                        if from_date <= forecast_date <= to_date:
                            fixed_post_value += line.default_value * record.room_count

                room_booking_id = record.id
                room_booking_str = str(record.id).split('_')[-1]
                if record.id is not int or record.id is not str or record.id is hex:
                    room_booking_id = record.id

                elif record.id is not int:
                    if "0x" in str(record.id):
                        room_booking_id = record.id
                    else:
                        room_booking_id = int(str(record.id).split('_')[-1])
                    print("room_booking_id", room_booking_id)

                # Search for existing forecast record
                existing_forecast = self.env['room.rate.forecast'].search([
                    ('room_booking_id', '=', room_booking_id),
                    ('date', '=', forecast_date)
                ], limit=1)

                # print(f'Existing Forecast for {forecast_date}: {existing_forecast}')

                # get_meal_rates = self.calculate_meal_rates(rate_details)
                # print("get_meal_rates", get_meal_rates)

                # Update or create forecast records
                # get_discount = self.calculate_total(before_discount, rate_detail_discount_value, is_percentage_value,
                #                                     is_amount_value, amount_selection_value)
                # print("GET DISCOUNT", get_discount)

                if not record.use_price:
                    _room_price = room_price
                else:
                    _room_price = record.room_price * record.room_count
                room_price_after_discount = record.calculate_total(
                    _room_price,
                    record.room_discount,
                    record.room_is_percentage,
                    record.room_is_amount,
                    record.room_amount_selection, record.use_price)

                if not record.use_meal_price:
                    _meal_price = meal_price
                else:
                    _meal_price = record.meal_price * record.adult_count * record.room_count
                    _meal_price += record.meal_child_price * record.child_count * record.room_count
                meal_price_after_discount = record.calculate_total(
                    _meal_price,
                    record.meal_discount,
                    record.meal_is_percentage,
                    record.meal_is_amount,
                    record.meal_amount_selection, record.use_meal_price)

                before_discount = room_price + meal_price + package_price + fixed_post_value

                print("GETTING DISCOUNT", before_discount, rate_detail_discount_value, is_percentage_value,
                      is_amount_value, amount_selection_value)
                get_discount = self.calculate_total(before_discount, rate_detail_discount_value, is_percentage_value,
                                                    is_amount_value, amount_selection_value, True)
                if is_percentage_value:
                    get_discount = 0

                # total = before_discount - get_discount - room_price - meal_price
                total = before_discount - get_discount - \
                    room_price_after_discount - meal_price_after_discount

                # meal_rates_get_discount = get_meal_rates + get_discount
                # print("meal_rates_ge  t_discount", meal_rates_get_discount)
                room_line_ids = record.room_line_ids.ids
                _logger.info(
                    f"Total: {total}, Before Discount: {before_discount}, Discount {get_discount}, Room Price {room_price_after_discount}, Meal Price {meal_price_after_discount}, ROOM LINE IDS {room_line_ids}")

                if existing_forecast:
                    existing_forecast.write({
                        # 'rate': room_price,
                        # 'rate': room_price_after_discount,
                        'rate': room_price - room_price_after_discount,
                        # 'meals': meal_price,
                        'meals': meal_price - meal_price_after_discount,
                        'packages': package_price,
                        'fixed_post': fixed_post_value,
                        # 'total': total_after_discount,
                        # 'total': get_discount + fixed_post_value,
                        'total': total,
                        'before_discount': before_discount,
                        'booking_line_ids': [(6, 0, room_line_ids)]
                    })
                else:
                    # Append new forecast line
                    forecast_lines.append((0, 0, {
                        'date': forecast_date,
                        'rate': room_price - room_price_after_discount,
                        # 'rate': room_price_after_discount if record.room_price else room_price,
                        # 'meals': meal_price_after_discount if record.meal_price else meal_price,
                        'meals': meal_price - meal_price_after_discount,
                        'packages': package_price,
                        'fixed_post': fixed_post_value,
                        'total': total,
                        'before_discount': before_discount,
                        'booking_line_ids': [(6, 0, room_line_ids)]
                    }))

            # Assign forecast lines to the record
            _logger.info(f"FORECAST LINES {forecast_lines}")
            record.rate_forecast_ids = forecast_lines

    hotel_id = fields.Many2one('hotel.hotel', string="Hotel",
                               help="Hotel associated with this booking", tracking=True)

    is_readonly_group_booking = fields.Boolean(
        string="Is Readonly", compute="_compute_is_readonly_group_booking", store=False
    )

    @api.depends('group_booking')
    def _compute_is_readonly_group_booking(self):
        for record in self:
            record.is_readonly_group_booking = bool(record.group_booking)

    # @api.depends('group_booking')
    # def _compute_is_readonly_group_booking(self):
    #     for record in self:
    #         record.is_readonly_group_booking = bool(record.group_booking)

    group_booking = fields.Many2one(
        'group.booking', string="Group Booking", help="Group associated with this booking", tracking=True)

    show_group_booking = fields.Boolean(
        string="Show Group Booking", compute="_compute_show_group_booking", store=False)

    # @api.constrains('state', 'group_booking')
    # def _check_group_booking(self):
    #     for record in self:
    #         if record.state == 'block' and not record.group_booking:
    #             raise ValidationError(_("Group Booking must be set when the booking is in 'block' state."))

    @api.onchange('room_count')
    def _compute_show_group_booking(self):
        for record in self:
            record.show_group_booking = record.room_count > 1

    @api.onchange('group_booking')
    def _onchange_group_booking(self):
        if self.group_booking:
            self.nationality = self.group_booking.nationality.id if self.group_booking.nationality else False
            self.partner_id = self.group_booking.company.id if self.group_booking.company else False
            self.source_of_business = self.group_booking.source_of_business.id if self.group_booking.source_of_business else False
            self.rate_code = self.group_booking.rate_code.id if self.group_booking.rate_code else False
            self.meal_pattern = self.group_booking.group_meal_pattern.id if self.group_booking.group_meal_pattern else False
            self.market_segment = self.group_booking.market_segment.id if self.group_booking.market_segment else False
            self.house_use = self.group_booking.house_use
            self.complementary = self.group_booking.complimentary
            self.payment_type = self.group_booking.payment_type
            self.complementary_codes = self.group_booking.complimentary_codes.id if self.group_booking.complimentary_codes else False
            self.house_use_codes = self.group_booking.house_use_codes_.id if self.group_booking.house_use_codes_ else False
            if self.group_booking.company and self.group_booking.company.is_vip:
                self.vip = True
                self.vip_code = self.group_booking.company.vip_code.id if self.group_booking.company.vip_code else False
            else:
                self.vip = False
                self.vip_code = False
            # self.meal_pattern = self.group_booking.meal_pattern.id if self.group_booking.meal_pattern else False
            # self.partner_id = self.group_booking.contact.id if self.group_booking.contact else False

    agent = fields.Many2one('agent.agent', string="Agent",
                            help="Agent associated with this booking", tracking=True)
    is_vip = fields.Boolean(related='partner_id.is_vip',
                            string="VIP", store=True,
                            tracking=True)

    allow_profile_change = fields.Boolean(
        related='group_booking.allow_profile_change',
        string='Allow changing profile data in the reservation form?',
        readonly=True,
        tracking=True
    )

    # @api.depends('group_booking', 'group_booking.allow_profile_change')
    # def _compute_is_readonly_group_booking(self):
    #     for record in self:
    #         if record.group_booking:
    #             # Fields are read-only if allow_profile_change is False
    #             record.allow_profile_change = not record.group_booking.allow_profile_change
    #         else:
    #             # Fields are editable when no group_booking is selected
    #             record.allow_profile_change = False

    # allow_profile_change = fields.Boolean(related='group_booking.allow_profile_change', ☻string='Allow changing profile data in the reservation form?', readonly=True)

    company_id = fields.Many2one('res.company', string="Hotel",
                                 help="Choose the Hotel",
                                 index=True,
                                 default=lambda self: self.env.company)
    # partner_id = fields.Many2one('res.partner', string="Customer",
    #                              help="Customers of hotel",
    #                              required=True, index=True, tracking=1,
    #                              domain="[('type', '!=', 'private'),"
    #                                     " ('company_id', 'in', "
    #                                     "(False, company_id))]")
    is_agent = fields.Boolean(string='Is Company')
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact'

    )

    # reference_contact = fields.Many2one(
    #     'res.partner',
    #     string='Contact Reference'

    # )

    reference_contact_ = fields.Char(string=_('Contact Reference'))

    # @api.onchange('partner_id')
    # def _onchange_customer(self):
    #     if self.partner_id:
    #         self.nationality = self.partner_id.nationality.id
    #         self.source_of_business = self.partner_id.source_of_business.id
    #         self.rate_code = self.partner_id.rate_code.id

    @api.onchange('partner_id')
    def _onchange_customer(self):
        if self.group_booking:
            # If group_booking is selected, skip this onchange
            return
        if self.partner_id:
            self.nationality = self.partner_id.nationality.id
            self.source_of_business = self.partner_id.source_of_business.id
            self.rate_code = self.partner_id.rate_code.id
            self.market_segment = self.partner_id.market_segments.id
            self.meal_pattern = self.partner_id.meal_pattern.id
            if self.partner_id.is_vip:
                self.vip = True
                self.vip_code = self.partner_id.vip_code.id if self.partner_id.vip_code else False
            else:
                self.vip = False
                self.vip_code = False

    @api.onchange('is_agent')
    def _onchange_is_agent(self):
        self.partner_id = False
        return {
            'domain': {
                'partner_id': [('is_company', '=', self.is_agent)]
            }
        }

    # date_order = fields.Datetime(string="Order Date",
    #                              required=True, copy=False,
    #                              help="Creation date of draft/sent orders,"
    #                                   " Confirmation date of confirmed orders",
    #                              default=fields.Datetime.now)
    date_order = fields.Datetime(
        string='Order Date', required=True, default=lambda self: self._get_default_order_date())

    @api.model
    def _get_default_order_date(self):
        # Get the system date from res.company
        system_date = self.env['res.company'].search([], limit=1).system_date
        return system_date or fields.Datetime.now()

    def write(self, vals):
        self.check_room_meal_validation(vals, True)
        # print('937', vals)
        # if 'state' in vals:
        #     for record in self:
        #         # Set 'previous_state' to the current state before changing it
        #         if record.state != vals['state']:
        #             vals['previous_state'] = record.state
        # self._onchange_price_discount(self)
        if 'active' in vals:
            return super(RoomBooking, self).write(vals)

        if 'room_count' in vals and vals['room_count'] <= 0:
            raise ValidationError(
                "Room count cannot be zero or less. Please select at least one room.")

        if 'adult_count' in vals and vals['adult_count'] <= 0:
            raise ValidationError(
                "Adult count cannot be zero or less. Please select at least one adult.")

        if 'child_count' in vals and vals['child_count'] < 0:
            raise ValidationError("Child count cannot be less than zero.")

        # if 'infant_count' in vals and vals['infant_count'] < 0:
        #     raise ValidationError("Infant count cannot be less than zero.")

        if 'checkin_date' in vals and not vals['checkin_date']:
            raise ValidationError(
                _("Check-In Date is required and cannot be empty."))

        if 'date_order' not in vals:
            system_date = self.env['res.company'].search(
                [], limit=1).system_date
            if system_date:
                vals['date_order'] = system_date
        # print("in write for testing", vals)
        # Determine if 'state' is being updated
        state_changed = 'state' in vals and vals['state'] != self.state

        # Perform the write operation
        res = super(RoomBooking, self).write(vals)
        # print("in write vals1",state_changed)

        if state_changed:
            new_state = vals.get('state')
            for record in self:
                for line in record.room_line_ids:
                    self.env['room.booking.line.status'].create({
                        'booking_line_id': line.id,
                        'status': new_state,
                        'change_time': fields.Datetime.now(),
                    })
        room_line_count = self.env['room.booking.line'].search_count([
            # Replace with the correct relation field for room lines
            ('booking_id', '=', self.id)
        ])
        if 'state' in vals and 'parent_booking_id' in vals and 'parent_booking_name' in vals and room_line_count > 1:
            # Check if there is more than one room line and remove the others
            room_lines = self.env['room.booking.line'].search([
                # Correct relation field
                ('booking_id', '=', vals.get('parent_booking_id'))
            ], order='counter asc')
            # Get the count of the lines in the sorted order
            room_line_count = len(room_lines)
            final_room_line = room_lines[room_line_count - 1]
            if room_line_count > 1:
                # Unlink all but the last record
                # Iterate over all but the last record
                for ctr in range(room_line_count - 1):
                    room_lines[ctr].unlink()
                # vals['room_count'] = 1
                res = super(RoomBooking, self).write({'room_count': 1})
                _logger.info(final_room_line, "this is final",
                             final_room_line.counter, vals.get('parent_booking_id'))
                # adult_lines = self.env['reservation.adult'].search([
                #     ('reservation_id', '=', vals.get('parent_booking_id'))
                #      # ('room_sequence', '!=', final_room_line.counter)
                #        # Correct relation field
                # ], order='room_sequence asc')

                adult_lines = self.env['reservation.adult'].search([
                    # Match parent booking ID
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)  # Exclude matching counter value
                ], order='room_sequence asc')
                # adult_lines.write({'room_sequence': final_room_line.counter})
                adult_count = len(adult_lines)
                if adult_count > 1:
                    # for ctr in range(1 * self.adult_count, adult_count):
                    for ctr in range(adult_count - self.adult_count):
                        adult_lines[ctr].unlink()

                adult_lines = self.env['reservation.adult'].search(
                    [('reservation_id', '=', vals.get('parent_booking_id')),
                     # ('room_sequence', '!=', final_room_line.counter)  # Exclude matching counter value
                     ], order='room_sequence asc')
                adult_count = len(adult_lines)

                for ctr in range(self.adult_count):
                    if ctr < len(adult_lines):
                        # Update existing record
                        record = adult_lines[ctr]
                        if record.exists():
                            if final_room_line.counter is not None:
                                record.write(
                                    {'room_sequence': final_room_line.counter})
                            else:
                                print("final_room_line.counter is not set.")
                        else:
                            print(
                                f"Record at index {ctr} does not exist in adult_lines.")

                child_lines = self.env['reservation.child'].search([
                    # Match parent booking ID
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)  # Exclude matching counter value
                ], order='room_sequence asc')
                # adult_lines.write({'room_sequence': final_room_line.counter})
                print('1078', child_lines)
                child_count = len(child_lines)
                if child_count > 1:
                    # for ctr in range(1 * self.adult_count, adult_count):
                    for ctr in range(child_count - self.child_count):
                        child_lines[ctr].unlink()

                child_lines = self.env['reservation.child'].search([
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)# Correct relation field
                ], order='room_sequence asc')
                # child_count = len(child_lines)

                for ctr in range(self.child_count):
                    if ctr < len(child_lines):
                        # Update existing record
                        record = child_lines[ctr]
                        if record.exists():
                            if final_room_line.counter is not None:
                                record.write(
                                    {'room_sequence': final_room_line.counter})
                            else:
                                print("final_room_line.counter is not set.")
                        else:
                            print(
                                f"Record at index {ctr} does not exist in child_lines.")

                infant_lines = self.env['reservation.infant'].search([
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)
                ], order='room_sequence asc')
                infant_count = len(infant_lines)
                if infant_count > 1:
                    for ctr in range(infant_count - self.infant_count):
                        infant_lines[ctr].unlink()

                infant_lines = self.env['reservation.infant'].search([
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)
                ], order='room_sequence asc')
                # infant_count = len(infant_lines)
                for ctr in range(self.infant_count):
                    if ctr < len(infant_lines):
                        # Update existing record
                        record = infant_lines[ctr]
                        if record.exists():
                            if final_room_line.counter is not None:
                                record.write(
                                    {'room_sequence': final_room_line.counter})
                            else:
                                print("final_room_line.counter is not set.")
                        else:
                            print(
                                f"Record at index {ctr} does not exist in infant_lines.")

                for adult in self.adult_ids:
                    if final_room_line:
                        adult.room_id = final_room_line.room_id.id
                        # adult.room_type_id = final_room_line.hotel_room_type.id
                        # Assign room type to hotel_room_type in room.booking
                        self.hotel_room_type = final_room_line.hotel_room_type.id
                        # print(f"Updated Adult {adult.id} with Room ID: {final_room_line.room_id.id} and updated Booking Room Type to: {final_room_line.hotel_room_type.id}")
                        # print(f"Updated Adult {adult.id} with Room ID: {final_room_line.room_id.id}")
                for child in self.child_ids:
                    if final_room_line:
                        child.room_id = final_room_line.room_id.id
                        # adult.room_type_id = final_room_line.hotel_room_type.id
                        # self.hotel_room_type = final_room_line.hotel_room_type.id  # Assign room type to hotel_room_type in room.booking
                        print(
                            f"Updated child {child.id} with Room ID: {final_room_line.room_id.id}")

                for infant in self.infant_ids:
                    if final_room_line:
                        infant.room_id = final_room_line.room_id.id
                        _logger.info(
                            f"Updated Infant {infant.id} with Room ID: {final_room_line.room_id.id}")

                # Return window action to refresh the view
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
        return res

        # return super(RoomBooking, self).write(vals)

    is_checkin = fields.Boolean(default=False, string="Is Checkin",
                                help="sets to True if the room is occupied")
    maintenance_request_sent = fields.Boolean(default=False,
                                              string="Maintenance Request sent"
                                                     "or Not",
                                              help="sets to True if the "
                                                   "maintenance request send "
                                                   "once", tracking=True)
    checkin_date = fields.Datetime(string="Check In",
                                   default=lambda self: fields.Datetime.now(),
                                   help="Date of Checkin", required=True, tracking=True)
    # default=fields.Datetime.now()
    checkout_date = fields.Datetime(string="Check Out",
                                    help="Date of Checkout", required=True, tracking=True)

    # @api.onchange('checkin_date')
    # def _onchange_checkin_date(self):
    #     current_time = fields.Datetime.now() - timedelta(minutes=10)  # 10-minute buffer
    #     if self.checkin_date and self.checkin_date < current_time:
    #         raise UserError(
    #             "Check-In Date cannot be more than 10 minutes in the past. Please select a valid time.")

    #     if self.checkin_date:
    #         # Set checkout_date to the end of the checkin_date
    #         self.checkout_date = self.checkin_date + timedelta(hours=23, minutes=59, seconds=59)

    no_of_nights = fields.Integer(string="No of Nights", default=1)

    @api.onchange('checkout_date')
    def _onchange_checkout_date(self):
        if self.checkin_date and self.checkout_date:
            if self.checkout_date < self.checkin_date:
                self.checkout_date = self.checkin_date + timedelta(days=1)
                return {
                    'warning': {
                        'title': 'Invalid Check-Out Date',
                        'message': "Check-Out Date cannot be before Check-In Date. It has been reset."
                    }
                }
            delta = (self.checkout_date - self.checkin_date).days
            self.no_of_nights = delta

    @api.onchange('checkin_date', 'no_of_nights')
    def _onchange_checkin_date_or_no_of_nights(self):
        if self.checkin_date:
            # Convert current time to user's timezone
            current_time = fields.Datetime.context_timestamp(
                self, fields.Datetime.now())
            buffer_time = current_time - timedelta(minutes=10)

            # Convert checkin_date to user's timezone for comparison
            checkin_user_tz = fields.Datetime.context_timestamp(
                self, self.checkin_date)

            # if checkin_user_tz < buffer_time:
            #     # Reset to current time if invalid
            #     self.checkin_date = fields.Datetime.to_string(current_time)
            #     return {
            #         'warning': {
            #             'title': 'Invalid Date',
            #             'message': "Check-In Date cannot be in the past."
            #         }
            #     }

            # Validate no_of_nights field
            # if not self.no_of_nights or self.no_of_nights < 0:
            if self.no_of_nights is not None and self.no_of_nights < 0:
                # self.no_of_nights = 1
                return {
                    'warning': {
                        'title': 'Invalid Number of Nights',
                        'message': "Number of nights must be at least 0."
                    }
                }
            if self.no_of_nights == 0:
                # If no_of_nights is 0, add 30 minutes to checkin_date
                self.checkout_date = self.checkin_date + timedelta(minutes=30)
            else:
                # Calculate checkout_date based on checkin_date and no_of_nights
                self.checkout_date = self.checkin_date + \
                    timedelta(days=self.no_of_nights)

    # working
    # @api.onchange('checkin_date')
    # def _onchange_checkin_date(self):
    #     if self.checkin_date:
    #         # Convert current time to user's timezone
    #         current_time = fields.Datetime.context_timestamp(self, fields.Datetime.now())
    #         buffer_time = current_time - timedelta(minutes=10)

    #         # Convert checkin_date to user's timezone for comparison
    #         checkin_user_tz = fields.Datetime.context_timestamp(self, self.checkin_date)

    #         if checkin_user_tz < buffer_time:
    #             # Reset to current time if invalid
    #             self.checkin_date = fields.Datetime.to_string(current_time)
    #             return {
    #                 'warning': {
    #                     'title': 'Invalid Date',
    #                     'message': "Check-In Date cannot be in the Past."
    #                 }
    #             }

    #         # Set checkout_date to next day same time
    #         # end_of_day = checkin_user_tz.replace(hour=23, minute=59, second=59)
    #         self.checkout_date = self.checkin_date + timedelta(hours=23, minutes=59, seconds=59)

    def _adjust_checkout_date(self):
        """Adjust checkout_date to one day after checkin_date if invalid."""
        if self.checkin_date:
            self.checkout_date = self.checkin_date + timedelta(days=1)

    # @api.constrains('checkout_date')
    # def _onchange_checkout_date(self):

    #     if self.checkout_date and self.checkin_date:
    #         # Compare dates without converting to the user's timezone
    #         if self.checkout_date <= self.checkin_date:
    #             # Set checkout_date to one day after checkin_date

    #             # self.checkout_date = False
    #             # self.checkout_date = self.checkin_date + timedelta(days=1)
    #             # raise UserError(
    #             #     "Check-Out Date must be after Check-In Date. It has been adjusted accordingly.")

    #             self._adjust_checkout_date()

    #             # Show a warning message
    #             return {
    #                 'warning': {
    #                     'title': 'Invalid Date',
    #                     'message': "Check-Out Date must be after Check-In Date. It has been set to one day after the Check-In Date."
    #                 }
    #             }

    # @api.onchange('checkout_date')
    # def _onchange_checkout_date(self):
    #     if self.checkout_date and self.checkin_date and self.checkout_date <= self.checkin_date:
    #         self.checkout_date = self.checkin_date + timedelta(days=1)
    #         # Raise a UserError (modal popup) to alert the user each time.
    #         raise UserError("Check-Out Date must be after Check-In Date. It has been adjusted accordingly.")

    # @api.constrains('checkin_date', 'checkout_date')
    # def _check_dates(self):
    #     print("Inside line 1956")
    #     for record in self:
    #         if record.checkout_date and record.checkin_date:
    #             print(record.checkout_date, record.checkin_date)
    #             if record.checkout_date <= record.checkin_date:
    #                 raise UserError(
    #                     "Check-Out Date must be greater than Check-In Date."
    #                 )

    hotel_policy = fields.Selection([("prepaid", "On Booking"),
                                     ("manual", "On Check In"),
                                     ("picking", "On Checkout"),
                                     ],
                                    default="manual", string="Hotel Policy",
                                    help="Hotel policy for payment that "
                                         "either the guest has to pay at "
                                         "booking time, check-in "
                                         "or check-out time.", tracking=True)
    duration = fields.Integer(string="Duration in Days",
                              help="Number of days which will automatically "
                                   "count from the check-in and check-out "
                                   "date.", )
    invoice_button_visible = fields.Boolean(string='Invoice Button Display',
                                            help="Invoice button will be "
                                                 "visible if this button is "
                                                 "True")
    invoice_status = fields.Selection(
        selection=[('no_invoice', 'Nothing To Invoice'),
                   ('to_invoice', 'To Invoice'),
                   ('invoiced', 'Invoiced'),
                   ], string="Invoice Status",
        help="Status of the Invoice",
        default='no_invoice', tracking=True)
    hotel_invoice_id = fields.Many2one("account.move",
                                       string="Invoice",
                                       help="Indicates the invoice",
                                       copy=False)
    duration_visible = fields.Float(string="Duration",
                                    help="A dummy field for Duration")
    need_service = fields.Boolean(default=False, string="Need Service",
                                  help="Check if a Service to be added with"
                                       " the Booking")
    need_fleet = fields.Boolean(default=False, string="Need Vehicle",
                                help="Check if a Fleet to be"
                                     " added with the Booking")
    need_food = fields.Boolean(default=False, string="Need Food",
                               help="Check if a Food to be added with"
                                    " the Booking")
    need_event = fields.Boolean(default=False, string="Need Event",
                                help="Check if a Event to be added with"
                                     " the Booking")
    service_line_ids = fields.One2many("service.booking.line",
                                       "booking_id",
                                       string="Service",
                                       help="Hotel services details provided to"
                                            "Customer and it will included in "
                                            "the main Invoice.")  #
    event_line_ids = fields.One2many("event.booking.line",
                                     'booking_id',
                                     string="Event",
                                     help="Hotel event reservation detail.")  #
    vehicle_line_ids = fields.One2many("fleet.booking.line",
                                       "booking_id",
                                       string="Vehicle",
                                       help="Hotel fleet reservation detail.")  #
    room_line_ids = fields.One2many("room.booking.line",
                                    "booking_id", string="Room",
                                    help="Hotel room reservation detail.")  #

    # @api.constrains('room_line_ids')
    # def _check_adults_and_children_names(self):
    #     """Validate that all adults and children have first and last names when room_line_ids is updated."""
    #     for booking in self:
    #         for line in booking.room_line_ids:
    #             if line.room_id:
    #                 # Check adults
    #                 for adult in booking.adult_ids:
    #                     if not adult.first_name or not adult.last_name:
    #                         raise ValidationError(
    #                             f"Adult with ID {adult.id} is missing a first name or last name. "
    #                             "Please fill in these fields before assigning a room."
    #                         )

    #                 # Check children
    #                 for child in booking.child_ids:
    #                     if not child.first_name or not child.last_name:
    #                         raise ValidationError(
    #                             f"Child with ID {child.id} is missing a first name or last name. "
    #                             "Please fill in these fields before assigning a room."
    #                         )
    food_order_line_ids = fields.One2many("food.booking.line",
                                          "booking_id",
                                          string='Food',
                                          help="Food details provided"
                                               " to Customer and"
                                               " it will included in the "
                                               "main invoice.", )  #
    state = fields.Selection(selection=[
        ('not_confirmed', 'Not Confirmed'),
        # ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('waiting', 'Waiting List'),
        ('no_show', 'No Show'),
        ('block', 'Block'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('reserved', 'Reserved')
    ], string='State', help="State of the Booking", default='not_confirmed', tracking=True)

    reservation_status_id = fields.Many2one(
        'reservation.status.code',
        string="Reservation Status",
        help="Select the reservation status for this booking."
    )

    # reservation_status_count_as = fields.Selection(
    #     related='reservation_status_id.count_as',
    #     string="Reservation Count As",
    #     readonly=True,
    #     store=True,
    #     compute='_compute_reservation_status_count_as'
    # )

    reservation_status_count_as = fields.Selection(
        selection=[
            ('not_confirmed', 'Not Confirmed'),
            ('confirmed', 'Confirmed'),
            ('wait_list', 'Wait List'),
            # ('tentative', 'Tentative'),
            ('release', 'Release'),
            ('cancelled', 'Cancelled'),
            ('other', 'Other'),
        ],
        string="Reservation Count As",
        readonly=True,
        store=True,
        compute='_compute_reservation_status_count_as', tracking=True)

    @api.depends('state', 'reservation_status_id')
    def _compute_reservation_status_count_as(self):
        """Automatically set reservation_status_count_as based on state and reservation_status_id."""
        state_mapping = {
            'not_confirmed': 'not_confirmed',
            'confirmed': 'confirmed',
            'waiting': 'wait_list',
            'block': 'confirmed',
            'no_show': 'confirmed',
            'check_in': 'confirmed',
            'check_out': 'confirmed',
            'done': 'confirmed',
            'cancel': 'cancelled',
            'reserved': 'wait_list',
        }
        for record in self:
            # First, map based on state.
            state_based_value = state_mapping.get(
                record.state, 'confirmed')  # Default to 'confirmed'

            # Then, prioritize the related reservation status if it exists.
            if record.reservation_status_id and record.reservation_status_id.count_as:
                record.reservation_status_count_as = record.reservation_status_id.count_as
            else:
                record.reservation_status_count_as = state_based_value

        # for record in self:
        #     # First, map based on state.
        #     state_based_value = state_mapping.get(record.state, 'other')

        #     # Then, prioritize the related reservation status if it exists.
        #     record.reservation_status_count_as = record.reservation_status_id.count_as or state_based_value

    @api.onchange('no_show_')
    def _onchange_no_show(self):
        """Update child room lines to 'no_show' when parent is marked as 'No Show'."""
        if self.no_show_:
            for line in self.room_line_ids:
                if line.state == 'block':
                    line.state = 'no_show'

    show_confirm_button = fields.Boolean(string="Confirm Button")
    show_cancel_button = fields.Boolean(string="Cancel Button")

    hotel_room_type = fields.Many2one(
        'room.type', string="Room Type", tracking=True)

    def action_confirm_booking(self):
        # Ensure all selected records have the same state
        states = self.mapped('state')
        if len(set(states)) > 1:
            raise ValidationError("Please select records with the same state.")

        # Ensure the state of all selected records is 'not_confirmed'
        if any(record.state != 'not_confirmed' for record in self):
            raise ValidationError(
                "Please select only records in the 'Not Confirmed' state to confirm.")

        today = fields.Date.context_today(self)
        state_changed = False  # Flag to track if any state was changed to 'confirmed'

        for booking in self:
            # if not booking.availability_results:
            #     raise ValidationError("Search Room is empty. Please search for available rooms before confirming.")
            # If the booking is a parent, process its children
            child_bookings = self.search(
                [('parent_booking_name', '=', booking.name)])

            for child in child_bookings:
                if child.state == 'not_confirmed':
                    # Call the action to split rooms
                    child.action_split_rooms()

                    # Adjust availability for each result
                    for search_result in child.availability_results:
                        search_result.available_rooms -= search_result.rooms_reserved

                    # Confirm the child booking
                    child.write({"state": "confirmed"})
                    state_changed = True
                    print(
                        f"Child Booking ID {child.id} confirmed and rooms adjusted.")

            # If the current booking is not a parent, process it directly
            if not child_bookings and booking.state == 'not_confirmed':
                # Call the action to split rooms
                booking.action_split_rooms()

                # Adjust availability for each result
                for search_result in booking.availability_results:
                    search_result.available_rooms -= search_result.rooms_reserved

                # Confirm the booking
                booking.write({"state": "confirmed"})
                state_changed = True
                print(f"Booking ID {booking.id} confirmed and rooms adjusted.")

        # Only retrieve dashboard counts and display the notification if the state changed to 'confirmed'
        if state_changed:
            dashboard_data = self.retrieve_dashboard()
            print("Updated dashboard data after confirm action:", dashboard_data)

            # Display success notification with updated dashboard data
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': "Booking Confirmed Successfully!",
                    'next': {'type': 'ir.actions.act_window_close'},
                    'dashboard_data': dashboard_data,
                }
            }
        else:
            raise ValidationError(
                _("No bookings were confirmed. Please ensure the state is 'not_confirmed' before confirming."))

    def action_no_show_tree(self):
        current_date = fields.Date.context_today(self)
        state_changed = False  # Flag to track if any state was changed to 'no_show'

        for booking in self:
            # If the booking is a parent, process its children
            child_bookings = self.search(
                [('parent_booking_name', '=', booking.name)])

            # Process child bookings
            for child in child_bookings:
                if child.state == 'block':
                    # Validate that the check-in date is today
                    if fields.Date.to_date(child.checkin_date) != current_date:
                        raise ValidationError(
                            _(f"Child Booking ID {child.id}: The 'No Show' action can only be performed on the check-in date.")
                        )

                    # Release rooms and update availability
                    for line in child.room_line_ids:
                        if line.room_id:
                            availability_result = self.env['room.availability.result'].search([
                                ('room_booking_id', '=', child.id)
                            ], limit=1)

                            if availability_result:
                                reserved_rooms = line.room_count if hasattr(
                                    line, 'room_count') else 1
                                availability_result.available_rooms += reserved_rooms
                                availability_result.rooms_reserved -= reserved_rooms

                            # Clear the room assignment
                            line.room_id = None
                            line.state = 'no_show'

                    # Remove the room lines by unlinking them
                    child.room_line_ids.unlink()
                    child.write({"state": "no_show"})
                    state_changed = True
                    print(
                        f"Child Booking ID {child.id} marked as 'No Show' and rooms released.")

            # If the current booking is not a parent, process it directly
            if not child_bookings and booking.state == 'block':
                if fields.Date.to_date(booking.checkin_date) != current_date:
                    raise ValidationError(
                        _("The 'No Show' action can only be performed on the check-in date.")
                    )

                # Release rooms and update availability
                for line in booking.room_line_ids:
                    if line.room_id:
                        availability_result = self.env['room.availability.result'].search([
                            ('room_booking_id', '=', booking.id)
                        ], limit=1)

                        if availability_result:
                            reserved_rooms = line.room_count if hasattr(
                                line, 'room_count') else 1
                            availability_result.available_rooms += reserved_rooms
                            availability_result.rooms_reserved -= reserved_rooms

                        # Clear the room assignment
                        line.room_id = None
                        line.state = 'no_show'

                # Remove the room lines by unlinking them
                booking.room_line_ids.unlink()
                booking.write({"state": "no_show"})
                state_changed = True
                print(
                    f"Booking ID {booking.id} marked as 'No Show' and rooms released.")

        # Only show the notification if any state was changed to 'no_show'
        if state_changed:
            dashboard_data = self.retrieve_dashboard()
            print("Updated dashboard data after 'No Show' action:", dashboard_data)

            # Display success notification with updated dashboard data
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': "Booking marked as 'No Show' successfully!",
                    'next': {'type': 'ir.actions.act_window_close'},
                    'dashboard_data': dashboard_data,
                }
            }
        else:
            raise ValidationError(
                _("No bookings were marked as 'No Show'. Please ensure the state is 'block' before performing this action."))

    def action_cancel_booking(self):
        # Ensure all selected records have the same state
        states = self.mapped('state')
        if len(set(states)) > 1:
            raise ValidationError("Please select records with the same state.")

        # Define allowed states for cancellation
        allowed_states = ['not_confirmed', 'confirmed', 'block']

        # Explicitly check if any record is in 'check_in' state and raise an error
        # if any(record.state == 'check_in' for record in self):
        #     raise ValidationError("You cannot cancel records that are in the 'Checkin' state.")

        if any(record.state not in allowed_states for record in self):
            raise ValidationError(
                "You are not allowed to cancel bookings in the current state.")

        today = fields.Date.context_today(self)

        for booking in self:
            # Find child bookings if the current booking is a parent
            child_bookings = self.search(
                [('parent_booking_name', '=', booking.name)])

            # Process child bookings
            for child in child_bookings:
                if child.state in allowed_states:
                    # Cancel child booking and make rooms available
                    child.write({"state": "cancel"})
                    print(f"Child Booking ID {child.id} cancelled.")

                    if child.room_line_ids:
                        for room in child.room_line_ids:
                            room.room_id.write({
                                'status': 'available',
                            })
                            room.room_id.is_room_avail = True

            # Process the current booking if it's not a parent
            if not child_bookings and booking.state in allowed_states:
                booking.write({"state": "cancel"})
                print(f"Booking ID {booking.id} cancelled.")

                if booking.room_line_ids:
                    for room in booking.room_line_ids:
                        room.room_id.write({
                            'status': 'available',
                        })
                        room.room_id.is_room_avail = True

        # Commit the transaction to ensure changes are saved immediately
        self.env.cr.commit()

        # Retrieve updated dashboard counts
        dashboard_data = self.retrieve_dashboard()
        print("Updated dashboard data after cancel action:", dashboard_data)

        # Display success notification with updated dashboard data
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': "Booking Cancelled Successfully!",
                'next': {'type': 'ir.actions.act_window_close'},
                'dashboard_data': dashboard_data,
            }
        }

    def action_checkin_booking(self):
        today = datetime.now().date()
        all_bookings = self

        for booking in all_bookings:
            if len(booking.room_line_ids) > 1:
                continue
            if booking.state != 'block':
                raise ValidationError(
                    _("All selected bookings must be in the 'block' state to proceed with check-in."))
            if booking.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot check-in  booking with a check-in date in the past."))

        future_bookings = all_bookings.filtered(
            lambda b: fields.Date.to_date(b.checkin_date) > today)

        if future_bookings:
            # Return wizard if any booking is in the future
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'booking.checkin.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_booking_ids': future_bookings.mapped('id'),
                }
            }

        # If no future bookings, continue directly
        # return self._perform_bulk_checkin(all_bookings, today)
        self._perform_bulk_checkin(all_bookings, today)
        self.env.cr.commit()

        # Update the dashboard after the function completes
        # self.retrieve_dashboard()
        # return result
        return {
            'type': 'ir.actions.act_window',
            'name': 'Room Booking',
            'res_model': 'room.booking',
            'view_mode': 'tree,form',
            'target': 'current',
        }

    def _perform_bulk_checkin(self, all_bookings, today):
        today = datetime.now()
        print("Line 1486", all_bookings)
        print("Line 1486 - Bookings to check in:", all_bookings.mapped('id'))
        state_changed = False
        for booking in all_bookings:
            print("Line 1472", booking)
            if len(booking.room_line_ids) > 1:
                continue

            room_availability = booking.check_room_availability_all_hotels_split_across_type(
                checkin_date=today,
                checkout_date=today + timedelta(days=1),
                room_count=len(booking.room_line_ids),
                adult_count=sum(booking.room_line_ids.mapped('adult_count')),
                hotel_room_type_id=booking.room_line_ids.mapped(
                    'hotel_room_type').id if booking.room_line_ids else None
            )
            print("Line 1503", room_availability)

            # Check if room_availability indicates no available rooms
            if not room_availability or isinstance(room_availability, dict):
                raise ValidationError(
                    _("No rooms are available for today's date. Please select a different date."))

            room_availability_list = room_availability[1]
            total_available_rooms = sum(
                int(res.get('available_rooms', 0)) for res in room_availability_list)

            if total_available_rooms <= 0:
                raise ValidationError(
                    _("No rooms are available for the selected date. Please select a different date."))

            # If the check-in date is today and rooms are available, proceed with check-in
            booking._perform_checkin()
            state_changed = True

        # Only retrieve dashboard counts and display notification if state changed
        if state_changed:
            dashboard_data = self.retrieve_dashboard()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': "Booking Checked In Successfully!",
                    'next': {'type': 'ir.actions.act_window_close'},
                    'dashboard_data': dashboard_data,
                }
            }
        else:
            raise ValidationError(
                _("No bookings were checked in. Please ensure the state is 'block' before checking in."))

    # working
    # def action_checkin_booking(self):
    #     today = datetime.now().date()
    #     state_changed = False  # Flag to track if any state was changed to 'check_in'

    #     for booking in self:
    #         # If the booking is a parent, process its children
    #         child_bookings = self.search([('parent_booking_name', '=', booking.name)])

    #         # Process child bookings
    #         for child in child_bookings:
    #             if child.state == 'block':
    #                 # Ensure check-in date is today
    #                 if fields.Date.to_date(child.checkin_date.date()) != today:
    #                     raise ValidationError(
    #                         _("You can only check in on the reservation's check-in date, which should be today.")
    #                     )

    #                 # Validate that room details are provided
    #                 if not child.room_line_ids:
    #                     raise ValidationError(_("Please Enter Room Details"))

    #                 # Set each room's status to 'occupied' and mark it as unavailable
    #                 for room in child.room_line_ids:
    #                     room.room_id.write({
    #                         'status': 'occupied',
    #                     })
    #                     room.room_id.is_room_avail = False

    #                 # Update the child booking state to 'check_in'
    #                 child.write({"state": "check_in"})
    #                 state_changed = True
    #                 print(f"Child Booking ID {child.id} checked in and rooms updated to occupied.")

    #         # If the current booking is not a parent, process it directly
    #         if not child_bookings and booking.state == 'block':
    #             if fields.Date.to_date(booking.checkin_date.date()) != today:
    #                 raise ValidationError(
    #                     _("You can only check in on the reservation's check-in date, which should be today.")
    #                 )

    #             if not booking.room_line_ids:
    #                 raise ValidationError(_("Please Enter Room Details"))

    #             for room in booking.room_line_ids:
    #                 room.room_id.write({
    #                     'status': 'occupied',
    #                 })
    #                 room.room_id.is_room_avail = False

    #             booking.write({"state": "check_in"})
    #             state_changed = True
    #             print(f"Booking ID {booking.id} checked in and rooms updated to occupied.")

    #     # Only retrieve dashboard counts and display the notification if the state changed to 'check_in'
    #     if state_changed:
    #         dashboard_data = self.retrieve_dashboard()
    #         print("Updated dashboard data after check-in action:", dashboard_data)

    #         # Display success notification with updated dashboard data
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'type': 'success',
    #                 'message': "Booking Checked In Successfully!",
    #                 'next': {'type': 'ir.actions.act_window_close'},
    #                 'dashboard_data': dashboard_data,
    #             }
    #         }
    #     else:
    #         # If no state was changed, do not show a success message
    #         raise ValidationError(_("No bookings were checked in. Please ensure the state is 'block' before checking in."))

    # working 14 dec
    def _perform_checkout(self):
        """Helper method to perform check-out and update room availability."""
        parent_booking_id = self.parent_booking_id.id if self.parent_booking_id else self.id
        print("Line 1727 Parent Booking ID:", parent_booking_id)

        # Loop through each room in the room_line_ids
        for room in self.room_line_ids:
            # Update room status to 'available'
            room.room_id.write({
                'status': 'available',
            })
            room.room_id.is_room_avail = True

            # Update the available rooms count and increase rooms_reserved count
            if room.room_id:
                availability_result = self.env['room.availability.result'].search([
                    ('room_booking_id', '=', parent_booking_id)
                ], limit=1)

                if availability_result:
                    # Use room count from the room line or a default value of 1
                    reserved_rooms = room.room_count if hasattr(
                        room, 'room_count') else 1

                    # Increase available_rooms and decrease rooms_reserved
                    availability_result.available_rooms += reserved_rooms
                    availability_result.rooms_reserved -= reserved_rooms

        # Update the booking state to 'check_out'
        self.write({"state": "check_out", "checkout_date": datetime.now()})

        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': "Booking Checked Out Successfully!",
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_checkout_booking(self):
        # if not self.posting_item_ids:
        #     raise ValidationError("You cannot proceed with checkout. Please add at least one Posting Item.")
        today = datetime.now().date()
        all_bookings = self

        # Filter out bookings with more than one room line
        eligible_bookings = all_bookings.filtered(
            lambda b: len(b.room_line_ids) <= 1)

        for booking in eligible_bookings:
            print("Line 1465", booking)
            if booking.state != 'check_in':
                raise ValidationError(
                    _("All selected bookings must be in the 'check_in' state to proceed with check-out."))

        created_invoices = []
        for booking in eligible_bookings:
            if not booking.room_line_ids:
                raise ValidationError(
                    _("Please enter room details for booking ID %s.") % booking.id)

            posting_item_meal, _1, _2, _3 = booking.get_meal_rates(
                booking.meal_pattern.id)
            print(f"The Posting Item Meal is: {posting_item_meal}")
            meal_price, room_price, package_price, posting_item_value, line_posting_items = booking.get_all_prices(
                booking.checkin_date, booking)
            print(f"Rate Posting Item: {posting_item_value}")
            print(f"Line Posting Items: {line_posting_items}")

            # Compute booking amounts
            booking_list = booking._compute_amount_untaxed(True)

            if booking_list:
                account_move = self.env["account.move"].create({
                    'move_type': 'out_invoice',
                    'invoice_date': today,
                    'partner_id': booking.partner_id.id,
                    'ref': booking.name,
                    'hotel_booking_id': booking.id,  # Set the current booking
                    # Group Booking Name
                    'group_booking_name': booking.group_booking.name if booking.group_booking else '',
                    'parent_booking_name': booking.parent_booking_name or '',  # Parent Booking Name
                    'room_numbers': booking.room_ids_display or '',  # Room Numbers
                })
                for posting_item in booking.posting_item_ids:
                    account_move.invoice_line_ids.create({
                        'posting_item_id': posting_item.posting_item_id.id,  # Posting item
                        'posting_description': posting_item.description,  # Description
                        'posting_default_value': posting_item.default_value,  # Default value
                        'move_id': account_move.id,  # Link to account.move
                    })

                # Add lines from filtered lines
                filtered_lines = [
                    line for line in booking.rate_forecast_ids if line.date == today]
                print(
                    f"Debug: Number of filtered rate_forecast_ids lines = {len(filtered_lines)}")

                for line in filtered_lines:
                    line_data = []

                    # Check and add Rate line if rate is available and greater than 0
                    if line.rate and line.rate > 0:
                        line_data.append({
                            'posting_item_id': posting_item_value,  # Posting item for rate
                            'posting_description': 'Rate',  # Description for rate
                            'posting_default_value': line.rate,  # Default value for rate
                            'move_id': account_move.id,
                        })

                    # Check and add Meal line if meals is available and greater than 0
                    if line.meals and line.meals > 0:
                        line_data.append({
                            'posting_item_id': posting_item_meal,  # Posting item for meal
                            'posting_description': 'Meal',  # Description for meal
                            'posting_default_value': line.meals,  # Default value for meal
                            'move_id': account_move.id,
                        })

                    # Check and add Package line if packages is available and greater than 0
                    if line.packages and line.packages > 0:
                        line_data.append({
                            # Posting item for package
                            'posting_item_id': line_posting_items[-1],
                            'posting_description': 'Package',  # Description for package
                            'posting_default_value': line.packages,  # Default value for package
                            'move_id': account_move.id,
                        })

                    # Create lines in account.move.line
                    if line_data:
                        account_move.invoice_line_ids.create(line_data)

                # for rec in booking_list:
                #     account_move.invoice_line_ids.create({
                #         'name': rec['name'],
                #         'quantity': rec['quantity'],
                #         'price_unit': rec['price_unit'],
                #         'move_id': account_move.id,
                #         'product_type': rec['product_type'],
                #     })

                # Update booking invoice status
                booking.write({'invoice_status': "invoiced"})
                booking.write({'state': "check_out"})
                booking.invoice_button_visible = True
                created_invoices.append(account_move)

        # Filter bookings with future checkout dates
        future_bookings = eligible_bookings.filtered(
            lambda b: fields.Date.to_date(b.checkout_date) > today)
        print("Line 1470", future_bookings)

        if future_bookings:
            # Return wizard if any booking has a future checkout date
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'confirm.early.checkout.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_booking_ids': future_bookings.mapped('id'),
                }
            }

        self._perform_bulk_checkout(eligible_bookings, today)

    #     return {
    #     'type': 'ir.actions.client',
    #     'tag': 'display_notification',
    #     'params': {
    #         'type': 'success',
    #         'message': _("Booking Checked Out Successfully!"),
    #         'next': {'type': 'ir.actions.act_window_close'},
    #     }
    # }

        # Update the dashboard after the function completes
        self.env.cr.commit()
        # self.retrieve_dashboard()
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Room Booking',
        #     'res_model': 'room.booking',
        #     'view_mode': 'tree,form',
        #     'target': 'current',
        # }
        # Display a success notification

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking Checked Out Successfully!"),
            },
        }, {
            'type': 'ir.actions.act_window',
            'name': 'Room Booking',
            'res_model': 'room.booking',
            'view_mode': 'tree,form',
            'target': 'current',
        }

    # Working 04/01/2025
    # def action_checkout_booking(self):
    #     # if not self.posting_item_ids:
    #     #     raise ValidationError("You cannot proceed with checkout. Please add at least one Posting Item.")
    #     today = datetime.now().date()
    #     all_bookings = self

    #     # Filter out bookings with more than one room line
    #     eligible_bookings = all_bookings.filtered(lambda b: len(b.room_line_ids) <= 1)

    #     for booking in eligible_bookings:
    #         print("Line 1465", booking)
    #         if booking.state != 'check_in':
    #             raise ValidationError(
    #                 _("All selected bookings must be in the 'check_in' state to proceed with check-out."))

    #     created_invoices = []
    #     for booking in eligible_bookings:
    #         if not booking.room_line_ids:
    #             raise ValidationError(_("Please enter room details for booking ID %s.") % booking.id)

    #         # Compute booking amounts
    #         booking_list = booking._compute_amount_untaxed(True)

    #         if booking_list:
    #             account_move = self.env["account.move"].create({
    #                 'move_type': 'out_invoice',
    #                 'invoice_date': today,
    #                 'partner_id': booking.partner_id.id,
    #                 'ref': booking.name,
    #                 'hotel_booking_id': self.id,  # Set the current booking
    #                 'group_booking_name': self.group_booking.name if self.group_booking else '',  # Group Booking Name
    #                 'parent_booking_name': self.parent_booking_name or '',  # Parent Booking Name
    #                 'room_numbers': self.room_ids_display or '',  # Room Numbers
    #             })

    #             for rec in booking_list:
    #                 account_move.invoice_line_ids.create({
    #                     'name': rec['name'],
    #                     'quantity': rec['quantity'],
    #                     'price_unit': rec['price_unit'],
    #                     'move_id': account_move.id,
    #                     'product_type': rec['product_type'],
    #                 })

    #             # Update booking invoice status
    #             booking.write({'invoice_status': "invoiced"})
    #             booking.write({'state': "check_out"})
    #             booking.invoice_button_visible = True
    #             created_invoices.append(account_move)

    #     # Filter bookings with future checkout dates
    #     future_bookings = eligible_bookings.filtered(lambda b: fields.Date.to_date(b.checkout_date) > today)
    #     print("Line 1470", future_bookings)

    #     if future_bookings:
    #         # Return wizard if any booking has a future checkout date
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'res_model': 'confirm.early.checkout.wizard',
    #             'view_mode': 'form',
    #             'target': 'new',
    #             'context': {
    #                 'default_booking_ids': future_bookings.mapped('id'),
    #             }
    #         }
    #     # Create invoices for eligible bookings

    #     # if created_invoices:
    #     #     return {
    #     #         'type': 'ir.actions.act_window',
    #     #         'name': 'Invoices',
    #     #         'view_mode': 'form',
    #     #         'view_type': 'form',
    #     #         'res_model': 'account.move',
    #     #         'view_id': self.env.ref('account.view_move_form').id,
    #     #         'res_id': created_invoices[0].id,
    #     #         'context': "{'create': False}"
    #     #     }

    #     # If no future bookings, continue directly with checkout
    #     # return self._perform_bulk_checkout(eligible_bookings, today)
    #     self._perform_bulk_checkout(eligible_bookings, today)

    #     # Update the dashboard after the function completes
    #     self.env.cr.commit()
    #     # self.retrieve_dashboard()
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Room Booking',
    #         'res_model': 'room.booking',
    #         'view_mode': 'tree,form',
    #         'target': 'current',
    #     }

    def _perform_bulk_checkout(self, all_bookings, today):
        print("Line 1486 - Bookings to check out:", all_bookings.mapped('id'))
        state_changed = False

        for booking in all_bookings:
            print("Line 1472", booking)
            if len(booking.room_line_ids) > 1:
                continue

            booking._perform_checkout()
            state_changed = True

        # Display notification if any state changed
        if state_changed:
            dashboard_data = self.retrieve_dashboard()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': "Booking Checked Out Successfully!",
                    'next': {'type': 'ir.actions.act_window_close'},
                    'dashboard_data': dashboard_data,
                }
            }
        else:
            raise ValidationError(
                _("No bookings were checked out. Please ensure the state is 'check_in' before checking out."))

    # working 14 dec
    # def action_checkout_booking(self):
    #     today = datetime.now().date()
    #     state_changed = False  # Flag to track if any state was changed to 'check_out'

    #     # Ensure all selected bookings are in the 'check_in' state
    #     for booking in self:
    #         if len(booking.room_line_ids) > 1:
    #             continue
    #         if booking.state != 'check_in':
    #             raise ValidationError(_("All selected bookings must be in the 'check_in' state to proceed with check-out."))

    #         booking._perform_checkout()
    #         state_changed = True

    #     if state_changed:
    #         # If checkout performed directly (no wizard needed)
    #         dashboard_data = self.retrieve_dashboard()
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'type': 'success',
    #                 'message': "Booking Checked Out Successfully!",
    #                 'next': {'type': 'ir.actions.act_window_close'},
    #                 'dashboard_data': dashboard_data,
    #             }
    #         }

    # working
    # def action_checkout_booking(self):
    #     today = datetime.now().date()
    #     state_changed = False  # Flag to track if any state was changed to 'check_out'

    #     for booking in self:
    #         # If the booking is a parent, process its children
    #         child_bookings = self.search([('parent_booking_name', '=', booking.name)])

    #         # Process child bookings
    #         for child in child_bookings:
    #             if child.state == 'check_in':
    #                 # Validate that today's date matches the child's checkout date
    #                 if child.checkout_date.date() != today:
    #                     raise ValidationError(
    #                         _("You can only check out on the reservation's check-out date, which should be today.")
    #                     )

    #                 # Update child booking state to 'check_out'
    #                 child.write({"state": "check_out"})

    #                 # Set each room's status to 'available' and mark it as available
    #                 for room in child.room_line_ids:
    #                     room.room_id.write({
    #                         'status': 'available',
    #                         'is_room_avail': True
    #                     })
    #                     # Update the checkout date to today's date for each room
    #                     room.write({'checkout_date': fields.Datetime.now()})

    #                 state_changed = True
    #                 print(f"Child Booking ID {child.id} checked out and rooms updated to available.")

    #         # If the current booking is not a parent, process it directly
    #         if not child_bookings and booking.state == 'check_in':
    #             # Validate that today's date matches the booking's checkout date
    #             if booking.checkout_date.date() != today:
    #                 raise ValidationError(
    #                     _("You can only check out on the reservation's check-out date, which should be today.")
    #                 )

    #             # Update booking state to 'check_out'
    #             booking.write({"state": "check_out"})

    #             # Set each room's status to 'available' and mark it as available
    #             for room in booking.room_line_ids:
    #                 room.room_id.write({
    #                     'status': 'available',
    #                     'is_room_avail': True
    #                 })
    #                 # Update the checkout date to today's date for each room
    #                 room.write({'checkout_date': fields.Datetime.now()})

    #             state_changed = True
    #             print(f"Booking ID {booking.id} checked out and rooms updated to available.")

    #     # Only retrieve dashboard counts and display the notification if the state changed to 'check_out'
    #     if state_changed:
    #         dashboard_data = self.retrieve_dashboard()
    #         print("Updated dashboard data after check-out action:", dashboard_data)

    #         # Display success notification with updated dashboard data
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'type': 'success',
    #                 'message': _("Booking Checked Out Successfully!"),
    #                 'next': {'type': 'ir.actions.act_window_close'},
    #                 'dashboard_data': dashboard_data,
    #             }
    #         }
    #     else:
    #         # If no state was changed, do not show a success message
    #         raise ValidationError(_("No bookings were checked out. Please ensure the state is 'check_in' before checking out."))

    visible_states = fields.Char(compute='_compute_visible_states')

    @api.depends('state')
    def _compute_visible_states(self):
        for record in self:
            if record.state == 'not_confirmed':
                record.visible_states = 'not_confirmed,confirmed,cancel'
            elif record.state == 'confirmed':
                record.visible_states = 'confirmed,check_in,check_out,no_show'
            else:
                record.visible_states = 'not_confirmed,confirmed,waiting,no_show,block,check_in,check_out,done'

    room_type_name = fields.Many2one('room.type', string='Room Type')

    def action_unconfirm(self):
        """Set the booking back to 'not_confirmed' state from 'confirmed' or 'block'"""
        for record in self:
            if record.state in ['block', 'confirmed', 'waiting', 'cancel']:
                record.state = 'not_confirmed'

    # def action_confirm(self):
    #      for record in self:
    #         record.state = 'confirmed'

    def action_confirm(self):
        today = datetime.now().date()
        for record in self:
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot confirm a booking with a check-in date in the past."))

            if not record.parent_booking_name:
                if not record.availability_results:
                    raise ValidationError(
                        "Search Room is empty. Please search for available rooms before confirming.")
            # if not record.availability_results:
            #     raise ValidationError("Search Room is empty. Please search for available rooms before confirming.")

            if not record.room_line_ids:
                record.action_split_rooms()

            # 4) Check if there is any line in block state
            block_line = record.room_line_ids.filtered(
                lambda l: l.state_ == 'block')
            if block_line:
                # Open wizard for the first line in block
                return {
                    'name': _("Confirm Booking"),
                    'type': 'ir.actions.act_window',
                    'res_model': 'confirm.booking.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_message': _(
                            "Room number will be released."
                            "Do you want to proceed?"
                        ),
                        'default_line_id': block_line[0].id,
                        'default_booking_id': record.id,
                    },
                }

            # 5) If we reached here, there is NO line in block state => we can confirm now
            record.state = "confirmed"

            # 6) Adjust availability
            for search_result in record.availability_results:
                search_result.available_rooms -= search_result.rooms_reserved

        return True

        # record.state = "confirmed"

        # for search_result in record.availability_results:
        #     search_result.available_rooms -= search_result.rooms_reserved

        # for line in record.room_line_ids:
        #     line.room_id = False
        #     line.state_ = 'confirmed'
        # for line in record.room_line_ids:
        #     return {
        #         'name': _("Confirm Booking"),
        #         'type': 'ir.actions.act_window',
        #         'res_model': 'confirm.booking.wizard',
        #         'view_mode': 'form',
        #         'target': 'new',
        #         'context': {
        #             'default_message': _("Room ID will be deleted for the line in 'block' state. Do you want to proceed?"),
        #             'default_line_id': line.id,
        #             'default_booking_id': record.id,
        #         },
        #     }
        # line.room_id = False
        # line.state_ = 'confirmed'

    def action_waiting(self):
        today = datetime.now().date()
        for record in self:
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot sent a booking to Waiting List with a check-in date in the past."))
            if not record.availability_results:
                raise UserError(
                    "You have to Search room first then you can Send to Waiting List.")
            record.state = 'waiting'

    # The above code snippet is a Python method that seems to be part of a larger system or application.
    # Here is a breakdown of what the code is doing:
    def no_show(self):
        for record in self:
            # Get room lines associated with the booking
            room_lines = self.env['room.booking.line'].search(
                [('booking_id', '=', record.id)])
            current_date = datetime.now().date()
            checkin_date = record.checkin_date.date()

            # Validate the action date
            if checkin_date != current_date:
                raise UserError(
                    "The 'No Show' action can only be performed on the current check-in date.")

            print("Current Record ID:", record.id)

            # Get the parent booking ID
            parent_booking_id = record.parent_booking_id.id if record.parent_booking_id else record.id
            print("Parent Booking ID:", parent_booking_id)

            # Release rooms and update inventory
            if room_lines:
                for line in room_lines:
                    if line.room_id:
                        print("Processing Room Line ID:", line.id)

                        # Update the available rooms count and reduce rooms_reserved count
                        availability_result = self.env['room.availability.result'].search([
                            ('room_booking_id', '=', parent_booking_id)
                        ], limit=1)

                        print("Availability Result:", availability_result)

                        if availability_result:
                            # Use room count from the room line or a calculated value
                            reserved_rooms = line.room_count if hasattr(
                                line, 'room_count') else 1

                            # Increase available_rooms and decrease rooms_reserved
                            availability_result.available_rooms += reserved_rooms
                            availability_result.rooms_reserved -= reserved_rooms

                        # Clear the room assignment
                        line.room_id = None
                        line.state = 'no_show'

            # Update the booking state
            record.state = 'no_show'

    #     def no_show(self):
    #         for record in self:
    #             # print(record)
    #             room_lines = self.env['room.booking.line'].search([('booking_id', '=', record.id)])
    #             print("room_lines", room_lines)
    #             current_date = datetime.now().date()
    #             checkin_date = record.checkin_date.date()
    #
    #             # Log the IDs of the records found
    #             print(f"Found room line records: {room_lines.ids}")
    #             if checkin_date != current_date:
    #                 raise UserError("The 'No Show' action can only be performed on the current check-in date.")
    #
    #             if room_lines:
    #                 room_lines.room_id = None
    #                 room_lines.room_id = None
    #                 room_lines.state = 'no_show'
    #                 # if record.availability_results:
    #                 #     record.availability_results.available_rooms += record.room_count
    #                 # # room_lines.unlink()
    #                 # else:
    #                 #     room_avail = self.env['room.availability.result'].search(
    #                 #         [('room_booking_id', '=', record.parent_booking_id.id)])
    #                 #     if room_avail:
    #                 #         room_avail.available_rooms += record.room_count
    #
    #             record.state = 'no_show'

    # def no_show(self):
    #     for record in self:
    #         # Validate the action for the current date
    #         current_date = fields.Date.today()
    #         if record.checkin_date.date() != current_date:
    #             raise UserError("The 'No Show' action can only be performed on the current check-in date.")

    #         # Find related room booking lines
    #         room_lines = self.env['room.booking.line'].search([('booking_id', '=', record.id)])
    #         print("ROOM LINES", room_lines)
    #         if room_lines:
    #             # Reset room assignment and mark the lines as 'no_show'
    #             room_lines.write({'room_id': False, 'state': 'no_show'})

    #             # Update room availability
    #             room_avail = self.env['room.availability.result'].search([
    #                 ('room_booking_id', '=', record.id),
    #                 # ('room_type', '=', record.hotel_room_type.id)
    #                 # ('availability_date', '=', current_date)
    #             ])
    #             print("ROOM AVAIL", room_avail)
    #             if room_avail:
    #                 # Increment the count of available rooms
    #                 room_avail.sudo().write({'available_rooms': room_avail.available_rooms + record.room_count})
    #                 print(f"Updated availability: {room_avail.available_rooms} for room_type {record.hotel_room_type} on {current_date}")
    #             else:
    #                 print(f"No availability record found for room_type {record.hotel_room_type} on {current_date}")

    #         # Update the booking state
    #         record.write({'state': 'no_show'})

    # def no_show(self):
    #     for record in self:
    #         current_date = datetime.now().date()
    #         checkin_date = record.checkin_date.date()

    #         if checkin_date != current_date:
    #             raise UserError("The 'No Show' action can only be performed on the current check-in date.")

    #         # record.state = 'no_show'

    #         for room_line in record.room_line_ids:
    #             room_line.unlink()

    #         record.state = 'no_show'

    def action_make_reservation(self):
        """Method called by the button to make a reservation and check its status."""
        for record in self:
            # Ensure that only one record is being processed (optional)
            # record.ensure_one()

            # Get necessary data from the current record
            partner_id = record.partner_id.id
            checkin_date = record.checkin_date
            checkout_date = record.checkout_date
            room_type_id = record.room_type_name.id
            num_rooms = record.room_count
            print(partner_id, checkin_date,
                  checkout_date, room_type_id, num_rooms)

            try:
                # Call the make_reservation method
                record.make_reservation(
                    partner_id=partner_id,
                    checkin_date=checkin_date,
                    checkout_date=checkout_date,
                    room_type_id=room_type_id,
                    num_rooms=num_rooms
                )
                # Update state and notify user
                record.state = 'confirmed'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Reservation Confirmed',
                        'message': 'Your reservation has been successfully confirmed.',
                        'sticky': False,
                    }
                }
            except exceptions.UserError as e:
                # Handle reservation failure
                record.state = 'waiting'  # Optionally set state to waiting
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Reservation Failed',
                        'message': str(e),
                        'sticky': False,
                    }
                }

    @api.model
    def make_reservation(self, partner_id, checkin_date, checkout_date, room_type_id, num_rooms):
        checkin_date = fields.Datetime.to_datetime(checkin_date)
        checkout_date = fields.Datetime.to_datetime(checkout_date)

        # Step 1: Check room availability
        available_rooms = self._get_available_rooms(
            checkin_date, checkout_date, room_type_id, num_rooms, False)

        if available_rooms and len(available_rooms) >= num_rooms:
            # Step 2: Create booking lines for each room
            for room in available_rooms[:num_rooms]:
                self.env['room.booking.line'].create({
                    'booking_id': self.id,
                    'room_id': room.id,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                })
            # Set state to 'confirmed'
            self.state = 'confirmed'
            return self
        else:
            # Step 3: Add to waiting list
            self.env['room.waiting.list'].create({
                'partner_id': partner_id,
                'checkin_date': checkin_date,
                'checkout_date': checkout_date,
                'room_type_id': room_type_id,
                'num_rooms': num_rooms,
            })
            # Step 4: Set state to 'waiting' and inform the user
            self.state = 'waiting'
            self.message_post(
                body='No rooms available for the selected dates. The reservation has been added to the waiting list.')
            return self

    def _get_available_rooms(self, checkin_date, checkout_date, room_type_id, num_rooms, is_api):
        # Get all rooms of the specified type
        rooms = self.env['hotel.room'].search([
            ('room_type_name', '=', room_type_id),
        ])

        available_rooms = []
        for room in rooms:
            # Check for overlapping bookings
            overlapping_bookings = self.env['room.booking.line'].search([
                ('room_id', '=', room.id),
                ('booking_id.state', 'in', ['confirmed']),
                ('checkin_date', '<', checkout_date),
                ('checkout_date', '>', checkin_date),
            ])
            if not overlapping_bookings:
                available_rooms.append(room)
                if not is_api:
                    if len(available_rooms) >= num_rooms:
                        break
        return available_rooms

    def get_available_rooms_for_hotel_api(self, checkin_date, checkout_date, room_type_id, num_rooms, is_api, hotel_id):
        # Get all rooms of the specified type
        rooms = self.env['hotel.room'].search([
            ('room_type_name', '=', room_type_id),
        ])

        available_rooms = []
        for room in rooms:
            # Check for overlapping bookings
            overlapping_bookings = self.env['room.booking.line'].search([
                ('room_id', '=', room.id),
                ('booking_id.state', 'in', ['confirmed']),
                ('booking_id.company_id', '=', hotel_id),
                ('checkin_date', '<', checkout_date),
                ('checkout_date', '>', checkin_date),
            ])
            if not overlapping_bookings:
                available_rooms.append(room)
                if not is_api:
                    if len(available_rooms) >= num_rooms:
                        break
        return available_rooms

    def get_available_rooms_for_api(self, checkin_date, checkout_date, room_type_id, num_rooms, is_api, pax, hotel_id):
        # Get all rooms of the specified type
        rooms = self.env['hotel.room'].search([
            ('room_type_name', '=', room_type_id),
            # ('num_person', '>=', pax),
            ('num_person', '=', pax),
        ])

        available_rooms = []
        for room in rooms:
            # Check for overlapping bookings
            overlapping_bookings = self.env['room.booking.line'].search([
                ('room_id', '=', room.id),
                ('booking_id.state', 'in', ['confirmed']),
                ('booking_id.company_id', '=', hotel_id),
                ('checkin_date', '<', checkout_date),
                ('checkout_date', '>', checkin_date),
            ])
            if not overlapping_bookings:
                available_rooms.append(room)
                if not is_api:
                    if len(available_rooms) >= num_rooms:
                        break
        return available_rooms

    user_id = fields.Many2one(comodel_name='res.partner',
                              string="Address",
                              compute='_compute_user_id',
                              help="Sets the User automatically",
                              required=True,
                              domain="['|', ('company_id', '=', False), "
                                     "('company_id', '=',"
                                     " company_id)]")

    pricelist_id = fields.Many2one(comodel_name='product.pricelist',
                                   string="Pricelist",
                                   compute='_compute_pricelist_id',
                                   store=True, readonly=False,
                                   tracking=1,
                                   help="If you change the pricelist,"
                                        " only newly added lines"
                                        " will be affected.")

    currency_id = fields.Many2one(
        string="Currency", help="This is the Currency used",
        related='pricelist_id.currency_id',
        depends=['pricelist_id.currency_id'],
        tracking=True
    )

    invoice_count = fields.Integer(compute='_compute_invoice_count',
                                   string="Invoice "
                                          "Count",
                                   help="The number of invoices created", tracking=True)

    account_move = fields.Integer(string='Invoice Id',
                                  help="Id of the invoice created")
    amount_untaxed = fields.Monetary(string="Total Untaxed Amount",
                                     help="This indicates the total untaxed "
                                          "amount", store=True,
                                     compute='_compute_amount_untaxed',
                                     tracking=5)
    amount_tax = fields.Monetary(string="Taxes", help="Total Tax Amount",
                                 store=True, compute='_compute_amount_untaxed')
    amount_total = fields.Monetary(string="Total", store=True,
                                   help="The total Amount including Tax",
                                   compute='_compute_amount_untaxed',
                                   tracking=4)
    amount_untaxed_room = fields.Monetary(string="Room Untaxed",
                                          help="Untaxed Amount for Room",
                                          compute='_compute_amount_untaxed',
                                          tracking=5)
    amount_untaxed_food = fields.Monetary(string="Food Untaxed",
                                          help="Untaxed Amount for Food",
                                          compute='_compute_amount_untaxed',
                                          tracking=5)
    amount_untaxed_event = fields.Monetary(string="Event Untaxed",
                                           help="Untaxed Amount for Event",
                                           compute='_compute_amount_untaxed',
                                           tracking=5)
    amount_untaxed_service = fields.Monetary(
        string="Service Untaxed", help="Untaxed Amount for Service",
        compute='_compute_amount_untaxed', tracking=5)
    amount_untaxed_fleet = fields.Monetary(string="Amount Untaxed",
                                           help="Untaxed amount for Fleet",
                                           compute='_compute_amount_untaxed',
                                           tracking=5)
    amount_taxed_room = fields.Monetary(string="Rom Tax", help="Tax for Room",
                                        compute='_compute_amount_untaxed',
                                        tracking=5)
    amount_taxed_food = fields.Monetary(string="Food Tax", help="Tax for Food",
                                        compute='_compute_amount_untaxed',
                                        tracking=5)
    amount_taxed_event = fields.Monetary(string="Event Tax",
                                         help="Tax for Event",
                                         compute='_compute_amount_untaxed',
                                         tracking=5)
    amount_taxed_service = fields.Monetary(string="Service Tax",
                                           compute='_compute_amount_untaxed',
                                           help="Tax for Service", tracking=5)
    amount_taxed_fleet = fields.Monetary(string="Fleet Tax",
                                         compute='_compute_amount_untaxed',
                                         help="Tax for Fleet", tracking=5)
    amount_total_room = fields.Monetary(string="Total Amount for Room",
                                        compute='_compute_amount_untaxed',
                                        help="This is the Total Amount for "
                                             "Room", tracking=5)
    amount_total_food = fields.Monetary(string="Total Amount for Food",
                                        compute='_compute_amount_untaxed',
                                        help="This is the Total Amount for "
                                             "Food", tracking=5)
    amount_total_event = fields.Monetary(string="Total Amount for Event",
                                         compute='_compute_amount_untaxed',
                                         help="This is the Total Amount for "
                                              "Event", tracking=5)
    amount_total_service = fields.Monetary(string="Total Amount for Service",
                                           compute='_compute_amount_untaxed',
                                           help="This is the Total Amount for "
                                                "Service", tracking=5)
    amount_total_fleet = fields.Monetary(string="Total Amount for Fleet",
                                         compute='_compute_amount_untaxed',
                                         help="This is the Total Amount for "
                                              "Fleet", tracking=5)

    passport = fields.Char(string='Passport', tracking=True)
    nationality = fields.Many2one(
        'res.country', string='Nationality', tracking=True, required=True)
    source_of_business = fields.Many2one(
        'source.business', string='Source of Business', tracking=True, required=True)
    market_segment = fields.Many2one(
        'market.segment', string='Market Segment', tracking=True, required=True)

    rate_details = fields.One2many(
        'room.type.specific.rate', compute="_compute_rate_details", string="Rate Details")
    # rate_details = fields.One2many('rate.detail', compute="_compute_rate_details", string="Rate Details")
    rate_code = fields.Many2one('rate.code', string='Rate Code', tracking=True, required=True)

    monday_pax_1 = fields.Float(string="Monday (1 Pax)", tracking=True)

    # Fields for all weekdays and pax counts
    monday_pax_1_rb = fields.Float(string="Monday (1 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    monday_pax_2_rb = fields.Float(string="Monday (2 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    monday_pax_3_rb = fields.Float(string="Monday (3 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    monday_pax_4_rb = fields.Float(string="Monday (4 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    monday_pax_5_rb = fields.Float(string="Monday (5 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    monday_pax_6_rb = fields.Float(string="Monday (6 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    tuesday_pax_1_rb = fields.Float(string="Tuesday (1 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_2_rb = fields.Float(string="Tuesday (2 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_3_rb = fields.Float(string="Tuesday (3 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_4_rb = fields.Float(string="Tuesday (4 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_5_rb = fields.Float(string="Tuesday (5 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_6_rb = fields.Float(string="Tuesday (6 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    wednesday_pax_1_rb = fields.Float(string="Wednesday (1 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_2_rb = fields.Float(string="Wednesday (2 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_3_rb = fields.Float(string="Wednesday (3 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_4_rb = fields.Float(string="Wednesday (4 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_5_rb = fields.Float(string="Wednesday (5 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_6_rb = fields.Float(string="Wednesday (6 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    thursday_pax_1_rb = fields.Float(string="Thursday (1 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_2_rb = fields.Float(string="Thursday (2 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_3_rb = fields.Float(string="Thursday (3 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_4_rb = fields.Float(string="Thursday (4 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_5_rb = fields.Float(string="Thursday (5 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_6_rb = fields.Float(string="Thursday (6 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    friday_pax_1_rb = fields.Float(string="Friday (1 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_2_rb = fields.Float(string="Friday (2 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_3_rb = fields.Float(string="Friday (3 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_4_rb = fields.Float(string="Friday (4 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_5_rb = fields.Float(string="Friday (5 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_6_rb = fields.Float(string="Friday (6 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    saturday_pax_1_rb = fields.Float(string="Saturday (1 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_2_rb = fields.Float(string="Saturday (2 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_3_rb = fields.Float(string="Saturday (3 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_4_rb = fields.Float(string="Saturday (4 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_5_rb = fields.Float(string="Saturday (5 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_6_rb = fields.Float(string="Saturday (6 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    sunday_pax_1_rb = fields.Float(string="Sunday (1 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_2_rb = fields.Float(string="Sunday (2 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_3_rb = fields.Float(string="Sunday (3 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_4_rb = fields.Float(string="Sunday (4 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_5_rb = fields.Float(string="Sunday (5 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_6_rb = fields.Float(string="Sunday (6 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)

    pax_1_rb = fields.Float(string="Default (1 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_2_rb = fields.Float(string="Default (2 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_3_rb = fields.Float(string="Default (3 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_4_rb = fields.Float(string="Default (4 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_5_rb = fields.Float(string="Default (5 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_6_rb = fields.Float(string="Default (6 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)

    @api.onchange('hotel_room_type')
    def _onchange_hotel_room_type(self):
        for record in self:
            # Define the days variable at the beginning to ensure it is always accessible
            days = ["monday", "tuesday", "wednesday",
                    "thursday", "friday", "saturday", "sunday"]

            # Clear rate code and pax fields if no hotel room type is selected
            if not record.hotel_room_type:
                record.rate_code = False
                for day in days:
                    for pax in range(1, 7):
                        setattr(record, f"{day}_pax_{pax}_rb", 0.0)
                return

            # Attempt to find rate details in room.type.specific.rate
            specific_rate_detail = self.env['room.type.specific.rate'].search([
                ('room_type_id', '=', record.hotel_room_type.id)
            ], limit=1)

            # Check if specific rate detail exists and has non-zero values
            use_specific_rate = False
            if specific_rate_detail:
                # Check if any pax rate for any day is greater than 0.0
                for day in days:
                    for pax in range(1, 7):
                        field_name = f"room_type_{day}_pax_{pax}"
                        if getattr(specific_rate_detail, field_name, 0.0) > 0.0:
                            use_specific_rate = True
                            break
                    if use_specific_rate:
                        break

            if use_specific_rate:
                # Use room.type.specific.rate data if any pax rate is non-zero
                record.rate_code = specific_rate_detail.rate_code_id
                for day in days:
                    for pax in range(1, 7):
                        field_name = f"room_type_{day}_pax_{pax}"
                        rb_field_name = f"{day}_pax_{pax}_rb"
                        value = getattr(specific_rate_detail, field_name, 0.0)
                        setattr(record, rb_field_name, value)

                # Update rate_details field to reflect specific rate detail
                record.update({
                    'rate_details': [(6, 0, specific_rate_detail.ids)]
                })
            else:
                # Fallback to rate.detail if all values in room.type.specific.rate are 0.0
                general_rate_detail = self.env['rate.detail'].search([
                    ('rate_code_id', '=', record.rate_code.id)
                ], limit=1)

                # Set rate code from general rate detail if available
                record.rate_code = general_rate_detail.rate_code_id if general_rate_detail else False

                # Assign values from rate.detail to RoomBooking fields
                if general_rate_detail:
                    for day in days:
                        for pax in range(1, 7):
                            field_name = f"{day}_pax_{pax}"
                            rb_field_name = f"{day}_pax_{pax}_rb"
                            value = getattr(
                                general_rate_detail, field_name, 0.0)
                            setattr(record, rb_field_name, value)

                    # Update rate_details field with the general rate detail data
                    record.update({
                        'rate_details': [(6, 0, general_rate_detail.ids)]
                    })
                else:
                    # If no data is found in either model, clear the fields
                    record.rate_code = False
                    for day in days:
                        for pax in range(1, 7):
                            setattr(record, f"{day}_pax_{pax}_rb", 0.0)

    # @api.onchange('hotel_room_type')
    # def _onchange_hotel_room_type(self):
    #     for record in self:
    #         # Clear rate code and pax fields if no hotel room type is selected
    #         if not record.hotel_room_type:
    #             record.rate_code = False
    #             for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
    #                 for pax in range(1, 7):
    #                     setattr(record, f"{day}_pax_{pax}_rb", 0.0)
    #             return

    #         # Find the related rate detail for the selected room type
    #         rate_detail = self.env['room.type.specific.rate'].search([
    #             ('room_type_id', '=', record.hotel_room_type.id)
    #         ], limit=1)

    #         # Set the rate code if found
    #         record.rate_code = rate_detail.rate_code_id if rate_detail else False

    #         # Assign the specific pax values from the rate detail to the fields in RoomBooking
    #         if rate_detail:
    #             days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    #             for day in days:
    #                 for pax in range(1, 7):
    #                     field_name = f"room_type_{day}_pax_{pax}"
    #                     rb_field_name = f"{day}_pax_{pax}_rb"
    #                     value = getattr(rate_detail, field_name, 0.0)
    #                     setattr(record, rb_field_name, value)

    @api.onchange('rate_code')
    def _onchange_rate_code(self):
        for record in self:
            # Initialize default values for all weekdays and pax counts
            weekdays = ["monday", "tuesday", "wednesday",
                        "thursday", "friday", "saturday", "sunday"]
            for day in weekdays:
                for pax in range(1, 7):
                    setattr(record, f"{day}_pax_{pax}_rb", 0.0)
            for pax in range(1, 7):
                setattr(record, f"pax_{pax}_rb", 0.0)

            # Check if rate_code and rate_detail exist
            if record.rate_code and record.rate_code.rate_detail_ids:

                # Assign the value from the first rate_detail in rate_detail_ids
                # Get the first rate_detail if it exists
                rate_detail = record.rate_code.rate_detail_ids[0]

                # Assign the values from rate_detail to weekday fields
                for day in weekdays:
                    for pax in range(1, 7):
                        field_name = f"{day}_pax_{pax}"
                        rb_field_name = f"{day}_pax_{pax}_rb"
                        value = getattr(rate_detail, field_name, 0.0) if getattr(
                            rate_detail, field_name, 0.0) else 0.0
                        setattr(record, rb_field_name, value)

                # Assign the values from rate_detail to default pax fields
                for pax in range(1, 7):
                    field_name = f"pax_{pax}"
                    rb_field_name = f"pax_{pax}_rb"
                    value = getattr(rate_detail, field_name, 0.0) if getattr(
                        rate_detail, field_name, 0.0) else 0.0
                    setattr(record, rb_field_name, value)

    @api.depends('rate_code')
    def _compute_rate_details_(self):
        for record in self:
            # Initialize default value for monday_pax_1 field
            record.monday_pax_1 = 0.0

            # Check if rate_code and rate_detail exist
            if record.rate_code and record.rate_code.rate_detail_ids:
                rate_detail = record.rate_code.rate_detail_ids.filtered(
                    lambda r: r.monday_pax_1 is not None)  # Filter rate_details with non-None values
                if rate_detail:
                    record.monday_pax_1 = rate_detail[0].monday_pax_1

    id_number = fields.Char(string='ID Number')
    house_use = fields.Boolean(string='House Use')

    @api.depends('rate_code')
    def _compute_rate_details_(self):
        pass

    is_customer_company = fields.Boolean(
        string="Filter Company Customers", default=False)  # New helper field

    @api.model
    def name_get(self):
        res = super(RoomBooking, self).name_get()
        for partner in self.env['res.partner'].search([]):
            print(
                f"Partner Name: {partner.name}, is_company: {partner.is_company}")
        return res

    vip = fields.Boolean(string='VIP')
    vip_code = fields.Many2one('vip.code', string="VIP Code")
    show_vip_code = fields.Boolean(
        string="Show VIP Code", compute="_compute_show_vip_code", store=True)

    complementary = fields.Boolean(string='Complementary')
    complementary_codes = fields.Many2one(
        'complimentary.code', string='Complementary Code')
    show_complementary_code = fields.Boolean(string="Show Complementary Code", compute="_compute_show_codes",
                                             store=True)

    house_use = fields.Boolean(string='House Use')
    house_use_codes = fields.Many2one('house.code', string='House Use Code')
    show_house_use_code = fields.Boolean(
        string="Show Complementary Code", compute="_compute_show_codes", store=True)

    @api.depends('vip', 'complementary', 'house_use')
    def _compute_show_codes(self):
        for record in self:
            record.show_vip_code = record.vip
            record.show_complementary_code = record.complementary
            record.show_house_use_code = record.house_use

    @api.onchange('vip', 'complementary', 'house_use')
    def _onchange_codes(self):
        if not self.vip:
            self.vip_code = False  # Clear vip_code when VIP is unchecked
        if not self.complementary:
            self.complementary_codes = False
        if not self.house_use:
            self.house_use_codes = False

    # @api.constrains('vip', 'complementary', 'house_use', 'vip_code', 'complementary_codes', 'house_use_codes')
    # def _check_required_codes(self):
    #     # Skip validation in these cases
    #     if (self.env.context.get('skip_code_validation') or
    #         self._context.get('skip_code_validation') or
    #         self.env.context.get('no_validation')):
    #         return

    #     for record in self:
    #         # Also check context at record level
    #         if (record.env.context.get('skip_code_validation') or
    #             record._context.get('skip_code_validation')):
    #             continue

    #         if record.vip and not record.vip_code:
    #             raise ValidationError(_("Please select a VIP Code when VIP is checked."))
    #         if record.complementary and not record.complementary_codes:
    #             raise ValidationError(_("Please select a Complementary Code when Complementary is checked."))
    #         if record.house_use and not record.house_use_codes:
    #             raise ValidationError(_("Please select a House Use Code when House Use is checked."))

    # @api.constrains('vip', 'complementary', 'house_use', 'vip_code', 'complementary_codes', 'house_use_codes')
    # def _check_required_codes(self):
    #     if self.env.context.get('skip_code_validation'):
    #         return
    #     if self.env.context.get('no_validation'):
    #         return
    #     for record in self:
    #         if record.vip and not record.vip_code:
    #             raise ValidationError(_("Please select a VIP Code when VIP is checked."))
    #         if record.complementary and not record.complementary_codes:
    #             raise ValidationError(_("Please select a Complementary Code when Complementary is checked."))
    #         if record.house_use and not record.house_use_codes:
    #             raise ValidationError(_("Please select a House Use Code when House Use is checked."))

    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('prepaid_credit', 'Pre-Paid / Credit Limit'),
        ('credit_limit', 'Credit Limit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment')
    ], string='Payment Type')

    def unlink(self):
        for rec in self:
            if rec.state != 'cancel' and rec.state != 'draft':
                raise ValidationError(
                    'Cannot delete the Booking. Cancel the Booking ')
        return super().unlink()

    rooms_searched = fields.Boolean(
        string="Rooms Searched",
        default=False,
        store=True,
        copy=False,
        help="Indicates whether rooms have been searched for this booking.")

    @api.model
    def create(self, vals_list):
        self.check_room_meal_validation(vals_list, False)
        # print('2427', vals_list)
        # if 'state' not in vals_list:
        #     vals_list['state'] = 'not_confirmed'
        # vals_list['previous_state'] = vals_list.get('state', 'not_confirmed')
        # self._onchange_price_discount()
        if 'checkin_date' in vals_list and 'checkout_date' in vals_list:
            checkin_date = fields.Date.from_string(vals_list['checkin_date'])
            checkout_date = fields.Date.from_string(vals_list['checkout_date'])
            if checkin_date and checkout_date:
                delta = (checkout_date - checkin_date).days
                if delta > 999:
                    raise ValidationError(
                        "Number of nights cannot exceed 999. Please adjust the check-in or check-out dates.")
                # Ensure no_of_nights is set correctly in vals
                vals_list['no_of_nights'] = delta

        if 'room_count' in vals_list and vals_list['room_count'] <= 0:
            raise ValidationError(
                "Room count cannot be zero or less. Please select at least one room.")

        if 'adult_count' in vals_list and vals_list['adult_count'] <= 0:
            raise ValidationError(
                "Adult count cannot be zero or less. Please select at least one adult.")

        if 'child_count' in vals_list and vals_list['child_count'] < 0:
            raise ValidationError("Child count cannot be less than zero.")

        if 'infant_count' in vals_list and vals_list['infant_count'] < 0:
            raise ValidationError("Infant count cannot be less than zero.")

        if not vals_list.get('checkin_date'):
            raise ValidationError(
                _("Check-In Date is required and cannot be empty."))
        # Fetch the company_id from vals_list or default to the current user's company
        company_id = vals_list.get('company_id', self.env.user.company_id.id)
        company = self.env['res.company'].browse(company_id)
        current_company_name = company.name

        if vals_list.get('name', 'New') == 'New':
            if vals_list.get('parent_booking_id'):
                # Handle child booking
                parent = self.browse(vals_list['parent_booking_id'])
                parent_company_id = parent.company_id.id
                # Ensure child booking inherits parent's company
                vals_list['company_id'] = parent_company_id

                sequence = self.env['ir.sequence'].search(
                    [('code', '=', 'room.booking'),
                     ('company_id', '=', parent_company_id)],
                    limit=1
                )
                if not sequence:
                    raise ValueError(
                        f"No sequence configured for company: {parent.company_id.name}")

                next_sequence = sequence.next_by_id()

                vals_list['name'] = f"{parent.company_id.name}/{next_sequence}"
                vals_list['parent_booking_name'] = parent.name
            else:
                # Handle new parent booking
                sequence = self.env['ir.sequence'].search(
                    [('code', '=', 'room.booking'),
                     ('company_id', '=', company_id)],
                    limit=1
                )
                if not sequence:
                    raise ValueError(
                        f"No sequence configured for company: {current_company_name}")

                next_sequence = sequence.next_by_id()
                vals_list['name'] = f"{current_company_name}/{next_sequence}"

        if not vals_list.get('date_order'):
            vals_list['date_order'] = self._get_default_order_date()

        record = super(RoomBooking, self).create(vals_list)

        # Log the initial state for all room lines
        if record.state:
            for line in record.room_line_ids:
                self.env['room.booking.line.status'].create({
                    'booking_line_id': line.id,
                    'status': record.state,
                    'change_time': fields.Datetime.now(),
                })

        return record

        # return super(RoomBooking, self).create(vals_list)

    def _get_default_order_date(self):
        """Helper method to get default order date"""
        return fields.Datetime.now()

    @api.depends('partner_id')
    def _compute_user_id(self):
        """Computes the User id"""
        for order in self:
            order.user_id = \
                order.partner_id.address_get(['invoice'])[
                    'invoice'] if order.partner_id else False

    # def _compute_invoice_count(self):
    #     """Compute the invoice count"""
    #     for record in self:
    #         record.invoice_count = self.env['account.move'].search_count(
    #             [('ref', '=', self.name)])
    def _compute_invoice_count(self):
        """Compute the invoice count"""
        for record in self:
            record.invoice_count = self.env['account.move'].search_count(
                # Use `record.name` instead of `self.name`
                [('ref', '=', record.name)]
            )

    @api.depends('partner_id')
    def _compute_pricelist_id(self):
        """Computes PriceList"""
        for order in self:
            if not order.partner_id:
                order.pricelist_id = False
                continue
            order = order.with_company(order.company_id)
            order.pricelist_id = order.partner_id.property_product_pricelist

    @api.depends('room_line_ids.price_subtotal', 'room_line_ids.price_tax',
                 'room_line_ids.price_total',
                 'food_order_line_ids.price_subtotal',
                 'food_order_line_ids.price_tax',
                 'food_order_line_ids.price_total',
                 'service_line_ids.price_subtotal',
                 'service_line_ids.price_tax', 'service_line_ids.price_total',
                 'vehicle_line_ids.price_subtotal',
                 'vehicle_line_ids.price_tax', 'vehicle_line_ids.price_total',
                 'event_line_ids.price_subtotal', 'event_line_ids.price_tax',
                 'event_line_ids.price_total',
                 )
    @api.depends('room_line_ids', 'food_order_line_ids', 'service_line_ids', 'vehicle_line_ids', 'event_line_ids')
    def _compute_amount_untaxed(self, flag=False):
        for rec in self:
            # Initialize amounts for each record
            amount_untaxed_room = 0.0
            amount_untaxed_food = 0.0
            amount_untaxed_fleet = 0.0
            amount_untaxed_event = 0.0
            amount_untaxed_service = 0.0
            amount_taxed_room = 0.0
            amount_taxed_food = 0.0
            amount_taxed_fleet = 0.0
            amount_taxed_event = 0.0
            amount_taxed_service = 0.0
            amount_total_room = 0.0
            amount_total_food = 0.0
            amount_total_fleet = 0.0
            amount_total_event = 0.0
            amount_total_service = 0.0
            booking_list = []

            # Fetch and filter account move lines for the current record
            account_move_line = self.env['account.move.line'].search_read(
                domain=[('ref', '=', rec.name),
                        ('display_type', '!=', 'payment_term')],
                fields=['name', 'quantity', 'price_unit', 'product_type']
            )

            # Remove the 'id' key from account move lines
            for line in account_move_line:
                del line['id']

            # Calculate amounts for each type of line item
            if rec.room_line_ids:
                amount_untaxed_room += sum(
                    rec.room_line_ids.mapped('price_subtotal'))
                amount_taxed_room += sum(rec.room_line_ids.mapped('price_tax'))
                amount_total_room += sum(rec.room_line_ids.mapped('price_total'))
                for room in rec.room_line_ids:
                    booking_dict = {'name': room.room_id.name, 'quantity': room.uom_qty, 'price_unit': room.price_unit,
                                    'product_type': 'room'}
                    if booking_dict not in account_move_line:
                        if not account_move_line:
                            booking_list.append(booking_dict)
                        else:
                            for move_line in account_move_line:
                                if move_line['product_type'] == 'room' and booking_dict['name'] == move_line['name']:
                                    if booking_dict['price_unit'] == move_line['price_unit'] and booking_dict[
                                            'quantity'] != move_line['quantity']:
                                        booking_list.append({
                                            'name': room.room_id.name,
                                            "quantity": booking_dict['quantity'] - move_line['quantity'],
                                            "price_unit": room.price_unit,
                                            "product_type": 'room'
                                        })
                                    else:
                                        booking_list.append(booking_dict)
                    if flag:
                        room.booking_line_visible = True

            if rec.food_order_line_ids:
                for food in rec.food_order_line_ids:
                    booking_list.append(self.create_list(food))
                amount_untaxed_food += sum(
                    rec.food_order_line_ids.mapped('price_subtotal'))
                amount_taxed_food += sum(
                    rec.food_order_line_ids.mapped('price_tax'))
                amount_total_food += sum(
                    rec.food_order_line_ids.mapped('price_total'))

            if rec.service_line_ids:
                for service in rec.service_line_ids:
                    booking_list.append(self.create_list(service))
                amount_untaxed_service += sum(
                    rec.service_line_ids.mapped('price_subtotal'))
                amount_taxed_service += sum(
                    rec.service_line_ids.mapped('price_tax'))
                amount_total_service += sum(
                    rec.service_line_ids.mapped('price_total'))

            if rec.vehicle_line_ids:
                for fleet in rec.vehicle_line_ids:
                    booking_list.append(self.create_list(fleet))
                amount_untaxed_fleet += sum(
                    rec.vehicle_line_ids.mapped('price_subtotal'))
                amount_taxed_fleet += sum(
                    rec.vehicle_line_ids.mapped('price_tax'))
                amount_total_fleet += sum(
                    rec.vehicle_line_ids.mapped('price_total'))

            if rec.event_line_ids:
                for event in rec.event_line_ids:
                    booking_list.append(self.create_list(event))
                amount_untaxed_event += sum(
                    rec.event_line_ids.mapped('price_subtotal'))
                amount_taxed_event += sum(rec.event_line_ids.mapped('price_tax'))
                amount_total_event += sum(
                    rec.event_line_ids.mapped('price_total'))

            # Assign computed amounts to the current record
            rec.amount_untaxed = amount_untaxed_food + amount_untaxed_room + \
                amount_untaxed_fleet + amount_untaxed_event + amount_untaxed_service
            rec.amount_untaxed_food = amount_untaxed_food
            rec.amount_untaxed_room = amount_untaxed_room
            rec.amount_untaxed_fleet = amount_untaxed_fleet
            rec.amount_untaxed_event = amount_untaxed_event
            rec.amount_untaxed_service = amount_untaxed_service
            rec.amount_tax = amount_taxed_food + amount_taxed_room + \
                amount_taxed_fleet + amount_taxed_event + amount_taxed_service
            rec.amount_taxed_food = amount_taxed_food
            rec.amount_taxed_room = amount_taxed_room
            rec.amount_taxed_fleet = amount_taxed_fleet
            rec.amount_taxed_event = amount_taxed_event
            rec.amount_taxed_service = amount_taxed_service
            rec.amount_total = amount_total_food + amount_total_room + \
                amount_total_fleet + amount_total_event + amount_total_service
            rec.amount_total_food = amount_total_food
            rec.amount_total_room = amount_total_room
            rec.amount_total_fleet = amount_total_fleet
            rec.amount_total_event = amount_total_event
            rec.amount_total_service = amount_total_service

        return booking_list

    # def _compute_amount_untaxed(self, flag=False):
    #     """Compute the total amounts of the Sale Order"""
    #     amount_untaxed_room = 0.0
    #     amount_untaxed_food = 0.0
    #     amount_untaxed_fleet = 0.0
    #     amount_untaxed_event = 0.0
    #     amount_untaxed_service = 0.0
    #     amount_taxed_room = 0.0
    #     amount_taxed_food = 0.0
    #     amount_taxed_fleet = 0.0
    #     amount_taxed_event = 0.0
    #     amount_taxed_service = 0.0
    #     amount_total_room = 0.0
    #     amount_total_food = 0.0
    #     amount_total_fleet = 0.0
    #     amount_total_event = 0.0
    #     amount_total_service = 0.0
    #     room_lines = self.room_line_ids
    #     food_lines = self.food_order_line_ids
    #     service_lines = self.service_line_ids
    #     fleet_lines = self.vehicle_line_ids
    #     event_lines = self.event_line_ids
    #     booking_list = []
    #     account_move_line = self.env['account.move.line'].search_read(
    #         domain=[('ref', '=', self.name),
    #                 ('display_type', '!=', 'payment_term')],
    #         fields=['name', 'quantity', 'price_unit', 'product_type'], )
    #     for rec in account_move_line:
    #         del rec['id']
    #     if room_lines:
    #         amount_untaxed_room += sum(room_lines.mapped('price_subtotal'))
    #         amount_taxed_room += sum(room_lines.mapped('price_tax'))
    #         amount_total_room += sum(room_lines.mapped('price_total'))
    #         for room in room_lines:
    #             booking_dict = {'name': room.room_id.name,
    #                             'quantity': room.uom_qty,
    #                             'price_unit': room.price_unit,
    #                             'product_type': 'room'}
    #             if booking_dict not in account_move_line:
    #                 if not account_move_line:
    #                     booking_list.append(booking_dict)
    #                 else:
    #                     for rec in account_move_line:
    #                         if rec['product_type'] == 'room':
    #                             if booking_dict['name'] == rec['name'] and \
    #                                     booking_dict['price_unit'] == rec[
    #                                 'price_unit'] and booking_dict['quantity']\
    #                                     != rec['quantity']:
    #                                 booking_list.append(
    #                                     {'name': room.room_id.name,
    #                                      "quantity": booking_dict[
    #                                                      'quantity'] - rec[
    #                                                      'quantity'],
    #                                      "price_unit": room.price_unit,
    #                                      "product_type": 'room'})
    #                             else:
    #                                 booking_list.append(booking_dict)
    #                 if flag:
    #                     room.booking_line_visible = True
    #     if food_lines:
    #         for food in food_lines:
    #             booking_list.append(self.create_list(food))
    #         amount_untaxed_food += sum(food_lines.mapped('price_subtotal'))
    #         amount_taxed_food += sum(food_lines.mapped('price_tax'))
    #         amount_total_food += sum(food_lines.mapped('price_total'))
    #     if service_lines:
    #         for service in service_lines:
    #             booking_list.append(self.create_list(service))
    #         amount_untaxed_service += sum(
    #             service_lines.mapped('price_subtotal'))
    #         amount_taxed_service += sum(service_lines.mapped('price_tax'))
    #         amount_total_service += sum(service_lines.mapped('price_total'))
    #     if fleet_lines:
    #         for fleet in fleet_lines:
    #             booking_list.append(self.create_list(fleet))
    #         amount_untaxed_fleet += sum(fleet_lines.mapped('price_subtotal'))
    #         amount_taxed_fleet += sum(fleet_lines.mapped('price_tax'))
    #         amount_total_fleet += sum(fleet_lines.mapped('price_total'))
    #     if event_lines:
    #         for event in event_lines:
    #             booking_list.append(self.create_list(event))
    #         amount_untaxed_event += sum(event_lines.mapped('price_subtotal'))
    #         amount_taxed_event += sum(event_lines.mapped('price_tax'))
    #         amount_total_event += sum(event_lines.mapped('price_total'))
    #     for rec in self:
    #         rec.amount_untaxed = amount_untaxed_food + amount_untaxed_room + \
    #                              amount_untaxed_fleet + \
    #                              amount_untaxed_event + amount_untaxed_service
    #         rec.amount_untaxed_food = amount_untaxed_food
    #         rec.amount_untaxed_room = amount_untaxed_room
    #         rec.amount_untaxed_fleet = amount_untaxed_fleet
    #         rec.amount_untaxed_event = amount_untaxed_event
    #         rec.amount_untaxed_service = amount_untaxed_service
    #         rec.amount_tax = (amount_taxed_food + amount_taxed_room
    #                           + amount_taxed_fleet
    #                           + amount_taxed_event + amount_taxed_service)
    #         rec.amount_taxed_food = amount_taxed_food
    #         rec.amount_taxed_room = amount_taxed_room
    #         rec.amount_taxed_fleet = amount_taxed_fleet
    #         rec.amount_taxed_event = amount_taxed_event
    #         rec.amount_taxed_service = amount_taxed_service
    #         rec.amount_total = (amount_total_food + amount_total_room
    #                             + amount_total_fleet + amount_total_event
    #                             + amount_total_service)
    #         rec.amount_total_food = amount_total_food
    #         rec.amount_total_room = amount_total_room
    #         rec.amount_total_fleet = amount_total_fleet
    #         rec.amount_total_event = amount_total_event
    #         rec.amount_total_service = amount_total_service
    #     return booking_list

    @api.onchange('need_food')
    def _onchange_need_food(self):
        """Unlink Food Booking Line if Need Food is false"""
        if not self.need_food and self.food_order_line_ids:
            for food in self.food_order_line_ids:
                food.unlink()

    @api.onchange('need_service')
    def _onchange_need_service(self):
        """Unlink Service Booking Line if Need Service is False"""
        if not self.need_service and self.service_line_ids:
            for serv in self.service_line_ids:
                serv.unlink()

    @api.onchange('need_fleet')
    def _onchange_need_fleet(self):
        """Unlink Fleet Booking Line if Need Fleet is False"""
        if not self.need_fleet:
            if self.vehicle_line_ids:
                for fleet in self.vehicle_line_ids:
                    fleet.unlink()

    @api.onchange('need_event')
    def _onchange_need_event(self):
        """Unlink Event Booking Line if Need Event is False"""
        if not self.need_event:
            if self.event_line_ids:
                for event in self.event_line_ids:
                    event.unlink()

    @api.onchange('food_order_line_ids', 'room_line_ids',
                  'service_line_ids', 'vehicle_line_ids', 'event_line_ids')
    def _onchange_room_line_ids(self):
        """Invokes the Compute amounts function"""
        self._compute_amount_untaxed()
        self.invoice_button_visible = False

    # @api.constrains("room_line_ids")
    # def _check_duplicate_folio_room_line(self):
    #     """
    #     This method is used to validate the room_lines.
    #     ------------------------------------------------
    #     @param self: object pointer
    #     @return: raise warning depending on the validation
    #     """
    #     for record in self:
    #         # Create a set of unique ids
    #         ids = set()
    #         for line in record.room_line_ids:
    #             if line.room_id.id in ids:
    #                 raise ValidationError(
    #                     _(
    #                         """Room Entry Duplicates Found!, """
    #                         """You Cannot Book "%s" Room More Than Once!"""
    #                     )
    #                     % line.room_id.name
    #                 )
    #             ids.add(line.room_id.id)

    def create_list(self, line_ids):
        """Returns a Dictionary containing the Booking line Values"""
        account_move_line = self.env['account.move.line'].search_read(
            domain=[('ref', '=', self.name),
                    ('display_type', '!=', 'payment_term')],
            fields=['name', 'quantity', 'price_unit', 'product_type'], )
        for rec in account_move_line:
            del rec['id']
        booking_dict = {}
        for line in line_ids:
            name = ""
            product_type = ""
            if line_ids._name == 'food.booking.line':
                name = line.food_id.name
                product_type = 'food'
            elif line_ids._name == 'fleet.booking.line':
                name = line.fleet_id.name
                product_type = 'fleet'
            elif line_ids._name == 'service.booking.line':
                name = line.service_id.name
                product_type = 'service'
            elif line_ids._name == 'event.booking.line':
                name = line.event_id.name
                product_type = 'event'
            booking_dict = {'name': name,
                            'quantity': line.uom_qty,
                            'price_unit': line.price_unit,
                            'product_type': product_type}
        return booking_dict

    def action_reserve(self):
        """Button Reserve Function"""
        if self.state == 'reserved':
            message = _("Room Already Reserved.")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': message,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        if self.room_line_ids:
            for room in self.room_line_ids:
                room.room_id.write({
                    'status': 'reserved',
                })
                room.room_id.is_room_avail = False
            self.write({"state": "reserved"})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': "Rooms reserved Successfully!",
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        raise ValidationError(_("Please Enter Room Details"))

    def action_cancel(self):
        for record in self:
            # Determine the parent booking ID or fallback to the current record ID
            parent_booking_id = record.parent_booking_id.id if record.parent_booking_id else record.id
            print("Parent Booking ID:", parent_booking_id)

            # Retrieve room lines for the booking
            room_lines = self.env['room.booking.line'].search(
                [('booking_id', '=', record.id)])
            if room_lines:
                # Set room lines state to 'cancel'
                room_lines.write({'state': 'cancel'})

                for line in room_lines:
                    if line.room_id:
                        print("Processing Room Line ID:", line.id)

                        # Retrieve all availability results linked to the parent booking
                        availability_results = self.env['room.availability.result'].search([
                            ('room_booking_id', '=', parent_booking_id)
                        ])

                        for availability_result in availability_results:
                            print("Availability Result:", availability_result)

                            # Use a fixed count of 1 for each line or determine from another field if available
                            reserved_rooms = 1

                            # Debug print to verify the reserved rooms count
                            print(f"Reserved Rooms Count: {reserved_rooms}")

                            # Safeguard to prevent negative available rooms
                            if availability_result.rooms_reserved >= reserved_rooms:
                                availability_result.available_rooms += reserved_rooms
                                availability_result.rooms_reserved -= reserved_rooms
                            else:
                                print(
                                    "Warning: Attempt to reduce more rooms than reserved.")
                                availability_result.available_rooms += availability_result.rooms_reserved
                                availability_result.rooms_reserved = 0

            # Update the booking state to 'cancel'
            record.write({'state': 'cancel'})
            print(f"Booking ID {record.id} has been canceled.")

    # def action_cancel(self):
    #     for record in self:
    #         room_lines = self.env['room.booking.line'].search([('booking_id', '=', record.id)])
    #         if room_lines:
    #             room_lines.write({'state': 'cancel'})
    #
    #         room_avail_records = self.env['room.availability.result'].search(
    #             [('room_booking_id', '=', record.parent_booking_id.id)]
    #         )
    #         for room_avail in room_avail_records:
    #             room_avail.available_rooms += record.room_count
    #
    #         record.state = 'cancel'
    #
    #     # if self.room_line_ids:
    #     #     for room in self.room_line_ids:
    #     #         room.room_id.write({
    #     #             'status': 'available',
    #     #         })
    #     #         room.room_id.is_room_avail = True
    #     # self.write({"state": "cancel"})

    # def action_maintenance_request(self):
    #     """
    #     Function that handles the maintenance request
    #     """
    #     room_list = []
    #     for rec in self.room_line_ids.room_id.ids:
    #         room_list.append(rec)
    #     if room_list:
    #         room_id = self.env['hotel.room'].search([
    #             ('id', 'in', room_list)])
    #         self.env['maintenance.request'].sudo().create({
    #             'date': fields.Date.today(),
    #             'state': 'draft',
    #             'type': 'room',
    #             'room_maintenance_ids': room_id.ids,
    #         })
    #         self.maintenance_request_sent = True
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'type': 'success',
    #                 'message': "Maintenance Request Sent Successfully",
    #                 'next': {'type': 'ir.actions.act_window_close'},
    #             }
    #         }
    #     raise ValidationError(_("Please Enter Room Details"))

    def action_done(self):
        """Method for creating invoice"""
        if not self.room_line_ids:
            raise ValidationError(_("Please Enter Room Details"))
        booking_list = self._compute_amount_untaxed(True)
        if booking_list:
            account_move = self.env["account.move"].create([{
                'move_type': 'out_invoice',
                'invoice_date': fields.Date.today(),
                'partner_id': self.partner_id.id,
                'ref': self.name,
            }])
            for rec in booking_list:
                account_move.invoice_line_ids.create([{
                    'name': rec['name'],
                    'quantity': rec['quantity'],
                    'price_unit': rec['price_unit'],
                    'move_id': account_move.id,
                    'price_subtotal': rec['quantity'] * rec['price_unit'],
                    'product_type': rec['product_type'],
                }])
            self.write({'invoice_status': "invoiced"})
            self.invoice_button_visible = True
            return {
                'type': 'ir.actions.act_window',
                'name': 'Invoices',
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'account.move',
                'view_id': self.env.ref('account.view_move_form').id,
                'res_id': account_move.id,
                'context': "{'create': False}"
            }

    # working
    # def action_done(self):
    #     """Button action_confirm function"""
    #     for rec in self.env['account.move'].search(
    #             [('ref', '=', self.name)]):
    #         if rec.payment_state != 'not_paid':
    #             self.write({"state": "done"})
    #             self.is_checkin = False
    #             if self.room_line_ids:
    #                 return {
    #                     'type': 'ir.actions.client',
    #                     'tag': 'display_notification',
    #                     'params': {
    #                         'type': 'success',
    #                         'message': "Booking Checked Out Successfully!",
    #                         'next': {'type': 'ir.actions.act_window_close'},
    #                     }
    #                 }
    #         raise ValidationError(_('Your Invoice is Due for Payment.'))
    #     self.write({"state": "done"})

    def action_checkout(self):
        posting_item_meal, _1, _2, _3 = self.get_meal_rates(
            self.meal_pattern.id)
        _logger.info(f"The Posting Item Meal is: {posting_item_meal}")
        # forecast_date = self.forecast_date  # Assuming this is set in your class
        record = self  # Assuming the current record is used as 'record'
        meal_price, room_price, package_price, posting_item_value, line_posting_items = self.get_all_prices(
            record.checkin_date, record)
        _logger.info(f"Rate Posting Item: {posting_item_value}")
        _logger.info(f"Line Posting Items: {line_posting_items}")
        # if not self.posting_item_ids:
        #     raise ValidationError("You cannot proceed with checkout. Please add at least one Posting Item.")

        # today = fields.Date.context_today(self)
        today = datetime.now().date()

        _logger.info(
            f"Debug: action_checkout called for Booking ID: {self.id}")
        _logger.info(f"Debug: Today's date = {today}")
        _logger.info(f"Debug: checkout_date = {self.checkout_date}")

        if not self.room_line_ids:
            raise ValidationError(_("Please Enter Room Details"))
        filtered_lines = [
            line for line in self.rate_forecast_ids if line.date == today]
        _logger.info(
            f"Debug: Number of filtered rate_forecast_ids lines = {len(filtered_lines)}")
        for line in filtered_lines:
            print(f"Rate Forecast Line ID: {line.id}")
            print(f" - Room Booking ID: {line.room_booking_id.id}")
            print(f" - Forecasted Rate: {line.rate}")
            print(f" - Forecast Date: {line.date}")

        booking_list = self._compute_amount_untaxed(True)
        _logger.info(f"BOOKING LIST {booking_list}")
        if booking_list:
            account_move = self.env["account.move"].create([{
                'move_type': 'out_invoice',
                'invoice_date': today,
                'partner_id': self.partner_id.id,
                'ref': self.name,
                'hotel_booking_id': self.id,  # Set the current booking
                # Group Booking Name
                'group_booking_name': self.group_booking.name if self.group_booking else '',
                'parent_booking_name': self.parent_booking_name or '',  # Parent Booking Name
                'room_numbers': self.room_ids_display or '',  # Room Numbers
            }])
            for posting_item in self.posting_item_ids:
                account_move.invoice_line_ids.create({
                    'posting_item_id': posting_item.posting_item_id.id,  # Posting item
                    'posting_description': posting_item.description,  # Description
                    'posting_default_value': posting_item.default_value,  # Default value
                    'move_id': account_move.id,  # Link to account.move
                })
            for line in filtered_lines:
                line_data = []

                # Check and add Rate line if rate is available and greater than 0
                if line.rate and line.rate > 0:
                    line_data.append({
                        'posting_item_id': posting_item_value,  # Posting item for rate
                        'posting_description': 'Rate',  # Description for rate
                        # Default value for rate (dynamic)
                        'posting_default_value': line.rate,
                        'move_id': account_move.id,
                        # 'date': line.date,
                    })

                # Check and add Meal line if meals is available and greater than 0
                if line.meals and line.meals > 0:
                    line_data.append({
                        'posting_item_id': posting_item_meal,  # Posting item for meal
                        'posting_description': 'Meal',  # Description for meal
                        # Default value for meal (dynamic)
                        'posting_default_value': line.meals,
                        'move_id': account_move.id,
                        # 'date': line.date,
                    })

                # Check and add Package line if packages is available and greater than 0
                if line.packages and line.packages > 0:
                    line_data.append({
                        # Posting item for package
                        'posting_item_id': line_posting_items[-1],
                        'posting_description': 'Package',  # Description for package
                        # Default value for package (dynamic)
                        'posting_default_value': line.packages,
                        'move_id': account_move.id,
                        # 'date': line.date,
                    })

                # Create lines in account.move.line
                if line_data:
                    account_move.invoice_line_ids.create(line_data)
            # for rec in booking_list:
            #     account_move.invoice_line_ids.create([{
            #         'name': rec['name'],
            #         'quantity': rec['quantity'],
            #         'price_unit': rec['price_unit'],
            #         'move_id': account_move.id,
            #         'price_subtotal': rec['quantity'] * rec['price_unit'],
            #         'product_type': rec['product_type'],
            #     }])
            self.write({'invoice_status': "invoiced"})
            self.write({"state": "check_out"})
            self.invoice_button_visible = True
            # return {
            #         'type': 'ir.actions.act_window',
            #         'name': 'Invoices',
            #         'view_mode': 'form',
            #         'view_type': 'form',
            #         'res_model': 'account.move',
            #         'view_id': self.env.ref('account.view_move_form').id,
            #         'res_id': account_move.id,
            #         'context': "{'create': False}"
            # }

        # If checkout_date is not set or is in the future, prompt for early check-out confirmation
        # if not self.checkout_date or fields.Date.to_date(self.checkout_date) > today:
        # print("------------>", datetime.strptime(str(self.checkout_date), '%Y-%m-%d').date())

        # Convert checkout_date to a date object while stripping time
        if self.checkout_date:
            checkout_date = datetime.strptime(
                str(self.checkout_date).split(' ')[0], '%Y-%m-%d').date()
            print(self.checkout_date)
            print("checkout_date", checkout_date)
        else:
            checkout_date = None

        if not self.checkout_date or checkout_date > today:
            return {
                'name': _('Confirm Early Check-Out'),
                'type': 'ir.actions.act_window',
                'res_model': 'confirm.early.checkout.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_booking_ids': self.ids},
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _("Booking Checked Out Successfully!"),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

    # Working on 04/01/2025
    # def action_checkout(self):
    #     # if not self.posting_item_ids:
    #     #     raise ValidationError("You cannot proceed with checkout. Please add at least one Posting Item.")

    #     # today = fields.Date.context_today(self)
    #     today = datetime.now().date()

    #     print(f"Debug: action_checkout called for Booking ID: {self.id}")
    #     print(f"Debug: Today's date = {today}")
    #     print(f"Debug: checkout_date = {self.checkout_date}")
    #     if not self.room_line_ids:
    #         raise ValidationError(_("Please Enter Room Details"))
    #     booking_list = self._compute_amount_untaxed(True)
    #     _logger.info(f"BOOKING LIST {booking_list}")
    #     if booking_list:
    #         account_move = self.env["account.move"].create([{
    #             'move_type': 'out_invoice',
    #             'invoice_date': today,
    #             'partner_id': self.partner_id.id,
    #             'ref': self.name,
    #             'hotel_booking_id': self.id,  # Set the current booking
    #             'group_booking_name': self.group_booking.name if self.group_booking else '',  # Group Booking Name
    #             'parent_booking_name': self.parent_booking_name or '',  # Parent Booking Name
    #             'room_numbers': self.room_ids_display or '',  # Room Numbers
    #         }])
    #         for rec in booking_list:
    #             account_move.invoice_line_ids.create([{
    #                 'name': rec['name'],
    #                 'quantity': rec['quantity'],
    #                 'price_unit': rec['price_unit'],
    #                 'move_id': account_move.id,
    #                 'price_subtotal': rec['quantity'] * rec['price_unit'],
    #                 'product_type': rec['product_type'],
    #             }])
    #         self.write({'invoice_status': "invoiced"})
    #         self.write({"state": "check_out"})
    #         self.invoice_button_visible = True
    #         # return {
    #         #         'type': 'ir.actions.act_window',
    #         #         'name': 'Invoices',
    #         #         'view_mode': 'form',
    #         #         'view_type': 'form',
    #         #         'res_model': 'account.move',
    #         #         'view_id': self.env.ref('account.view_move_form').id,
    #         #         'res_id': account_move.id,
    #         #         'context': "{'create': False}"
    #         # }

    #     # If checkout_date is not set or is in the future, prompt for early check-out confirmation
    #     # if not self.checkout_date or fields.Date.to_date(self.checkout_date) > today:
    #     # print("------------>", datetime.strptime(str(self.checkout_date), '%Y-%m-%d').date())

    #     # Convert checkout_date to a date object while stripping time
    #     if self.checkout_date:
    #         checkout_date = datetime.strptime(str(self.checkout_date).split(' ')[0], '%Y-%m-%d').date()
    #         print(self.checkout_date)
    #         print("checkout_date", checkout_date)
    #     else:
    #         checkout_date = None

    #     if not self.checkout_date or checkout_date > today:
    #         return {
    #             'name': _('Confirm Early Check-Out'),
    #             'type': 'ir.actions.act_window',
    #             'res_model': 'confirm.early.checkout.wizard',
    #             'view_mode': 'form',
    #             'target': 'new',
    #             'context': {'default_booking_ids': self.ids},
    #         }

    #     # Convert checkout_date to date and compare
    #     # checkout_date = fields.Date.to_date(self.checkout_date)
    #     # checkout_date = datetime.strptime(str(self.checkout_date).split(' ')[0], '%Y-%m-%d').date()
    #     # print(f"Debug: Converted checkout_date = {checkout_date}")

    #     # If checkout_date is not today, raise a validation error
    #     if checkout_date != today:
    #         print("Debug: Validation error triggered.")
    #         raise ValidationError(
    #             _("You can only check out on the reservation's check-out date, which should be today.")
    #         )

    #     # Change booking state to 'check_out'
    #     self.write({"state": "check_out", "checkout_date": today})
    #     print(f"Debug: State after write operation = {self.state}")

    #     # Return success notification
    # return {
    #     'type': 'ir.actions.client',
    #     'tag': 'display_notification',
    #     'params': {
    #         'type': 'success',
    #         'message': _("Booking Checked Out Successfully!"),
    #         'next': {'type': 'ir.actions.act_window_close'},
    #     }
    # }

    def action_view_invoices(self):
        """Method for Returning invoice View"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'view_mode': 'tree,form',
            'view_type': 'tree,form',
            'res_model': 'account.move',
            'domain': [('ref', '=', self.name)],
            'context': "{'create': False}"
        }

    def action_checkin(self):
        today = datetime.now().date()
        for record in self:
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot check-in  booking with a check-in date in the past."))
        """ Handles the check-in action by asking for confirmation if check-in is in the future or showing unavailability """
        today = fields.Date.context_today(self)

        # Ensure room details are entered
        if not self.room_line_ids:
            raise ValidationError(_("Please Enter Room Details"))

        # Check availability for rooms on the current date

        room_availability = self.check_room_availability_all_hotels_split_across_type(
            checkin_date=today,
            checkout_date=today + timedelta(days=1),
            room_count=len(self.room_line_ids),
            adult_count=sum(self.room_line_ids.mapped('adult_count')),
            hotel_room_type_id=self.room_line_ids.mapped(
                'hotel_room_type').id if self.room_line_ids else None
        )
        print("line 1976", today, room_availability, len(self.room_line_ids),
              sum(self.room_line_ids.mapped('adult_count')))

        # Check if room_availability indicates no available rooms and handle it here
        if not room_availability or isinstance(room_availability, dict):
            raise ValidationError(
                _("No rooms are available for today's date. Please select a different date."))

        # Validate room availability data
        # if not isinstance(room_availability, list) or any(
        #         int(res.get('available_rooms', 0)) <= 0 for res in room_availability):
        #     raise ValidationError(_(" Please select a different date."))
        room_availability_list = room_availability[1]
        total_available_rooms = sum(
            int(res.get('available_rooms', 0)) for res in room_availability_list)

        if total_available_rooms > 0:
            print("Pass")
        else:
            raise ValidationError(
                _("No rooms are available for the selected date. Please select a different date."))

        # Check if the check-in date is in the future
        if fields.Date.to_date(self.checkin_date) > today:
            # Open the confirmation wizard to ask the user for confirmation
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'booking.checkin.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_booking_ids': self.ids,
                }
            }

        # If the check-in date is today and rooms are available, proceed with check-in
        return self._perform_checkin()

    def _perform_checkin(self):
        """Helper method to perform check-in and update room availability."""
        parent_booking_id = self.parent_booking_id.id if self.parent_booking_id else self.id
        print("Parent Booking ID:", parent_booking_id)

        for room in self.room_line_ids:
            # Update room status to 'occupied'
            room.room_id.write({
                'status': 'occupied',
            })
            room.room_id.is_room_avail = False

            # Update the available rooms count and reduce rooms_reserved count
            if room.room_id:
                availability_result = self.env['room.availability.result'].search([
                    ('room_booking_id', '=', parent_booking_id)
                ], limit=1)

                print("Availability Result:", availability_result)

                if availability_result:
                    # Use room count from the room line or a calculated value
                    reserved_rooms = room.room_count if hasattr(
                        room, 'room_count') else 1

                    # Increase available_rooms and decrease rooms_reserved
                    availability_result.available_rooms -= reserved_rooms
                    availability_result.rooms_reserved += reserved_rooms

        # Update the booking state to 'check_in'
        self.write({"state": "check_in"})

        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': "Booking Checked In Successfully!",
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    # def _perform_checkin(self):
    #     """ Helper method to perform check-in """
    #     for room in self.room_line_ids:
    #         room.room_id.write({
    #             'status': 'occupied',
    #         })
    #         room.room_id.is_room_avail = False
    #     self.write({"state": "check_in"})
    #     return {
    #         'type': 'ir.actions.client',
    #         'tag': 'display_notification',
    #         'params': {
    #             'type': 'success',
    #             'message': "Booking Checked In Successfully!",
    #             'next': {'type': 'ir.actions.act_window_close'},
    #         }
    #     }

    @api.model
    def action_confirm_checkin(self, record_id):
        """ This method is called when the user confirms to change the check-in date """
        record = self.browse(record_id)
        if record.exists():
            record.checkin_date = datetime.now()
            return record._perform_checkin()
        return False

    @api.model
    def action_confirm_checkin(self, record_id):
        """ This method is called when the user confirms to change the check-in date """
        record = self.browse(record_id)
        if record.exists():
            record.checkin_date = fields.Date.context_today(self)
            return record._perform_checkin()
        return False

    # def action_checkin(self):
    #     today = fields.Date.context_today(self)
    #     if fields.Date.to_date(self.checkin_date) != today:
    #         raise ValidationError(
    #             _("You can only check in on the reservation's check-in date, which should be today.test"))
    #     """
    #     @param self: object pointer
    #     """
    #     if not self.room_line_ids:
    #         raise ValidationError(_("Please Enter Room Details"))
    #     else:
    #         for room in self.room_line_ids:
    #             room.room_id.write({
    #                 'status': 'occupied',
    #             })
    #             room.room_id.is_room_avail = False
    #         self.write({"state": "check_in"})
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'type': 'success',
    #                 'message': "Booking Checked In Successfully!",
    #                 'next': {'type': 'ir.actions.act_window_close'},
    #             }
    #         }

    # def action_block(self):
    #     for record in self:
    #         record.state = "block"
    def action_block(self):
        today = datetime.now().date()
        for record in self:
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot block  booking with a check-in date in the past."))
            # Check if all room_ids are assigned in room_line_ids
            unassigned_lines = record.room_line_ids.filtered(
                lambda line: not line.room_id)
            if unassigned_lines:
                raise ValidationError(
                    "All rooms must be assigned in room lines before moving to the 'block' state."
                )

            # If all rooms are assigned, allow state change
            record.state = "block"
            # record.is_room_line_readonly = True

    all_rooms_assigned = fields.Boolean(
        string="All Rooms Assigned",
        compute="_compute_all_rooms_assigned",
        store=True
    )

    # @api.depends('room_line_ids.room_id')
    # def _compute_all_rooms_assigned(self):
    #     for record in self:
    #         record.all_rooms_assigned = all(line.room_id for line in record.room_line_ids)
    #         if record.all_rooms_assigned:
    #             record.action_reload_page()

    @api.depends('room_line_ids.room_id')
    def _compute_all_rooms_assigned(self):
        for record in self:
            # record.all_rooms_assigned = all(line.room_id for line in record.room_line_ids)
            # if record.all_rooms_assigned:
            #     record.action_reload_page()
            if record.room_line_ids:
                record.all_rooms_assigned = all(
                    line.room_id for line in record.room_line_ids)
            else:
                record.all_rooms_assigned = False

            # Call action_reload_page if all rooms are assigned
            if record.all_rooms_assigned:
                record.action_reload_page()

    def action_reload_page(self):
        """Reload the current page when all rooms are assigned."""
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_auto_assign_room(self):
        pass

    def button_split_rooms(self):
        pass

    def get_details(self):
        """ Returns different counts for displaying in dashboard"""
        today = datetime.today()
        tz_name = False
        if self.env.user.tz:
            tz_name = self.env.user.tz
        today_utc = pytz.timezone('UTC').localize(today,
                                                  is_dst=False)
        if tz_name:
            context_today = today_utc.astimezone(pytz.timezone(tz_name))
            total_room = self.env['hotel.room'].search_count([])
            check_in = self.env['room.booking'].search_count(
                [('state', '=', 'check_in')])
            available_room = self.env['hotel.room'].search(
                [('status', '=', 'available')])
            reservation = self.env['room.booking'].search_count(
                [('state', '=', 'reserved')])
            check_outs = self.env['room.booking'].search([])
            check_out = 0
            staff = 0
            for rec in check_outs:
                for room in rec.room_line_ids:
                    if room.checkout_date.date() == context_today.date():
                        check_out += 1
                """staff"""
                staff = self.env['res.users'].search_count(
                    [('groups_id', 'in',
                      [self.env.ref('hotel_management_odoo.hotel_group_admin').id,
                       self.env.ref(
                           'hotel_management_odoo.cleaning_team_group_head').id,
                       self.env.ref(
                           'hotel_management_odoo.cleaning_team_group_user').id,
                       self.env.ref(
                           'hotel_management_odoo.hotel_group_reception').id,
                       self.env.ref(
                           'hotel_management_odoo.maintenance_team_group_leader').id,
                       self.env.ref(
                           'hotel_management_odoo.maintenance_team_group_user').id
                       ])])
            total_vehicle = self.env['fleet.vehicle.model'].search_count([])
            available_vehicle = total_vehicle - self.env[
                'fleet.booking.line'].search_count(
                [('state', '=', 'check_in')])
            total_event = self.env['event.event'].search_count([])
            pending_event = self.env['event.event'].search([])
            pending_events = 0
            today_events = 0
            for pending in pending_event:
                if pending.date_end >= fields.datetime.now():
                    pending_events += 1
                if pending.date_end.date() == fields.date.today():
                    today_events += 1
            food_items = self.env['lunch.product'].search_count([])
            food_order = len(self.env['food.booking.line'].search([]).filtered(
                lambda r: r.booking_id.state not in ['check_out', 'cancel',
                                                     'done']))
            """total Revenue"""
            total_revenue = 0
            today_revenue = 0
            pending_payment = 0
            for rec in self.env['account.move'].search(
                    [('payment_state', '=', 'paid')]):
                if rec.ref:
                    if 'BOOKING' in rec.ref:
                        total_revenue += rec.amount_total
                        if rec.date == fields.date.today():
                            today_revenue += rec.amount_total
            for rec in self.env['account.move'].search(
                    [('payment_state', 'in', ['not_paid', 'partial'])]):
                if rec.ref and 'BOOKING' in rec.ref:
                    if rec.payment_state == 'not_paid':
                        pending_payment += rec.amount_total
                    elif rec.payment_state == 'partial':
                        pending_payment += rec.amount_residual
            return {
                'total_room': total_room,
                'available_room': len(available_room),
                'staff': staff,
                'check_in': check_in,
                'reservation': reservation,
                'check_out': check_out,
                'total_vehicle': total_vehicle,
                'available_vehicle': available_vehicle,
                'total_event': total_event,
                'today_events': today_events,
                'pending_events': pending_events,
                'food_items': food_items,
                'food_order': food_order,
                'total_revenue': round(total_revenue, 2),
                'today_revenue': round(today_revenue, 2),
                'pending_payment': round(pending_payment, 2),
                'currency_symbol': self.env.user.company_id.currency_id.symbol,
                'currency_position': self.env.user.company_id.currency_id.position
            }
        else:
            raise ValidationError(
                _("Please Enter time zone in user settings."))

    room_count = fields.Integer(string='Rooms', tracking=True)

    @api.onchange('room_count')
    def _check_room_count(self):
        for record in self:
            if record.room_count < 0:
                pass
                # raise ValidationError("Kindly select at least one room for room booking.")

    adult_count = fields.Integer(string='Adults', tracking=True)

    # @api.onchange('adult_count')
    # def _onchange_adult_count(self):
    #     if self.adult_count == 0:
    #         raise ValidationError('Adult count cannot be zero. Please enter a valid number of adults.')

    child_count = fields.Integer(string='Children', default=0, tracking=True)
    infant_count = fields.Integer(string='Infant', default=0, tracking=True)
    child_ages = fields.One2many(
        'hotel.child.age', 'booking_id', string='Children Ages')
    total_people = fields.Integer(
        string='Total People', compute='_compute_total_people', store=True, tracking=True)
    rooms_to_add = fields.Integer(
        string='Rooms to Add', default=0, tracking=True)

    room_ids_display = fields.Char(string="Room Names", compute="_compute_room_ids_display",
                                   search="_search_room_ids_display", tracking=True)
    room_type_display = fields.Char(
        string="Room Types", compute="_compute_room_type_display", tracking=True)

    room_price = fields.Float(string="Room Price", default=0, tracking=True)
    room_child_price = fields.Float(string="Room Child Price", tracking=True)
    room_infant_price = fields.Float(string="Room Infant Price", tracking=True)
    meal_price = fields.Float(string="Meal Price", default=0, tracking=True)
    meal_child_price = fields.Float(string="Meal Child Price", tracking=True, default=0)
    meal_infant_price = fields.Float(string="Meal Infant Price", tracking=True)
    # Discount Fields
    room_discount = fields.Float(
        string="Room Discount", default=0, digits=(16, 2), tracking=True)
    meal_discount = fields.Float(
        string="Meal Discount", default=0, tracking=True)

    def check_room_meal_validation(self, vals, is_write):
        _logger.info(f"VALIDATION STARTED: {vals}, IS_WRITE: {is_write}")

        for record in self:
            if vals.get('use_price', record.use_price):
                _logger.info(
                    f"USE ROOM PRICE {vals.get('use_price', record.use_price)}")

                if vals.get('room_price', record.room_price) < 0:
                    raise UserError("Room Price cannot be less than 0.")

                # if vals.get('child_count', record.child_count) > 0:
                #     if vals.get('room_child_price', record.room_child_price) < 1:
                #         raise UserError(
                #             "Room Child Price cannot be less than 1.")

                # if vals.get('infant_count', record.infant_count) > 0:
                #     if vals.get('room_infant_price', record.room_infant_price) < 1:
                #         raise UserError(
                #             "Room Infant Price cannot be less than 1.")

                # _logger.info(f"TEST {vals.get('room_discount', record.room_discount) * 100}")
                if vals.get('room_is_percentage', record.room_is_percentage):
                    if vals.get('room_discount', record.room_discount) * 100 < 1:
                        raise UserError("Room Discount cannot be less than 1.")
                else:
                    if vals.get('room_discount', record.room_discount) < 0:
                        raise UserError("Room Discount cannot be less than 0.")

            # Meal Price validation
            if vals.get('use_meal_price', record.use_meal_price):
                if vals.get('meal_price', record.meal_price) < 0:
                    raise UserError("Meal Price cannot be less than 0.")

                if vals.get('child_count', record.child_count) > 0:
                    if vals.get('meal_child_price', record.meal_child_price) < 0:
                        raise UserError(
                            "Meal Child Price cannot be less than 0.")

                # if vals.get('infant_count', record.infant_count) > 0:
                #     if vals.get('meal_infant_price', record.meal_infant_price) < 1:
                #         raise UserError(
                #             "Meal Infant Price cannot be less than 1.")

                if vals.get('meal_is_percentage', record.meal_is_percentage):
                    if vals.get('meal_discount', record.meal_discount) * 100 < 1:
                        raise UserError("Meal Discount cannot be less than 1.")
                else:
                    if vals.get('meal_discount', record.meal_discount) < 0:
                        raise UserError("Meal Discount cannot be less than 0.")

        _logger.info("VALIDATION COMPLETED")

    # @api.onchange('room_price', 'meal_price', 'room_discount', 'meal_discount', 'room_child_price', 'room_infant_price',
    #               'meal_child_price', 'meal_infant_price')
    # def _onchange_price_discount(self):
    #     for record in self:
    #         # _logger.info(
    #         #     f"{record.child_count}, '{record.infant_count}', '{record.room_price}', '{record.meal_price}', '{record.room_discount}', '{record.meal_discount}', '{record.room_child_price}', '{record.room_infant_price}', '{record.meal_child_price}', '{record.meal_infant_price}'")
    #         _logger.info(f"USE ROOM PRICE {record.use_price}")
    #         if record.use_price:
    #             _logger.info(f"ADULT ROOM PRICE {record.room_price}")
    #             if record.room_price < 1:
    #                 raise UserError("Room Price cannot be less than 1.")
    #
    #             if record.child_count > 0:
    #                 _logger.info(f"CHILD ROOM PRICE {record.room_child_price}")
    #                 if record.room_child_price < 1:
    #                     raise UserError("Room Child Price cannot be less than 1.")
    #
    #             if record.infant_count > 0:
    #                 _logger.info(f"INFANT ROOM PRICE {record.room_infant_price}")
    #                 if record.room_infant_price < 1:
    #                     raise UserError("Room Infant Price cannot be less than 1.")
    #
    #             _logger.info(f"ROOM DISCOUNT {record.room_discount}")
    #             if record.room_discount < 1:
    #                 raise UserError("Room Discount cannot be less than 1.")
    #
    #         if record.use_meal_price:
    #             if record.meal_price < 1:
    #                 raise UserError("Meal Price cannot be less than 1.")
    #
    #             if record.child_count > 0:
    #                 if record.meal_child_price < 1:
    #                     raise UserError("Meal Child Price cannot be less than 1.")
    #
    #             if record.infant_count > 0:
    #                 if record.meal_infant_price < 1:
    #                     raise UserError("Meal Infant Price cannot be less than 1.")
    #
    #             _logger.info(f"MEAL DISCOUNT {record.meal_discount}")
    #             if record.meal_discount < 1:
    #                 raise UserError("Meal Discount cannot be less than 1.")

    # Discount Type Selection for Room
    room_is_amount = fields.Boolean(
        string="Room Discount(Amount)", default=True, tracking=True)
    room_is_percentage = fields.Boolean(
        string="Room Discount(%)", default=False, tracking=True)

    room_discount_display = fields.Char(
        string="Room Discount Display", tracking=True)

    @api.onchange('room_discount', 'room_is_percentage')
    def _onchange_room_discount(self):
        for record in self:
            if record.room_is_percentage and record.room_discount > 100:
                # record.room_discount = 0  # Cap the percentage to 100%
                pass

    @api.onchange('room_is_percentage')
    def _onchange_room_is_percentage(self):
        _logger.info(
            f"ROOM IS PERCENTAGE {self.room_is_percentage} {self.room_is_amount}")
        if self.room_is_percentage:
            self.room_discount = (self.room_discount / self.room_price)
            self.room_is_amount = False

        else:
            self.room_is_amount = True
        # if self.room_is_percentage:
        #     self.room_is_amount = False
        #     if self.room_discount and self.room_discount > 1:
        #         # Convert value to percentage format
        #         self.room_discount = self.room_discount / 100
        # else:
        #     self.room_is_amount = True
        #     if self.room_discount and self.room_discount <= 1:
        #         # Convert value back from percentage to actual format
        #         self.room_discount = self.room_discount * 100

    # @api.onchange('room_is_percentage')
    # def _onchange_room_is_percentage(self):
    #     if self.room_discount:
    #         if self.room_is_percentage:
    #             # When switching to percentage, no need to multiply
    #             self.room_discount = self.room_discount
    #         else:
    #             # When switching from percentage, no need to divide
    #             self.room_discount = self.room_discount

    # Discount Type Selection for Meal
    meal_is_amount = fields.Boolean(
        string="Meal Discount as Amount", default=True, tracking=True)
    meal_is_percentage = fields.Boolean(
        string="Meal Discount as Percentage", default=False, tracking=True)

    @api.onchange('meal_is_percentage')
    def _onchange_meal_is_percentage(self):
        _logger.info(
            f"MEAL IS PERCENTAGE {self.meal_is_percentage} {self.meal_is_amount}")
        if self.meal_is_percentage:
            self.meal_discount = (self.meal_discount / self.meal_price)
            # if self.meal_discount < 1:
            #     self.meal_discount = 1
            print(self.meal_discount)
            self.meal_is_amount = False

        else:
            self.meal_is_amount = True

    @api.onchange('meal_is_amount')
    def _onchange_meal_is_amount(self):
        _logger.info(
            f"MEAL IS AMOUNT {self.meal_is_amount} {self.meal_is_percentage}")
        if self.meal_is_amount:
            self.meal_discount = self.meal_price * self.meal_discount
            self.meal_is_percentage = False

        else:
            self.meal_is_percentage = True

    # Amount Selection for Room and Meal Prices
    room_amount_selection = fields.Selection([
        ('total', 'Total'),
        ('line_wise', 'Line Wise')
    ], string="Room Amount Selection", default='total', tracking=True)

    meal_amount_selection = fields.Selection([
        ('total', 'Total'),
        ('line_wise', 'Line Wise')
    ], string="Meal Amount Selection", default='total', tracking=True)

    @api.onchange('room_is_amount')
    def _onchange_room_is_amount(self):
        _logger.info(
            f"ROOM IS AMOUNT {self.room_is_amount} {self.room_is_percentage}")
        if self.room_is_amount:
            self.room_discount = self.room_price * self.room_discount
            self.room_is_percentage = False

        else:
            self.room_is_percentage = True
            # self.room_discount = self.room_discount * 100

    # @api.onchange('room_is_percentage')
    # def _onchange_room_is_percentage(self):
    #     if self.room_is_percentage:
    #         self.room_is_amount = False
    #         if self.room_discount and self.room_discount > 1:
    #             # Convert value to percentage format
    #             # self.room_discount = self.room_discount * 100
    #             self.room_discount = 0
    #     else:
    #         self.room_is_amount = True
    #         if self.room_discount and self.room_discount > 100:
    #             # Convert value back from percentage to actual format
    #             # self.room_discount = self.room_discount / 100
    #             self.room_discount = 0

    # @api.onchange('meal_is_amount')
    # def _onchange_meal_is_amount(self):
    #     if self.meal_is_amount:
    #         self.meal_is_percentage = False
    #         self.meal_discount = self.meal_discount * 100

    # @api.onchange('meal_is_percentage')
    # def _onchange_meal_is_percentage(self):
    #     if self.meal_is_percentage:
    #         self.meal_is_amount = False
    #         # self.meal_discount = self.meal_discount / 100
    use_price = fields.Boolean(string="Use Price", store=True, tracking=True)
    use_meal_price = fields.Boolean(
        string="Use Meal Price", store=True, tracking=True)

    @api.onchange('use_price')
    def _onchange_use_price(self):
        if self.use_price and self.room_price <= 0.00:
            # Set use_price to False and raise a warning
            self.use_price = False
            raise UserError(
                "You cannot check 'Use Price' when 'Price' is 0.00 or less.")

    @api.onchange('meal_price')
    def _onchange_use_price(self):
        if self.use_meal_price and self.meal_price <= 0.00:
            # Set use_price to False and raise a warning
            self.meal_price = False
            raise UserError(
                "You cannot check 'Meal Price' when 'Meal Price' is 0.00 or less.")

    hide_fields = fields.Boolean(string="Hide Fields", default=False)

    @api.depends('room_line_ids')
    def _compute_room_ids_display(self):
        for record in self:
            room_names = record.room_line_ids.mapped(
                'room_id.name')  # Get all room names
            record.room_ids_display = ", ".join(
                room_names) if room_names else "Room Not Assigned"

    def _search_room_ids_display(self, operator, value):
        # Implement a custom search domain
        # For example, search for room_line_ids that have a room_id name matching the value:
        return [('room_line_ids.room_id.name', operator, value)]

    @api.depends('room_line_ids')
    def _compute_room_type_display(self):
        for record in self:
            # Correctly map the room type name from the room_line_ids
            # room_types = record.room_line_ids.mapped('room_id.room_type_name.room_type')  # Get all room type names
            room_types = record.room_line_ids.mapped(
                'hotel_room_type.room_type')
            # print('2458', room_types)
            record.room_type_display = ", ".join(
                room_types) if room_types else "Rooms Not Assigned"
            # print('2461', record.room_type_display)

    # parent_booking = fields.Selection(
    #     selection=lambda self: self._get_booking_names(),
    #     string="Parent Booking",
    #     store=True,
    # )
    # parent_booking = fields.Many2one(
    #     'room.booking', string="Parent Booking", store=True
    # )
    parent_booking = fields.Char(
        string="Parent Booking", store=True, tracking=True)

    parent_booking_name = fields.Char(
        string="Parent Booking Name",
        compute="_compute_parent_booking_name",
        store=True,
        readonly=True, tracking=True
    )

    parent_booking_id = fields.Many2one(
        'room.booking',
        string="Parent Booking",
        help="Reference to the parent booking if this is a child booking.", tracking=True
    )

    child_bookings = fields.One2many(
        'room.booking', 'parent_booking_id', string="Child Bookings")

    @api.depends('parent_booking')
    def _compute_child_bookings(self):
        for record in self:
            if record.name:
                record.child_bookings = self.search(
                    [('parent_booking', '=', record.name)])
            else:
                record.child_bookings = self.env['room.booking']

    # @api.depends('parent_booking')
    # def _compute_parent_booking_name(self):
    #     for record in self:
    #         if record.parent_booking:
    #             # Get the name of the parent booking based on the selection
    #             booking = self.env['room.booking'].search([('id', '=', int(record.parent_booking))], limit=1)
    #             record.parent_booking_name = booking.name if booking else ''

    @api.depends('parent_booking_id')
    def _compute_parent_booking_name(self):
        """Compute the Parent Booking Name based on parent_booking_id."""
        for record in self:
            record.parent_booking_name = record.parent_booking_id.name if record.parent_booking_id else False

    def assign_room(self):
        """Create child booking when room is assigned"""
        self.ensure_one()

        # Create child booking
        child_vals = {
            'parent_booking_id': self.id,
            'room_line_ids': self.room_line_ids.copy_data(),
            'checkin_date': self.checkin_date,
            'checkout_date': self.checkout_date,
            'state': 'block',
            'adult_ids': [(0, 0, vals) for vals in self.adult_ids.copy_data()],
            'is_room_line_readonly': True
        }

        child_booking = self.create(child_vals)
        return child_booking

    def _get_booking_names(self):
        bookings = self.search([])  # Retrieve all room bookings
        return [(str(booking.id), booking.name) for booking in bookings]

    @api.onchange('rooms_to_add')
    def _onchange_rooms_to_add(self):
        for line in self.room_line_ids:
            line.adult_count = self.adult_count
            print("adult line added")
            line.child_count = self.child_count
            line.infant_count = self.infant_count

    @api.depends('adult_count', 'child_count')
    def _compute_total_people(self):
        for rec in self:
            rec.total_people = rec.adult_count + rec.child_count + rec.infant_count

    # @api.onchange('room_id')
    # def _find_rooms_for_capacity(self):
    #     # Get currently selected room IDs
    #     current_room_ids = self.room_line_ids.mapped('room_id.id')

    #     # Calculate the total number of people (adults + children)
    #     total_people = self.adult_count + self.child_count

    #     # Calculate how many rooms we should add in this batch
    #     rooms_to_add = self.rooms_to_add if self.rooms_to_add else self.room_count

    #     # Fetch available rooms that can accommodate the total number of people and are not already used in this booking
    #     available_rooms = self.env['hotel.room'].search([
    #     ('status', '=', 'available'),
    #     ('id', 'not in', current_room_ids),
    #     ('num_person', '>=', total_people),
    #     ('id', 'not in', self.env['room.booking.line'].search([
    #         ('checkin_date', '<', self.checkout_date),
    #         ('checkout_date', '>', self.checkin_date),
    #         ('room_id', '!=', False)
    #     ]).mapped('room_id.id'))  # Exclude rooms with conflicting bookings
    # ], limit=rooms_to_add)

    #     # if not available_rooms:
    #     #     raise UserError('No more rooms available for booking that can accommodate the specified number of people.')

    #     # if len(available_rooms) < rooms_to_add:
    #     #     raise UserError(
    #     #         f'Only {len(available_rooms)} rooms are available that can accommodate the specified number of people. You requested {rooms_to_add} rooms.')

    #     return available_rooms

    is_button_clicked = fields.Boolean(
        string="Is Button Clicked", default=False, tracking=True)

    # def button_find_rooms(self):
    #     if not self.hotel_room_type:
    #         raise UserError("Please select your Room Type before proceeding.")
    #     # if self.is_button_clicked:
    #     #     raise UserError("Rooms have already been added. You cannot add them again.")

    #     total_people = self.adult_count + self.child_count

    #     # Validate check-in and check-out dates
    #     if not self.checkin_date or not self.checkout_date:
    #         raise UserError('Check-in and Check-out dates must be set before finding rooms.')

    #     checkin_date = self.checkin_date
    #     checkout_date = self.checkout_date
    #     duration = (checkout_date - checkin_date).days + (checkout_date - checkin_date).seconds / (24 * 3600)

    #     if duration <= 0:
    #         raise UserError('Checkout date must be later than Check-in date.')

    #     # Calculate remaining available rooms
    #     total_available = self.env['hotel.room'].search_count([('status', '=', 'available')])
    #     currently_booked = len(self.room_line_ids)

    #     # Validate if enough rooms are available
    #     if self.room_count > (total_available + currently_booked):
    #         raise UserError(f'Not enough rooms available. Total available rooms: {total_available}')

    #     # Check for overlapping bookings with the same date range
    #     overlapping_bookings = self.env['room.booking'].search([
    #         ('id', '!=', self.id),
    #         ('checkin_date', '<', checkout_date),
    #         ('checkout_date', '>', checkin_date),
    #     ])

    #     # if overlapping_bookings:
    #     #     raise UserError('Date conflict found with existing booking. Please change the Check-in and Check-out dates.')

    #     # Find valid rooms based on criteria
    #     new_rooms = self._find_rooms_for_capacity()
    #     # print('new_rooms', new_rooms)
    #     # if new_rooms:
    #         # Prepare room lines
    #     room_lines = []
    #     if new_rooms:
    #         for room in new_rooms:
    #             room_lines.append((0, 0, {
    #                 'room_id': False,
    #                 'checkin_date': checkin_date,
    #                 'checkout_date': checkout_date,
    #                 'uom_qty': duration,
    #                 'adult_count': self.adult_count,
    #                 'child_count': self.child_count
    #             }))
    #             # room.write({'status': 'reserved'})
    #     else:
    #         # Add an unassigned room line if no suitable rooms are found
    #         room_lines.append((0, 0, {
    #             'room_id': False,
    #             'checkin_date': checkin_date,
    #             'checkout_date': checkout_date,
    #             'uom_qty': duration,
    #             'adult_count': self.adult_count,
    #             'child_count': self.child_count,
    #             'is_unassigned': True  # Custom field to mark as unassigned
    #         }))

    #         self.state = 'waiting'
    #         # raise UserError('No rooms are currently available. Your booking has been assigned to the Waiting List.')

    #     # Append new room lines to existing room lines
    #     self.write({
    #         'room_line_ids': room_lines
    #     })

    #     # Reset rooms_to_add after successful addition
    #     self.rooms_to_add = 0

    def button_find_rooms(self):
        if not self.hotel_room_type:
            raise UserError("Please select your Room Type before proceeding.")

        total_people = self.adult_count + self.child_count

        if not self.checkin_date or not self.checkout_date:
            raise UserError(
                'Check-in and Check-out dates must be set before finding rooms.')

        checkin_date = self.checkin_date
        checkout_date = self.checkout_date
        duration = (checkout_date - checkin_date).days + \
                   (checkout_date - checkin_date).seconds / (24 * 3600)

        if duration <= 0:
            raise UserError('Checkout date must be later than Check-in date.')

        total_available = self.env['hotel.room'].search_count([
            ('status', '=', 'available'),
            ('room_type_name', '=', self.hotel_room_type.id)
        ])
        if self.room_count > total_available:
            raise UserError(
                f'Not enough rooms available for the selected room type. Total available rooms: {total_available}')

        new_rooms = self._find_rooms_for_capacity()
        room_lines = []
        if new_rooms:
            for room in new_rooms:
                room_lines.append((0, 0, {
                    'room_id': False,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'uom_qty': duration,
                    'adult_count': self.adult_count,
                    'child_count': self.child_count
                }))
            self.write({'room_line_ids': room_lines})
        else:
            raise UserError('No rooms found matching the selected criteria.')

    @api.model
    def _find_rooms_for_capacity(self):
        current_room_ids = self.room_line_ids.mapped('room_id.id')
        total_people = self.adult_count + self.child_count
        rooms_to_add = self.room_count

        print(current_room_ids, total_people, rooms_to_add)

        available_rooms = self.env['hotel.room'].search([
            ('status', '=', 'available'),
            ('id', 'not in', current_room_ids),
            ('num_person', '>=', total_people),
            ('room_type_name', '=', self.hotel_room_type.id),
            # ('id', 'not in', self.env['room.booking.line'].search([
            #     ('checkin_date', '<', self.checkout_date),
            #     ('checkout_date', '>', self.checkin_date),
            #     ('room_id', '!=', False)
            # ]).mapped('room_id.id'))
        ], limit=rooms_to_add)

        print("available_rooms", available_rooms)

        return available_rooms

    @api.model
    def check_room_availability_all_hotels_split_across_type(
            self,
            checkin_date,
            checkout_date,
            room_count,
            adult_count,
            hotel_room_type_id=None
    ):
        # Ensure checkin_date and checkout_date are date objects
        checkin_date = self._convert_to_date(checkin_date)
        checkout_date = self._convert_to_date(checkout_date)

        results = []
        total_available_rooms = 0  # Sum of total available rooms

        # Retrieve companies from hotel inventory
        # companies = self.env['hotel.inventory'].read_group([], ['company_id'], ['company_id'])
        company_id = self.env.context.get('company_id', self.env.company.id)
        domain = [('company_id', '=', company_id)] if company_id else []
        companies = self.env['hotel.inventory'].read_group(
            domain, ['company_id'], ['company_id'])

        # Retrieve all room types and map them by ID
        room_types = self.env['room.type'].search_read(
            [], [], order='user_sort ASC')
        room_types_dict = {room_type['id']: room_type for room_type in room_types}

        # Calculate total available rooms
        for company in companies:
            loop_company_id = company['company_id'][0]
            total_available_rooms += self._calculate_available_rooms(
                loop_company_id,
                checkin_date,
                checkout_date,
                adult_count,
                hotel_room_type_id,
                room_types_dict
            )
            print('5867', total_available_rooms)

            if total_available_rooms == 99999:  # Unlimited rooms
                break

        # # Handle insufficient rooms
        # if total_available_rooms < room_count:
        #     return self._trigger_waiting_list_wizard(
        #         room_count, total_available_rooms, hotel_room_type_id
        #     )

        # Handle insufficient rooms
        if total_available_rooms < room_count:
            wizard_result = self._trigger_waiting_list_wizard(
                room_count, total_available_rooms, hotel_room_type_id
            )
            return (total_available_rooms, [wizard_result])

        # Proceed with allocation
        return total_available_rooms, self._allocate_rooms(
            companies,
            room_count,
            checkin_date,
            checkout_date,
            adult_count,
            hotel_room_type_id,
            room_types_dict
        )

    # def _convert_to_date(self, date_value):
    #     """Helper to convert date strings or datetime objects to date."""
    #     if isinstance(date_value, datetime):
    #         return date_value.date()
    #     elif isinstance(date_value, str):
    #         return datetime.strptime(date_value, "%Y-%m-%d").date()
    #     return date_value

    def _convert_to_date(self, date_value):
        """Helper to convert date strings or datetime objects to date."""
        if isinstance(date_value, (datetime, date)):
            return date_value.date() if isinstance(date_value, datetime) else date_value
        elif isinstance(date_value, str):
            return datetime.strptime(date_value, "%Y-%m-%d").date()
        return date_value

    # def _allocate_rooms(self, companies, room_count, checkin_date, checkout_date, adult_count, hotel_room_type_id,
    #                     room_types_dict):
    #     """Allocate rooms based on availability."""
    #     results = []
    #     remaining_rooms = room_count

    #     for company in companies:
    #         loop_company_id = company['company_id'][0]
    #         room_availabilities_domain = [
    #             ('company_id', '=', loop_company_id),
    #             ('pax', '>=', adult_count),
    #         ]

    #         if hotel_room_type_id:
    #             room_availabilities_domain.append(('room_type', '=', hotel_room_type_id))

    #         room_availabilities = self.env['hotel.inventory'].search_read(
    #             room_availabilities_domain,
    #             ['room_type', 'pax', 'total_room_count', 'overbooking_allowed', 'overbooking_rooms'],
    #             order='pax ASC'
    #         )

    #         for availability in room_availabilities:
    #             room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
    #                 availability['room_type']

    #             # Exclude already allocated bookings from search
    #             booked_rooms = self.env['room.booking.line'].search_count([
    #                 ('hotel_room_type', '=', room_type_id),
    #                 ('booking_id.room_count', '=', 1),
    #                 ('adult_count', '=', availability['pax']),
    #                 ('checkin_date', '<=', checkout_date),
    #                 ('checkout_date', '>=', checkin_date),
    #                 ('booking_id.state', 'in', ['confirmed', 'check_in', 'block']),
    #                 ('id', 'not in', self.env.context.get('already_allocated', []))  # Exclude allocated lines
    #             ])

    #             if availability['overbooking_allowed']:
    #                 available_rooms = max(
    #                     availability['total_room_count'] - booked_rooms + availability['overbooking_rooms'], 0)
    #             else:
    #                 available_rooms = max(availability['total_room_count'] - booked_rooms, 0)
    #             print("line 2582", remaining_rooms, available_rooms)
    #             current_rooms_reserved = min(remaining_rooms, available_rooms)

    #             # Track allocated bookings in context
    #             if current_rooms_reserved > 0:
    #                 allocated_lines = self.env['room.booking.line'].search([
    #                     ('hotel_room_type', '=', room_type_id),
    #                     # ('booking_id.room_count', '=', 1),
    #                     ('adult_count', '=', availability['pax']),
    #                     ('checkin_date', '<=', checkout_date),
    #                     ('checkout_date', '>=', checkin_date),
    #                     ('booking_id.state', 'in', ['confirmed', 'check_in', 'block']),
    #                 ], limit=current_rooms_reserved)

    #                 already_allocated_ids = self.env.context.get('already_allocated', [])
    #                 already_allocated_ids += allocated_lines.ids
    #                 self = self.with_context(already_allocated=already_allocated_ids)

    #             results.append({
    #                 'company_id': loop_company_id,
    #                 'room_type': room_type_id,
    #                 'pax': availability['pax'],
    #                 'rooms_reserved': current_rooms_reserved,
    #                 'available_rooms': 'Unlimited' if available_rooms == 99999 else str(available_rooms),
    #                 'description': room_types_dict.get(room_type_id, {}).get('description', ''),
    #                 'user_sort': room_types_dict.get(room_type_id, {}).get('user_sort', ''),
    #                 'abbreviation': room_types_dict.get(room_type_id, {}).get('abbreviation', ''),
    #             })

    #             remaining_rooms -= current_rooms_reserved
    #             if remaining_rooms <= 0:
    #                 break

    #         if remaining_rooms <= 0:
    #             break

    #     return results

    def _allocate_rooms(self, companies, room_count, checkin_date, checkout_date, adult_count, hotel_room_type_id,
                        room_types_dict):
        """Allocate rooms based on availability."""
        results = []
        remaining_rooms = room_count
        today_date = datetime.today().strftime('%Y-%m-%d')

        for company in companies:
            loop_company_id = company['company_id'][0]
            room_availabilities_domain = [
                ('company_id', '=', loop_company_id),
                # ('pax', '>=', adult_count),
            ]

            if hotel_room_type_id:
                room_availabilities_domain.append(
                    ('room_type', '=', hotel_room_type_id))

            # room_availabilities = self.env['hotel.inventory'].search_read(room_availabilities_domain,
            #     ['room_type', 'pax', 'total_room_count', 'overbooking_allowed', 'overbooking_rooms'],
            #     order='pax ASC'
            # )

            room_availabilities = self.env['hotel.inventory'].search_read(room_availabilities_domain,
                                                                          ['room_type', 'total_room_count',
                                                                           'overbooking_allowed', 'overbooking_rooms'],
                                                                          order='room_type ASC'
                                                                          )
            grouped_availabilities = {}
            for availability in room_availabilities:
                room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
                    availability['room_type']
                if room_type_id not in grouped_availabilities:
                    grouped_availabilities[room_type_id] = {
                        'total_room_count': 0,
                        'overbooking_allowed': availability['overbooking_allowed'],
                        # 'overbooking_rooms': availability['overbooking_rooms'],
                        'overbooking_rooms': 0,
                        'entries': []
                    }
                grouped_availabilities[room_type_id]['total_room_count'] += availability['total_room_count']
                # Sum overbooking rooms
                grouped_availabilities[room_type_id]['overbooking_rooms'] += availability['overbooking_rooms']
                grouped_availabilities[room_type_id]['entries'].append(
                    availability)

            for room_type_id, availability in grouped_availabilities.items():
                # room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
                #     availability['room_type']

                # Exclude already allocated bookings from search
                # booked_rooms = self.env['room.booking.line'].search_count([
                #     ('hotel_room_type', '=', room_type_id),
                #     ('booking_id.room_count', '=', 1),
                #     # ('adult_count', '=', availability['pax']),
                #     ('checkin_date', '<=', checkout_date),
                #     ('checkout_date', '>=', checkin_date),
                #     ('booking_id.state', 'in', [
                #         'confirmed', 'check_in', 'block']),
                #     # Exclude allocated lines
                #     ('id', 'not in', self.env.context.get('already_allocated', []))
                # ])
                booked_rooms = self.env['room.booking'].search_count([
                    ('hotel_room_type', '=', room_type_id),
                    # ('booking_id.room_count', '=', 1),
                    # ('adult_count', '=', availability['pax']),
                    ('checkin_date', '<=', checkout_date),
                    ('checkout_date', '>=', checkin_date),
                    # ('checkout_date', '!=', today_date), 
                    ('checkout_date', 'not like', today_date + '%'), 
                    ('state', 'in', [
                         'check_in', 'block']),
                    # Exclude allocated lines
                    ('id', 'not in', self.env.context.get('already_allocated', []))
                ])

                rooms_on_hold_count = self.env['rooms.on.hold.management.front.desk'].search_count([
                    ('company_id', '=', self.env.company.id),
                    ('room_type', '=', room_type_id),
                    ('from_date', '<=', checkout_date),
                    ('to_date', '>=', checkin_date)
                ])

                # Count out-of-order rooms for the current company and matching room type
                out_of_order_rooms_count = self.env['out.of.order.management.fron.desk'].search_count([
                    ('company_id', '=', self.env.company.id),
                    ('room_type', '=', room_type_id),
                    ('from_date', '<=', checkout_date),
                    ('to_date', '>=', checkin_date)
                ])
                booked_rooms = booked_rooms + rooms_on_hold_count + out_of_order_rooms_count


                if availability['overbooking_allowed']:
                    available_rooms = max(
                        availability['total_room_count'] - booked_rooms + availability['overbooking_rooms'], 0)
                else:
                    available_rooms = max(
                        availability['total_room_count'] - booked_rooms, 0)
                # print("line 2582", remaining_rooms, available_rooms)
                current_rooms_reserved = min(remaining_rooms, available_rooms)

                # Track allocated bookings in context
                if current_rooms_reserved > 0:
                    allocated_lines = self.env['room.booking.line'].search([
                        ('hotel_room_type', '=', room_type_id),
                        # ('booking_id.room_count', '=', 1),
                        # ('adult_count', '=', availability['pax']),
                        ('checkin_date', '<=', checkout_date),
                        ('checkout_date', '>=', checkin_date),
                        ('booking_id.state', 'in', [
                            'confirmed', 'check_in', 'block']),
                    ], limit=current_rooms_reserved)

                    already_allocated_ids = self.env.context.get(
                        'already_allocated', [])
                    already_allocated_ids += allocated_lines.ids
                    self = self.with_context(
                        already_allocated=already_allocated_ids)

                results.append({
                    'company_id': loop_company_id,
                    'room_type': room_type_id,
                    # 'pax': availability['pax'],
                    'rooms_reserved': current_rooms_reserved,
                    'available_rooms': 'Unlimited' if available_rooms == 99999 else str(available_rooms),
                    'description': room_types_dict.get(room_type_id, {}).get('description', ''),
                    'user_sort': room_types_dict.get(room_type_id, {}).get('user_sort', ''),
                    'abbreviation': room_types_dict.get(room_type_id, {}).get('abbreviation', ''),
                })
                # print('3174', results)

                remaining_rooms -= current_rooms_reserved
                # print('3172', remaining_rooms)
                if remaining_rooms <= 0:
                    break

            if remaining_rooms <= 0:
                break

        return results

    def _trigger_waiting_list_wizard(self, room_count, total_available_rooms, hotel_room_type_id):
        """Trigger a wizard for the waiting list decision."""
        room_type_name = ''
        if hotel_room_type_id:
            room_type_record = self.env['room.type'].browse(hotel_room_type_id)
            room_type_name = room_type_record.description or room_type_record.room_type

        message = f"""
    <div style="text-align: center; font-size: 14px; line-height: 1.6; padding: 10px; white-space: nowrap;">
        <strong>Room Availability:</strong> You requested <strong>{room_count}</strong> room(s) of type <strong>{room_type_name}</strong>, 
        but only <strong>{total_available_rooms}</strong> room(s) are available.<br>
        Would you like to send this booking to the <strong>Waiting List</strong>?
    </div>
    """

        return {
            'type': 'ir.actions.act_window',
            'name': 'Room Availability',
            'res_model': 'room.availability.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_room_booking_id': self.id,
                'default_message': message,
            },
        }

    # def _calculate_available_rooms(self, company_id, checkin_date, checkout_date, adult_count, hotel_room_type_id,
    #                                room_types_dict):
    #     """Calculate available rooms for a company."""
    #     room_availabilities_domain = [
    #         ('company_id', '=', company_id),
    #         ('pax', '>=', adult_count),
    #     ]

    #     if hotel_room_type_id:
    #         room_availabilities_domain.append(('room_type', '=', hotel_room_type_id))

    #     room_availabilities = self.env['hotel.inventory'].search_read(
    #         room_availabilities_domain,
    #         ['room_type', 'pax', 'total_room_count', 'overbooking_allowed', 'overbooking_rooms'],
    #         order='pax ASC'
    #     )

    #     total_available_rooms = 0
    #     for availability in room_availabilities:
    #         room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
    #             availability['room_type']
    #         # print('2666', room_type_id, availability['pax'], checkout_date, checkin_date)
    #         # Exclude already allocated bookings from search
    #         booked_rooms = self.env['room.booking.line'].search_count([
    #             ('hotel_room_type', '=', room_type_id),
    #             ('booking_id.room_count', '=', 1),  # Include only bookings with room_count = 1
    #             ('adult_count', '=', availability['pax']),
    #             ('checkin_date', '<=', checkout_date),  # Check-in date filter
    #             ('checkout_date', '>=', checkin_date),  # Check-out date filter
    #             ('booking_id.state', 'in', ['confirmed', 'block', 'check_in']),  # Booking state filter
    #             ('id', 'not in', self.env.context.get('already_allocated', []))
    #             # ('hotel_room_type', '=', room_type_id),
    #             # ('adult_count', '=', availability['pax']),
    #             # ('checkin_date', '<', checkout_date),
    #             # ('checkout_date', '>', checkin_date),
    #             # ('state', 'in', ['confirmed', 'block', 'check_in']),
    #             # ('id', 'not in', self.env.context.get('already_allocated', []))  # Exclude allocated lines
    #         ])
    #         # print("line 2676",booked_rooms)

    #         if availability['overbooking_allowed']:
    #             available_rooms = max(
    #                 availability['total_room_count'] - booked_rooms + availability['overbooking_rooms'], 0
    #             )
    #             if availability['overbooking_rooms'] == 0:
    #                 return 99999  # Unlimited rooms
    #         else:
    #             # print("2693",availability['total_room_count'], booked_rooms,max(availability['total_room_count'] - booked_rooms, 0))
    #             available_rooms = max(availability['total_room_count'] - booked_rooms, 0)

    #         total_available_rooms += available_rooms
    #         # print('line 2697',total_available_rooms)

    #     return total_available_rooms

    # Working 27/12
    def _calculate_available_rooms(self, company_id, checkin_date, checkout_date, adult_count, hotel_room_type_id,
                                   room_types_dict):
        """Calculate available rooms for a company."""
        room_availabilities_domain = [
            ('company_id', '=', company_id),
            # ('pax', '>=', adult_count),
        ]

        today_date = datetime.today().strftime('%Y-%m-%d')

        if hotel_room_type_id:
            room_availabilities_domain.append(
                ('room_type', '=', hotel_room_type_id))

        # room_availabilities = self.env['hotel.inventory'].search_read(room_availabilities_domain,
        #     ['room_type', 'pax', 'total_room_count', 'overbooking_allowed', 'overbooking_rooms'],
        #     order='pax ASC'
        # )

        room_availabilities = self.env['hotel.inventory'].search_read(room_availabilities_domain,
                                                                      ['room_type', 'total_room_count',
                                                                       'overbooking_allowed', 'overbooking_rooms'],
                                                                      order='room_type ASC'
                                                                      )

        grouped_availabilities = {}

        for availability in room_availabilities:
            room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
                availability['room_type']
            if room_type_id not in grouped_availabilities:
                grouped_availabilities[room_type_id] = {
                    'total_room_count': 0,
                    'overbooking_allowed': availability['overbooking_allowed'],
                    # 'overbooking_rooms': availability['overbooking_rooms'],
                    'overbooking_rooms': 0,
                    'entries': []
                }
            grouped_availabilities[room_type_id]['total_room_count'] += availability['total_room_count']
            # Sum overbooking rooms
            grouped_availabilities[room_type_id]['overbooking_rooms'] += availability['overbooking_rooms']
            grouped_availabilities[room_type_id]['entries'].append(
                availability)
            print('3245', grouped_availabilities)

        total_available_rooms = 0
        for room_type_id, availability in grouped_availabilities.items():
            # room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
            #     availability['room_type']
            # print('2666', room_type_id, availability['pax'], checkout_date, checkin_date)
            # Exclude already allocated bookings from search
            # booked_rooms = self.env['room.booking.line'].search_count([
            #     ('hotel_room_type', '=', room_type_id),
            #     # Include only bookings with room_count = 1
            #     ('booking_id.room_count', '=', 1),
            #     # ('adult_count', '=', availability['pax']),
            #     ('checkin_date', '<=', checkout_date),  # Check-in date filter
            #     ('checkout_date', '>=', checkin_date),  # Check-out date filter
            #     # Booking state filter
            #     ('booking_id.state', 'in', ['block', 'check_in']),
            #     ('id', 'not in', self.env.context.get('already_allocated', []))
            #     # ('hotel_room_type', '=', room_type_id),
            #     # ('adult_count', '=', availability['pax']),
            #     # ('checkin_date', '<', checkout_date),
            #     # ('checkout_date', '>', checkin_date),
            #     # ('state', 'in', ['confirmed', 'block', 'check_in']),
            #     # ('id', 'not in', self.env.context.get('already_allocated', []))  # Exclude allocated lines
            # ])
            # print("line 2676",booked_rooms)

            booked_rooms = self.env['room.booking'].search_count([
                    ('hotel_room_type', '=', room_type_id),
                    # ('booking_id.room_count', '=', 1),
                    # ('adult_count', '=', availability['pax']),
                    ('checkin_date', '<=', checkout_date),
                    ('checkout_date', '>=', checkin_date),
                    # ('checkout_date', '!=', today_date), 
                    ('checkout_date', 'not like', today_date + '%'), 
                    ('state', 'in', [
                         'check_in', 'block']),
                    # Exclude allocated lines
                    ('id', 'not in', self.env.context.get('already_allocated', []))
                ])
            
            rooms_on_hold_count = self.env['rooms.on.hold.management.front.desk'].search_count([
                    ('company_id', '=', self.env.company.id),
                    ('room_type', '=', room_type_id),
                    ('from_date', '<=', checkout_date),
                    ('to_date', '>=', checkin_date)
                ])

            # Count out-of-order rooms for the current company and matching room type
            out_of_order_rooms_count = self.env['out.of.order.management.fron.desk'].search_count([
                    ('company_id', '=', self.env.company.id),
                    ('room_type', '=', room_type_id),
                    ('from_date', '<=', checkout_date),
                    ('to_date', '>=', checkin_date)
                ])
            
            booked_rooms = booked_rooms + rooms_on_hold_count + out_of_order_rooms_count
            
            print("line 6408",booked_rooms)

            

            if availability['overbooking_allowed']:
                available_rooms = max(
                    availability['total_room_count'] - booked_rooms +
                    availability['overbooking_rooms'], 0
                )
                print('6251', available_rooms)
                if availability['overbooking_rooms'] == 0:
                    return 99999  # Unlimited rooms
            else:
                # print("2693",availability['total_room_count'], booked_rooms,max(availability['total_room_count'] - booked_rooms, 0))
                available_rooms = max(
                    availability['total_room_count'] - booked_rooms, 0)

            total_available_rooms += available_rooms
            # print('line 2697',total_available_rooms)

        return total_available_rooms

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'block':
            for line in self.room_line_ids:
                line._update_inventory(
                    line.room_type_name.id, self.company_id.id, increment=False)
        elif self.state == 'confirmed':
            for line in self.room_line_ids:
                line._update_inventory(
                    line.room_type_name.id, self.company_id.id, increment=False)
        else:
            for line in self.room_line_ids:
                line._update_inventory(
                    line.room_type_name.id, self.company_id.id, increment=True)

    # def action_assign_all_rooms(self):
    #     """Assign all available rooms based on Room Type or any available rooms if no type is selected."""
    #     # for booking in self.with_context(skip_code_validation=True):
    #     for booking in self:
    #         if booking.state != 'confirmed':
    #             raise UserError(
    #                 "Rooms can only be assigned when the booking is in the 'Confirmed' state.")

    #         # for adult in booking.adult_ids:
    #         #     if not adult.first_name:
    #         #         raise ValidationError(f"Adult is missing a first name. Please fill it in before assigning rooms.")

    #         # # Validate child_ids for missing first_name
    #         # for child in booking.child_ids:
    #         #     if not child.first_name:
    #         #         raise ValidationError(f"Child is missing a first name. Please fill it in before assigning rooms.")

    #         if not booking.room_line_ids:
    #             raise UserError("No room lines to assign rooms to.")

    #         # Get available rooms
    #         # domain = [('status', '=', 'available')]
    #         # if booking.hotel_room_type:
    #         #     domain.append(
    #         #         ('room_type_name', '=', booking.hotel_room_type.id))
    #         domain = [
    #                 ('status', '=', 'available'),
    #                 ('id', 'not in', booked_room_ids + list(assigned_room_ids)),
    #                 ('room_type_name', '=', room_line_ids.hotel_room_type.id)  # Match room type
    #             ]

    #         # if booking.room_line_ids:
    #         #     max_pax = max(booking.room_line_ids.mapped('adult_count'))
    #         #     domain.append(('num_person', '=', max_pax))

    #         # Get room ids of rooms booked in the date range
    #         booked_room_lines = self.env['room.booking.line'].search([
    #             ('room_id', '!=', False),
    #             ('checkin_date', '<', booking.checkout_date),
    #             ('checkout_date', '>', booking.checkin_date)
    #         ])
    #         booked_room_ids = booked_room_lines.mapped('room_id').ids

    #         # Exclude the booked rooms
    #         domain.append(('id', 'not in', booked_room_ids))

    #         available_rooms = self.env['hotel.room'].search(domain)

    #         if not available_rooms:
    #             raise UserError("No available rooms to assign.")

    #         # Assign available rooms to each unassigned line
    #         ctr = 0
    #         assigned_rooms = []
    #         print("LEN of AVAIABLE ROOMS", len(available_rooms))
    #         unassigned_lines = booking.room_line_ids.filtered(lambda l: not l.room_id)
    #         for line in unassigned_lines:
    #             if ctr >= len(available_rooms):
    #                 break  # No more rooms to assign

    #             assigned_room = available_rooms[ctr]
    #             line.room_id = assigned_room.id
    #             # line.state = 'block'
    #             # line.sudo().with_context(skip_code_validation=True).booking_id.with_context(skip_code_validation=True)
    #             # line.sudo().with_context(skip_code_validation=True).write({
    #             #     'room_id': assigned_room.id
    #             # })
    #             assigned_rooms.append(assigned_room.id)
    #             ctr += 1

    #         if not assigned_rooms:
    #             raise UserError("No rooms assigned.")

    #         # Force recomputation of the state_ field
    #         booking.room_line_ids._compute_state()

    #         # Update Adults Page with Assigned Rooms
    #         self._update_adults_with_assigned_rooms(booking)

    #         booking._compute_show_in_tree()
    #         # child_bookings_ = self.env['room.booking'].search([
    #         #     ('parent_booking_id', '=', booking.id)
    #         # ])
    #         # print('child_booking__', child_bookings_)
    #         # if child_bookings_:
    #         #     matching_line = self.env['room.booking.line'].search([
    #         #         ('booking_id', 'in', child_bookings_.ids),
    #         #     ])
    #         #     for line in matching_line:
    #         #         line.write({'state_':'block'})
    #         # booking.state = 'block'

    def action_assign_all_rooms(self):
        """Assign unique available rooms to each line based on Room Type."""
        for booking in self:
            if booking.state != 'confirmed':
                raise UserError(
                    "Rooms can only be assigned when the booking is in the 'Confirmed' state.")

            if not booking.room_line_ids:
                raise UserError("No room lines to assign rooms to.")

            # Get room ids of rooms booked in the date range
            booked_room_lines = self.env['room.booking.line'].search([
                ('room_id', '!=', False),
                ('checkin_date', '<', booking.checkout_date),
                ('checkout_date', '>', booking.checkin_date)
            ])
            booked_room_ids = booked_room_lines.mapped('room_id').ids

            # Keep track of already assigned rooms
            assigned_room_ids = set()

            # Counter for successfully assigned rooms
            assigned_count = 0

            # Counter for unassignable lines
            unassignable_lines = []

            # Process each line and assign a unique room
            for line in booking.room_line_ids:
                if not line.hotel_room_type:  # Ensure the room line has a Room Type
                    raise UserError(
                        f"Room line {line.sequence} has no Room Type defined. Please specify a Room Type.")

                # Create a domain to fetch available rooms of the same type
                domain = [
                    ('company_id', '=', self.env.company.id),
                    ('id', 'not in', booked_room_ids + list(assigned_room_ids)),
                    # Match room type
                    ('room_type_name', '=', line.hotel_room_type.id)
                ]

                # Search for available rooms matching the domain
                available_rooms = self.env['hotel.room'].search(domain)

                if available_rooms:
                    # Check if the room is in a block state
                    for room in available_rooms:
                        if room.status == 'block':
                            raise ValidationError(
                                f"Room '{room.name}' is in a 'block' state and cannot be assigned."
                            )
                    # Assign the first available room to the line
                    assigned_room = available_rooms[0]
                    line.room_id = assigned_room.id
                    # Track assigned room
                    assigned_room_ids.add(assigned_room.id)
                    assigned_count += 1
                else:
                    # Add line to unassignable list
                    unassignable_lines.append(line)

            # If there are unassignable lines, raise an error
            if unassignable_lines:
                unassigned_count = len(unassignable_lines)
                raise UserError(
                    f"Only {assigned_count} rooms were assigned out of {len(booking.room_line_ids)} requested. "
                    f"{unassigned_count} room(s) could not be assigned due to unavailability."
                )

            # Ensure recomputation of state fields
            booking.room_line_ids._compute_state()

            # Update any related information
            # self._update_adults_with_assigned_rooms(booking)

            booking._compute_show_in_tree()

    # def action_assign_all_rooms(self):
    #     """Assign unique available rooms to each line based on Room Type."""

    #     for booking in self:
    #     #     available_with_ob, available_without_ob = self._calculate_available_rooms(
    #     #     company_id=booking.company_id.id,
    #     #     checkin_date=booking.checkin_date,
    #     #     checkout_date=booking.checkout_date,
    #     #     adult_count=0,
    #     #     hotel_room_type_id=booking.hotel_room_type.id,
    #     #     room_types_dict={}
    #     # )

    #     #     requested_rooms = booking.room_count
    #     #     print("requested_rooms", requested_rooms, "available_without_ob", available_without_ob, "available_with_ob", available_with_ob)

    #     #     # Only compare against "without" overbooking
    #     #     if requested_rooms > available_without_ob:
    #     #         raise ValidationError(_(
    #     #             "Cannot assign rooms. You've requested a total of %d rooms, "
    #     #             "but only %d rooms are available (without overbooking) in the given date range."
    #     #         ) % (requested_rooms, available_without_ob))

    #     #         break

    #         if booking.state != 'confirmed':
    #             raise UserError(
    #                 "Rooms can only be assigned when the booking is in the 'Confirmed' state.")

    #         if not booking.room_line_ids:
    #             raise UserError("No room lines to assign rooms to.")

    #         # Get room ids of rooms booked in the date range
    #         booked_room_lines = self.env['room.booking.line'].search([
    #             ('room_id', '!=', False),
    #             ('checkin_date', '<', booking.checkout_date),
    #             ('checkout_date', '>', booking.checkin_date)
    #         ])
    #         booked_room_ids = booked_room_lines.mapped('room_id').ids

    #         # Keep track of already assigned rooms
    #         assigned_room_ids = set()

    #         # Process each line and assign a unique room
    #         for line in booking.room_line_ids:
    #         # for line in booking.room_line_ids.filtered(lambda l: not l.room_id):
    #             if not line.hotel_room_type:  # Ensure the room line has a Room Type
    #                 raise UserError(f"Room line {line.sequence} has no Room Type defined. Please specify a Room Type.")

    #             # Create a domain to fetch available rooms of the same type
    #             domain = [
    #                 ('comapny_id', '=', self.env.company.id),
    #                 ('id', 'not in', booked_room_ids + list(assigned_room_ids)),
    #                 ('room_type_name', '=', line.hotel_room_type.id)  # Match room type
    #             ]

    #             # Search for available rooms matching the domain
    #             available_rooms = self.env['hotel.room'].search(domain)

    #             if not available_rooms:
    #                 # raise UserError(f"No available rooms found for Room Type: {line.hotel_room_type}.")
    #                 raise UserError(f"No available rooms found for Room Type: {line.hotel_room_type}. Total available rooms: {len(available_rooms)}.")

    #             # Assign the first available room to the line
    #             assigned_room = available_rooms[0]
    #             line.room_id = assigned_room.id
    #             assigned_room_ids.add(assigned_room.id)  # Track assigned room

    #         # Ensure recomputation of state fields
    #         booking.room_line_ids._compute_state()

    #         # Update any related information
    #         self._update_adults_with_assigned_rooms(booking)

    #         booking._compute_show_in_tree()

    def action_clear_rooms(self):
        print('inside clear')
        clear_search_results = self.env.context.get(
            'clear_search_results', False)

        for booking in self:
            # Unlink all room lines associated with this booking
            booking.room_line_ids.unlink()
            booking.adult_ids.unlink()
            booking.child_ids.unlink()
            booking.infant_ids.unlink()
            # booking.rate_forecast_ids.unlink()
            booking.write({'posting_item_ids': [(5, 0, 0)]})
            self.env['room.rate.forecast'].search(
                [('room_booking_id', '=', booking.id)]).unlink()

            # Clear search results only if the flag is True
            # if clear_search_results:
            search_results = self.env['room.availability.result'].search(
                [('room_booking_id', '=', booking.id)])
            if search_results:
                search_results.unlink()
                print('6750', search_results)
            booking.write({'state': 'not_confirmed'})
        print('outside clear')

    def action_split_rooms(self):
        for booking in self:
            # Retrieve related room.availability.result records
            availability_results = self.env['room.availability.result'].search(
                [('room_booking_id', '=', booking.id)]
            )

            # Ensure we have availability results to process
            if not availability_results:
                raise UserError(
                    "You have to Search room first then you can split room.")

            all_split = all(
                result.split_flag for result in availability_results)
            if all_split:
                raise UserError(
                    "All rooms have already been split. No new rooms to split.")

            room_line_vals = []
            counter = 1
            adult_inserts = []
            child_inserts = []
            infant_inserts = []
            max_counter = max(booking.room_line_ids.mapped(
                'counter') or [0])  # Use 0 if no lines exist
            counter = max_counter + 1  # Start from the next counter value
            print('Max Counter:', max_counter, 'New Counter:', counter)

            partner_name = booking.partner_id.name or ""
            name_parts = partner_name.split()  # Split the name by spaces
            # first_name = name_parts[0] if len(name_parts) > 0 else ""
            # last_name = name_parts[1] if len(name_parts) > 1 else ""
            # Assign first and last names
            first_name = name_parts[0] if name_parts else ""  # First part as first_name
            last_name = name_parts[-1] if len(name_parts) > 1 else ""  # Last part as last_name

            # Loop through each availability result and process room lines
            for result in availability_results:
                # Check if this record has already been split
                if result.split_flag:
                    continue  # Skip this record if already split

                rooms_reserved_count = int(result.rooms_reserved) if isinstance(
                    result.rooms_reserved, str) else result.rooms_reserved

                # Create room lines
                for _ in range(rooms_reserved_count):
                    new_booking_line = {
                        'room_id': False,  # Room can be assigned later
                        'checkin_date': booking.checkin_date,
                        'checkout_date': booking.checkout_date,
                        'uom_qty': 1,
                        'adult_count': booking.adult_count,
                        'child_count': booking.child_count,
                        'infant_count': booking.infant_count,
                        'hotel_room_type': result.room_type.id,
                        'counter': counter,
                    }
                    counter += 1
                    room_line_vals.append((0, 0, new_booking_line))

                # Append new adult records for this room
                total_adults_needed = rooms_reserved_count * booking.adult_count
                for _ in range(total_adults_needed):
                    adult_inserts.append((
                        booking.id,
                        result.room_type.id,
                        first_name, last_name, '', '', '', '', '', '', '', '', '',  # Empty fields
                    ))

                # Append new child records for this room
                total_children_needed = rooms_reserved_count * booking.child_count
                for _ in range(total_children_needed):
                    child_inserts.append((
                        booking.id,
                        result.room_type.id,
                        '', '', '', '', '', '', '', '', '', '', '',  # Empty fields
                    ))

                # Append new infant records for this room
                total_infants_needed = rooms_reserved_count * booking.infant_count
                for _ in range(total_infants_needed):
                    infant_inserts.append((
                        booking.id,
                        result.room_type.id,
                        '', '', '', '', '', '', '', '', '', '', '',  # Empty fields
                    ))

                # Mark this record as split
                result.split_flag = True

            # Perform bulk insert for adults
            if adult_inserts:
                insert_query_adults = """
                    INSERT INTO reservation_adult (
                        reservation_id, room_type_id, first_name, last_name, profile, nationality,
                        passport_number, id_number, visa_number, id_type, phone_number, relation, create_date
                    ) VALUES %s
                """
                self._bulk_insert(insert_query_adults, adult_inserts)

            # Perform bulk insert for children
            if child_inserts:
                insert_query_children = """
                    INSERT INTO reservation_child (
                        reservation_id, room_type_id, first_name, last_name, profile, nationality,
                        passport_number, id_number, visa_number, id_type, phone_number, relation, create_date
                    ) VALUES %s
                """
                self._bulk_insert(insert_query_children, child_inserts)

            # Perform bulk insert for infants
            if infant_inserts:
                self._bulk_insert("""
                    INSERT INTO reservation_infant (
                        reservation_id, room_type_id, first_name, last_name, profile, nationality,
                        passport_number, id_number, visa_number, id_type, phone_number, relation, create_date
                    ) VALUES %s
                """, infant_inserts)

            # Write room lines to the booking's room_line_ids
            if room_line_vals:
                booking.write({'room_line_ids': room_line_vals})

            self._update_adults_with_assigned_rooms_split_rooms(
                booking, max_counter)

    def _update_adults_with_assigned_rooms_split_rooms(self, booking, counter):
        """Update Adults with the assigned rooms from room_line_ids and set room sequence."""
        adult_count = 0
        child_count = 0
        infant_count = 0
        room_sequence_map = {}  # Dictionary to track the sequence for each room type and room
        ctr = counter + 1
        max_counter = counter + 1
        for line in booking.room_line_ids:
            if line.counter < max_counter:
                adult_count += line.adult_count
                child_count += line.child_count
                infant_count += line.infant_count
                continue
            for _ in range(line.adult_count):
                if adult_count < len(booking.adult_ids):
                    # print('4832', adult_count, len(booking.adult_ids))
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the adult
                    booking.adult_ids[adult_count].room_sequence = line.counter
                    booking.adult_ids[adult_count].room_type_id = line.hotel_room_type.id
                    booking.adult_ids[adult_count].room_id = line.room_id.id
                    adult_count += 1

            for _ in range(line.child_count):
                if child_count < len(booking.child_ids):
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.child_ids[child_count].room_sequence = line.counter
                    booking.child_ids[child_count].room_type_id = line.hotel_room_type.id
                    booking.child_ids[child_count].room_id = line.room_id.id
                    child_count += 1

            for _ in range(line.infant_count):
                if infant_count < len(booking.infant_ids):
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.infant_ids[infant_count].room_sequence = line.counter
                    booking.infant_ids[infant_count].room_type_id = line.hotel_room_type.id
                    booking.infant_ids[infant_count].room_id = line.room_id.id
                    infant_count += 1
            ctr += 1

    def _bulk_insert(self, query, values):
        from psycopg2.extras import execute_values
        cleaned_values = []

        # Replace empty strings with NULL for integer fields
        for value in values:
            cleaned_value = tuple(v if v != '' else None for v in value)
            cleaned_values.append(cleaned_value)

        if cleaned_values:
            execute_values(self.env.cr, query, cleaned_values,
                           template=None, page_size=100)
            self.env.cr.commit()

    def _update_adults_with_assigned_rooms(self, booking):
        """Update Adults with the assigned rooms from room_line_ids and set room sequence."""
        adult_count = 0
        child_count = 0
        infant_count = 0
        room_sequence_map = {}  # Dictionary to track the sequence for each room type and room
        ctr = 1

        for line in booking.room_line_ids:
            for _ in range(line.adult_count):
                if adult_count < len(booking.adult_ids):
                    print('4832', adult_count, len(booking.adult_ids))
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the adult
                    booking.adult_ids[adult_count].room_sequence = ctr
                    booking.adult_ids[adult_count].room_type_id = line.hotel_room_type.id
                    booking.adult_ids[adult_count].room_id = line.room_id.id
                    adult_count += 1

            for _ in range(line.child_count):
                if child_count < len(booking.child_ids):
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.child_ids[child_count].room_sequence = ctr
                    booking.child_ids[child_count].room_type_id = line.hotel_room_type.id
                    booking.child_ids[child_count].room_id = line.room_id.id
                    child_count += 1

            for _ in range(line.infant_count):
                if infant_count < len(booking.infant_ids):
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.infant_ids[infant_count].room_sequence = ctr
                    booking.infant_ids[infant_count].room_type_id = line.hotel_room_type.id
                    booking.infant_ids[infant_count].room_id = line.room_id.id
                    infant_count += 1

            ctr += 1

    def action_search_rooms(self):
        max_num_person = self.env['hotel.room'].search(
            [], order='num_person desc', limit=1).num_person

        all_num_persons = self.env['hotel.room'].search(
            []).mapped('num_person')
        # print("all_num_persons", all_num_persons)

        for record in self:
            if record.parent_booking_name and len(record.room_line_ids) == 1 and record.state == 'confirmed':
                raise ValidationError(
                    f"The booking '{record.name}' has already been split. You are not allowed to change the room."
                )

            if max_num_person == 0:
                raise ValidationError(
                    f"No room is configured for this company {record.company_id.name}. Please configure at least one room.")

            # if max_num_person > 0 and record.adult_count > max_num_person:
            #     raise ValidationError(f"The maximum allowed number of persons per room is {max_num_person}. Please reduce the number of adults.")
            if record.adult_count > 99:
                raise ValidationError(
                    f"The maximum allowed number of persons per room is 99. Please reduce the number of adults.")

            # if record.adult_count not in all_num_persons:
            #     raise ValidationError(f"There is no room available for the specified adult count: {record.adult_count}")

            if record.room_count <= 0 or record.adult_count <= 0:
                raise ValidationError(
                    "Room count and adult count cannot be zero or less. Please select at least one room and one adult.")

            record._get_forecast_rates()
            result = record.check_room_availability_all_hotels_split_across_type(
                record.checkin_date,
                record.checkout_date,
                record.room_count,
                record.adult_count,
                record.hotel_room_type.id if record.hotel_room_type else None
            )

            # If result is a tuple, unpack it
            if isinstance(result, tuple) and len(result) == 2:
                total_available_rooms, results = result
            else:
                raise ValueError(
                    "Expected a tuple with 2 elements, but got:", result)

            # Handle action dictionary directly if insufficient rooms
            if isinstance(results, list) and len(results) == 1 and isinstance(results[0], dict) and results[0].get(
                    'type') == 'ir.actions.act_window':
                return results[0]

            # Validate results as a list of dictionaries
            if not isinstance(results, list):
                raise ValueError(
                    "Expected a list of dictionaries, but got:", results)

            # Calculate total rooms reserved
            total_reserved_rooms = sum(
                [res['rooms_reserved'] for res in record.availability_results])
            requested_rooms = record.room_count

            if total_reserved_rooms + requested_rooms > total_available_rooms:  # Check if enough rooms are available
                raise ValidationError(
                    "Only {} rooms are available.".format(total_available_rooms - total_reserved_rooms))

            # Process valid results if rooms are available
            result_lines = []
            for res in results:
                if not isinstance(res, dict):
                    raise ValueError(f"Expected a dictionary, but got: {res}")
                available_rooms = int(res.get('available_rooms', 0))
                if available_rooms:
                    result_lines.append((0, 0, {
                        'company_id': res['company_id'],
                        'room_type': res['room_type'],
                        # 'pax': res['pax'],
                        'rooms_reserved': res['rooms_reserved'],
                        'available_rooms': res['available_rooms']
                    }))

            # Write results to availability_results and mark search_done
            # record.write({'availability_results': result_lines, 'rooms_searched': True})
            # record.flush(['availability_results', 'rooms_searched'])  # Ensure changes are written to the database

            # Write results to availability_results field
            record.write({'availability_results': result_lines})

    room_count_tree = fields.Integer(
        string="Room Count", store=False)

    room_count_tree_ = fields.Char(
        string="Remaining Room Count", compute="_compute_room_count", store=False)

    @api.depends("room_line_ids")
    def _compute_room_count(self):
        for record in self:
            false_room_count = len(record.room_line_ids.filtered(
                lambda line: not line.room_id))
            record.room_count_tree_ = str(
                false_room_count) if false_room_count > 0 else ''

    @api.onchange('room_line_ids')
    def _onchange_room_id(self):
        if self.env.context.get('skip_code_validation'):
            return
        # Populate available rooms in the dropdown list when user clicks the Room field
        if not self.is_button_clicked:
            return {'domain': {'room_id': [('id', 'in', [])]}}

        new_rooms = self._find_rooms_for_capacity()
        room_ids = new_rooms.mapped('id') if new_rooms else []
        return {'domain': {'room_id': [('id', 'in', room_ids)]}}

    # @api.onchange('room_count', 'adult_count', 'child_count')
    # def _onchange_room_or_adult_count(self):
    #     for record in self:
    #         if record.room_count < 0:
    #             pass
    #             # raise ValidationError("Kindly select at least one room for room booking.")

    #         # Calculate the required number of adults and children
    #         total_adults_needed = record.room_count * record.adult_count
    #         total_children_needed = record.room_count * record.child_count

    #         # Prepare adults
    #         current_adults = len(record.adult_ids)
    #         if total_adults_needed > current_adults:
    #             for _ in range(total_adults_needed - current_adults):
    #                 record.adult_ids += self.env['reservation.adult'].new({'reservation_id': record.id})
    #         elif total_adults_needed < current_adults:
    #             record.adult_ids = record.adult_ids[:total_adults_needed]

    #         # Prepare children
    #         current_children = len(record.child_ids)
    #         if total_children_needed > current_children:
    #             for _ in range(total_children_needed - current_children):
    #                 record.child_ids += self.env['reservation.child'].new({'reservation_id': record.id})
    #         elif total_children_needed < current_children:
    #             record.child_ids = record.child_ids[:total_children_needed]

    def increase_room_count(self):
        for record in self:
            # Increment room count
            record.room_count += 1

            # Calculate the required number of adults and children
            total_adults_needed = record.room_count * record.adult_count
            total_children_needed = record.room_count * record.child_count

            # Manage adults
            current_adults = len(record.adult_ids)
            if total_adults_needed > current_adults:
                # Add missing adult records
                for _ in range(total_adults_needed - current_adults):
                    self.env['reservation.adult'].create(
                        {'reservation_id': record.id})
            elif total_adults_needed < current_adults:
                # Remove extra adult records
                extra_adults = record.adult_ids[current_adults -
                                                total_adults_needed:]
                extra_adults.unlink()

            # Manage children
            current_children = len(record.child_ids)
            if total_children_needed > current_children:
                # Add missing child records
                for _ in range(total_children_needed - current_children):
                    self.env['reservation.child'].create(
                        {'reservation_id': record.id})
            elif total_children_needed < current_children:
                # Remove extra child records
                extra_children = record.child_ids[current_children -
                                                  total_children_needed:]
                extra_children.unlink()

    def decrease_room_count(self):
        for record in self:
            if record.room_count > 1:
                record.room_count -= 1

    def action_remove_room(self):
        """Remove the last added room from the booking"""
        self.ensure_one()
        if self.room_line_ids:
            last_room = self.room_line_ids[-1]
            # Reset the room status to available
            if last_room.room_id:
                last_room.room_id.write({'status': 'available'})
            # Remove the room line
            last_room.unlink()
            # Update room count
            if self.room_count > len(self.room_line_ids):
                self.room_count = len(self.room_line_ids)
                self.rooms_to_add = 0

    def increase_adult_count(self):
        for record in self:
            record.adult_count += 1
            # Add a new adult when count increases
            self.env['reservation.adult'].create({'reservation_id': record.id})

    def decrease_adult_count(self):
        for record in self:
            if record.adult_count > 1:
                if record.adult_ids:
                    last_adult = record.adult_ids[-1]
                    last_adult.unlink()  # Remove last adult record
                record.adult_count -= 1

    def increase_child_count(self):
        for record in self:
            record.child_count += 1
            self.env['reservation.child'].create({'reservation_id': record.id})

    def decrease_child_count(self):
        for record in self:
            if record.child_count > 0:
                # Archive the last child record instead of deleting it
                if record.child_ids:
                    last_child = record.child_ids[-1]
                    last_child.unlink()  # Archive the last child's record
                record.child_count -= 1


class RoomWaitingList(models.Model):
    _name = 'room.waiting.list'
    _description = 'Room Waiting List'

    partner_id = fields.Many2one('res.partner', string='Customer')
    checkin_date = fields.Datetime(string='Desired Check In', required=True)
    checkout_date = fields.Datetime(string='Desired Check Out', required=True)
    room_type_id = fields.Many2one('room.type', string='Room Type')
    num_rooms = fields.Integer(string='Number of Rooms', required=True)
    state = fields.Selection([
        ('waiting', 'Waiting'),
        ('notified', 'Notified'),
    ], default='waiting')


class HotelChildAge(models.Model):
    _name = 'hotel.child.age'
    _description = 'Children Age'

    age = fields.Selection(
        [(str(i), str(i)) for i in range(1, 18)],  # Ages from 1 to 17
        string='Age'
    )
    booking_id = fields.Many2one('room.booking', string='Booking')

    child_label = fields.Char(string='Child Label',
                              compute='_compute_child_label', store=True)

    @api.depends('booking_id.child_ages')
    def _compute_child_label(self):
        for record in self:
            if record.booking_id:
                # Safely try to get the index
                child_ids = record.booking_id.child_ages.ids
                if record.id in child_ids:
                    index = child_ids.index(record.id) + 1
                    record.child_label = f'Child {index}'
                else:
                    record.child_label = 'Child'


class ReservationAdult(models.Model):
    _name = 'reservation.adult'
    _description = 'Reservation Adult'

    room_sequence = fields.Integer(string="Room Sequence")
    first_name = fields.Char(string='First Name', required=True)
    last_name = fields.Char(string='Last Name')
    profile = fields.Char(string='Profile')
    nationality = fields.Many2one('res.country', string='Nationality')
    birth_date = fields.Date(string='Birth Date')
    passport_number = fields.Char(string='Passport No.')
    id_number = fields.Char(string='ID Number')
    visa_number = fields.Char(string='Visa Number')
    id_type = fields.Char(string='ID Type')
    phone_number = fields.Char(string='Phone Number')
    relation = fields.Char(string='Relation')

    # Link to the main reservation
    reservation_id = fields.Many2one('room.booking', string='Reservation')
    room_type_id = fields.Many2one('room.type', string='Room Type')
    room_id = fields.Many2one(
        'hotel.room', string='Room', help='Room assigned to the adult guest')


class ReservationChild(models.Model):
    _name = 'reservation.child'
    _description = 'Reservation Child'

    room_sequence = fields.Integer(string="Room Sequence")
    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    profile = fields.Char(string='Profile')
    nationality = fields.Many2one('res.country', string='Nationality')
    birth_date = fields.Date(string='Birth Date')
    passport_number = fields.Char(string='Passport No.')
    id_type = fields.Char(string='ID Type')
    id_number = fields.Char(string='ID Number')
    visa_number = fields.Char(string='Visa Number')
    type = fields.Selection(
        [('visitor', 'Visitor'), ('resident', 'Resident')], string='Type')
    phone_number = fields.Char(string='Phone Number')
    relation = fields.Char(string='Relation')

    # Link to the main reservation
    reservation_id = fields.Many2one('room.booking', string='Reservation')
    room_type_id = fields.Many2one('room.type', string='Room Type')
    room_id = fields.Many2one(
        'hotel.room', string='Room', help='Room assigned to the adult guest')


class ReservationInfant(models.Model):
    _name = 'reservation.infant'
    _description = 'Reservation Infant'

    room_sequence = fields.Integer(string="Room Sequence")
    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    profile = fields.Char(string='Profile')
    nationality = fields.Many2one('res.country', string='Nationality')
    birth_date = fields.Date(string='Birth Date')
    passport_number = fields.Char(string='Passport No.')
    id_type = fields.Char(string='ID Type')
    id_number = fields.Char(string='ID Number')
    visa_number = fields.Char(string='Visa Number')
    type = fields.Selection(
        [('visitor', 'Visitor'), ('resident', 'Resident')], string='Type')
    phone_number = fields.Char(string='Phone Number')
    relation = fields.Char(string='Relation')

    # Link to the main reservation
    reservation_id = fields.Many2one('room.booking', string='Reservation')
    room_type_id = fields.Many2one('room.type', string='Room Type')
    room_id = fields.Many2one(
        'hotel.room', string='Room', help='Room assigned to the adult guest')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_vip = fields.Boolean(
        string="VIP", help="Mark this contact as a VIP", tracking=True)
    vip_code = fields.Many2one('vip.code', string="VIP Code", tracking=True)

    @api.onchange('is_vip')
    def _onchange_is_vip(self):
        if not self.is_vip:
            self.vip_code = False

    rate_code = fields.Many2one('rate.code', string="Rate Code", tracking=True)
    source_of_business = fields.Many2one(
        'source.business', string="Source of Business", tracking=True)
    nationality = fields.Many2one(
        'res.country', string='Nationality', tracking=True)
    market_segments = fields.Many2one(
        'market.segment', string="Market Segment", tracking=True)
    meal_pattern = fields.Many2one(
        'meal.pattern', string="Meal Pattern", tracking=True, required=True)
    max_pax = fields.Integer(string="Max Room", tracking=True)

    hashed_password = fields.Char(string="Hashed Password")

    @api.model
    def set_password(self, password):
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        self.hashed_password = hashed.decode('utf-8')

    def check_password(self, password):
        if self.hashed_password:
            return bcrypt.checkpw(password.encode('utf-8'), self.hashed_password.encode('utf-8'))
        return False

    reservation_count = fields.Integer(
        string="Reservations",
        compute='_compute_reservation_count',
        store=False
    )

    def _compute_reservation_count(self):
        for partner in self:
            partner.reservation_count = self.env['room.booking'].search_count(
                [('partner_id', '=', partner.id)])

    def action_view_reservations(self):
        return {
            'name': 'Reservations',
            'type': 'ir.actions.act_window',
            'res_model': 'room.booking',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'target': 'current',
        }

    group_booking_ids = fields.Many2many('group.booking', string='Group Bookings',
                                         compute='_compute_group_booking_count')
    group_booking_count = fields.Integer(
        string='Group Booking Count', compute='_compute_group_booking_count')

    @api.depends('group_booking_ids')
    def _compute_group_booking_count(self):
        for partner in self:
            group_booking_records = self.env['group.booking'].search([
                ('company', '=', partner.id)
            ])
            partner.group_booking_ids = group_booking_records
            partner.group_booking_count = len(group_booking_records)

    def action_view_group_bookings(self):
        self.ensure_one()
        return {
            'name': 'Group Bookings',
            'type': 'ir.actions.act_window',
            'res_model': 'room.booking',
            'view_mode': 'tree,form',
            'domain': [('group_booking', 'in', self.group_booking_ids.ids)],
            'target': 'current',
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    posting_item_id = fields.Many2one(
        'posting.item', string="Posting Item",
        required=True, help="Select the posting item."
    )
    posting_description = fields.Char(
        string="Description",
        # related='posting_item_id.description',  # Related to posting.item.description
        readonly=True,
    )
    posting_default_value = fields.Float(
        string="Default Value",
        # related='posting_item_id.default_value',  # Related to posting.item.default_value
        readonly=True,
    )


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    rate_code_ids = fields.One2many(
        'rate.code', 'pricelist_id', string="Rate Codes")


class RateCodeInherit(models.Model):
    _inherit = 'rate.code'

    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', ondelete='cascade')


class SystemDate(models.Model):
    _inherit = 'res.company'

    @api.model
    def create(self, vals):
        # Print the input values for the company
        print("Creating company with values:", vals)

        # Create the company record
        company = super(SystemDate, self).create(vals)

        # Prepare sequence data
        sequence_data = {
            'name': f"{company.name}",
            'code': f"room.booking",
            'company_id': company.id,
            'prefix': '',
            'padding': 5,
            'number_increment': 1,
        }

        # Print the sequence data before creation
        print("Creating sequence with values:", sequence_data)

        # Create a sequence for the new company
        self.env['ir.sequence'].create(sequence_data)

        # Print confirmation after sequence creation
        print(
            f"Sequence created for company {company.name} (ID: {company.id})")

        return company

    owner = fields.Char(string='Owner')
    system_date = fields.Datetime(string="System Date")
    inventory_ids = fields.One2many(
        'hotel.inventory', 'company_id', string="Inventory")
    age_threshold = fields.Integer(string="Age Threshold")  #

    # data fields for hotel web
    web_title = fields.Char(string="Title", help="Title of the Hotel")
    web_star_rating = fields.Integer(
        string="Star Rating", help="Star rating of the hotel")
    # web_kaaba_view = fields.Boolean(string="Kaaba view", default=False, help="is Kaaba visible from the hotel")
    web_kaaba_view = fields.Selection(
        selection=[
            ('full_kaaba_view', 'Full Kaaba View'),
            ('partial_kaaba_view', 'Partial Kaaba View'),
            ('no_kaaba_view', 'No Kaaba View')
        ],
        string="Kaaba View",
        default='no_kaaba_view',
        help="Indicates the type of Kaaba view available from the hotel."
    )

    web_hotel_location = fields.Char(
        string="Hotel location", help="Location of the hotel")
    web_description = fields.Text(
        string="Hotel description", help="Description of the hotel")
    web_discount = fields.Float(
        string="Discount", help="General discount given to hotel customers")
    web_review = fields.Float(string="Guest review",
                              help="Guest review of the hotel")
    web_payment = fields.Float(
        string="Payment", help="Payment value", default=0.0)
    rate_code = fields.Many2one('rate.code', string="Rate Codes")
    source_business = fields.Many2one(
        'source.business', string="Source of Business")

    @api.constrains('web_star_rating')
    def _check_star_rating(self):
        for record in self:
            if record.web_star_rating < 1 or record.web_star_rating > 5:
                raise ValidationError("Star Rating must be between 1 and 5.")

    @api.constrains('web_discount')
    def _check_discount(self):
        for record in self:
            if record.web_discount < 1 or record.web_discount > 100:
                raise ValidationError("Discount must be between 1 and 100.")

    @api.constrains('web_payment')
    def _check_payment(self):
        for record in self:
            if record.web_payment < 1 or record.web_payment > 100:
                raise ValidationError("Payment must be between 1 and 100.")


class HotelInventory(models.Model):
    _name = 'hotel.inventory'
    _description = 'Hotel Inventory'
    _table = 'hotel_inventory'  # This should match the database table name

    # image = fields.Image(string="Image", max_width=128, max_height=128)
    image = fields.Binary(string='Image', attachment=True)
    hotel_name = fields.Integer(string="Hotel Name")
    room_type = fields.Many2one('room.type', string="Room Type")
    total_room_count = fields.Integer(string="Total Room Count")
    pax = fields.Integer(string="Pax")
    age_threshold = fields.Integer(string="Age Threshold")
    web_allowed_reservations = fields.Integer(
        string="Web Allowed Reservations")
    overbooking_allowed = fields.Boolean(string="Overbooking Allowed")
    overbooking_rooms = fields.Integer(string="Overbooking Rooms")
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company)


class RoomAvailabilityResult(models.Model):
    _name = 'room.availability.result'
    _description = 'Room Availability Result'

    room_booking_id = fields.Many2one(
        'room.booking', string="Room Booking", ondelete="cascade")
    company_id = fields.Many2one('res.company', string="Company")
    room_type = fields.Many2one('room.type', string="Room Type")
    pax = fields.Integer(string="Adults")
    rooms_reserved = fields.Integer(string="Searched Rooms Count")
    available_rooms = fields.Integer(string="Available Rooms")
    split_flag = fields.Boolean(string='Split Flag', default=False)

    # def action_delete_selected(self):
    #     for record in self:
    #         record.unlink()  # Deletes the current record

    def action_delete_selected(self):
        for record in self:
            # Ensure the availability record is linked to a booking
            if record.room_booking_id:
                # Search for related room lines specific to the availability record
                related_room_lines = self.env['room.booking.line'].search([
                    ('booking_id', '=', record.room_booking_id.id),
                    ('hotel_room_type', '=', record.room_type.id)
                ])

                # Check for conflicts: assigned room_id or state == 'confirmed'
                conflicting_lines = related_room_lines.filtered(
                    lambda line: line.room_id or line.state == 'confirmed'
                )

                if conflicting_lines:
                    # Prepare detailed error message
                    assigned_rooms = conflicting_lines.filtered(
                        lambda line: line.room_id).mapped('room_id.name')
                    assigned_room_names = ', '.join(
                        assigned_rooms) if assigned_rooms else "None"
                    has_confirmed = any(
                        line.state == 'confirmed' for line in conflicting_lines)

                    error_message = "Cannot delete this record because:"
                    if assigned_rooms:
                        error_message += f" the following rooms are already assigned: {assigned_room_names}."
                    if has_confirmed:
                        error_message += " Booking is in the 'confirmed' state."

                    raise ValidationError(error_message)

                # If no conflicts, delete the specific related room lines
                related_room_lines.unlink()

            # Delete the specific availability record
            record.unlink()

    def get_max_counter(self, booking_id):
        # Search for room booking lines related to the given booking ID
        room_lines = self.env['room.booking.line'].search(
            [('booking_id', '=', booking_id)])

        # If no lines are found, return 0
        if not room_lines:
            return 0

        # Get the maximum value of the 'counter' field
        max_counter = max(room_lines.mapped('counter'))
        return max_counter

    # def update_counter_res_search(self,booking):
    #     adult_count = 0
    #     room_sequence_map = {}  # Dictionary to track the sequence for each room type and room
    #     ctr = 1
    #     print("line 4712", self.id, booking.room_booking_id)
    #     for line in booking.room_booking_id.room_line_ids:
    #         for _ in range(line.adult_count):
    #             if adult_count < len(booking.room_booking_id.adult_ids):
    #                 # Get or initialize the sequence for the room
    #                 room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
    #                 if room_key not in room_sequence_map:
    #                     room_sequence_map[room_key] = len(room_sequence_map) + 1  # Increment sequence

    #                 # Update the room_sequence, room_type, and room_id for the adult
    #                 booking.room_booking_id.adult_ids[adult_count].room_sequence = ctr
    #                 booking.room_booking_id.adult_ids[adult_count].room_type_id = line.hotel_room_type.id
    #                 booking.room_booking_id.adult_ids[adult_count].room_id = line.room_id.id
    #                 adult_count += 1
    #         ctr += 1

    def update_counter_res_search(self, booking):
        adult_count = 0
        child_count = 0
        infant_count = 0
        room_sequence_map = {}  # Dictionary to track the sequence for each room type and room
        ctr = 1

        for line in booking.room_booking_id.room_line_ids:
            # Update adults
            for _ in range(line.adult_count):
                if adult_count < len(booking.room_booking_id.adult_ids):
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the adult
                    booking.room_booking_id.adult_ids[adult_count].room_sequence = ctr
                    booking.room_booking_id.adult_ids[adult_count].room_type_id = line.hotel_room_type.id
                    booking.room_booking_id.adult_ids[adult_count].room_id = line.room_id.id
                    adult_count += 1

            # Update children
            for _ in range(line.child_count):
                if child_count < len(booking.room_booking_id.child_ids):
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.room_booking_id.child_ids[child_count].room_sequence = ctr
                    booking.room_booking_id.child_ids[child_count].room_type_id = line.hotel_room_type.id
                    booking.room_booking_id.child_ids[child_count].room_id = line.room_id.id
                    child_count += 1

            # Update infants
            for _ in range(line.infant_count):
                if infant_count < len(booking.room_booking_id.infant_ids):
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the infant
                    booking.room_booking_id.infant_ids[infant_count].room_sequence = ctr
                    booking.room_booking_id.infant_ids[infant_count].room_type_id = line.hotel_room_type.id
                    booking.room_booking_id.infant_ids[infant_count].room_id = line.room_id.id
                    infant_count += 1

            ctr += 1

    def action_split_selected(self):
        for record in self:
            rooms_reserved_count = int(record.rooms_reserved) if isinstance(
                record.rooms_reserved, str) else record.rooms_reserved

            # Ensure we have an existing room.booking record to add lines to
            if not record.room_booking_id:
                raise UserError(
                    "No room booking record found to add lines to.")

            # Check if the record is already split
            if record.split_flag:
                raise UserError("This record has already been split.")

            booking = record.room_booking_id
            room_line_vals = []
            max_counter = self.get_max_counter(booking.id)
            counter = max_counter + 1  # Start from the next counter value
            print('7748', counter)
            for _ in range(rooms_reserved_count):
                new_booking_line = {
                    'room_id': False,
                    'checkin_date': booking.checkin_date,
                    'checkout_date': booking.checkout_date,
                    'uom_qty': 1,
                    'adult_count': booking.adult_count,
                    'child_count': booking.child_count,
                    'infant_count': booking.infant_count,
                    'booking_id': record.id,
                    'hotel_room_type': record.room_type.id,
                    'counter': counter,
                }
                counter += 1

                room_line_vals.append((0, 0, new_booking_line))

            # Add room lines to the booking's room_line_ids
            booking.write({'room_line_ids': room_line_vals})

            # Mark the record as split
            record.split_flag = True
            self._update_adults_with_assigned_rooms_split_selected(
                record, max_counter + 1)

    def _update_adults_with_assigned_rooms_split_selected(self, booking, counter):
        """Update Adults and Children with the assigned rooms from room_line_ids and set room sequence."""
        availability_results = self.env['room.availability.result'].search(
            [('id', '=', self.id)]
        )

        if not availability_results:
            raise UserError(
                "You have to Search room first then you can split room.")

        room_line_vals = []
        ctr = 1
        partner_name = booking.room_booking_id.partner_id.name or ""
        # partner_name = booking.partner_id.name or ""
        name_parts = partner_name.split()  # Split the name by spaces
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        # booking_id = booking.room_booking_id  # Adjust if the related field is different

        # # Fetch max counter value from reservation.adult for the given booking_id
        # max_counter = max(self.env['reservation.adult'].search([('reservation_id', '=', booking_id.id)]).mapped('room_sequence') or [0])

        # print('7402 Max Counter:', max_counter, 'Booking ID:', booking_id.id, 'Booking Name:', booking_id.name)

        # counter = max_counter + 1  # Start from the next counter value
        # print('7402 New Counter:', counter)
        for result in availability_results:

            rooms_reserved_count = int(result.rooms_reserved) if isinstance(
                result.rooms_reserved, str) else result.rooms_reserved
            print('7417', rooms_reserved_count, ctr)

            # Create room lines
            for _ in range(rooms_reserved_count):
                new_booking_line = {
                    'room_id': False,
                    'checkin_date': booking.room_booking_id.checkin_date,
                    'checkout_date': booking.room_booking_id.checkout_date,
                    'uom_qty': 1,
                    'adult_count': booking.room_booking_id.adult_count,
                    'child_count': booking.room_booking_id.child_count,
                    'infant_count': booking.room_booking_id.infant_count,
                    'hotel_room_type': result.room_type.id,
                    'counter': ctr,
                }
                ctr += 1
                room_line_vals.append((0, 0, new_booking_line))

            print('7433', ctr, counter, rooms_reserved_count)
            # Create new adult records for this room
            for room_idx in range(rooms_reserved_count):
                for _ in range(booking.room_booking_id.adult_count):
                    self.env['reservation.adult'].create({
                        'reservation_id': booking.room_booking_id.id,
                        'room_type_id': result.room_type.id,
                        'room_sequence': room_idx + counter,
                        'first_name': first_name,
                        'last_name': last_name,
                        'profile': '',
                        'nationality': '',
                        'passport_number': '',
                        'id_number': '',
                        'visa_number': '',
                        'id_type': '',
                        'phone_number': '',
                        'relation': '',
                    })

            # Create new child records for this room
            for room_idx in range(rooms_reserved_count):
                for _ in range(booking.room_booking_id.child_count):
                    self.env['reservation.child'].create({
                        'reservation_id': booking.room_booking_id.id,
                        'room_type_id': result.room_type.id,
                        'room_sequence': room_idx + counter,
                        'first_name': '',
                        'last_name': '',
                        'profile': '',
                        'nationality': '',
                        'passport_number': '',
                        'id_number': '',
                        'visa_number': '',
                        'id_type': '',
                        'phone_number': '',
                        'relation': '',
                    })

            # Create new infant records for this room
            for room_idx in range(rooms_reserved_count):
                for _ in range(booking.room_booking_id.infant_count):
                    self.env['reservation.infant'].create({
                        'reservation_id': booking.room_booking_id.id,
                        'room_type_id': result.room_type.id,
                        'room_sequence': room_idx + counter,
                        'first_name': '',
                        'last_name': '',
                        'profile': '',
                        'nationality': '',
                        'passport_number': '',
                        'id_number': '',
                        'visa_number': '',
                        'id_type': '',
                        'phone_number': '',
                        'relation': '',
                    })

            # Mark this record as split
            result.split_flag = True

        self.update_counter_res_search(booking)

    # WORKING 27/12
    # def action_split_selected(self):
    #     for record in self:
    #         rooms_reserved_count = int(record.rooms_reserved) if isinstance(
    #             record.rooms_reserved, str) else record.rooms_reserved
    #         print("rooms_reserved_count", rooms_reserved_count)

    #         # Ensure we have an existing room.booking record to add lines to
    #         if not record.room_booking_id:
    #             raise UserError("No room booking record found to add lines to.")

    #         # Check if the record is already split
    #         if record.split_flag:
    #             raise UserError("This record has already been split.")

    #         booking = record.room_booking_id
    #         room_line_vals = []
    #         max_counter = self.get_max_counter(booking.id)
    #         counter = max_counter + 1  # Start from the next counter value
    #         for _ in range(rooms_reserved_count):
    #             new_booking_line = {
    #                 'room_id': False,
    #                 'checkin_date': booking.checkin_date,
    #                 'checkout_date': booking.checkout_date,
    #                 'uom_qty': 1,
    #                 'adult_count': record.pax,
    #                 'child_count': 0,
    #                 'infant_count': 0,
    #                 'booking_id': record.id,
    #                 'hotel_room_type': record.room_type.id,
    #                 'counter': counter,
    #             }
    #             counter += 1
    #             room_line_vals.append((0, 0, new_booking_line))

    #         # Add room lines to the booking's room_line_ids
    #         booking.write({'room_line_ids': room_line_vals})

    #         # Mark the record as split
    #         record.split_flag = True
    #         self._update_adults_with_assigned_rooms_selected(record)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    website_name = fields.Char(string="Website Name")
    website_url = fields.Char(string="Website URL")
    max_rooms = fields.Integer(string="Max Rooms")


class RoomAvailabilityWizard(models.TransientModel):
    _name = 'room.availability.wizard'
    _description = 'Room Availability Wizard'

    room_booking_id = fields.Many2one('room.booking', string='Booking')
    message = fields.Html(readonly=True)

    html_message = fields.Html(
        string='Formatted Message', compute='_compute_html_message', sanitize=False)

    @api.depends('message')
    def _compute_html_message(self):
        for wizard in self:
            wizard.html_message = wizard.message

    def action_send_to_waiting(self):
        """Move the booking to Waiting List state."""
        self.room_booking_id.state = 'waiting'


class BookingCheckinWizard(models.TransientModel):
    _name = 'booking.checkin.wizard'
    _description = 'Check-in Confirmation Wizard'

    booking_ids = fields.Many2many(
        'room.booking', string='Booking', required=True)

    def action_confirm_checkin(self):
        """ Action to confirm check-in for all selected bookings and set check-in date to today """
        # today = fields.Date.context_today(self)
        today = datetime.now()
        print("perform checkin is called", self.booking_ids)
        for booking in self.booking_ids:

            # Skip if the booking has more than one room line
            if len(booking.room_line_ids) > 1:
                continue

            # Set the check-in date and perform the check-in
            booking.checkin_date = today
            booking._perform_checkin()

    # def action_confirm_checkin(self):
    #     for booking in self.booking_ids:
    #         booking._perform_checkin()
    #     """ Action to confirm the check-in and change the check-in date to today """
    #     self.booking_id.checkin_date = fields.Date.context_today(self)
    #     self.booking_id._perform_checkin()

    @api.model
    def default_get(self, fields_list):
        res = super(BookingCheckinWizard, self).default_get(fields_list)
        booking_ids = self._context.get('default_booking_ids')
        if booking_ids:
            res['booking_ids'] = [(6, 0, booking_ids)]
        return res

    def action_cancel(self):
        """ Action to cancel the check-in """
        return {'type': 'ir.actions.act_window_close'}


class RoomBookingReport(models.AbstractModel):
    _name = 'report.hotel_management_odoo.report_consolidated_template'
    _description = 'Consolidated Room Booking Report'

    def _get_record_from_context(self, context):
        room_booking_id = context.get('room_booking_id')
        if not room_booking_id:
            # Fallback to docids
            room_booking_id = self.env.context.get(
                'active_id') or self.env.context.get('active_ids', [])
        if room_booking_id:
            return self.env['room.booking'].browse(room_booking_id)
        return None

    @api.model
    def _calculate_average_rate(self, rate_field, records):
        """
        Helper function to calculate the average of rates in the given records.
        """
        rates = [getattr(record, rate_field, 0)
                 for record in records if getattr(record, rate_field, 0)]
        return sum(rates) / len(rates) if rates else 0

    def _get_report_values(self, docids, data=None):
        context = self.env.context
        _logger.info("Context received in report: %s", context)
        record = self._get_record_from_context(context)

        if not record:
            raise ValueError(
                "No record found for room_booking_id in the context.")

        # Fetch rates and meals for the room booking
        forecast_records = self.env['room.rate.forecast'].search(
            [('room_booking_id', '=', record.id)])
        if not forecast_records:
            raise ValueError(
                f"No forecast records found for room_booking_id {record.id}")

        # Calculate averages for rates and meals
        rate_avg = self._calculate_average_rate('rate', forecast_records)
        meals_avg = self._calculate_average_rate('meals', forecast_records)

        # Log details for debugging
        _logger.info("Rate Average: %s", rate_avg)
        _logger.info("Meals Average: %s", meals_avg)

        # Prepare booking details
        booking_details = [{
            'room_id': record.room_id.id if record.room_id else None,
            'room_number': record.room_id.name if record.room_id else 'N/A',
            'hotel_room_name': record.room_id.name if record.room_id else 'N/A',
            'adults': [{
                'Nationality': adult.nationality.name,
                'Passport NO.': adult.passport_number,
                'Tel no.': adult.phone_number,
                'ID Number': adult.id_number,
            } for adult in record.adult_ids],
            'children': [{
                'Nationality': child.nationality.name,
                'Passport NO.': child.passport_number,
                'Tel no.': child.phone_number,
                'ID Number': child.id_number,
            } for child in record.child_ids],
        }]
        # Log details for debugging
        _logger.info("Booking Details: %s", booking_details)

        return {
            'doc_ids': docids,
            'doc_model': 'room.booking',
            'docs': record,  # Pass the main record
            'data': data,  # Additional data, if needed
            'booking_details': booking_details,  # Booking details for the template
            'rate_avg': rate_avg,  # Average room rate
            'meals_avg': meals_avg,  # Average meal rate
        }


class ConfirmEarlyCheckoutWizard(models.TransientModel):
    _name = 'confirm.early.checkout.wizard'
    _description = 'Confirm Early Check-Out Wizard'

    booking_ids = fields.Many2many('room.booking', string='Booking')

    @api.model
    def default_get(self, fields_list):
        res = super(ConfirmEarlyCheckoutWizard, self).default_get(fields_list)
        booking_ids = self._context.get('default_booking_ids')
        if booking_ids:
            res['booking_ids'] = [(6, 0, booking_ids)]
        return res

    def action_confirm_checkout(self):
        """Set checkout_date to today and proceed with check-out for all selected bookings"""
        # today = fields.Date.context_today(self)
        today = datetime.now()
        for booking in self.booking_ids:
            if len(booking.room_line_ids) > 1:
                continue
                # raise ValidationError(_("This booking has multiple room lines and cannot be checked out through early checkout."))

            booking.checkout_date = today
            booking._perform_checkout()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking Checked Out Successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    # def action_confirm_checkout(self):
    #     """Set checkout_date to today and proceed with check-out"""
    #     self.booking_id.write({'checkout_date': datetime.now()})
    #     print(f"Debug: In wizard, booking_id = {self.booking_id.id}")
    #     self.booking_id.action_checkout()


class BookingPostingItem(models.Model):
    _name = 'booking.posting.item'
    _description = 'Booking Posting Item'

    booking_id = fields.Many2one(
        'room.booking', string="Booking", required=True, ondelete='cascade')
    posting_item_id = fields.Many2one('posting.item', string="Posting Item")
    posting_item_selection = fields.Selection(
        [
            ('first_night', 'First Night'),
            ('every_night', 'Every Night'),
        ],
        string="Posting Item Option",
        help="Select whether the posting applies to the first night or every night."
    )
    default_value = fields.Float(
        related='posting_item_id.default_value', string="Default Value", readonly=True)
    item_code = fields.Char(
        related='posting_item_id.item_code', string="Item Code", readonly=True)
    description = fields.Char(
        related='posting_item_id.description', string="Description", readonly=True)


class RoomBookingPostingItem(models.Model):
    _name = 'room.booking.posting.item'

    booking_id = fields.Many2one(
        'room.booking',
        string="Room Booking",
        ondelete='cascade',
        required=True,
        help="Reference to the room booking."
    )
    # posting_item_id = fields.Many2one(
    #     'posting.item',
    #     string="Posting Item",
    #     required=True,
    #     help="The posting item linked to this booking."
    # )

#     posting_item_id = fields.Many2one(
#     'posting.item',
#     string="Posting Item",
#     required=True,
#     domain="[('main_department', '!=', False), '|', ('main_department.charge_room', '=', True), '|', ('main_department.charge_food', '=', True), '|', ('main_department.charge_beverage', '=', True), '|', ('main_department.charge_telephone', '=', True), ('main_department.charge_other', '=', True)]",
#     help="The posting item linked to this booking, filtered by department settings."
# )
    posting_item_id = fields.Many2one(
        'posting.item',
        string="Posting Item",
        required=True,
         domain="""[
            ('main_department', '!=', False),
            ('main_department.charge_type', '!=', False)
        ]""",
        # domain="""[
        #     ('main_department', '!=', False),
        #     '|', '|', '|', '|', '|', '|', '|',
        #     ('main_department.charge_room', '=', True),
        #     ('main_department.charge_food', '=', True),
        #     ('main_department.charge_beverage', '=', True),
        #     ('main_department.charge_telephone', '=', True),
        #     ('main_department.charge_other', '=', True),
        #     ('main_department.payment_cash', '=', True),
        #     ('main_department.payment_credit_card', '=', True),
        #     '|', '|', '|',
        #     ('main_department.payment_other', '=', True),
        #     ('main_department.tax_service_charge', '=', True),
        #     ('main_department.tax_vat', '=', True),
        #     '|',
        #     ('main_department.tax_other', '=', True),
        #     ('main_department.tax_municipality', '=', True)
        # ]""",
        help="The posting item linked to this booking, filtered by department settings."
    )



    item_code = fields.Char(string="Item Code")
    description = fields.Char(string="Description")
    # posting_item_selection = fields.Selection(
    #     related="posting_item_id.posting_item_selection",
    #     readonly=False,
    #     string="Posting Item Option"
    # )
    posting_item_selection = fields.Selection(
        [
            ('first_night', 'First Night'),
            ('every_night', 'Every Night'),
            ('custom_date', 'Custom Date')
        ],
        required=True,
        string="Posting Item Option",
        help="Select whether the posting applies to the first night or every night."
    )
    from_date = fields.Datetime(string="From Date")
    to_date = fields.Datetime(string="To Date")

    @api.constrains('posting_item_selection', 'from_date', 'to_date')
    def _check_custom_date_required_fields(self):
        for record in self:
            if record.posting_item_selection == 'custom_date':
                if not record.from_date or not record.to_date:
                    raise exceptions.ValidationError(
                        "Both 'From Date' and 'To Date' are required when 'Custom Date' is selected."
                    )

    default_value = fields.Float(string="Default Value")

    @api.constrains('posting_item_id', 'booking_id')
    def _check_unique_posting_item(self):
        """Ensure the same posting_item_id is not selected twice in the same booking."""
        for record in self:
            duplicates = self.env['room.booking.posting.item'].search([
                ('booking_id', '=', record.booking_id.id),
                ('posting_item_id', '=', record.posting_item_id.id),
                ('id', '!=', record.id)  # Exclude the current record
            ])
            if duplicates:
                raise ValidationError(
                    f"The Posting Item '{record.posting_item_id}' is already selected for this booking. "
                    "Please choose a different Posting Item."
                )

    @api.onchange('from_date', 'to_date')
    def _onchange_dates(self):
        """Validate that from_date and to_date are within the check-in and check-out date range."""
        for record in self:
            if record.to_date and not record.from_date:
                raise ValidationError(
                    "Please select 'From Date' before selecting 'To Date'.")
            if record.booking_id:
                # Convert check-in, check-out, from_date, and to_date to date only
                checkin_date = fields.Date.to_date(
                    record.booking_id.checkin_date)
                checkout_date = fields.Date.to_date(
                    record.booking_id.checkout_date)
                from_date = fields.Date.to_date(
                    record.from_date) if record.from_date else None
                to_date = fields.Date.to_date(
                    record.to_date) if record.to_date else None

                # Debugging: Print normalized dates
                print('Normalized Dates:', {
                    'from_date': from_date,
                    'to_date': to_date,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date
                })

                # Validate from_date
                if from_date:
                    if not (checkin_date <= from_date <= checkout_date):
                        raise ValidationError(
                            "The 'From Date' must be between the check-in and check-out dates of the booking."
                        )

                # Validate to_date
                if to_date:
                    if not (from_date <= to_date <= checkout_date):
                        raise ValidationError(
                            "The 'To Date' must be greater than or equal to 'From Date' and within the check-out date."
                        )

    @api.onchange('posting_item_id')
    def _onchange_posting_item_id(self):
        """Update related fields when posting_item_id changes."""
        if self.posting_item_id:
            self.item_code = self.posting_item_id.item_code
            self.description = self.posting_item_id.description
            # self.posting_item_selection = self.posting_item_id.posting_item_selection
            # self.from_date = self.posting_item_id.from_date
            # self.to_date = self.posting_item_id.to_date
            self.default_value = self.posting_item_id.default_value
            # if self.booking_id:
            #     duplicate = self.booking_id.posting_item_ids.filtered(
            #         lambda item: item.posting_item_id == self.posting_item_id and item.id != self.id
            #     )
            #     if duplicate:
            #         # Reset the posting_item_id field and raise a warning
            #         self.posting_item_id = False
            #         return {
            #             'warning': {
            #                 'title': "Duplicate Posting Item",
            #                 'message': "This Posting Item has already been selected for this booking. Please choose another.",
            #             }
            #         }


class RoomBookingLineStatus(models.Model):
    _name = 'room.booking.line.status'
    _description = 'Room Booking Line Status'

    booking_line_id = fields.Many2one(
        'room.booking.line', string="Booking Line", ondelete='cascade')
    status = fields.Selection([
        ('not_confirmed', 'Not Confirmed'),
        ('confirmed', 'Confirmed'),
        ('waiting', 'Waiting List'),
        ('no_show', 'No Show'),
        ('block', 'Block'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('reserved', 'Reserved')
    ], string="Status")
    change_time = fields.Datetime(
        string="Change Time", default=fields.Datetime.now)


# class RoomBookingUpdateWizard(models.TransientModel):
#     _name = 'room.booking.update.wizard'
#     _description = 'Wizard to Update Room Booking Fields'

#     # Fields
#     group_booking = fields.Many2one(
#         'group.booking', string="Group Booking", help="Group associated with this booking")
#     # group_booking_ids = fields.Many2many('group.booking', string='Group Bookings',)
#     checkin_date = fields.Datetime()
#     checkout_date = fields.Datetime()
#     nationality = fields.Many2one('res.country', string='Nationality')

#     # Readonly flags for inconsistent fields
#     group_booking_readonly = fields.Boolean(store=False)
#     checkin_date_readonly = fields.Boolean(store=False)
#     checkout_date_readonly = fields.Boolean(store=False)
#     nationality_readonly = fields.Boolean(store=False)

#     # Hidden field to store initial values for change detection
#     initial_values = fields.Text(store=False)
#     data_dict = {}

#     @api.model
#     def default_get(self, fields_list):
#         res = super(RoomBookingUpdateWizard, self).default_get(fields_list)
#         active_ids = self.env.context.get('active_ids', [])
#         bookings = self.env['room.booking'].browse(active_ids)

#         def get_common_value(field_name):
#             """ Returns the common value if all records have the same value, else False """
#             values = bookings.mapped(field_name)
#             return values[0] if len(set(values)) == 1 else False

#         def is_field_different(field_name):
#             """ Checks if the field has different values across records """
#             return len(set(bookings.mapped(field_name))) > 1

#         # Prepare initial values
#         initial_data = {
#             'group_booking': get_common_value('group_booking').id if get_common_value('group_booking') else False,
#             'checkin_date': get_common_value('checkin_date').isoformat() if get_common_value('checkin_date') else None,
#             'checkout_date': get_common_value('checkout_date').isoformat() if get_common_value('checkout_date') else None,
#             'nationality': get_common_value('nationality').id if get_common_value('nationality') else False,
#         }

#         # Update the wizard fields with values
#         res.update({
#             'group_booking': initial_data['group_booking'],
#             'group_booking_readonly': is_field_different('group_booking'),

#             'checkin_date': get_common_value('checkin_date'),
#             'checkin_date_readonly': is_field_different('checkin_date'),

#             'checkout_date': get_common_value('checkout_date'),
#             'checkout_date_readonly': is_field_different('checkout_date'),

#             'nationality': initial_data['nationality'],
#             'nationality_readonly': is_field_different('nationality'),

#             # Serialize initial values for comparison
#             # 'initial_values': json.dumps(initial_data),
#         })
#         return res

#     def action_update_bookings(self):
#         active_ids = self.env.context.get('active_ids', [])
#         bookings = self.env['room.booking'].browse(active_ids)

#         # Deserialize initial values for comparison
#         initial_values = json.loads(self.initial_values or "{}")
#         print(bookings, active_ids, initial_values)

#         # Identify and update only changed fields
#         update_values = {}
#         if self.group_booking.id and self.group_booking.id != initial_values.get('group_booking'):
#             update_values['group_booking'] = self.group_booking.id
#         if self.checkin_date and self.checkin_date.isoformat() != initial_values.get('checkin_date'):
#             update_values['checkin_date'] = self.checkin_date
#         if self.checkout_date and self.checkout_date.isoformat() != initial_values.get('checkout_date'):
#             update_values['checkout_date'] = self.checkout_date
#         if self.nationality.id and self.nationality.id != initial_values.get('nationality'):
#             update_values['nationality'] = self.nationality.id

#         print(update_values)
#         # Perform write operation only for changed values
#         if update_values:
#             bookings.write(update_values)

#         return {'type': 'ir.actions.act_window_close'}

class RoomBookingUpdateWizard(models.TransientModel):
    _name = 'room.booking.update.wizard'
    _description = 'Wizard to Update Check-In and Check-Out Dates'

    checkin_date = fields.Datetime(string='Check-In Date')
    checkout_date = fields.Datetime(string='Check-Out Date')
    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern")
    readonly_meal_pattern = fields.Boolean(
        string="Is Meal Pattern Readonly", default=False)
    rate_code = fields.Many2one('rate.code', string='Rate Code')
    readonly_rate_code = fields.Boolean(
        string="Is Rate Code Readonly", default=False)
    nationality = fields.Many2one('res.country', string='Nationality')
    readonly_nationality = fields.Boolean(
        string="Is Nationality Readonly", default=False)
    source_of_business = fields.Many2one(
        'source.business', string='Source of Business')
    room_type = fields.Many2one('room.type', string='Room Type')
    readonly_source_of_business = fields.Boolean(
        string="Is Nationality Readonly", default=False)
    market_segment = fields.Many2one('market.segment', string='Market Segment')
    readonly_market_segment = fields.Boolean(
        string="Is Nationality Readonly", default=False)
    readonly_checkin_date = fields.Boolean(
        string="Is Check-In Date Readonly", default=False)
    readonly_checkout_date = fields.Boolean(
        string="Is Check-Out Date Readonly", default=False)
    blocked_room_action = fields.Selection(
        [
            ('auto_assign', 'Automatically assign rooms of the new type'),
            ('unassign_confirm',
             'Unassign the room and change the booking status to Confirmed')
        ],
        string='Blocked Room Action'
    )

    # def action_update_selected_bookings(self):
    #     # Get the selected bookings from the context
    #     active_ids = self.env.context.get('active_ids', [])
    #     if active_ids:
    #         bookings = self.env['room.booking'].browse(active_ids)
    #         bookings.write({
    #             # 'checkin_date': self.checkin_date,
    #             # 'checkout_date': self.checkout_date,
    #             'meal_pattern': self.meal_pattern.id,
    #         })

    @api.constrains('checkin_date', 'checkout_date')
    def _check_dates(self):
        today = datetime.now()
        for record in self:
            if record.checkin_date and record.checkin_date < today:
                raise UserError("Check-In Date cannot be earlier than today.")
            if record.checkin_date and record.checkout_date and record.checkout_date <= record.checkin_date:
                raise UserError(
                    "Check-Out Date must be greater than Check-In Date.")

    @api.model
    def default_get(self, fields_list):
        today = datetime.now()
        res = super(RoomBookingUpdateWizard, self).default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])

        if active_ids:
            bookings = self.env['room.booking'].browse(active_ids)

        return res

    def action_update_selected_bookings(self):
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return {'type': 'ir.actions.act_window_close'}

        bookings = self.env['room.booking'].browse(active_ids)
        grouped_data = {}

        # Group room names by their room types
        for booking in bookings:
            for line in booking.room_line_ids:
                room_name = line.room_id.name
                room_type = line.hotel_room_type.room_type

                if room_type:
                    grouped_data.setdefault(room_type, []).append(room_name)

        # Check for overlapping bookings for each room
        for room_type, room_names in grouped_data.items():
            for room_name in room_names:
                if not room_name:
                    continue  # Skip undefined rooms

                overlapping_bookings = self.env['room.booking.line'].search([
                    ('room_id', '=', room_name),
                    ('booking_id.state', 'in', ['block', 'check_in']),
                    '|',
                    '&', ('checkin_date', '<=', self.checkout_date), (
                        'checkout_date', '>=', self.checkin_date),
                    '&', ('checkin_date', '>=', self.checkin_date), ('checkin_date',
                                                                     '<=', self.checkout_date),
                ])

                if overlapping_bookings:
                    raise ValidationError(
                        f"Room '{room_name}' of type '{room_type}' is not available for "
                        f"check-in on {self.checkin_date} and check-out on {self.checkout_date} "
                        f"because it is already booked in 'block' or 'check-in' state."
                    )
        for booking in bookings:
            if booking.state != 'block':
                raise ValidationError(
                    f"Booking '{booking.name}' is not in the 'block' state. "
                    "All selected bookings must be in the 'block' state."
                )
            room_count = len(booking.room_line_ids)
            adult_count = sum(booking.room_line_ids.mapped('adult_count'))
            hotel_room_type_id = booking.room_line_ids.mapped(
                'hotel_room_type').id if booking.room_line_ids else None

            room_availability = booking.check_room_availability_all_hotels_split_across_type(
                checkin_date=self.checkin_date,
                checkout_date=self.checkout_date,
                room_count=room_count,
                adult_count=adult_count,
                hotel_room_type_id=hotel_room_type_id
            )

            if not room_availability:
                raise ValidationError(
                    f"Rooms of type '{room_type}' are not available for the selected check-in and check-out dates."
                )
        for booking in bookings:
            update_values = {
                'checkin_date': self.checkin_date,
                'checkout_date': self.checkout_date,
                'meal_pattern': self.meal_pattern.id,
                'nationality': self.nationality.id,
                'rate_code': self.rate_code.id,
                'source_of_business': self.source_of_business.id,
                'market_segment': self.market_segment.id,
            }
            if self.blocked_room_action == 'unassign_confirm':
                booking.write(update_values)
                for booking in bookings:
                    for line in booking.room_line_ids:
                        line.write({
                            'hotel_room_type': self.room_type.id,
                            'state_': 'confirmed'
                        })

            elif self.blocked_room_action == 'auto_assign':
                update_values['state'] = 'confirmed'
                booking.write(update_values)
                # booking.write({'state': 'confirmed'})
                self.env.cr.flush()

                for line in booking.room_line_ids:
                    line.write({
                        'hotel_room_type': self.room_type.id,
                        'state_': 'confirmed'
                    })
                # Call the method to assign available rooms
                booking.action_assign_all_rooms()

            else:
                # Default case: Just update the booking with the common fields
                booking.write(update_values)

        # If no overlapping bookings, update the selected bookings
        # if self.blocked_room_action == 'unassign_confirm':
        #     bookings.write({
        #         'checkin_date': self.checkin_date,
        #         'checkout_date': self.checkout_date,
        #         'meal_pattern': self.meal_pattern.id,
        #         'nationality': self.nationality.id,
        #         'rate_code': self.rate_code.id,
        #         'source_of_business':self.source_of_business.id,
        #         'market_segment':self.market_segment.id,
        #         # 'hotel_room_type': self.room_type.id
        #     })
        #     for line in booking.room_line_ids:
        #         line.write({'hotel_room_type': self.room_type.id,
        #         'state_': 'confirmed'})

        # if self.blocked_room_action == 'auto_assign':
        #     bookings.write({
        #         'checkin_date': self.checkin_date,
        #         'checkout_date': self.checkout_date,
        #         'meal_pattern': self.meal_pattern.id,
        #         'nationality': self.nationality.id,
        #         'rate_code': self.rate_code.id,
        #         'source_of_business':self.source_of_business.id,
        #         'market_segment':self.market_segment.id,
        #         'state': 'confirmed'
        #         # 'hotel_room_type': self.room_type.id
        #     })
        #     # booking.write({
        #     #     'state': 'confirmed'})
        #     for line in booking.room_line_ids:
        #         line.write({'hotel_room_type': self.room_type.id,
        #         'state_': 'confirmed'})
        #     booking.action_assign_all_rooms()
        # # Close the window after a successful update
        # return {'type': 'ir.actions.act_window_close'}

    # working
    # def action_update_selected_bookings(self):
    #     active_ids = self.env.context.get('active_ids', [])
    #     if active_ids:
    #         bookings = self.env['room.booking'].browse(active_ids)

    #         grouped_data = {}
    #         for booking in bookings:
    #             for line in booking.room_line_ids:
    #                 room_name = line.room_id.name
    #                 room_type = line.hotel_room_type.room_type
    #                 if room_type:
    #                     if room_type not in grouped_data:
    #                         grouped_data[room_type] = []
    #                     grouped_data[room_type].append(room_name)

    #         # Print the grouped data for debugging
    #         print("Grouped Room Names by Room Types:")
    #         for room_type, room_ids in grouped_data.items():
    #             print(f"Room Type: {room_type}, Room Names: {room_ids}")
    #             for room in room_ids:
    #                 print('6370', room, room_ids)
    #                 if not room:
    #                     continue  # Skip if the room is not defined

    #                 # Search for bookings where this room is in 'block' or 'check_in' state and dates overlap
    #                 print('6375', self.checkout_date )
    #                 overlapping_bookings = self.env['room.booking.line'].search([
    #                     ('room_id', '=', room),
    #                     ('booking_id.state', 'in', ['block', 'check_in']),
    #                     '|',
    #                     '&', ('checkin_date', '<=', self.checkout_date), ('checkout_date', '>=', self.checkin_date),
    #                     '&', ('checkin_date', '>=', self.checkin_date), ('checkin_date', '<=', self.checkout_date),
    #                 ])

    #                 if overlapping_bookings:
    #                     raise ValidationError(
    #                         f"Room '{room}' of type '{room_type}' is not available for "
    #                         f"check-in on {self.checkin_date} and check-out on {self.checkout_date} "
    #                         f"because it is already booked in 'block' or 'check-in' state."
    #                     )

    #         # If all rooms are available
    #         print("All rooms are available for the new check-in and check-out dates.")
    #         bookings.write({
    #             'checkin_date': self.checkin_date,
    #             'checkout_date': self.checkout_date,
    #             'meal_pattern': self.meal_pattern.id,
    #             'nationality':self.nationality,
    #             'rate_code':self.rate_code
    #         })


# email configuration
class EmailConfigurationSettings(models.Model):
    _inherit = 'res.company'

    cron_name = fields.Char(
        string="Action Name",
        # related='model_id.name',
        # readonly=True,
        help="The name of the action associated with the selected model."
    )

    model_id = fields.Many2one(
        'ir.model',
        string="Model",
        # required=True, #Issue here
        # ondelete='set null',  # This is the default behavior and safe to use
        help="Model on which the server action runs."
    )

    template_id = fields.Many2one(
        'mail.template', string='Confirmation Email Template',
        help="Select the email template for reminder communication."
    )

    pre_template_id = fields.Many2one(
        'mail.template', string='Pre-Arrival Email Template',
        help="Select the email template for pre-arrival communication."
    )

    pre_arrival_days_before = fields.Integer(
        string="Days Before Arrival", default=3,
        help="Number of days before check-in to send the pre-arrival email."
    )

    reminder_days_before = fields.Integer(
        string="Days Before Reminder", default=3,
        help="Number of days before check-in to send the pre-arrival email."
    )

    scheduler_user_id = fields.Many2one(
        'res.users', string="Scheduler User", required=True,
        help="User responsible for executing the scheduled action."
    )
    allowed_groups = fields.Many2many(
        'res.groups', string="Allowed Groups",
        help="Groups allowed to configure this action."
    )
    interval_number = fields.Integer(
        string="Execute Every",
        default=1,
        help="Number of units (minutes, hours, days, etc.) to wait before the next execution."
    )
    execution_frequency_unit = fields.Selection(
        [('minutes', 'Minutes'),
         ('hours', 'Hours'),
         ('days', 'Days'),
         ('weeks', 'Weeks'),
         ('months', 'Months')],
        string="Execution Frequency Unit", default='days',
        help="Unit of time for the execution frequency."
    )
    number_of_calls = fields.Integer(
        string="Number of Calls", default=-1,
        help="Number of times the scheduler should run. Use -1 for unlimited."
    )
    priority = fields.Integer(
        string="Priority", help='Can be 1 - 5', default=5)
    active = fields.Boolean(string="Active", default=True)

    enable_reminder = fields.Boolean(
        string="Enable Reminder",
        help="Enable or disable pre-arrival email reminders."
    )

    @api.onchange('enable_reminder')
    def _onchange_enable_reminder(self):
        scheduled_action = self.env.ref('hotel_management_odoo.cron_send_prearrival_emails_company',
                                        raise_if_not_found=False)
        print('8107', scheduled_action)
        if scheduled_action:
            # Update the active field based on enable_reminder
            scheduled_action.sudo().write({'active': self.enable_reminder})
        if not self.enable_reminder:
            self.pre_template_id = False
            self.pre_arrival_days_before = 0

    @api.model
    def write(self, values):
        # Handle active field for the scheduled action during record updates
        if 'enable_reminder' in values:
            scheduled_action = self.env.ref('hotel_management_odoo.cron_send_prearrival_emails_company',
                                            raise_if_not_found=False)
            print('8153', scheduled_action)
            if scheduled_action:
                scheduled_action.sudo().write(
                    {'active': values['enable_reminder']})
        return super(EmailConfigurationSettings, self).write(values)


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model
    def search(self, domain, *args, **kwargs):
        # Append filtering conditions
        domain += [
            ('summary', '=', 'Room Availability Notification'),
            ('res_model', '=', 'room.booking'),
        ]
        _logger.info("Search domain applied: %s", domain)
        return super(MailActivity, self).search(domain, *args, **kwargs)


class AccountMoveInherit(models.Model):
    _inherit = "account.move"

    hotel_booking_id = fields.Many2one(
        'room.booking',
        string='Booking Reference',
        readonly=True
    )

    group_booking_name = fields.Char(
        string='Group Booking Name',
        store=True,
        readonly=True
    )
    parent_booking_name = fields.Char(
        string='Parent Booking Name',
        store=True,
        readonly=True
    )
    room_numbers = fields.Char(
        string='Room Numbers',
        store=True,
        readonly=True
    )


class ConfirmBookingWizard(models.TransientModel):
    _name = "confirm.booking.wizard"
    _description = "Confirm Booking Wizard"

    message = fields.Text(string="Confirmation Message", readonly=True)
    line_id = fields.Many2one(
        'room.booking.line', string="Room Line", readonly=True)
    booking_id = fields.Many2one(
        'room.booking', string="Booking", readonly=True)

    # def action_confirm(self):
    #     self.line.room_id = False
    #     self.line_id.state_ = 'confirmed'
    #     return {'type': 'ir.actions.act_window_close'}

    def action_confirm(self):
        """YES button: if the line is in 'block' state,
           set room_id to False and change state to 'confirmed'."""
        if self.line_id and self.line_id.state_ == 'block':
            self.line_id.room_id = False
            self.line_id.state_ = 'confirmed'
        return {'type': 'ir.actions.act_window_close'}

    def action_block(self):
        # self.line_id.state_ = 'block'
        # self.booking_id.state = 'block'
        return {'type': 'ir.actions.act_window_close'}

    # def action_cancel(self):
    #     """
    #     NO button:
    #     - DO NOT confirm the booking
    #     - DO NOT modify anything
    #     - Just close the wizard
    #     """
    #     return {'type': 'ir.actions.act_window_close'}
