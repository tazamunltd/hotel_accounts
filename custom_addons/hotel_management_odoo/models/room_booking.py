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
from odoo.fields import Datetime
from pytz import timezone
import re
from datetime import time      # ← this shadows the real time module
from collections import defaultdict


_logger = logging.getLogger(__name__)


class RoomBooking(models.Model):
    """Model that handles the hotel room booking and all operations related
     to booking"""
    _name = "room.booking"
    _order = 'create_date desc'
    _description = "Waiting List Room Availability"
    _inherit = ['mail.thread', 'mail.activity.mixin']


    

    

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
        # today = fields.Date.context_today(self)
        today = self.env.company.system_date.date()
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
        # today = datetime.now().date()
        today = self.env.company.system_date.date()

        # Step 1: Search for bookings in the 'cancel' state for today
        canceled_bookings = self.env['room.booking'].search([
            ('state', '=', 'cancel'),
            ('checkin_date', '>=', today),
            ('checkout_date', '>=', today),
            ('notification_sent', '=', False)
        ])

        if not canceled_bookings:
            return


        for canceled_booking in canceled_bookings:

            # Step 2: Search for bookings in the 'waiting' state with matching dates
            waiting_bookings = self.env['room.booking'].search([
                ('state', '=', 'waiting'),
                ('checkin_date', '>=', datetime.combine(
                    today, datetime.min.time())),
                ('checkout_date', '<=', canceled_booking.checkout_date.date()),
                ('company_id', '=', self.env.company.id)
            ], order='create_date asc')

            # _logger.info(
            #     f"Found {len(waiting_bookings)} waiting bookings for canceled booking '{canceled_booking.name}'.")

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
                    continue

                cumulative_room_count += booking.room_count
                selected_bookings.append(booking)

                # Stop when the cumulative room count matches or exceeds the canceled booking's room count
                if cumulative_room_count >= canceled_booking.room_count:
                    break

            # Notify about the selected bookings
            if selected_bookings:
                for booking in selected_bookings:
                    message = f"Booking '{booking.name}' is now available for the canceled booking '{canceled_booking.name}'."

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
            # else:
            #     _logger.info(
            #         f"No suitable bookings found for canceled booking '{canceled_booking.name}'.")

    
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

    previous_state = fields.Char(string=_("Previous State"), translate=True)

    is_checkin_in_past = fields.Boolean(
        string="Is Check-in in Past",
        compute="_compute_is_checkin_in_past",
        store=True
    )
    active = fields.Boolean(string="Active", default=True)

    is_offline_search = fields.Boolean(string="Is Offline search", default=True)

    @api.model
    def action_archive_as_delete_redirect(self,record_ids):
        records = self.browse(record_ids)
        if records.exists():
            records.action_archive_as_delete()
        # self.action_archive_as_delete()
        # self.action_archive_as_delete()
        # return {
        #     'status': 'success',
        #     'message': 'Reservation(s) deleted successfully!',
        # }
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': 'Success',
        #         'message': 'Reservation(s) deleted successfully!',
        #         'sticky': True,  # False means it disappears automatically
        #         'type': 'success',
        #         # Optionally redirect to a view:
        #         # 'next': {
        #         #    'type': 'ir.actions.act_window',
        #         #    'res_model': 'room.booking',
        #         #    'view_mode': 'tree,form',
        #         #    'target': 'current',
        #         # }
        #     }
        # }

        # self.env.user.notify_info(
        #         message=f"Reservation(s) deleted successfully!",
        #         title="Success"
        #     )
        
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Room Bookings',
        #     'res_model': 'room.booking',
        #     'view_mode': 'tree,form',
        #     'target': 'current',
        # }

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

        

    # @api.depends('checkin_date')
    # def _compute_is_checkin_in_past(self):
    #     today = fields.Date.context_today(self)
    #     # today = self.env.user.company_id.system_date
    #     for record in self:
    #         if record.checkin_date:
    #             checkin_date = record.checkin_date.date() if isinstance(record.checkin_date,
    #                                                                     datetime) else record.checkin_date
    #             record.is_checkin_in_past = checkin_date < today
    #         else:
    #             record.is_checkin_in_past = False

    @api.depends('checkin_date')
    def _compute_is_checkin_in_past(self):
        # Fetch system_date from the company configuration
        system_date = self.env.company.system_date.date()
        # if system_date:
        #     # Ensure system_date is correctly formatted to a date
        #     system_date = system_date.date() if isinstance(system_date, datetime) else fields.Date.to_date(system_date)
        # else:
        #     print("System Date is not set!")

        for record in self:
            if record.checkin_date:
                # Convert checkin_date to a date if it's a datetime object
                checkin_date_ = record.checkin_date.date()

                # Compare checkin_date with system_date
                record.is_checkin_in_past = (checkin_date_ < system_date)
                
            else:
                record.is_checkin_in_past = False


    def move_to_no_show(self):
        company_ids = self.env['res.company'].search([])
    
        for company in company_ids:
            company_env = self.env(context=dict(self.env.context, allowed_company_ids=[company.id], 
                                            force_company=company.id))


            # Get the current date and subtract one day to get yesterday's date
            system_date = company.system_date.date()
            yesterday = datetime.combine((system_date - timedelta(days=1)), time.min)
            # print("------->", system_date, yesterday.date(), company, company.id, company_env)

            # Find bookings with checkin_date equal to yesterday and in the specified states
            bookings = self.search([
                ('state', 'in', ['not_confirmed', 'confirmed', 'block']),
                ('checkin_date', '<', yesterday.date()),
                ('company_id', '=', company.id)
            ])
            # print("BOOKINGS: ", bookings)

            # Update the state to 'no_show' using the no_show method
            for booking in bookings:
                try:
                    # Call the no_show method
                    booking.no_show()
                    print(
                        f"Successfully processed booking ID {booking.id} as 'no_show'.")
                except Exception as e:
                    # Log or print the exception to handle any issues
                    print(f"Failed to process booking ID {booking.id}: {e}")

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
                booking.room_line_ids.write({'state_': 'no_show'})

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
    special_request = fields.Text(string="Special Request", tracking=True)
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

    hotel_id = fields.Many2one('res.company', string="Hotel ID", tracking=True)
    # company_address_id = fields.Many2one(
    #     'res.company',
    #     string='Company Address',
    #     help="Select the address from the company model"
    # )
    address_id = fields.Many2one(
        'res.partner', string="Address", tracking=True)
    phone = fields.Char(related='address_id.phone',
                        string="Phone Number", tracking=True)
    # room_booking_line_id = fields.Many2one('room.booking.line', string="Room Line", tracking=True)

    room_id = fields.Many2one(
        'room.booking.line', string="Room Line", tracking=True)
    room_type = fields.Many2one('room.type', string="Hotel Room Type", tracking=True)

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

    # @api.onchange('checkin_date', 'checkout_date')
    # def _compute_no_of_nights(self):
    #     for record in self:
    #         if record.checkin_date and record.checkout_date:
    #             delta = record.checkout_date.date() - record.checkin_date.date()
    #             record.no_of_nights = delta.days
    #             if record.no_of_nights > 999:
    #                 raise ValidationError(
    #                     "Number of nights cannot exceed 999. Please adjust the check-in or check-out dates.")
    #         else:
    #             record.no_of_nights = 0

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
            if not record.room_line_ids:
                record.show_in_tree = True
            else:
                # record.show_in_tree = True
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
        
        system_date = (
            company.system_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if company.system_date
            else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )
        end_of_day = system_date + timedelta(days=1) - timedelta(seconds=1)
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
            ('checkin_date', '>=', system_date),
            ('checkin_date', '<=', system_date + timedelta(days=1) - timedelta(seconds=1)),
            # ('checkin_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_in'),
            # ('parent_booking_name', '!=', False)

        ])

        actual_checkout_count = self.search_count([
            # ('checkout_date', '>=', today),
            ('checkout_date', '>=', system_date),
            ('checkout_date', '<=', system_date + timedelta(days=1) - timedelta(seconds=1)),
            # ('checkout_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_out'),
            # ('parent_booking_name', '!=', False)

        ])

        today_checkin_count = self.search_count([
            # ('checkin_date', '>=', today),
            ('checkin_date', '>=', system_date),
            ('checkin_date', '<=', system_date + timedelta(days=1) - timedelta(seconds=1)),
            # ('checkin_date', '<', today + timedelta(days=1)),
            ('state', '=', 'block'),
            # ('parent_booking_name', '!=', False)

        ])
        today_checkout_count = self.search_count([
            # ('checkout_date', '>=', today),
            ('checkout_date', '>=', system_date),
            # ('checkout_date', '<=', end_of_day),
            ('checkout_date', '<=', system_date + timedelta(days=1) - timedelta(seconds=1)),
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
        # get_total_reservation_count = self.env['room.booking'].search_count([('company_id', '=', self.env.company.id)])
        get_total_reservation_count = confirmed_count + not_confirm_count + waiting_count + checkin_count + checkout_count

        
        


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
            'vacant': get_total_reservation_count,
            # 'default': confirmed_count + not_confirm_count + waiting_count + checkin_count + checkout_count,
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

    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern", domain=lambda self: [('company_id', '=', self.env.company.id)], tracking=True)

    group_booking_id = fields.Many2one(
        'group.booking',  # The source model (group bookings)
        string='Group Booking ID',
        ondelete='cascade',
        tracking=True
    )

    name = fields.Char(string="Booking ID", readonly=True, index=True,copy=False, default="New", help="Name of Folio", tracking=True)

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

    room_rate_municiplaity_tax = fields.Float(string="Room Rate Municipality Tax", store=False, tracking=True)    
    room_rate_vat = fields.Float(string="Room Rate VAT", store=False, tracking=True)
    room_rate_untaxed = fields.Float(string="Room Rate Untaxed", store=False, tracking=True)

    meal_rate_municiplaity_tax = fields.Float(string="Meal Rate Municipality Tax", store=False, tracking=True)    
    meal_rate_vat = fields.Float(string="Meal Rate VAT", store=False, tracking=True)
    meal_rate_untaxed = fields.Float(string="Meal Rate Untaxed", store=False, tracking=True)

    packages_municiplaity_tax = fields.Float(string="Packages Municipality Tax", store=False, tracking=True)
    packages_vat = fields.Float(string="Packages VAT", store=False, tracking=True)
    packages_untaxed = fields.Float(string="Packages Untaxed", store=False, tracking=True)

    fixed_post_vat = fields.Float(string="Fixed Post VAT", store=False, tracking=True)
    fixed_post_municiplaity_tax = fields.Float(string="Fixed Post Municipality Tax", store=False, tracking=True)
    fixed_post_untaxed = fields.Float(string="Fixed Post Untaxed", store=False, tracking=True)

    total_municipality_tax = fields.Float(string="Total Municipality Tax", tracking=True)
    total_vat = fields.Float(string="Total VAT", tracking=True)
    total_untaxed = fields.Float(string="Total Untaxed", store=False, tracking=True)

    
    def _onchange_rate_code_taxes(self):
        for rec in self:
            total_rate_amount = rec.total_rate_after_discount
            # print("total_rate_amount", total_rate_amount)
            taxes = rec.rate_code.rate_posting_item.taxes
            if taxes:
                vat_tax = taxes[0] if len(taxes) > 0 else None
                unit_price = 0.0
                if vat_tax:
                    try:
                        percentage_value = vat_tax.amount
                        total_percentage_value = total_rate_amount + (total_rate_amount * (percentage_value / 100))
                        if total_percentage_value == 0:
                            raise ZeroDivisionError("Total percentage value is zero, cannot divide")
                        unit_price = total_rate_amount * (total_rate_amount / total_percentage_value)
                        rec.room_rate_vat = total_rate_amount - unit_price
                    except ZeroDivisionError as e:
                        rec.room_rate_vat = 0.0  # Or handle gracefully
                    except ValueError:
                        rec.room_rate_vat = 0.0
                municipality_tax = taxes[1] if len(taxes) > 1 else None

                if municipality_tax:
                    try:
                        percentage_value = municipality_tax.amount
                        total_percentage_value = unit_price + (unit_price * (percentage_value / 100))
                        if total_percentage_value == 0:
                            raise ZeroDivisionError("Municipality total percentage value is zero!")
                        unit_price_municipality = unit_price * (unit_price / total_percentage_value)
                        rec.room_rate_municiplaity_tax = unit_price - unit_price_municipality
                        rec.room_rate_untaxed = unit_price_municipality

                    except ZeroDivisionError as e:
                        rec.room_rate_municiplaity_tax = 0.0
                        rec.room_rate_untaxed = unit_price  # default to unit_price if error

                    except Exception as e:
                        rec.room_rate_municiplaity_tax = 0.0
                        rec.room_rate_untaxed = unit_price

            if rec.room_rate_vat == 0.0 and rec.room_rate_municiplaity_tax == 0.0:
                rec.room_rate_untaxed = total_rate_amount

            # else:
            #     rec.room_rate_vat = rec.room_rate_municiplaity_tax = rec.room_rate_untaxed = 0.0

    
    # def _onchange_rate_code_taxes(self):
    #     for rec in self:
    #         total_rate_amount = rec.total_rate_after_discount
    #         taxes = rec.rate_code.rate_posting_item.taxes if rec.rate_code and rec.rate_code.rate_posting_item else []
            
    #         # Initialize all tax fields
    #         rec.room_rate_vat = 0.0
    #         rec.room_rate_municiplaity_tax = 0.0
    #         rec.room_rate_untaxed = total_rate_amount  # Default to total rate if no taxes
            
    #         if taxes:
    #             # Calculate VAT tax if exists
    #             vat_tax = taxes[0] if len(taxes) > 0 else None
    #             if vat_tax:
    #                 try:
    #                     percentage_value = vat_tax.amount
    #                     total_percentage_value = total_rate_amount + (total_rate_amount * (percentage_value / 100))
    #                     if total_percentage_value != 0:
    #                         unit_price = total_rate_amount * (total_rate_amount / total_percentage_value)
    #                         rec.room_rate_vat = total_rate_amount - unit_price
    #                         rec.room_rate_untaxed = unit_price
    #                 except (ZeroDivisionError, ValueError):
    #                     pass  # Keep default values if calculation fails
                
    #             # Calculate Municipality tax if exists
    #             municipality_tax = taxes[1] if len(taxes) > 1 else None
    #             if municipality_tax and rec.room_rate_untaxed > 0:
    #                 try:
    #                     percentage_value = municipality_tax.amount
    #                     municipality_tax_amount = rec.room_rate_untaxed * (percentage_value / 100)
    #                     rec.room_rate_municiplaity_tax = municipality_tax_amount
    #                     rec.room_rate_untaxed = rec.room_rate_untaxed - municipality_tax_amount
    #                 except (ZeroDivisionError, ValueError):
    #                     pass  # Keep previous values if calculation fails
            
    #         # Final check - if both taxes are 0, set untaxed to total rate
    #         if rec.room_rate_vat == 0.0 and rec.room_rate_municiplaity_tax == 0.0:
    #             rec.room_rate_untaxed = total_rate_amount

   
    def _onchange_meal_rate_taxes(self):
        for rec in self:
            meal_base_amount = rec.total_meal_after_discount or 0.0
            total_vat = 0.0
            total_municipality = 0.0
            total_untaxed = 0.0

            posting_items = []

            if rec.meal_pattern and rec.meal_pattern.meal_posting_item:
                posting_items.append(rec.meal_pattern.meal_posting_item)
            elif rec.meal_pattern and rec.meal_pattern.meals_list_ids:
                for line in rec.meal_pattern.meals_list_ids:
                    if line.meal_code and line.meal_code.posting_item:
                        posting_items.append(line.meal_code.posting_item)

            if posting_items:
                for posting_item in posting_items:
                    meal_taxes = posting_item.taxes
                    vat_amount = 0.0
                    muni_amount = 0.0
                    untaxed_amount = 0.0

                    # Step 1: VAT
                    vat_tax = meal_taxes[0] if len(meal_taxes) > 0 else None
                    if vat_tax:
                        vat_pct = vat_tax.amount
                        vat_amount = meal_base_amount * (vat_pct / (100 + vat_pct))
                        base_after_vat = meal_base_amount - vat_amount
                    else:
                        base_after_vat = meal_base_amount

                    # Step 2: Municipality
                    municipality_tax = meal_taxes[1] if len(meal_taxes) > 1 else None
                    if municipality_tax:
                        muni_pct = municipality_tax.amount
                        muni_amount = base_after_vat * (muni_pct / (100 + muni_pct))
                        untaxed_amount = base_after_vat - muni_amount
                    else:
                        untaxed_amount = base_after_vat

                    # Accumulate — base stays same, so taxes stack
                    total_vat += vat_amount
                    total_municipality += muni_amount
                    total_untaxed += untaxed_amount

            else:
                total_untaxed = meal_base_amount

            # Assign with rounding
            rec.meal_rate_vat = round(total_vat, 2)
            rec.meal_rate_municiplaity_tax = round(total_municipality, 2)
            rec.meal_rate_untaxed = round(total_untaxed, 2)
    
    # def _onchange_packaged_taxes(self):
    #     for rec in self:
        
    #         checkin_date = fields.Date.from_string(rec.checkin_date)
    #         checkout_date = fields.Date.from_string(rec.checkout_date)

    #         rate_details = self.env['rate.detail'].search([
    #             ('rate_code_id', '=', rec.rate_code.id),
    #             ('from_date', '<=', checkin_date),
    #             ('to_date', '>=', checkout_date)
    #         ], limit=1)

    #         package_base_total = package_vat = package_municipality = package_untaxed = 0.0
            
    #         if rate_details:
    #             for line in rate_details.line_ids:
    #                 # base = line.packages_value or 0.0
    #                 base = rec.total_package_after_discount or 0.0
    #                 posting_item_taxes = line.packages_posting_item.taxes
    #                 unit_price = 0.0

    #                 if posting_item_taxes:
    #                     vat_tax = posting_item_taxes[0] if len(posting_item_taxes) > 0 else None
                        
    #                     if vat_tax:
    #                         percentage = vat_tax.amount
    #                         total_with_vat = base + (base * percentage / 100)
                            
    #                         if total_with_vat != 0:
    #                             unit_price = base * (base / total_with_vat)
    #                         else:
    #                             unit_price = 0.0  # fallback to prevent crash
                                
    #                         package_vat += base - unit_price
    #                         rec.packages_vat = package_vat

    #                     municipality_tax = posting_item_taxes[1] if len(posting_item_taxes) > 1 else None
                        
    #                     if municipality_tax:
    #                         percentage = municipality_tax.amount
    #                         total_with_municipality = unit_price + (unit_price * percentage / 100)
                            
    #                         if total_with_municipality != 0:
    #                             unit_price_municipality = unit_price * (unit_price / total_with_municipality)
    #                         else:
    #                             unit_price_municipality = 0.0

    #                         package_municipality += unit_price - unit_price_municipality
    #                         rec.packages_municiplaity_tax = package_municipality
    #                         package_untaxed += unit_price_municipality
    #                         rec.packages_untaxed = package_untaxed
    #                     else:
    #                         package_untaxed += unit_price
    #                         rec.packages_untaxed = package_untaxed

    #                 package_base_total += base

    def _onchange_packaged_taxes(self):
        for rec in self:
            # Initialize all package tax fields
            rec.packages_vat = 0.0
            rec.packages_municiplaity_tax = 0.0
            rec.packages_untaxed = rec.total_package_after_discount or 0.0  # Default to total package amount
            
            # Get date range for rate details
            checkin_date = fields.Date.from_string(rec.checkin_date)
            checkout_date = fields.Date.from_string(rec.checkout_date)

            # Find applicable rate details
            rate_details = self.env['rate.detail'].search([
                ('rate_code_id', '=', rec.rate_code.id),
                ('from_date', '<=', checkin_date),
                ('to_date', '>=', checkout_date)
            ], limit=1)

            if rate_details:
                package_base_total = 0.0
                total_package_vat = 0.0
                total_package_municipality = 0.0
                total_package_untaxed = 0.0

                for line in rate_details.line_ids:
                    base = rec.total_package_after_discount or 0.0
                    package_base_total += base
                    posting_item_taxes = line.packages_posting_item.taxes if line.packages_posting_item else []

                    if posting_item_taxes:
                        # Calculate VAT if exists
                        vat_tax = posting_item_taxes[0] if len(posting_item_taxes) > 0 else None
                        if vat_tax:
                            try:
                                percentage = vat_tax.amount
                                total_with_vat = base + (base * percentage / 100)
                                if total_with_vat != 0:
                                    unit_price = base * (base / total_with_vat)
                                    package_vat = base - unit_price
                                    total_package_vat += package_vat
                                    base = unit_price  # Update base for next tax calculation
                            except (ZeroDivisionError, ValueError):
                                pass

                        # Calculate Municipality tax if exists
                        municipality_tax = posting_item_taxes[1] if len(posting_item_taxes) > 1 else None
                        if municipality_tax:
                            try:
                                percentage = municipality_tax.amount
                                total_with_municipality = base + (base * percentage / 100)
                                if total_with_municipality != 0:
                                    unit_price_municipality = base * (base / total_with_municipality)
                                    package_municipality = base - unit_price_municipality
                                    total_package_municipality += package_municipality
                                    base = unit_price_municipality  # Final untaxed amount
                            except (ZeroDivisionError, ValueError):
                                pass

                    total_package_untaxed += base

                # Update record fields
                rec.packages_vat = total_package_vat
                rec.packages_municiplaity_tax = total_package_municipality
                rec.packages_untaxed = total_package_untaxed

                # Final check - if both taxes are 0, set untaxed to total package amount
                if rec.packages_vat == 0.0 and rec.packages_municiplaity_tax == 0.0:
                    rec.packages_untaxed = rec.total_package_after_discount or 0.0

    # def _onchange_fixed_post_taxes(self):
    #     for record in self:
    #         posting_items = record.posting_item_ids

    #         # Initialize totals
    #         # fixed_base = sum(line.default_value for line in posting_items)
    #         fixed_base = record.total_fixed_post_after_discount or 0.0
        
    #         fixed_vat = 0.0
    #         fixed_municipality = 0.0
    #         fixed_untaxed = 0.0
    #         base = 0.0

    #         # Loop through posting items
    #         for line in posting_items:
    #             # base = line.default_value or 0.0
    #             base = fixed_base
    #             posting_item = line.posting_item_id
    #             unit_price = 0.0

    #             if posting_item and posting_item.taxes:
    #                 vat_tax = posting_item.taxes[0] if len(posting_item.taxes) > 0 else None
    #                 if vat_tax:
    #                     vat_percentage = vat_tax.amount
    #                     total_with_vat = fixed_base + (fixed_base * (vat_percentage / 100))
    #                     if total_with_vat != 0:
    #                         unit_price = fixed_base * (fixed_base / total_with_vat)
    #                     else:
    #                         unit_price = 0.0
    #                     fixed_vat += fixed_base - unit_price
    #                     record.fixed_post_vat = fixed_vat

    #                 municipality_tax = posting_item.taxes[1] if len(posting_item.taxes) > 1 else None
    #                 if municipality_tax:
    #                     municipality_percentage = municipality_tax.amount
    #                     total_with_municipality = unit_price + (unit_price * (municipality_percentage / 100))
    #                     if total_with_municipality != 0:
    #                         unit_price_municipality = unit_price * (unit_price / total_with_municipality)
    #                     else:
    #                         unit_price_municipality = 0.0
    #                     fixed_municipality += unit_price - unit_price_municipality
    #                     record.fixed_post_municiplaity_tax = fixed_municipality
    #                     record.fixed_post_untaxed = fixed_base - fixed_vat - fixed_municipality
    #                 else:
    #                     # No municipality tax
    #                     fixed_untaxed += unit_price
                        
    #             else:
    #                 # No taxes at all
    #                 fixed_untaxed += fixed_base

    def _onchange_fixed_post_taxes(self):
        for record in self:
            # Initialize all tax fields
            record.fixed_post_vat = 0.0
            record.fixed_post_municiplaity_tax = 0.0
            record.fixed_post_untaxed = record.total_fixed_post_after_discount or 0.0  # Default to total fixed post amount
            
            fixed_base = record.total_fixed_post_after_discount or 0.0
            total_vat = 0.0
            total_municipality = 0.0
            total_untaxed = 0.0

            for line in record.posting_item_ids:
                posting_item = line.posting_item_id
                if not posting_item or not posting_item.taxes:
                    # No taxes - add full amount to untaxed
                    total_untaxed += fixed_base
                    continue
                
                base = fixed_base
                taxes = posting_item.taxes
                
                # Calculate VAT if exists
                vat_tax = taxes[0] if len(taxes) > 0 else None
                if vat_tax:
                    try:
                        percentage = vat_tax.amount
                        total_with_vat = base + (base * percentage / 100)
                        if total_with_vat != 0:
                            unit_price = base * (base / total_with_vat)
                            vat_amount = base - unit_price
                            total_vat += vat_amount
                            base = unit_price  # Update base for next tax calculation
                    except (ZeroDivisionError, ValueError):
                        pass

                # Calculate Municipality tax if exists
                municipality_tax = taxes[1] if len(taxes) > 1 else None
                if municipality_tax:
                    try:
                        percentage = municipality_tax.amount
                        total_with_municipality = base + (base * percentage / 100)
                        if total_with_municipality != 0:
                            unit_price_municipality = base * (base / total_with_municipality)
                            municipality_amount = base - unit_price_municipality
                            total_municipality += municipality_amount
                            base = unit_price_municipality  # Final untaxed amount
                    except (ZeroDivisionError, ValueError):
                        pass

                total_untaxed += base

            # Update record fields
            record.fixed_post_vat = total_vat
            record.fixed_post_municiplaity_tax = total_municipality
            record.fixed_post_untaxed = total_untaxed

            # Final check - if both taxes are 0, set untaxed to total fixed post amount
            if record.fixed_post_vat == 0.0 and record.fixed_post_municiplaity_tax == 0.0:
                record.fixed_post_untaxed = record.total_fixed_post_after_discount or 0.0
    
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
                
        self._onchange_rate_code_taxes()
        self._onchange_meal_rate_taxes()
        self._onchange_fixed_post_taxes()
        self._onchange_packaged_taxes()

        # ✅ Total Tax Summary
        record.total_municipality_tax = (
            record.room_rate_municiplaity_tax +
            record.meal_rate_municiplaity_tax +
            record.packages_municiplaity_tax +
            record.fixed_post_municiplaity_tax
        )
        record.total_vat = (
            record.room_rate_vat +
            record.meal_rate_vat +
            record.packages_vat +
            record.fixed_post_vat
        )
        record.total_untaxed = (
            record.room_rate_untaxed +
            record.meal_rate_untaxed +
            record.packages_untaxed +
            record.fixed_post_untaxed
        )

    
    total_meal_forecast = fields.Float(
        string='Total Meals',
        compute='_compute_total_meal_forecast',
        tracking=True
    )
    
    meal_taxes = fields.Many2many(
        comodel_name='account.tax',
        string='Meal Taxes',
        help='Taxes from meal posting item'
    )

    # @api.depends('rate_forecast_ids.meals', 'rate_code.include_meals', 'meal_pattern')
    # def _compute_total_meal_forecast(self):
    #     for record in self:
    #         # Check if include_meals is checked in rate.code
    #         include_meals = record.rate_code.include_meals if record.rate_code else False
            
    #         if include_meals and record.meal_pattern:
    #             # If include_meals is True, use meal rates from meal_pattern
    #             posting_item_id, meal_rate_pax, meal_rate_child, meal_rate_infant, meal_taxes = self.get_meal_rates(record.meal_pattern.id)
    #             print(f"Using meal rates from pattern: pax={meal_rate_pax}, child={meal_rate_child}, infant={meal_rate_infant}")
    #             print(f"Using meal taxes: {meal_taxes}")
                
    #             # Calculate the total based on number of adults, children, and rooms
    #             meal_rate_pax_price = meal_rate_pax * record.adult_count * record.room_count
    #             meal_rate_child_price = meal_rate_child * record.child_count * record.room_count
                
    #             # Set the total meal forecast
    #             if record.use_meal_price and record.meal_is_amount and record.meal_amount_selection.lower() == "total":
    #                 # Apply discount if needed
    #                 record.total_meal_forecast = (meal_rate_pax_price + meal_rate_child_price) - record.meal_discount
    #             else:
    #                 record.total_meal_forecast = meal_rate_pax_price + meal_rate_child_price
                    
    #             # Store the taxes for later use
    #             record.meal_taxes = meal_taxes
                    
    #             # Update the meals value in rate_forecast_ids if needed
    #             total_days = (fields.Date.from_string(record.checkout_date) - fields.Date.from_string(record.checkin_date)).days
    #             if total_days > 0 and record.rate_forecast_ids:
    #                 meal_per_day = record.total_meal_forecast / total_days
    #                 for forecast in record.rate_forecast_ids:
    #                     forecast.meals = meal_per_day
    #         else:
    #             # When include_meals is False, use rate.detail model's meal_pattern_id
    #             rate_details = self.env['rate.detail'].search([
    #                 ('rate_code_id', '=', record.rate_code.id),
    #                 ('from_date', '<=', fields.Date.from_string(record.checkin_date)),
    #                 ('to_date', '>=', fields.Date.from_string(record.checkout_date))
    #             ], limit=1)
                
    #             if rate_details and rate_details.meal_pattern_id:
    #                 # Get meal rates from rate.detail's meal_pattern_id
    #                 posting_item_id, meal_rate_pax, meal_rate_child, meal_rate_infant, meal_taxes = self.get_meal_rates(rate_details.meal_pattern_id.id)
    #                 print(f"Using meal rates from rate.detail.meal_pattern_id: pax={meal_rate_pax}, child={meal_rate_child}, infant={meal_rate_infant}")
    #                 print(f"Using meal taxes: {meal_taxes}")
                    
    #                 # Calculate the total based on number of adults, children, and rooms
    #                 meal_rate_pax_price = meal_rate_pax * record.adult_count * record.room_count
    #                 meal_rate_child_price = meal_rate_child * record.child_count * record.room_count
                    
    #                 # Set the total meal forecast
    #                 if record.use_meal_price and record.meal_is_amount and record.meal_amount_selection.lower() == "total":
    #                     # Apply discount if needed
    #                     record.total_meal_forecast = (meal_rate_pax_price + meal_rate_child_price) - record.meal_discount
    #                 else:
    #                     record.total_meal_forecast = meal_rate_pax_price + meal_rate_child_price
                    
    #                 # Store the taxes for later use
    #                 record.meal_taxes = meal_taxes
                        
    #                 # Update the meals value in rate_forecast_ids if needed
    #                 total_days = (fields.Date.from_string(record.checkout_date) - fields.Date.from_string(record.checkin_date)).days
    #                 if total_days > 0 and record.rate_forecast_ids:
    #                     meal_per_day = record.total_meal_forecast / total_days
    #                     for forecast in record.rate_forecast_ids:
    #                         forecast.meals = meal_per_day
    #             else:
    #                 # Fall back to original logic if no valid meal_pattern_id found
    #                 if record.use_meal_price:
    #                     if record.meal_amount_selection.lower() == "total":
    #                         total = sum(line.meals for line in record.rate_forecast_ids)
    #                         if record.meal_is_amount:
    #                             record.total_meal_forecast = total - (record.meal_discount)
    #                         else:
    #                             record.total_meal_forecast = sum(line.meals for line in record.rate_forecast_ids)
    #                     else:
    #                         record.total_meal_forecast = sum(line.meals for line in record.rate_forecast_ids)
    #                 else:
    #                     record.total_meal_forecast = sum(line.meals for line in record.rate_forecast_ids)

    
    
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
            record.total_fixed_post_forecast = sum(line.fixed_post for line in record.rate_forecast_ids)

    total_total_forecast = fields.Float(
        string='Grand Total',
        compute='_compute_total_total_forecast',
        store = False,
        tracking=True
    )

    # @api.depends('rate_forecast_ids.total')
    # def _compute_total_total_forecast(self):
    #     for record in self:
    #         record.total_total_forecast = sum(line.total for line in record.rate_forecast_ids)

    # @api.depends('rate_forecast_ids.total',
    #              'room_is_amount', 'room_amount_selection',
    #              'meal_is_amount', 'meal_amount_selection')
    # def _compute_total_total_forecast(self):
    #     for record in self:
    #         # Fetch rate details for the record's rate code
    #         checkin_date = fields.Date.from_string(record.checkin_date)

    #         checkin_date = fields.Date.from_string(record.checkin_date)
    #         checkout_date = fields.Date.from_string(record.checkout_date)
    #         total_days = (checkout_date - checkin_date).days
    #         _logger.info(f"Total days {total_days}")
    #         if total_days == 0:
    #             total_days = 1

    #         rate_details = self.env['rate.detail'].search([
    #             ('rate_code_id', '=', record.rate_code.id),
    #             ('from_date', '<=', checkin_date),
    #             ('to_date', '>=', checkin_date)
    #         ], limit=1)

    #         # Initialize discount-related variables
    #         is_amount_value = rate_details.is_amount if rate_details else None
    #         is_percentage_value = rate_details.is_percentage if rate_details else None
    #         amount_selection_value = rate_details.amount_selection if rate_details else None
    #         rate_detail_discount_value = int(
    #             rate_details.rate_detail_dicsount) if rate_details else 0

    #         # print(f'Rate Details -> Is Amount: {is_amount_value}, Is Percentage: {is_percentage_value}, '
    #         #       f'Amount Selection: {amount_selection_value}, Discount: {rate_detail_discount_value}')

    #         # Calculate total_total_forecast
    #         # total_sum = sum(line.total for line in record.rate_forecast_ids)
    #         total_sum = record.total_before_discount_forecast
    #         _logger.info(
    #             f"Initial Total Sum: {total_sum}, amount {is_amount_value}, percent {is_percentage_value}, amount selection {amount_selection_value}, discount {rate_detail_discount_value}")
    #         if is_amount_value and amount_selection_value == 'total':
    #             # record.total_total_forecast = total_sum - rate_detail_discount_value
    #             total_sum -= rate_detail_discount_value
    #             _logger.info(
    #                 f"After Rate Discount ({rate_detail_discount_value}): {total_sum}")

    #         for day in range(total_days):
    #             if is_amount_value and amount_selection_value == 'line_wise':
    #                 # record.total_total_forecast = total_sum - rate_detail_discount_value
    #                 total_sum -= rate_detail_discount_value
    #                 _logger.info(
    #                     f"After Rate Discount Line ({rate_detail_discount_value}): {total_sum}")

    #         if is_percentage_value and not record.use_price:
    #             # record.total_total_forecast = total_sum - rate_detail_discount_value
    #             percentage_discount = (
    #                                           total_sum * rate_detail_discount_value) / 100
    #             total_sum -= percentage_discount
    #             _logger.info(
    #                 f"After Rate Discount ({rate_detail_discount_value}): {total_sum}")

    #         # Apply discount if room_is_percentage is True for room_price
    #         if record.room_is_percentage and record.use_price:
    #             # record.total_total_forecast = total_sum - record.room_discount
    #             # percentage_discount = record.total_rate_forecast * record.room_count * record.no_of_nights
    #             for line in record.rate_forecast_ids: 
    #                 room_rate = line.before_discount - line.meals - line.packages - line.fixed_post
    #                 percentage_discount = (
    #                         room_rate * record.room_discount * record.room_count * record.no_of_nights)
    #                 total_sum -= percentage_discount
    #             _logger.info(
    #                 f"After Percent Room Discount ({record.room_discount}): {total_sum}")

    #         # Apply discount if is_amount is True and amount_selection_value is 'total' for room_price
    #         if record.room_is_amount and record.room_amount_selection == 'total' and record.use_price:
    #             # record.total_total_forecast = total_sum - record.room_discount
    #             total_sum -= record.room_discount
    #             _logger.info(
    #                 f"After Total Room Discount ({record.room_discount}): {total_sum}")

    #         # Apply discount if is_amount is True and amount_selection_value is 'line_wise' for room_price
    #         if record.room_is_amount and record.room_amount_selection == 'line_wise' and record.use_price:
    #             # record.total_total_forecast = total_sum - record.room_discount
    #             total_sum -= record.room_discount * record.no_of_nights
    #             _logger.info(
    #                 f"After Line wise Room Discount ({record.room_discount}): {total_sum}")

    #         # Apply discount if meal_is_percentage is True for room_price
    #         if record.meal_is_percentage and record.use_meal_price:
    #             # record.total_total_forecast = total_sum - record.room_discount
    #             percentage_discount = (
    #                     record.meal_price * record.meal_discount * record.adult_count * record.no_of_nights * record.room_count)
    #             percentage_discount += (
    #                     record.meal_child_price * record.meal_discount * record.child_count * record.no_of_nights * record.room_count)
    #             total_sum -= percentage_discount
    #             _logger.info(
    #                 f"After Percent Meal Discount ({record.meal_discount}): {total_sum}")

    #         # Apply discount if is_amount is True and amount_selection_value is 'total' for meal_price
    #         if record.meal_is_amount and record.meal_amount_selection == 'total' and record.use_meal_price:
    #             # record.total_total_forecast = total_sum - record.meal_discount
    #             total_sum -= record.meal_discount
    #             _logger.info(
    #                 f"After Total Meal Discount ({record.meal_discount}): {total_sum}")

    #         # Apply discount if is_amount is True and amount_selection_value is 'line_wise' for meal_price
    #         if record.meal_is_amount and record.meal_amount_selection == 'line_wise' and record.use_meal_price:
    #             # record.total_total_forecast = total_sum - record.meal_discount
    #             total_sum -= record.meal_discount * record.no_of_nights
    #             _logger.info(
    #                 f"After Line wise Meal Discount ({record.meal_discount}): {total_sum}")

    #             # Ensure the total doesn't go below zero
    #         record.total_total_forecast = total_sum

    @api.depends(
    'rate_forecast_ids.total',
    'room_is_amount', 'room_amount_selection',
    'meal_is_amount', 'meal_amount_selection'
)
    def _compute_total_total_forecast(self):
        for record in self:

            checkin_date = fields.Date.from_string(record.checkin_date)
            checkout_date = fields.Date.from_string(record.checkout_date)
            total_days = (checkout_date - checkin_date).days


            rate_details = self.env['rate.detail'].search([
                ('rate_code_id', '=', record.rate_code.id),
                ('from_date', '<=', checkin_date),
                ('to_date', '>=', checkin_date)
            ], limit=1)

            is_amount_value = rate_details.is_amount if rate_details else None
            is_percentage_value = rate_details.is_percentage if rate_details else None
            amount_selection_value = rate_details.amount_selection if rate_details else None
            percentage_selection_value = rate_details.percentage_selection if rate_details else None
            rate_detail_discount_value = int(rate_details.rate_detail_dicsount) if rate_details else 0

            total_rate_forecast = record.total_rate_forecast or 0
            total_meal_forecast = record.total_meal_forecast or 0
            total_package_forecast = record.total_package_forecast or 0
            total_fixed_post_forecast = record.total_fixed_post_forecast or 0

            total_sum = (
                total_rate_forecast
                + total_meal_forecast
                + total_package_forecast
                + total_fixed_post_forecast
            )


            # if is_amount_value and amount_selection_value == 'total':
            #     record.total_total_forecast = total_sum - rate_detail_discount_value
            #     record.total_rate_after_discount = total_rate_forecast - rate_detail_discount_value  * total_days
            #     record.total_meal_after_discount = total_meal_forecast - rate_detail_discount_value  * total_days
            #     record.total_package_after_discount = total_package_forecast - rate_detail_discount_value  * total_days
            #     record.total_fixed_post_after_discount = total_fixed_post_forecast 
            #     record.total_total_forecast = record.total_rate_after_discount + record.total_meal_after_discount + record.total_package_after_discount + record.total_fixed_post_after_discount

            if is_amount_value and amount_selection_value == 'total':
                # Calculate total discount first
                total_discount = rate_detail_discount_value
                
                # Apply discounts with protection against negative values
                rate_discount_amount = rate_detail_discount_value * total_days
                record.total_rate_after_discount = max(0, total_rate_forecast - rate_discount_amount)
                
                meal_discount_amount = rate_detail_discount_value * total_days
                record.total_meal_after_discount = max(0, total_meal_forecast - meal_discount_amount)
                
                package_discount_amount = rate_detail_discount_value * total_days
                record.total_package_after_discount = max(0, total_package_forecast - package_discount_amount)
                
                # Fixed post doesn't get discounted
                record.total_fixed_post_after_discount = total_fixed_post_forecast 
                
                # Recalculate total forecast based on protected values
                record.total_total_forecast = (
                    record.total_rate_after_discount + 
                    record.total_meal_after_discount + 
                    record.total_package_after_discount + 
                    record.total_fixed_post_after_discount
                )

            elif is_amount_value and amount_selection_value == 'line_wise':
                rate_discount_amount = rate_detail_discount_value * record.room_count * total_days
                record.total_rate_after_discount = max(0, total_rate_forecast - rate_discount_amount)
                record.total_meal_after_discount = max(0, total_meal_forecast - rate_discount_amount)
                record.total_package_after_discount = max(0, total_package_forecast - rate_discount_amount) 
                record.total_fixed_post_after_discount = total_fixed_post_forecast 
                record.total_total_forecast = record.total_rate_after_discount + record.total_meal_after_discount + record.total_package_after_discount + record.total_fixed_post_after_discount

            elif is_percentage_value and percentage_selection_value == 'total':
                rate_discount_amount = (total_rate_forecast * rate_detail_discount_value / 100) 
                meal_discount_amount = (total_meal_forecast * rate_detail_discount_value / 100) 
                package_discount_amount = (total_package_forecast * rate_detail_discount_value / 100) 

                record.total_rate_after_discount = max(0, record.total_rate_forecast - rate_discount_amount)
                record.total_meal_after_discount = max(0, record.total_meal_forecast - meal_discount_amount)
                record.total_package_after_discount = max(0, record.total_package_forecast - package_discount_amount)
                record.total_fixed_post_after_discount = total_fixed_post_forecast  # No discount applied here
                record.total_total_forecast = record.total_rate_after_discount + record.total_meal_after_discount + record.total_package_after_discount + record.total_fixed_post_after_discount

            elif is_percentage_value and percentage_selection_value == 'line_wise':
                room_count = record.room_count or 1
                rate_discount_amount = record.total_rate_forecast * (rate_detail_discount_value / 100)     
                meal_discount_amount = record.total_meal_forecast * (rate_detail_discount_value / 100)
                package_discount_amount = record.total_package_forecast * (rate_detail_discount_value / 100)
                # Final totals after discount
                record.total_total_forecast = total_sum - (rate_discount_amount + meal_discount_amount + package_discount_amount)
                record.total_rate_after_discount = total_rate_forecast - rate_discount_amount
                record.total_meal_after_discount = total_meal_forecast - meal_discount_amount
                record.total_package_after_discount = total_package_forecast - package_discount_amount
                record.total_fixed_post_after_discount = total_fixed_post_forecast  
                record.total_total_forecast = record.total_rate_after_discount + record.total_meal_after_discount + record.total_package_after_discount + record.total_fixed_post_after_discount

            
            # elif is_percentage_value:
            #     discount_amount = (total_sum * rate_detail_discount_value) / 100
            #     record.total_total_forecast = total_sum - discount_amount

            # elif is_percentage_value:
            #     record.total_total_forecast = (total_sum * rate_detail_discount_value) / 100
            #     print(f"Applied percentage discount: {rate_detail_discount_value}%")
            
            else:
                record.total_total_forecast = total_sum or 0

    
    total_rate_after_discount = fields.Float(
        string='Total Rate After Discount'
    )

    total_meal_after_discount = fields.Float(
        string='Total Meal After Discount'
    )

    total_package_after_discount = fields.Float(
        string='Total Package After Discount'
    )

    total_fixed_post_after_discount = fields.Float(
        string='Total Fixed Post After Discount'
    )

    # @api.onchange('total_fixed_post_after_discount')
    # def _onchange_fixed_post(self):
    #     self._onchange_fixed_post_taxes()


    total_before_discount_forecast = fields.Float(
        string='Grand Total Before Discount',
        compute='_compute_total_before_discount_forecast'
    )

    @api.depends('rate_forecast_ids.before_discount')
    def _compute_total_before_discount_forecast(self):
        for record in self:
            # record.total_before_discount_forecast = record.total_rate_forecast + record.total_meal_forecast + record.total_package_forecast + record.total_fixed_post_forecast
            record.total_before_discount_forecast = sum(line.before_discount for line in record.rate_forecast_ids)

    def get_meal_rates(self, id):
        meal_rate_pax = 0
        meal_rate_child = 0
        meal_rate_infant = 0
        posting_item_id = None
        

        meal_pattern = self.env['meal.pattern'].search([('id', '=', id)])
        if meal_pattern:
            posting_item_id = meal_pattern.meal_posting_item.id
            for meal_code in meal_pattern.meals_list_ids:
                meal_rate_pax += meal_code.meal_code.price_pax
                meal_rate_child += meal_code.meal_code.price_child
                meal_rate_infant += meal_code.meal_code.price_infant
            

        return posting_item_id, meal_rate_pax, meal_rate_child, meal_rate_infant

    
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
            # Check if price type is "room_only" and meal_pattern.id is False
            if rate_details.price_type == "rate_meals":
                take_meal_price = True

            if rate_details.price_type == "room_only":
                take_meal_price = False

            # Check if meal_pattern.id exists
            if record.meal_pattern.id:
                take_meal_price = True

            # elif rate_details.price_type == "rate_meals":
            #     _logger.info("Meal pattern does not exist, setting take_meal_price to False")
            #     take_meal_price = False

        if take_meal_price:
            if not record.use_meal_price:
                _1, meal_rate_pax, meal_rate_child, _not_used = self.get_meal_rates(
                    record.meal_pattern.id)

                if meal_rate_pax == 0:
                    if rate_details:
                        if rate_details.customize_meal == 'meal_pattern':
                            _1, meal_rate_pax, meal_rate_child, _not_used = self.get_meal_rates(
                                rate_details[0].meal_pattern_id.id)
                        elif rate_details.customize_meal == 'customize':
                            meal_rate_pax = rate_details.adult_meal_rate
                            meal_rate_child = rate_details.child_meal_rate
                            # meal_rate_infant = rate_details.infant_meal_rate

                # meal_rate_pax_price = meal_rate_pax * record.adult_count
                meal_rate_pax_price = meal_rate_pax * record.adult_count * record.room_count
                # print("MEAL PRICE ADULT", meal_rate_pax_price)
                # meal_rate_child_price = meal_rate_child * record.child_count
                meal_rate_child_price = meal_rate_child * \
                                        record.child_count * record.room_count
                # print("MEAL PRICE CHILD", meal_rate_child_price)
                # meal_rate_infant_price = meal_rate_infant * \
                #     record.infant_count * record.room_count
                # print("MEAL PRICE INFANT", meal_rate_infant_price)
                meal_price += (meal_rate_pax_price + meal_rate_child_price)
                # print("MEAL PRICE FINAL", meal_price)
                # meal_price += record.meal_price * record.adult_count * record.room_count
            else:
                meal_price += record.meal_price * record.adult_count * record.room_count
                meal_price += record.meal_child_price * record.child_count * record.room_count
                # meal_price += record.meal_infant_price * \
                #     record.infant_count * record.room_count

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
                    if record.hotel_room_type:
                        room_type_specific_rate = self.env['room.type.specific.rate'].search([
                            ('rate_code_id', '=', record.rate_code.id),
                            ('from_date', '<=', forecast_date),
                            ('to_date', '>=', forecast_date),
                            ('room_type_id', '=', record.hotel_room_type.id),
                            ('company_id', '=', self.env.company.id)
                        ], limit=1)

                        if room_type_specific_rate.id:
                            _room_type_var = f"room_type_{_day}_pax_{record.adult_count}"
                            if record.adult_count > 6:
                                _room_type_var = f"room_type_{_day}_pax_1"
                                room_price += room_type_specific_rate[_room_type_var] * record.adult_count
                            else:
                                room_price += room_type_specific_rate[_room_type_var]

                            _room_type_child_rate = f"room_type_{_day}_child_pax_1"
                            room_price += room_type_specific_rate[_room_type_child_rate] * record.child_count

                            _room_type_infant_rate = f"room_type_{_day}_infant_pax_1"
                            room_price += room_type_specific_rate[_room_type_infant_rate] * record.infant_count

                        else:
                            room_price += rate_details[0][_var] * record.room_count * _adult_count
                            # print("ROOM PRICE ADULT", room_price)
                            room_price += rate_details[0][_var_child] * record.room_count * record.child_count
                            # print("ROOM PRICE CHILD", room_price)
                            room_price += rate_details[0][_var_infant] * record.room_count * record.infant_count

                    else:
                        room_price += rate_details[0][_var] * record.room_count * _adult_count
                        # print("ROOM PRICE ADULT", room_price)
                        room_price += rate_details[0][_var_child] * record.room_count * record.child_count
                        # print("ROOM PRICE CHILD", room_price)
                        room_price += rate_details[0][_var_infant] * record.room_count * record.infant_count
                    # print("ROOM PRICE INFANT", room_price)

                    room_price_room_line = self.get_rate_details_on_room_number_specific_rate(_day, record, forecast_date)
                    if room_price_room_line > 0:
                        room_price = room_price_room_line
                # else:
                #     room_price += 0
                # if len(rate_details) == 1:
                #     room_price += rate_details[_var] * record.room_count

                elif len(rate_details) > 1:
                    room_price += rate_details[0][_var] * record.room_count
                    # print("ROOM PRICE ADULT 1", room_price)
                    room_price += rate_details[0][_var_child] * record.room_count
                    # print("ROOM PRICE CHILD 1", room_price)
                    room_price += rate_details[0][_var_infant] * record.room_count
                    # print("ROOM PRICE INFANT 1", room_price)

                # else:
                #     room_price += 0

            elif record.use_price:
                room_price += record.room_price * record.room_count
                room_price += record.room_child_price * record.room_count
                room_price += record.room_infant_price * record.room_count

        if record.rate_code.id:
            for line in rate_details.line_ids:
                posting_item_id = line.packages_posting_item.id
                line_posting_items.append(posting_item_id)
                # print(f"Posting Item ID lne: {posting_item_id}")
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
    def calculate_total(self, price, discount, is_percentage, is_amount, percentage_selection, amount_selection, condition,
                            room_price=0.0,
                            meal_price=0.0,   
                            package_price=0.0):
        if condition:
            multiplier = 0
            if room_price != 0:
                multiplier += 1
            if meal_price != 0:
                multiplier += 1
            if package_price != 0:
                multiplier += 1
            # if is_percentage:
            #     total = (price * discount)
            if is_amount and amount_selection == 'line_wise':
                total = discount * self.room_count * multiplier
            elif is_amount and amount_selection == 'total':
                total = discount * multiplier
            # elif is_percentage and percentage_selection == 'line_wise':
            #     print("Percentage Selection Line Wise")
            #     total = (price * discount) / 100 
            
            # elif is_percentage and percentage_selection == 'line_wise':
            elif is_percentage and percentage_selection in ['line_wise', 'total']:
                discount_ = 0.0
                # Get first forecast line
                if self.rate_forecast_ids:
                    forecast_line = self.rate_forecast_ids[0]
                    rate = forecast_line.rate or 0.0
                    meals = forecast_line.meals or 0.0
                    packages = forecast_line.packages or 0.0
                    forecast_line_fixed_post = forecast_line.fixed_post or 0.0
                    price = rate + meals + packages
                    discount_ = price * discount 
                else:
                    price = 0.0
                
                total = round(discount_, 2)

            # elif is_percentage and percentage_selection == 'total':
            #     total = (price * discount) / 100
            else:
                total = 0
        else:
            total = 0

        return total  # Ensure the total doesn't go below zero

    
    
    
    @api.model
    def calculate_meal_rates(self, rate_details):
        total_default_value = 0

        # Retrieve the posting item from rate details
        rate_detail_posting_item = rate_details.posting_item if rate_details else 0
        if rate_detail_posting_item:
            # Get the default value of the posting item
            default_value = getattr(rate_detail_posting_item, 'default_value', 0)
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
                 'meal_amount_selection', 'use_price', 'use_meal_price', 'room_line_ids.room_id','complementary',
                 'complementary_codes')
    def _get_forecast_rates(self, from_rate_code=False):
        for record in self:
            checkin_date = fields.Date.from_string(record.checkin_date)
            checkout_date = fields.Date.from_string(record.checkout_date)
            total_days = (checkout_date - checkin_date).days
            if total_days == 0:
                total_days = 1
            _system_date = fields.Date.from_string(self.env.company.system_date)

            for rate_forecast in record.rate_forecast_ids:
                if rate_forecast:
                    if isinstance(rate_forecast.room_booking_id, NewId):
                        continue

                    # Check if rate_forecast's date is between checkin_date and checkout_date
                    forecast_date = fields.Date.from_string(rate_forecast.date)
                    if not (checkin_date <= forecast_date < checkout_date):
                        # Set room_booking_id to None if not in range
                        rate_forecast.room_booking_id = None

            if not record.checkin_date or not record.checkout_date:
                record.rate_forecast_ids = []
                continue

            checkin_date = fields.Date.from_string(record.checkin_date)
            checkout_date = fields.Date.from_string(record.checkout_date)
            total_days = (checkout_date - checkin_date).days
            if total_days == 0:
                total_days = 1

            _system_date = self.env.company.system_date

            from_start = True
            if record.state == 'check_in':
                from_start = False

            
            posting_items = record.posting_item_ids

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
            percentage_selection_value = rate_details.percentage_selection if rate_details else None
            if is_amount_value:
                rate_detail_discount_value = int(
                    rate_details.rate_detail_dicsount) if rate_details else 0
            else:
                rate_detail_discount_value = int(rate_details.rate_detail_dicsount) / 100 if rate_details else 0

            # if is_percentage_value:
            #     print("Percentage Value")
            #     rate_detail_discount_value = int(rate_details.rate_detail_dicsount) if rate_details else 0
            #     print("Rate Detail Discount Value Percentage", rate_detail_discount_value)
            # else:
            #     print("ELSE Percentage Value")
            #     rate_detail_discount_value = int(rate_details.rate_detail_dicsount) / 100 if rate_details else 0


            # Prepare forecast rates
            forecast_lines = []

            for day in range(total_days):
                # if not from_start:
                #     forecast_date = _system_date + timedelta(days=day)
                # else:
                forecast_date = checkin_date + timedelta(days=day)
                change = True
                today_date = fields.Date.today()
                if record.state == 'check_in':
                    _date = _system_date.date()
                    if forecast_date < _date and not from_rate_code:
                        change = False

                    if forecast_date < today_date and from_rate_code:
                        change = False

                # if today_date < forecast_date and _system_date > today_date:
                #     change = False

                if change:
                    meal_price, room_price, package_price, _1, _2 = self.get_all_prices(forecast_date, record)
                    if day == 0:  # First day logic
                        if every_night_value is None:
                            # Adjusted for room_count
                            fixed_post_value = (first_night_value or 0) * record.room_count
                        elif first_night_value is None:
                            # Adjusted for room_count
                            fixed_post_value = (every_night_value or 0) * record.room_count
                        else:
                            fixed_post_value = (first_night_value + every_night_value) * record.room_count
                    else:  # Other days
                        if every_night_value is None:
                            # Adjusted for room_count
                            fixed_post_value = (first_night_value or 0) * record.room_count
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

                    # Search for existing forecast record
                    existing_forecast = self.env['room.rate.forecast'].search([
                        ('room_booking_id', '=', room_booking_id),
                        ('date', '=', forecast_date)
                    ], limit=1)


                    if not record.use_price:
                        _room_price = room_price
                    else:
                        _room_price = record.room_price * record.room_count

                    room_price_after_discount = record.calculate_total(
                                                        _room_price,
                                                        record.room_discount,
                                                        record.room_is_percentage,
                                                        percentage_selection_value,
                                                        record.room_is_amount,
                                                        record.room_amount_selection,
                                                        record.use_price, 0, 0 ,0)

                    if not record.use_meal_price:
                        _meal_price = meal_price
                    else:
                        _meal_price = record.meal_price * record.adult_count * record.room_count
                        _meal_price += record.meal_child_price * record.child_count * record.room_count
                    meal_price_after_discount = record.calculate_total(
                        _meal_price,
                        record.meal_discount,
                        record.meal_is_percentage,
                        percentage_selection_value,
                        record.meal_is_amount,
                        record.meal_amount_selection, record.use_meal_price, 0, 0, 0)
                    
                    
                    
                    before_discount = room_price + meal_price + package_price + fixed_post_value

                    

                    get_discount = self.calculate_total(before_discount, rate_detail_discount_value,
                                                        is_percentage_value, is_amount_value, percentage_selection_value,
                                                        amount_selection_value, True, room_price, meal_price, package_price)    

                                                # (self, price, discount, is_percentage, is_amount, percentage_selection, amount_selection, condition)

                    # if is_percentage_value:
                    #     get_discount = 0

                    # total = before_discount - get_discount - room_price - meal_price
                    total = before_discount - get_discount - room_price_after_discount - meal_price_after_discount
                    
                    room_line_ids = record.room_line_ids.ids
                    actual_room_price = room_price - room_price_after_discount
                    actual_meal_price = meal_price - meal_price_after_discount
                    if record.complementary and record.complementary_codes.id:
                        if record.complementary_codes.type == 'room':
                            actual_room_price = 0

                        elif record.complementary_codes.type == 'fb':
                            actual_meal_price = 0

                        elif record.complementary_codes.type == "both":
                            actual_room_price = 0
                            actual_meal_price = 0
                        
                        before_discount = actual_room_price + actual_meal_price + package_price + fixed_post_value

                        total = before_discount - get_discount - \
                            room_price_after_discount - meal_price_after_discount


                    if existing_forecast:
                        existing_forecast.write({
                            # 'rate': room_price,
                            # 'rate': room_price_after_discount,
                            'rate': actual_room_price,
                            # 'meals': meal_price,
                            'meals': actual_meal_price,
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
                            'rate': actual_room_price,
                            # 'rate': room_price_after_discount if record.room_price else room_price,
                            # 'meals': meal_price_after_discount if record.meal_price else meal_price,
                            'meals': actual_meal_price,
                            'packages': package_price,
                            'fixed_post': fixed_post_value,
                            'total': total,
                            'before_discount': before_discount,
                            'booking_line_ids': [(6, 0, room_line_ids)]
                        }))


            # Assign forecast lines to the record
            record.rate_forecast_ids = forecast_lines

            

    # hotel_id = fields.Many2one('hotel.hotel', string="Hotel",
    #                            help="Hotel associated with this booking", tracking=True)

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
        'group.booking', string="Group Booking", domain=[('group_name', '!=', False)],
        help="Group associated with this booking", tracking=True)

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
            self.reference_contact_= self.group_booking.reference if self.group_booking.reference else False
            # self.partner_id = self.group_booking.company.id if self.group_booking.company else False
            # Ensure 'partner_id' (Contact) is assigned correctly
            # Ensure 'partner_id' (Contact) is assigned correctly
            
            self.source_of_business = self.group_booking.source_of_business.id if self.group_booking.source_of_business else False
            self.rate_code = self.group_booking.rate_code.id if self.group_booking.rate_code else False
            self.meal_pattern = self.group_booking.group_meal_pattern.id if self.group_booking.group_meal_pattern else False
            self.market_segment = self.group_booking.market_segment.id if self.group_booking.market_segment else False
            self.house_use = self.group_booking.house_use
            self.complementary = self.group_booking.complimentary
            self.payment_type = self.group_booking.payment_type
            # self.is_agent = self.group_booking.is_grp_company

            
            self.complementary_codes = self.group_booking.complimentary_codes.id if self.group_booking.complimentary_codes else False
            self.house_use_codes = self.group_booking.house_use_codes_.id if self.group_booking.house_use_codes_ else False
            if self.group_booking.company and self.group_booking.company.is_vip:
                self.vip = True
                self.vip_code = self.group_booking.company.vip_code.id if self.group_booking.company.vip_code else False
            else:
                self.vip = False
                self.vip_code = False

            self.is_agent = self.group_booking.is_grp_company
            if self.group_booking.company:
                self.partner_id = self.group_booking.company.id
            else:
                # Debugging line
                self.partner_id = False  # Reset partner_id if no company is set
            # self.meal_pattern = self.group_booking.meal_pattern.id if self.group_booking.meal_pattern else False
            # self.partner_id = self.group_booking.contact.id if self.group_booking.contact else False

    agent = fields.Many2one('agent.agent', string="Agent",
                            help="Agent associated with this booking", tracking=True)
    is_vip = fields.Boolean(related='partner_id.is_vip',
                            string="IS VIP", store=True,
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
                                 default=lambda self: self.env.company,
                                 readonly=True)
    # partner_id = fields.Many2one('res.partner', string="Customer",
    #                              help="Customers of hotel",
    #                              required=True, index=True, tracking=1,
    #                              domain="[('type', '!=', 'private'),"
    #                                     " ('company_id', 'in', "
    #                                     "(False, company_id))]")
    is_agent = fields.Boolean(string='Is Company')
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=False
        
    )

    company_ids_ = fields.Many2many(
        'res.partner',
        compute='_compute_company_ids',
        store=False
        )

    def _compute_company_ids(self):
        for rec in self:
            companies = self.env['res.company'].search([]).mapped('partner_id').ids
            rec.company_ids_ = companies


    
    @api.onchange('is_agent')
    def _onchange_is_agent(self):
        # (Optional) Clear the previously selected partner:
        # self.partner_id = False
        
        # Gather partner IDs used by Odoo companies
        company_partner_ids = self.env['res.company'].search([]).mapped('partner_id').ids
        
        # Return a domain excluding those company-partner IDs
        return {
            'domain': {
                'partner_id': [
                    ('is_company', '=', self.is_agent),
                    ('id', 'not in', company_partner_ids),
                ]
            }
        }

    # reference_contact = fields.Many2one(
    #     'res.partner',
    #     string='Contact Reference'

    # )

    reference_contact_ = fields.Char(string=_('Contact Reference'))


    @api.onchange('partner_id')
    def _onchange_customer(self):
        if self.group_booking:
            # If group_booking is selected, skip this onchange
            return

        if self.partner_id:
            self.nationality = self.partner_id.nationality.id
            self.source_of_business = self.partner_id.source_of_business.id
            self.market_segment = self.partner_id.market_segments.id

            # Fetch the rate_code and meal_pattern from partner.detail based on partner_id and current company
            partner_detail = self.env['partner.details'].search([
                ('partner_id', '=', self.partner_id.id),
                ('partner_company_id', '=', self.env.company.id)  # Ensure it matches the current company
            ], limit=1)

            if partner_detail:
                self.rate_code = partner_detail.rate_code.id
                self.meal_pattern = partner_detail.meal_pattern.id
            else:
                self.rate_code = False
                self.meal_pattern = False

            # Set VIP details
            if self.partner_id.is_vip:
                self.vip = True
                self.vip_code = self.partner_id.vip_code.id if self.partner_id.vip_code else False
            else:
                self.vip = False
                self.vip_code = False




    # date_order = fields.Datetime(string="Order Date",
    #                              required=True, copy=False,
    #                              help="Creation date of draft/sent orders,"
    #                                   " Confirmation date of confirmed orders",
    #                              default=fields.Datetime.now)

    # date_order = fields.Datetime(string='Order Date', required=True, default=lambda self: self._get_default_order_date())
    date_order = fields.Datetime(string='Order Date', required=True, default=lambda self: self.env.company.system_date)

    @api.onchange('company_id')
    def _onchange_company_id_date_order(self):
        if self.company_id:
            self.date_order = self.company_id.system_date

    # @api.model
    # def _get_default_order_date(self):
    #     # Get the system date from res.company
    #     system_date = lambda self: self.env.user.company_id.system_date
    #     # system_date = self.env['res.company'].search([], limit=1).system_date
    #     return system_date or fields.Datetime.now()

    search_done = fields.Boolean(string="Search Done", default=False)


    def write(self, vals):
        # if self.env.context.get('ignore_search_guard'):
        #     return super().write(vals)

        # for rec in self:
        #     future_state = vals.get("state", rec.state)
        #     future_flag  = vals.get("search_performed",
        #                              rec.search_performed)
        #     if future_state == "confirmed" and not future_flag:
        #         raise ValidationError(_(
        #             "You changed the Room Count. "
        #             "Click the “Search Rooms” button before saving."
        #         ))
            
        self.check_room_meal_validation(vals, True)

        if 'company_id' in vals:
            company = self.env['res.company'].browse(vals['company_id'])
            if 'checkin_date' not in vals:  # Only update if not explicitly provided
                vals['checkin_date'] = company.system_date
            # if 'date_order' not in vals:  # Only update if not explicitly provided
            #     vals['date_order'] = company.system_date

        
        if 'active' in vals and vals['active'] is False:
            res = super(RoomBooking, self).write(vals)
            return res

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
            raise ValidationError(_("Check-In Date is required and cannot be empty."))
        
        # if 'checkin_date' in vals or 'checkout_date' in vals:
        #     for booking in self:
        #         updated_checkin_date = vals.get('checkin_date', booking.checkin_date)
        #         updated_checkout_date = vals.get('checkout_date', booking.checkout_date)
        #
        #         # Update the associated room.booking.line records
        #         booking.room_line_ids.write({
        #             'checkin_date': updated_checkin_date,
        #             'checkout_date': updated_checkout_date
        #         })
        if 'checkin_date' in vals or 'checkout_date' in vals:
            for booking in self:
                updated_checkin_date = vals.get('checkin_date', booking.checkin_date)
                updated_checkout_date = vals.get('checkout_date', booking.checkout_date)

                if booking.state == 'block' and booking.room_line_ids:
                    for line in booking.room_line_ids:
                        overlapping_bookings = self.env['room.booking.line'].search([
                            ('room_id', '=', line.room_id.id),
                            ('id', '!=', line.id),  # Exclude current line
                            ('state', '=', 'block'),  # You can also include other active states like 'confirmed'
                            ('checkin_date', '<', updated_checkout_date),
                            ('checkout_date', '>', updated_checkin_date)
                        ])
                        if overlapping_bookings:
                            raise UserError(f"Room {line.room_id.name} is already booked for the selected date range.")

                    # No conflicts found, update the dates
                    booking.room_line_ids.write({
                        'checkin_date': updated_checkin_date,
                        'checkout_date': updated_checkout_date
                    })

        # if 'date_order' not in vals:
        #     system_date = self.env['res.company'].search(
        #         [], limit=1).system_date
        #     if system_date:
        #         vals['date_order'] = system_date
        # print("in write for testing", vals)
        # Determine if 'state' is being updated
        state_changed = 'state' in vals and vals['state'] != self.state

        # Perform the write operation
        res = super(RoomBooking, self).write(vals)
        # print("in write vals1",state_changed)

        if state_changed:
            new_state = vals.get('state')
            get_sys_date = self.env.company.system_date.date() 
            current_time = datetime.now().time()
            get_sys_date = datetime.combine(get_sys_date, current_time)
            for record in self:
                for line in record.room_line_ids:
                    self.env['room.booking.line.status'].create({
                        'booking_line_id': line.id,
                        'status': new_state,
                        # 'change_time': fields.Datetime.now(),
                        'change_time': get_sys_date,
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
                print(final_room_line, "this is final", final_room_line.counter, vals.get('parent_booking_id'))
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

                for infant in self.infant_ids:
                    if final_room_line:
                        infant.room_id = final_room_line.room_id.id

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
                                #    default=lambda self: self.env.user.company_id.system_date.date() + datetime.now().time(),
                                default=lambda self: self.env.user.company_id.system_date.replace(hour=0, minute=0, second=0, microsecond=0),
                                   #    default=lambda self: fields.Datetime.now(),
                                   help="Date of Checkin", required=True, tracking=True)

    # default=fields.Datetime.now()
    checkout_date = fields.Datetime(string="Check Out",
                                    help="Date of Checkout", required=True, tracking=True)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Update checkin_date based on the new company's system_date."""
        if self.company_id:
            self.checkin_date = self.company_id.system_date.replace(hour=0, minute=0, second=0, microsecond=0)

    @api.onchange('checkin_date')
    def _onchange_checkin_date(self):
        # current_time = fields.Datetime.now() - timedelta(minutes=10)  # 10-minute buffer
        system_date = lambda self: self.env.user.company_id.system_date,
        # if self.checkin_date and self.checkin_date < system_date:
        #     raise UserError(
        #         "Check-In Date cannot be more than 10 minutes in the past. Please select a valid time.")

        if self.checkin_date:
            # Set checkout_date to the end of the checkin_date
            self.checkout_date = self.checkin_date + timedelta(hours=23, minutes=59, seconds=59)

    # no_of_nights = fields.Integer(string="No of Nights", default=1)

    no_of_nights = fields.Integer(
        string="No of Nights",
        compute="_compute_no_of_nights",
        inverse="_inverse_no_of_nights",
        default=1,
        store=True,
        readonly=False,  # so the user can edit it if you want to allow that
    )

    # @api.depends('checkin_date', 'checkout_date')
    # def _compute_no_of_nights(self):
    #     """
    #     Calculate the difference in days between Check-In and Check-Out.
    #     If either date is missing or checkout < checkin, result is 0.
    #     """
    #     for rec in self:
    #         if rec.checkin_date and rec.checkout_date:
    #             # If checkout is before checkin, just interpret as 0
    #             delta_days = (rec.checkout_date - rec.checkin_date).days
    #             rec.no_of_nights = delta_days if delta_days >= 0 else 0
    #         else:
    #             rec.no_of_nights = 0

    @api.depends('checkin_date', 'checkout_date')
    def _compute_no_of_nights(self):
        for rec in self:
            if rec.checkin_date and rec.checkout_date:
                # Convert to date objects so time of day is ignored
                in_date = fields.Date.to_date(rec.checkin_date)
                out_date = fields.Date.to_date(rec.checkout_date)
                diff_days = (out_date - in_date).days
                rec.no_of_nights = diff_days if diff_days >= 0 else 0
            else:
                rec.no_of_nights = 0

    # def _inverse_no_of_nights(self):
    #     """
    #     When a user edits no_of_nights directly, recompute checkout_date
    #     based on checkin_date + no_of_nights days.
    #     """
    #     for rec in self:
    #         # Only update checkout_date if we have a checkin_date
    #         # and a non-negative no_of_nights
    #         if rec.checkin_date and rec.no_of_nights >= 0:
    #             rec.checkout_date = rec.checkin_date + timedelta(days=rec.no_of_nights)
    #         # If checkin_date is empty or no_of_nights < 0, do nothing

    def _inverse_no_of_nights(self):
        """
        When a user edits no_of_nights directly, recompute checkout_date
        based on checkin_date + no_of_nights days.
        If no_of_nights is 0, set checkout_date to 2 hours after checkin_date.
        """
        for rec in self:
            if rec.checkin_date:
                if rec.no_of_nights > 0:
                    # Normal case: Add no_of_nights days
                    rec.checkout_date = rec.checkin_date + timedelta(days=rec.no_of_nights)
                else:
                    # If no_of_nights is 0, set checkout_date to 2 hours after checkin_date
                    rec.checkout_date = rec.checkin_date + timedelta(hours=2)
    
    
    

    @api.onchange('checkout_date')
    def _onchange_checkout_date(self):
        if self.checkin_date and self.checkout_date:
            if self.checkout_date < self.checkin_date:
                self.checkout_date = self.checkin_date + timedelta(days=1)
                print("Checkout Date: %s", self.checkout_date)
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
            current_time = fields.Datetime.context_timestamp(self, fields.Datetime.now())
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

    
    def _adjust_checkout_date(self):
        """Adjust checkout_date to one day after checkin_date if invalid."""
        if self.checkin_date:
            self.checkout_date = self.checkin_date + timedelta(days=1)

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

        

    @api.onchange('no_show_')
    def _onchange_no_show(self):
        """Update child room lines to 'no_show' when parent is marked as 'No Show'."""
        if self.no_show_:
            for line in self.room_line_ids:
                if line.state == 'block':
                    line.state = 'no_show'

    show_confirm_button = fields.Boolean(string="Confirm Button")
    show_cancel_button = fields.Boolean(string="Cancel Button")

    # hotel_room_type = fields.Many2one(
    #     'room.type', string="Room Type", 
    #     domain=lambda self: [
    #     ('obsolete', '=', False),
    #     ('id', 'in', self.env['hotel.inventory'].search([
    #         ('company_id', '=', self.env.company.id),
    #     ]).mapped('room_type.id'))
    #     ],tracking=True)

    hotel_room_type = fields.Many2one(
        'hotel.inventory',
        string="Room Type",
        domain=lambda self: [
            # ('obsolete', '=', False),
            ('company_id', '=', self.env.company.id),
            ('room_type.obsolete', '=', False),
        ],
        tracking=True
    )

    def action_confirm_booking(self):
        # Ensure all selected records have the same state
        states = self.mapped('state')
        if len(set(states)) > 1:
            raise ValidationError("Please select records with the same state.")

        # Ensure the state of all selected records is 'not_confirmed'
        if any(record.state != 'not_confirmed' for record in self):
            raise ValidationError(
                "Please select only records in the 'Not Confirmed' state to confirm.")

        # Additional Validation: Check mandatory fields for each record
        for record in self:
            if not record.nationality:
                raise ValidationError(
                    _("The field 'Nationality' is required for record '%s'. Please fill it before confirming.")
                    % record.name
                )
            if not record.source_of_business:
                raise ValidationError(
                    _("The field 'Source of Business' is required for record '%s'. Please fill it before confirming.")
                    % record.name
                )
            if not record.market_segment:
                raise ValidationError(
                    _("The field 'Market Segment' is required for record '%s'. Please fill it before confirming.")
                    % record.name
                )

            if not record.rate_code:
                raise ValidationError(
                    _("The field 'Rate Code' is required for record '%s'. Please fill it before confirming.")
                    % record.name
                )
            if not record.meal_pattern:
                raise ValidationError(
                    _("The field 'Meal Pattern' is required for record '%s'. Please fill it before confirming.")
                    % record.name
                )

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
        """Convert parent + children *block* bookings to **no_show**
        (only on the check‑in date) and wipe related availability lines."""
        today = self.env.company.system_date.date()
        state_changed = False

        for parent in self:
            # ---------------- Children ----------------
            children = self.search([
                ("parent_booking_name", "=", parent.name)
            ])
            for child in children:
                if child.state == "block":
                    child._to_no_show(today)
                    state_changed = True

            # ---------------- Parent ------------------
            if parent.state == "block":
                parent._to_no_show(today)
                state_changed = True

        # ---------------- UI feedback ---------------
        if state_changed:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "success",
                    "message": _("Booking(s) marked as 'No Show' successfully!"),
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        raise ValidationError(_(
            "Nothing was marked as 'No Show'. "
            "Bookings must be in state 'block' and today must be the check‑in date."
        ))

    # ───────────────────────────────────────────────────────────────
    #  Helper: convert *one* booking to no_show and free its rooms
    # ───────────────────────────────────────────────────────────────
    def _to_no_show(self, today):
        self.ensure_one()

        # date guard
        if fields.Date.to_date(self.checkin_date) != today:
            raise ValidationError(_(
                f"Booking {self.name}: 'No Show' can only be done on the check‑in date."
            ))

        # ---- 1) Release rooms in lines ----------------------------------
        for line in self.room_line_ids:
            line.room_id = None
            line.state   = "no_show"
        # self.room_line_ids.unlink()

        # ---- 2) Delete availability result rows -------------------------
        avail_recs = self.env["room.availability.result"].search(
            [("room_booking_id", "=", self.id)]
        )
        if avail_recs:
            avail_recs.unlink()
            print("Availability lines removed for booking %s", self.name)

        # ---- 3) Switch booking state ------------------------------------
        self.write({"state": "no_show"})
        print("Booking %s → no_show", self.name)
    

    # def action_no_show_tree(self):
    #     # current_date = fields.Date.context_today(self)
    #     current_date = self.env.company.system_date.date()
    #     state_changed = False  # Flag to track if any state was changed to 'no_show'

    #     for booking in self:
    #         # If the booking is a parent, process its children
    #         child_bookings = self.search(
    #             [('parent_booking_name', '=', booking.name)])

    #         # Process child bookings
    #         for child in child_bookings:
    #             if child.state == 'block':
    #                 # Validate that the check-in date is today
    #                 if fields.Date.to_date(child.checkin_date) != current_date:
    #                     raise ValidationError(
    #                         _(f"Child Booking ID {child.id}: The 'No Show' action can only be performed on the check-in date.")
    #                     )

    #                 # Release rooms and update availability
    #                 for line in child.room_line_ids:
    #                     if line.room_id:
    #                         availability_result = self.env['room.availability.result'].search([
    #                             ('room_booking_id', '=', child.id)
    #                         ], limit=1)

    #                         if availability_result:
    #                             reserved_rooms = line.room_count if hasattr(
    #                                 line, 'room_count') else 1
    #                             availability_result.available_rooms += reserved_rooms
    #                             availability_result.rooms_reserved -= reserved_rooms

    #                         # Clear the room assignment
    #                         line.room_id = None
    #                         line.state = 'no_show'

    #                 # Remove the room lines by unlinking them
    #                 child.room_line_ids.unlink()
    #                 child.write({"state": "no_show"})
    #                 state_changed = True
    #                 print(
    #                     f"Child Booking ID {child.id} marked as 'No Show' and rooms released.")

    #         # If the current booking is not a parent, process it directly
    #         if not child_bookings and booking.state == 'block':
    #             if fields.Date.to_date(booking.checkin_date) != current_date:
    #                 raise ValidationError(
    #                     _("The 'No Show' action can only be performed on the check-in date.")
    #                 )

    #             # Release rooms and update availability
    #             for line in booking.room_line_ids:
    #                 if line.room_id:
    #                     availability_result = self.env['room.availability.result'].search([
    #                         ('room_booking_id', '=', booking.id)
    #                     ], limit=1)

    #                     if availability_result:
    #                         reserved_rooms = line.room_count if hasattr(
    #                             line, 'room_count') else 1
    #                         availability_result.available_rooms += reserved_rooms
    #                         availability_result.rooms_reserved -= reserved_rooms

    #                     # Clear the room assignment
    #                     line.room_id = None
    #                     line.state = 'no_show'

    #             # Remove the room lines by unlinking them
    #             booking.room_line_ids.unlink()
    #             booking.write({"state": "no_show"})
    #             state_changed = True
    #             print(
    #                 f"Booking ID {booking.id} marked as 'No Show' and rooms released.")

    #     # Only show the notification if any state was changed to 'no_show'
    #     if state_changed:
    #         dashboard_data = self.retrieve_dashboard()
    #         print("Updated dashboard data after 'No Show' action:", dashboard_data)

    #         # Display success notification with updated dashboard data
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'type': 'success',
    #                 'message': "Booking marked as 'No Show' successfully!",
    #                 'next': {'type': 'ir.actions.act_window_close'},
    #                 'dashboard_data': dashboard_data,
    #             }
    #         }
    #     else:
    #         raise ValidationError(
    #             _("No bookings were marked as 'No Show'. Please ensure the state is 'block' before performing this action."))

    def action_cancel_booking(self):
        # Ensure all selected records have the same state
        states = self.mapped('state')
        if len(set(states)) > 1:
            raise ValidationError("Please select records with the same state.")

        # Define allowed states for cancellation
        allowed_states = ['not_confirmed', 'confirmed', 'waiting']

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
        # today = datetime.now().date()
        today = self.env.company.system_date.date()
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
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Room Booking',
        #     'res_model': 'room.booking',
        #     'view_mode': 'tree,form',
        #     'target': 'current',
        # }
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': "Booking Checked In Successfully!",
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

    def _perform_bulk_checkin(self, all_bookings, today):
        # today = datetime.now()
        today = self.env.company.system_date.date()
        state_changed = False
        for booking in all_bookings:
            if len(booking.room_line_ids) > 1:
                continue

            # room_availability = booking.check_room_availability_all_hotels_split_across_type(
            #     checkin_date=today,
            #     checkout_date=today + timedelta(days=1),
            #     room_count=len(booking.room_line_ids),
            #     adult_count=sum(booking.room_line_ids.mapped('adult_count')),
            #     hotel_room_type_id=booking.room_line_ids.mapped(
            #         'hotel_room_type').id if booking.room_line_ids else None
            # )
            # print("Line 1503", room_availability)

            # # Check if room_availability indicates no available rooms
            # if not room_availability or isinstance(room_availability, dict):
            #     raise ValidationError(
            #         _("No rooms are available for today's date. Please select a different date."))

            # room_availability_list = room_availability[1]
            # total_available_rooms = sum(
            #     int(res.get('available_rooms', 0)) for res in room_availability_list)

            # if total_available_rooms <= 0:
            #     raise ValidationError(
            #         _("No rooms are available for the selected date. Please select a different date."))

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

        system_date_checkout = self.env.company.system_date.date()
        get_current_time = datetime.now().time()

        checkout_datetime = datetime.combine(system_date_checkout, get_current_time)

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
        # self.write({"state": "check_out", "checkout_date": datetime.now()})

        self.write({"state": "check_out", "checkout_date": checkout_datetime})
        self.room_line_ids.write({"state_": "check_out"})
    
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
        today = self.env.company.system_date.date()
        all_bookings = self

        # Filter eligible bookings with 1 or fewer room lines
        eligible_bookings = all_bookings.filtered(lambda b: len(b.room_line_ids) <= 1)

        for booking in eligible_bookings:
            if booking.state != 'check_in':
                raise ValidationError(
                    _("All selected bookings must be in the 'check_in' state to proceed with check-out.")
                )

        # Check for future checkout dates
        future_bookings = eligible_bookings.filtered(
            lambda b: b.checkout_date and fields.Date.to_date(b.checkout_date) > today
        )

        if future_bookings:
            # Trigger Early Checkout Wizard
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'confirm.early.checkout.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_booking_ids': future_bookings.mapped('id'),
                }
            }
        current_time = datetime.now().time()  # Get the current system time
        current_datetime = datetime.combine(today, current_time)
        # Direct checkout for bookings without future checkout dates
        for booking in eligible_bookings:
            booking._create_invoice()  # Call the invoice creation method
            booking.write({'invoice_status': "invoiced", 'state': "check_out","checkout_date": current_datetime})
            booking.room_line_ids.write({"state_": "check_out"})
            booking.invoice_button_visible = True

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking Checked Out Successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


    # def action_checkout_booking(self):
    #     # if not self.posting_item_ids:
    #     #     raise ValidationError("You cannot proceed with checkout. Please add at least one Posting Item.")
    #     # today = datetime.now().date()
    #     today = self.env.company.system_date.date()
    #     all_bookings = self

    #     # Filter out bookings with more than one room line
    #     eligible_bookings = all_bookings.filtered(
    #         lambda b: len(b.room_line_ids) <= 1)

    #     for booking in eligible_bookings:
    #         print("Line 1465", booking)
    #         if booking.state != 'check_in':
    #             raise ValidationError(
    #                 _("All selected bookings must be in the 'check_in' state to proceed with check-out."))

    #     created_invoices = []
    #     for booking in eligible_bookings:
    #         if not booking.room_line_ids:
    #             raise ValidationError(
    #                 _("Please enter room details for booking ID %s.") % booking.id)

    #         posting_item_meal, _1, _2, _3 = booking.get_meal_rates(
    #             booking.meal_pattern.id)
    #         print(f"The Posting Item Meal is: {posting_item_meal}")
    #         meal_price, room_price, package_price, posting_item_value, line_posting_items = booking.get_all_prices(
    #             booking.checkin_date, booking)
    #         print(f"Rate Posting Item: {posting_item_value}")
    #         print(f"Line Posting Items: {line_posting_items}")

    #         # Compute booking amounts
    #         booking_list = booking._compute_amount_untaxed(True)

    #         if booking_list:
    #             account_move = self.env["account.move"].create({
    #                 'move_type': 'out_invoice',
    #                 'invoice_date': today,
    #                 'partner_id': booking.partner_id.id,
    #                 'ref': booking.name,
    #                 'hotel_booking_id': booking.id,  # Set the current booking
    #                 # Group Booking Name
    #                 'group_booking_name': booking.group_booking.name if booking.group_booking else '',
    #                 'parent_booking_name': booking.parent_booking_name or '',  # Parent Booking Name
    #                 'room_numbers': booking.room_ids_display or '',  # Room Numbers
    #             })
    #             for posting_item in booking.posting_item_ids:
    #                 account_move.invoice_line_ids.create({
    #                     'posting_item_id': posting_item.posting_item_id.id,  # Posting item
    #                     'posting_description': posting_item.description,  # Description
    #                     'posting_default_value': posting_item.default_value,  # Default value
    #                     'move_id': account_move.id,  # Link to account.move
    #                 })

    #             # Add lines from filtered lines
    #             filtered_lines = [
    #                 line for line in booking.rate_forecast_ids if line.date == today]
    #             print(
    #                 f"Debug: Number of filtered rate_forecast_ids lines = {len(filtered_lines)}")

    #             for line in filtered_lines:
    #                 line_data = []

    #                 # Check and add Rate line if rate is available and greater than 0
    #                 if line.rate and line.rate > 0:
    #                     line_data.append({
    #                         'posting_item_id': posting_item_value,  # Posting item for rate
    #                         'posting_description': 'Rate',  # Description for rate
    #                         'posting_default_value': line.rate,  # Default value for rate
    #                         'move_id': account_move.id,
    #                     })

    #                 # Check and add Meal line if meals is available and greater than 0
    #                 if line.meals and line.meals > 0:
    #                     line_data.append({
    #                         'posting_item_id': posting_item_meal,  # Posting item for meal
    #                         'posting_description': 'Meal',  # Description for meal
    #                         'posting_default_value': line.meals,  # Default value for meal
    #                         'move_id': account_move.id,
    #                     })

    #                 # Check and add Package line if packages is available and greater than 0
    #                 if line.packages and line.packages > 0:
    #                     line_data.append({
    #                         # Posting item for package
    #                         'posting_item_id': line_posting_items[-1],
    #                         'posting_description': 'Package',  # Description for package
    #                         'posting_default_value': line.packages,  # Default value for package
    #                         'move_id': account_move.id,
    #                     })

    #                 # Create lines in account.move.line
    #                 if line_data:
    #                     account_move.invoice_line_ids.create(line_data)

    #             # for rec in booking_list:
    #             #     account_move.invoice_line_ids.create({
    #             #         'name': rec['name'],
    #             #         'quantity': rec['quantity'],
    #             #         'price_unit': rec['price_unit'],
    #             #         'move_id': account_move.id,
    #             #         'product_type': rec['product_type'],
    #             #     })

    #             # Update booking invoice status
    #             booking.write({'invoice_status': "invoiced"})
    #             booking.write({'state': "check_out"})
    #             booking.room_line_ids.write({"state_": "check_out"})
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

    #     self._perform_bulk_checkout(eligible_bookings, today)

    #     return {
    #     'type': 'ir.actions.client',
    #     'tag': 'display_notification',
    #     'params': {
    #         'type': 'success',
    #         'message': _("Booking Checked Out Successfully!"),
    #         'next': {'type': 'ir.actions.act_window_close'},
    #     }
    # }

    # # Update the dashboard after the function completes
    #     self.env.cr.commit()

    #     # return {
    #     #     'type': 'ir.actions.client',
    #     #     'tag': 'display_notification',
    #     #     'params': {
    #     #         'type': 'success',
    #     #         'message': _("Booking Checked Out Successfully!"),
    #     #     },
    #     # }, {
    #     #     'type': 'ir.actions.act_window',
    #     #     'name': 'Room Booking',
    #     #     'res_model': 'room.booking',
    #     #     'view_mode': 'tree,form',
    #     #     'target': 'current',
    #     # }

    
    
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
        state_changed = False

        for booking in all_bookings:
            if len(booking.room_line_ids) > 1:
                continue

            booking._perform_checkout()
            booking.room_line_ids.write({"state_": "check_out"})
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

    room_type_name = fields.Many2one('room.type', string='Room Type Name')

    def action_unconfirm(self):
        """Set the booking back to 'not_confirmed' state from 'confirmed' or 'block'"""
        for record in self:
            if record.state in ['block', 'confirmed', 'waiting', 'cancel']:
                record.state = 'not_confirmed'

    def _open_confirm_wizard(self, title, message, block_line=False):
        self.ensure_one()
        return {
            'name': "",
            'type': 'ir.actions.act_window',
            'res_model': 'confirm.booking.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_message': message,
                'default_line_id': block_line.id if block_line else False,
                'default_booking_id': self.id,
            },
        }


    def action_confirm(self):
        # today = datetime.now().date()
        today = self.env.company.system_date.date()
        for record in self:
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot confirm a booking with a check-in date in the past."))

            if not record.partner_id:
                raise ValidationError(_("The field 'Contact' is required. Please fill it before confirming."))

            if not record.nationality:
                raise ValidationError(_("The field 'Nationality' is required. Please fill it before confirming."))
            if not record.source_of_business:
                raise ValidationError(
                    _("The field 'Source of Business' is required. Please fill it before confirming."))
            if not record.market_segment:
                raise ValidationError(_("The field 'Market Segment' is required. Please fill it before confirming."))
            if not record.rate_code:
                raise ValidationError(_("The field 'Rate Code ' is required. Please fill it before confirming."))
            if not record.meal_pattern:
                raise ValidationError(_("The field 'Meal Pattern' is required. Please fill it before confirming."))

            if not record.parent_booking_name:
                # if not record.availability_results:
                if record.state != "no_show" and not record.availability_results:
                    raise ValidationError(
                        "Search Room is empty. Please search for available rooms before confirming.")
            # if not record.availability_results:
            #     raise ValidationError("Search Room is empty. Please search for available rooms before confirming.")

            if not record.room_line_ids:
                record.action_split_rooms()

            # 4) Check if there is any line in block state
            block_line = record.room_line_ids.filtered(
                lambda l: l.state_ == 'block')
            # if block_line:
            if record.state == 'block' or block_line:
                return record._open_confirm_wizard(
                    _("Confirm Booking"),
                    _("Room number will be released. Do you want to proceed?"),
                    block_line=block_line
                    
                )
                # confirm_msg = _("Room number will be released. Do you want to proceed?")
                # # Open wizard for the first line in block
                # return {
                #     'name': _("Confirm Booking"),
                #     'type': 'ir.actions.act_window',
                #     'res_model': 'confirm.booking.wizard',
                #     'view_mode': 'form',
                #     'target': 'new',
                #     'context': {
                #         'default_line_id': block_line[0].id if block_line else False,
                #         'default_booking_id': record.id,
                #     },
                # }

            # 5) If we reached here, there is NO line in block state => we can confirm now
            record.state = "confirmed"

            # 6) Adjust availability
            for search_result in record.availability_results:
                search_result.available_rooms -= search_result.rooms_reserved

        return True

    
    def action_waiting(self):
        # today = datetime.now().date()
        today = self.env.company.system_date.date()
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
            # current_date = datetime.now().date()
            current_date = self.env.company.system_date.date()
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
            ('company_id', '=', hotel_id),
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

    nationality = fields.Many2one('res.country', string='Nationality', tracking=True)
    source_of_business = fields.Many2one('source.business', string='Source of Business', 
    domain=lambda self: [
        # ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], tracking=True)
    market_segment = fields.Many2one('market.segment', string='Market Segment', 
    domain=lambda self: [
        # ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], tracking=True)

    rate_details = fields.One2many(
        'room.type.specific.rate', compute="_compute_rate_details", string="Rate Details")
    # rate_details = fields.One2many('rate.detail', compute="_compute_rate_details", string="Rate Details")
    rate_code = fields.Many2one('rate.code', string='Rate Code',  
    domain=lambda self: [
        ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ],tracking=True)

    # @api.onchange('hotel_room_type')
    # def _onchange_hotel_room_type(self):
    #     # ✅ Validation when Rate Code is empty
    #     if self.hotel_room_type and not self.rate_code:
    #         self.hotel_room_type = False  # Reset the selection
    #         raise ValidationError(
    #             "Please select a Rate Code first before choosing a Room Type.")
    
    @api.onchange('rate_code')
    def _onchange_rate_code_(self):
        for record in self:
            if record.rate_code.id:
                rate_details = self.env['rate.detail'].search([
                                ('rate_code_id', '=', record.rate_code.id),
                                ('from_date', '<=', record.checkin_date),
                                ('to_date', '>=', record.checkout_date)
                            ])
                # if rate_details.id == False:

                if not rate_details:
                    # raise ValidationError('The selected rate code is expired. Please select another rate code.')
                    raise ValidationError(
                        f'The selected rate code "{record.rate_code.code}" is expired. Please select another rate code.')
                # Search for rate.detail linked to the selected rate_code
                # rate_detail = self.env['rate.code'].search([('code', '=', record.rate_code.id)], limit=1)
                # print('4093', rate_detail)
                if rate_details.price_type != 'room_only' and rate_details.meal_pattern_id and not record.meal_pattern:
                    record.meal_pattern = rate_details.meal_pattern_id
                # if rate_details and rate_details.meal_pattern_id and not record.meal_pattern:
                #     # Set meal_pattern based on the meal_pattern_id from rate.detail
                #     record.meal_pattern = rate_details.meal_pattern_id


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

            rate_code = self.env['rate.code'].search([
                ('company_id', '=', self.env.company.id),

            ],)
            # Attempt to find rate details in room.type.specific.rate
            specific_rate_detail = self.env['room.type.specific.rate'].search([
                ('room_type_id', '=', record.hotel_room_type.id),
                ('company_id', '=', self.env.company.id),
                ('from_date', '<=', record.checkin_date),
                ('to_date', '>=', record.checkout_date)
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
    vip_code = fields.Many2one('vip.code', string="VIP Code", domain=[('obsolete', '=', False)])

    # @api.constrains('vip', 'vip_code')
    # def _check_vip_code(self):
    #     for record in self:
    #         if record.vip and not record.vip_code:
    #             raise ValidationError("VIP Code is required when VIP is selected!")


    show_vip_code = fields.Boolean(string="Show VIP Code", compute="_compute_show_vip_code", store=True)

    complementary = fields.Boolean(string='Complimentary')
    complementary_codes = fields.Many2one('complimentary.code', string='Complimentary Code', domain=[('obsolete', '=', False)])
    
    # @api.constrains('complementary', 'complementary_codes')
    # def _check_complementary_code(self):
    #     for record in self:
    #         if record.complementary and not record.complementary_codes:
    #             raise ValidationError(
    #                 "Complimentary Code is required when Complimentary is selected!")
    
    
    show_complementary_code = fields.Boolean(string="Show Complimentary Code", compute="_compute_show_codes",
                                             store=True)

    house_use = fields.Boolean(string='House Use')
    house_use_codes = fields.Many2one('house.code', string='House Use Code', domain=[('obsolete', '=', False)])

    # @api.constrains('house_use', 'house_use_codes')
    # def _check_house_use_code(self):
    #     for record in self:
    #         if record.house_use and not record.house_use_codes:
    #             raise ValidationError(
    #                 "House Use Code is required when House Use is selected!")

    
    @api.constrains('vip', 'vip_code', 'complementary', 'complementary_codes', 'house_use', 'house_use_codes')
    def _check_required_codes(self):
        for record in self:
            errors = []
            if record.vip and not record.vip_code:
                errors.append("VIP Code is required when VIP is selected.")
            if record.complementary and not record.complementary_codes:
                errors.append("Complimentary Code is required when Complimentary is selected.")
            if record.house_use and not record.house_use_codes:
                errors.append("House Use Code is required when House Use is selected.")
            if errors:
                raise ValidationError("Please correct the following:\n- " + "\n- ".join(errors))



    
    show_house_use_code = fields.Boolean(string="Show House Code", compute="_compute_show_codes", store=True)

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

        if not vals_list.get('company_id'):
            vals_list['company_id'] = self.env.company.id

            # Only generate Booking ID if it's still "New"
        if vals_list.get('name', 'New') == 'New':
            company = self.env['res.company'].browse(vals_list['company_id'])
            prefix = company.name + '/' if company else ''
            next_seq = self.env['ir.sequence'].next_by_code('room.booking') or '00001'
            vals_list['name'] = prefix + next_seq
        self.check_room_meal_validation(vals_list, False)
        
        if 'company_id' in vals_list:
            company = self.env['res.company'].browse(vals_list['company_id'])
            if 'checkin_date' not in vals_list:
                vals_list['checkin_date'] = company.system_date

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
        company_id = vals_list.get('company_id', self.env.company.id)
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

        record = super(RoomBooking, self).create(vals_list)

        # Log the initial state for all room lines
        
        if record.state:
            get_sys_date = self.env.company.system_date.date()
            current_time = datetime.now().time()
            get_sys_date = datetime.combine(get_sys_date, current_time)
            for line in record.room_line_ids:
                if record.state == 'block':
                    self.env['room.booking.line.status'].create({
                        'booking_line_id': line.id,
                        'status': 'confirmed',
                        'change_time': get_sys_date,
                    })

                # Now create the actual status record (e.g., 'block')
                self.env['room.booking.line.status'].create({
                    'booking_line_id': line.id,
                    'status': record.state,
                    'change_time': get_sys_date + timedelta(seconds=1),
                })
            

        return record

   
    
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

    
    def copy(self, default=None):
        restricted_states = ['not_confirmed', 'confirmed', 'block', 'check_in', 'check_out', 'cancel', 'no_show']
        if self.state not in restricted_states:
            raise UserError(_("You cannot duplicate a booking that is in '%s' state.") % self.state.capitalize())

        # Don’t provide 'name' in default, so create() assigns it automatically
        default = dict(default or {})
        
        # system_date = self.env.user.company_id.system_date
        # default['checkin_date'] = system_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # default['checkout_date'] = checkin_date + timedelta(days=1)

        # checkin_date = self.env.user.company_id.system_date.replace(hour=0, minute=0, second=0, microsecond=0)
        # default['checkin_date'] = checkin_date

        # # Set checkout_date to 1 day after checkin_date (start of day)
        # default['checkout_date'] = checkin_date + timedelta(days=1)

        return super(RoomBooking, self).copy(default)

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

    def _create_invoice(self):
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
        # today = datetime.now().date()
        today = self.env.company.system_date.date()
        current_time = datetime.now().time()  # Get the current system time
        current_datetime = datetime.combine(today, current_time)  # Combine date and time

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
            _logger.info(f"Rate Forecast Line ID: {line.id}")
            _logger.info(f" - Room Booking ID: {line.room_booking_id.id}")
            _logger.info(f" - Forecasted Rate: {line.rate}")
            _logger.info(f" - Forecast Date: {line.date}")

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

            self.write({'invoice_status': "invoiced"})
            self.write({"state": "check_out"})
            self.room_line_ids.write({"state_": "check_out"})
            self.invoice_button_visible = True

    def action_checkout(self):
        today = self.env.company.system_date.date()
        current_time = datetime.now().time()
        current_datetime = datetime.combine(today, current_time)
            
        if self.checkout_date:
            # Calculate the checkout_date
            get_current_time = datetime.now().time()
            checkout_datetime = datetime.combine(today, get_current_time)
            checkout_date = checkout_datetime

            if self.checkout_date.date() > today:
                return {
                    'name': _('Confirm Early Check-Out'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'confirm.early.checkout.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'default_booking_ids': self.ids},
                }
            else:
                self._create_invoice()
                self.write({"state": "check_out","checkout_date": current_datetime})
                self.room_line_ids.write({"state_": "check_out"})
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

    # def action_checkin(self):
    #     # today = datetime.now().date()
    #     today = self.env.company.system_date.date()
    #     for record in self:
    #         if record.checkin_date and record.checkin_date.date() < today:
    #             raise ValidationError(
    #                 _("You cannot check-in  booking with a check-in date in the past."))
    #     """ Handles the check-in action by asking for confirmation if check-in is in the future or showing unavailability """
    #     # today = fields.Date.context_today(self)

    #     # Ensure room details are entered
    #     if not self.room_line_ids:
    #         raise ValidationError(_("Please Enter Room Details"))

    #     room_availability = None

    #     # Check if the check-in date is in the future
    #     if fields.Date.to_date(self.checkin_date) > today:
    #         # Check availability for rooms on the current date
    #         room_availability = self.check_room_availability_all_hotels_split_across_type(
    #         checkin_date=today,
    #         checkout_date=today + timedelta(days=1),
    #         room_count=len(self.room_line_ids),
    #         adult_count=sum(self.room_line_ids.mapped('adult_count')),
    #         hotel_room_type_id=self.room_line_ids.mapped(
    #             'hotel_room_type').id if self.room_line_ids else None
    #     )
    #     print("line 5393", today, room_availability, len(self.room_line_ids),
    #           sum(self.room_line_ids.mapped('adult_count')))
        

    #     # Check if room_availability indicates no available rooms and handle it here
    #     if not room_availability or isinstance(room_availability, dict):
    #         raise ValidationError(_("No rooms are available for today's date. Please select a different date."))

        
    #     room_availability_list = room_availability[1]
    #     total_available_rooms = sum(
    #         int(res.get('available_rooms', 0)) for res in room_availability_list)

    #     if total_available_rooms > 0:
    #         print("Pass")
    #     else:
    #         raise ValidationError(
    #             _("No rooms are available for the selected date. Please select a different date."))
    #         # Open the confirmation wizard to ask the user for confirmation
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'res_model': 'booking.checkin.wizard',
    #             'view_mode': 'form',
    #             'target': 'new',
    #             'context': {
    #                 'default_booking_ids': self.ids,
    #             }
    #         }
    #     # today = self.env.company.system_date.date()
    #     get_current_time = datetime.now().time()
    #     # Combine date and time into a single datetime object
    #     checkin_datetime = datetime.combine(today, get_current_time)
    #     # print("TODAY SYSTEM DATE", today, "get CURRENT TIME", get_current_time, "checkin_datetime", checkin_datetime)

    #     record.checkin_date = checkin_datetime

    #     result = self._perform_checkin()
    #     # Perform early check-in
    #     early_result = self._early_perform_checkin()

    #     # If the check-in date is today and rooms are available, proceed with check-in
    #     # return self._perform_checkin()
    #     return result 

    def action_checkin(self):
        today = self.env.company.system_date.date()  # Get today's date from the company configuration

        for record in self:
            # Validate that check-in date is not in the past
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot check-in a booking with a check-in date in the past.")
                )

            # Ensure room details are entered
            if not record.room_line_ids:
                raise ValidationError(_("Please Enter Room Details"))

            # Check if the check-in date is in the future and you are trying to check-in today
            if fields.Date.to_date(record.checkin_date) > today:
                # Perform room availability check for today
                room_availability = record.check_room_availability_all_hotels_split_across_type(
                    checkin_date=today,
                    checkout_date=today + timedelta(days=1),
                    room_count=len(record.room_line_ids),
                    adult_count=sum(record.room_line_ids.mapped('adult_count')),
                    hotel_room_type_id=record.room_line_ids.mapped('hotel_room_type').id if record.room_line_ids else None,
                )
                print("Room Availability:", room_availability)

                # Check room availability result
                if not room_availability or isinstance(room_availability, dict):
                    raise ValidationError(_("No rooms are available for today's date. Please select a different date."))

                # Process room availability
                room_availability_list = room_availability[1]
                total_available_rooms = sum(
                    int(res.get('available_rooms', 0)) for res in room_availability_list
                )

                if total_available_rooms <= 0:
                    raise ValidationError(_("No rooms are available for today's date. Please select a different date."))

                # Open the confirmation wizard
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'booking.checkin.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_booking_ids': [record.id],
                    }
                }

            # Combine today's date and the current time into a single datetime object for check-in
            get_current_time = datetime.now().time()
            checkin_datetime = datetime.combine(today, get_current_time)
            record.checkin_date = checkin_datetime

            # Perform the check-in actions
            result = record._perform_checkin()

            # Return the result
            return result

    
    def _perform_checkin(self):
        """Helper method to perform check-in and update room availability."""
        parent_booking_id = self.parent_booking_id.id if self.parent_booking_id else self.id

        for room in self.room_line_ids:
            # Update room status to 'occupied'
            room.room_id.write({
                'status': 'occupied',
            })
            room.room_id.is_room_avail = False

            # Update the available rooms count and reduce rooms_reserved count
            # if room.room_id:
            #     availability_result = self.env['room.availability.result'].search([
            #         ('room_booking_id', '=', parent_booking_id)
            #     ], limit=1)

            #     print("Availability Result:", availability_result)

            #     if availability_result:
            #         # Use room count from the room line or a calculated value
            #         reserved_rooms = room.room_count if hasattr(
            #             room, 'room_count') else 1

            #         # Increase available_rooms and decrease rooms_reserved
            #         availability_result.available_rooms -= reserved_rooms
            #         availability_result.rooms_reserved += reserved_rooms

        # Update the booking state to 'check_in'
        self.write({"state": "check_in"})
        self.room_line_ids.write({"state_": "check_in"})
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

    
    def _early_perform_checkin(self):
        """Helper method to perform check-in and update room availability."""
        try:
            parent_booking_id = self.parent_booking_id.id if self.parent_booking_id else self.id
            print("Parent Booking ID:", parent_booking_id)
            today = self.env.company.system_date.date()

            for room in self.room_line_ids:
                # Update room status to 'occupied'
                room.room_id.write({
                    'status': 'occupied',
                })
                room.room_id.is_room_avail = False

            # Fetch room availability
            room_availability = self.check_room_availability_all_hotels_split_across_type(
                checkin_date=today,
                checkout_date=today + timedelta(days=1),
                room_count=len(self.room_line_ids),
                adult_count=sum(self.room_line_ids.mapped('adult_count')),
                hotel_room_type_id=self.room_line_ids.mapped(
                    'hotel_room_type').id if self.room_line_ids else None
            )

            print("Room Availability:", room_availability)

            if not room_availability or isinstance(room_availability, dict):
                raise ValidationError(_("No rooms are available for today's date. Please select a different date."))

            room_availability_list = room_availability[1]
            total_available_rooms = sum(
                int(res.get('available_rooms', 0)) for res in room_availability_list)

            if total_available_rooms <= 0:
                raise ValidationError(_("No rooms are available for the selected date. Please select a different date."))

            # Update availability results
            for room in self.room_line_ids:
                if room.room_id:
                    availability_result = self.env['room.availability.result'].search([
                        ('room_booking_id', '=', parent_booking_id)
                    ], limit=1)

                    if availability_result:
                        reserved_rooms = room.room_count if hasattr(room, 'room_count') else 1
                        availability_result.available_rooms -= reserved_rooms
                        availability_result.rooms_reserved += reserved_rooms

            # Update state
            self.write({"state": "check_in"})
            print("Booking Checked In Successfully!")
            

        except ValidationError as e:
            self.message_post(body=str(e))
            raise

        except Exception as e:
            print(f"Unexpected error: {e}")
            raise ValidationError(_("An unexpected error occurred during check-in. Please contact support."))



    @api.model
    def action_confirm_checkin(self, record_id):
        """ This method is called when the user confirms to change the check-in date """
        record = self.browse(record_id)
        if record.exists():
            # record.checkin_date = datetime.now()
            record.checkin_date = self.env.company.system_date.date()
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
        # today = datetime.now().date()
        today = self.env.company.system_date.date()
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


    adult_count = fields.Integer(string='Adults', tracking=True)
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
    
    @api.constrains('use_price', 'room_price')
    def _validate_room_price(self):
        for record in self:
            if record.use_price and record.room_price <= 0:
                raise ValidationError(
                    _("Room Price must be greater than 0 when 'Use Room Price' is selected!"))
            
    @api.constrains('use_meal_price', 'meal_price')
    def _validate_meal_price(self):
        for record in self:
            if record.use_meal_price and record.meal_price <= 0:
                raise ValidationError(
                    _("Meal Price must be greater than 0 when 'Use Meal Price' is selected!"))

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

    def get_rate_details_on_room_number_specific_rate(self, _day, record, forecast_date):
        room_price = 0
        _day = forecast_date.strftime('%A').lower()
        _var = f"room_number_{_day}_pax_{record.adult_count}"
        _var_child = f"room_number_{_day}_child_pax_1"
        _var_infant = f"room_number_{_day}_infant_pax_1"
        _adult_count = 1
        if record.adult_count > 6:
            _var = f"room_number_{_day}_pax_1"
            _adult_count = record.adult_count

        if record.rate_code.id and not record.use_price:
            for room_line in record.room_line_ids:
                room_number_specific_rate = self.env['room.number.specific.rate'].search([
                    ('rate_code_id', '=', record.rate_code.id),
                    ('from_date', '<=', forecast_date),
                    ('to_date', '>=', forecast_date),
                    ('room_fsm_location', '=', room_line.room_id.fsm_location.id),
                    # ('display_name', '=', room_line.room_id.display_name),
                    ('room_number', '=', room_line.room_id.display_name),
                    ('company_id', '=', self.env.company.id)
                    
                ])

                if room_number_specific_rate.id:
                    if record.adult_count > 6:
                        room_price += room_number_specific_rate[_var] * record.adult_count
                    else:
                        room_price += room_number_specific_rate[_var]

                    room_price += room_number_specific_rate[_var_child] * record.child_count
                    room_price += room_number_specific_rate[_var_infant] * record.infant_count

        return room_price


    def check_room_meal_validation(self, vals, is_write):
        for record in self:
            if vals.get('use_price', record.use_price):

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
        if self.room_is_percentage:
            if self.room_price == 0:  # Check if room_price is zero
                raise ValidationError("Room price is zero. You cannot select percentage.")
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
        if self.meal_is_percentage:
            if self.meal_price == 0:  # Check if room_price is zero
                raise ValidationError("Meal price is zero. You cannot select percentage.")
            self.meal_discount = (self.meal_discount / self.meal_price)
            # if self.meal_discount < 1:
            #     self.meal_discount = 1
            self.meal_is_amount = False

        else:
            self.meal_is_amount = True

    @api.onchange('meal_is_amount')
    def _onchange_meal_is_amount(self):
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

    # @api.onchange('use_price')
    # def _onchange_use_price(self):
    #     if self.use_price and self.room_price <= 0.00:
    #         # Set use_price to False and raise a warning
    #         self.use_price = False
    #         raise UserError(
    #             "You cannot check 'Use Price' when 'Price' is 0.00 or less.")

    # @api.onchange('meal_price')
    # def _onchange_use_price(self):
    #     if self.use_meal_price and self.meal_price <= 0.00:
    #         # Set use_price to False and raise a warning
    #         self.meal_price = False
    #         raise UserError(
    #             "You cannot check 'Meal Price' when 'Meal Price' is 0.00 or less.")

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
    # parent_booking = fields.Char(
    #     string="Parent Booking", store=True, tracking=True)

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
        print("company_id", company_id)
        domain = [('company_id', '=', company_id)] if company_id else []
        companies = self.env['hotel.inventory'].read_group(domain, ['company_id'], ['company_id'])
        print("LINR 6512", companies)

        # Retrieve all room types and map them by ID
        room_types = self.env['room.type'].search_read(
            [('obsolete', '=', False)], [], order='user_sort ASC')
        # print('room type', room_types)
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
        # today_date = datetime.today().strftime('%Y-%m-%d')
        today_date = self.env.company.system_date.date().strftime('%Y-%m-%d')

        for company in companies:
            loop_company_id = company['company_id'][0]
            room_availabilities_domain = [
                ('company_id', '=', loop_company_id),
                # ('pax', '>=', adult_count),
            ]

            if hotel_room_type_id:
                room_availabilities_domain.append(
                    ('room_type', '=', hotel_room_type_id))
            else:
                # If no room_type_id is provided, filter by room types in room_types_dict
                room_type_ids = list(room_types_dict.keys())
                if room_type_ids:
                    room_availabilities_domain.append(('room_type', 'in', room_type_ids))

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

                #TODO ADD Domain for Out of Order and rooms on hold  
                booked_rooms = self.env['room.booking'].search_count([
                    ('hotel_room_type', '=', room_type_id),
                    # ('booking_id.room_count', '=', 1),
                    # ('adult_count', '=', availability['pax']),
                    ('checkin_date', '<', checkout_date),
                    ('checkout_date', '>', checkin_date),
                    # ('checkout_date', '!=', today_date), 
                    ('checkout_date', 'not like', today_date + '%'),
                    ('state', 'in', ['check_in', 'block','confirmed']),
                    # Exclude allocated lines
                    ('id', 'not in', self.env.context.get('already_allocated', []))
                ])
                print('6769', booked_rooms,self.env.context.get('already_allocated', []))

                rooms_on_hold_count = self.env['rooms.on.hold.management.front.desk'].search_count([
                    ('company_id', '=', self.env.company.id),
                    ('room_type', '=', room_type_id),
                    ('from_date', '<=', checkout_date),
                    ('to_date', '>=', checkin_date)
                ])
                print(f"Rooms on hold count: {rooms_on_hold_count}")

                # Count out-of-order rooms for the current company and matching room type
                out_of_order_rooms_count = self.env['out.of.order.management.fron.desk'].search_count([
                    ('company_id', '=', self.env.company.id),
                    ('room_type', '=', room_type_id),
                    ('from_date', '<=', checkout_date),
                    ('to_date', '>=', checkin_date)
                ])
                print(f"Out of order rooms count: {out_of_order_rooms_count}")
                confirmed_bookings = self.env['room.booking'].search([
                    ('hotel_room_type', '=', room_type_id),
                    ('checkin_date', '<', checkout_date),
                    ('checkout_date', '>', checkin_date),
                    ('checkout_date', 'not like', today_date + '%'),
                    ('state', '=', 'confirmed'),
                    ('id', 'not in', self.env.context.get('already_allocated', []))
                ])
                print('6832', confirmed_bookings)
                # Get the count of room_line_ids for confirmed bookings
                confirmed_room_lines_count = sum(len(booking.room_line_ids) for booking in confirmed_bookings)
                if sum(len(booking.room_line_ids) for booking in confirmed_bookings) > 0:
                    confirmed_room_lines_count -= 1

                print('6795',confirmed_room_lines_count)

                
                booked_rooms = booked_rooms + rooms_on_hold_count + out_of_order_rooms_count+confirmed_room_lines_count
                print('6799', booked_rooms)

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
                        ('checkin_date', '<', checkout_date),
                        ('checkout_date', '>', checkin_date),
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

    

    def _calculate_available_rooms(self, company_id, checkin_date, checkout_date, adult_count, hotel_room_type_id,room_types_dict):
        """Calculate available rooms for a company."""
        print(f"Starting room calculation for company_id: {company_id}, checkin_date: {checkin_date}, checkout_date: {checkout_date}, adult_count: {adult_count}, hotel_room_type_id: {hotel_room_type_id}")

        room_availabilities_domain = [
            ('company_id', '=', company_id),
        ]
        print(f"Initial room_availabilities_domain: {room_availabilities_domain}")

        # today_date = datetime.today().strftime('%Y-%m-%d')
        today_date = self.env.company.system_date.date().strftime('%Y-%m-%d')
        print(f"Today's date: {today_date}")

        if hotel_room_type_id:
            room_availabilities_domain.append(('room_type', '=', hotel_room_type_id))
            print(f"Added room_type to domain: {hotel_room_type_id}")
        else:
            room_type_ids = list(room_types_dict.keys())
            if room_type_ids:
                room_availabilities_domain.append(('room_type', 'in', room_type_ids))
                print(f"Added multiple room_types to domain: {room_type_ids}")

        print(f"Final room_availabilities_domain: {room_availabilities_domain}")

        room_availabilities = self.env['hotel.inventory'].search_read(room_availabilities_domain,
                                                                    ['room_type', 'total_room_count',
                                                                    'overbooking_allowed', 'overbooking_rooms'],
                                                                    order='room_type ASC')
        print(f"Room availabilities found: {room_availabilities}")

        grouped_availabilities = {}

        for availability in room_availabilities:
            room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else availability['room_type']
            print(f"Processing availability for room_type_id: {room_type_id}")

            if room_type_id not in grouped_availabilities:
                grouped_availabilities[room_type_id] = {
                    'total_room_count': 0,
                    'overbooking_allowed': availability['overbooking_allowed'],
                    'overbooking_rooms': 0,
                    'entries': []
                }
            grouped_availabilities[room_type_id]['total_room_count'] += availability['total_room_count']
            grouped_availabilities[room_type_id]['overbooking_rooms'] += availability['overbooking_rooms']
            grouped_availabilities[room_type_id]['entries'].append(availability)

            print(f"Grouped availability so far: {grouped_availabilities}")

        total_available_rooms = 0
        for room_type_id, availability in grouped_availabilities.items():
            print(f"Calculating booked rooms for room_type_id: {room_type_id}")

            booked_rooms = self.env['room.booking'].search_count([
                ('hotel_room_type', '=', room_type_id),
                ('checkin_date', '<', checkout_date),
                ('checkout_date', '>', checkin_date),
                ('checkout_date', 'not like', today_date + '%'),
                ('state', 'in', ['check_in', 'block', 'confirmed']),
                ('id', 'not in', self.env.context.get('already_allocated', []))
            ])
            print(f"Booked rooms count: {booked_rooms}")

            rooms_on_hold_count = self.env['rooms.on.hold.management.front.desk'].search_count([
                ('company_id', '=', self.env.company.id),
                ('room_type', '=', room_type_id),
                ('from_date', '<=', checkout_date),
                ('to_date', '>=', checkin_date)
            ])
            print(f"Rooms on hold count: {rooms_on_hold_count}")

            out_of_order_rooms_count = self.env['out.of.order.management.fron.desk'].search_count([
                ('company_id', '=', self.env.company.id),
                ('room_type', '=', room_type_id),
                ('from_date', '<=', checkout_date),
                ('to_date', '>=', checkin_date)
            ])
            print(f"Out of order rooms count: {out_of_order_rooms_count}")

            confirmed_bookings = self.env['room.booking'].search([
                    ('hotel_room_type', '=', room_type_id),
                    ('checkin_date', '<=', checkout_date),
                    ('checkout_date', '>=', checkin_date),
                    ('checkout_date', 'not like', today_date + '%'),
                    ('state', '=', 'confirmed'),
                    ('id', 'not in', self.env.context.get('already_allocated', []))
                ])

            confirmed_room_lines_count = sum(len(booking.room_line_ids) for booking in confirmed_bookings)
            if sum(len(booking.room_line_ids) for booking in confirmed_bookings) > 0:
                confirmed_room_lines_count -= 1

                
            booked_rooms = booked_rooms + rooms_on_hold_count + out_of_order_rooms_count + confirmed_room_lines_count
                

            # booked_rooms += rooms_on_hold_count + out_of_order_rooms_count
            print(f"Total booked rooms (including on hold and out of order): {booked_rooms}")

            if availability['overbooking_allowed']:
                available_rooms = max(availability['total_room_count'] - booked_rooms + availability['overbooking_rooms'], 0)
                print(f"Available rooms with overbooking: {available_rooms}")

                if availability['overbooking_rooms'] == 0:
                    print("Overbooking rooms are zero, returning unlimited rooms")
                    return 99999  # Unlimited rooms
            else:
                available_rooms = max(availability['total_room_count'] - booked_rooms, 0)
                print(f"Available rooms without overbooking: {available_rooms}")

            total_available_rooms += available_rooms
            print(f"Total available rooms so far: {total_available_rooms}")

        print(f"Final total available rooms: {total_available_rooms}")
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
    #     start_time = datetime.now().time()
    #     print(f"Start time for room assignment: {start_time}")
    #     """Assign unique available rooms to each line based on Room Type."""
    #     for booking in self:
    #         if booking.state != 'confirmed':
    #             raise UserError(
    #                 "Rooms can only be assigned when the booking is in the 'Confirmed' state.")

    #         if not booking.room_line_ids:
    #             raise UserError("No room lines to assign rooms to.")

    #         # Get room ids of rooms booked in the date range
    #         booked_room_lines = self.env['room.booking.line'].search([
    #             ('room_id', '!=', False),
    #             ('checkin_date', '<', booking.checkout_date),
    #             ('checkout_date', '>', booking.checkin_date),
    #             ('booking_id.state', 'in', ['confirmed','block','check_in']),
    #         ])
    #         booked_room_ids = booked_room_lines.mapped('room_id').ids

    #         # Keep track of already assigned rooms
    #         assigned_room_ids = set()

    #         # Counter for successfully assigned rooms
    #         assigned_count = 0

    #         # Counter for unassignable lines
    #         unassignable_lines = []

    #         # Process each line and assign a unique room
    #         for line in booking.room_line_ids:
    #             if not line.hotel_room_type:  # Ensure the room line has a Room Type
    #                 raise UserError(
    #                     f"Room line {line.sequence} has no Room Type defined. Please specify a Room Type.")

    #             # Create a domain to fetch available rooms of the same type
    #             domain = [
    #                 ('company_id', '=', self.env.company.id),
    #                 ('id', 'not in', booked_room_ids + list(assigned_room_ids)),
    #                 # Match room type
    #                 ('room_type_name', '=', line.hotel_room_type.id)
    #             ]

    #             # Search for available rooms matching the domain
    #             available_rooms = self.env['hotel.room'].search(domain)

    #             if available_rooms:
    #                 # Check if the room is in a block state
    #                 for room in available_rooms:
    #                     if room.status == 'block':
    #                         raise ValidationError(
    #                             f"Room '{room.name}' is in a 'block' state and cannot be assigned."
    #                         )
    #                 # Assign the first available room to the line
    #                 assigned_room = available_rooms[0]
    #                 line.room_id = assigned_room.id
    #                 # Track assigned room
    #                 assigned_room_ids.add(assigned_room.id)
    #                 assigned_count += 1
    #             else:
    #                 # Add line to unassignable list
    #                 unassignable_lines.append(line)

    #         # If there are unassignable lines, raise an error
    #         if unassignable_lines:
    #             unassigned_count = len(unassignable_lines)
    #             raise UserError(
    #                 f"Only {assigned_count} rooms were assigned out of {len(booking.room_line_ids)} requested. "
    #                 f"{unassigned_count} room(s) could not be assigned due to unavailability."
    #             )

    #         # Ensure recomputation of state fields
    #         booking.room_line_ids._compute_state()

    #         # Update any related information
    #         # self._update_adults_with_assigned_rooms(booking)

    #         booking._compute_show_in_tree()
    #         end_time = datetime.now().time()
    #         print(f"End time for room assignment: {end_time}")
    #         # print(f"Time taken for room assignment: {end_time}")



    # def action_assign_all_rooms(self):
    #     print("START TIME", datetime.now())
    #     for booking in self:
    #         _logger.info("Starting assignment for booking ID: %s", booking.id)

    #         if booking.state != 'confirmed':
    #             _logger.warning("Booking %s is not confirmed", booking.name)
    #             raise UserError("Booking must be Confirmed first.")
    #         if not booking.room_line_ids:
    #             _logger.warning("No room lines found for booking %s", booking.name)
    #             raise UserError("No room lines to assign.")
                
    #         original_rate_forecasts = booking.rate_forecast_ids
    #         room_count = len(booking.room_line_ids)
    #         _logger.info("Dividing rate forecasts for %s room lines", room_count)
            
    #         forecast_data = []
    #         for forecast in original_rate_forecasts:
    #             divided_data = {
    #                 'date': forecast.date,
    #                 'rate': forecast.rate / room_count if room_count else forecast.rate,
    #                 'meals': forecast.meals / room_count if room_count else forecast.meals,
    #                 'packages': forecast.packages / room_count if room_count else forecast.packages,
    #                 'fixed_post': forecast.fixed_post / room_count if room_count else forecast.fixed_post,
    #                 'total': forecast.total / room_count if room_count else forecast.total,
    #                 'before_discount': forecast.before_discount / room_count if room_count else forecast.before_discount
    #             }
    #             forecast_data.append(divided_data)

    #             forecast.write(divided_data)
    #             _logger.debug("Updated parent forecast on %s with %s", forecast.date, divided_data)

    #         print("Calling stored procedure to split booking %s, %s", booking.id, datetime.now())
    #         self.env.cr.execute("CALL split_confirmed_booking(%s)", (booking.id,))
    #         print("Stored procedure executed successfully", datetime.now())

    #         child_bookings = self.env['room.booking'].search([
    #             ('parent_booking_id', '=', booking.id)
    #         ])
    #         _logger.info("Found %s child bookings", len(child_bookings))

    #         for child_booking in child_bookings:
    #             self.env.invalidate_all()
    #             child_forecasts = child_booking.rate_forecast_ids
    #             if not child_forecasts:
    #                 _logger.info("Creating new forecasts for child booking ID: %s", child_booking.id)
    #                 for data in forecast_data:
    #                     self.env['room.rate.forecast'].create({
    #                         'room_booking_id': child_booking.id,
    #                         'date': data['date'],
    #                         'rate': data['rate'],
    #                         'meals': data['meals'],
    #                         'packages': data['packages'],
    #                         'fixed_post': data['fixed_post'],
    #                         'total': data['total'],
    #                         'before_discount': data['before_discount']
    #                     })
    #             else:
    #                 _logger.info("Updating existing forecasts for child booking ID: %s", child_booking.id)
    #                 for forecast in child_forecasts:
    #                     matching_data = next((data for data in forecast_data if data['date'] == forecast.date), None)
    #                     if matching_data:
    #                         forecast.write(matching_data)
    #                         _logger.debug("Updated child forecast on %s with %s", forecast.date, matching_data)

    #         self.env.cr.execute("""
    #             SELECT MAX(CAST(regexp_replace(name, '.*/', '') AS INT))
    #             FROM room_booking
    #             WHERE company_id = %s
    #         """, (booking.company_id.id,))
    #         max_booking_number = self.env.cr.fetchone()[0] or 0
    #         _logger.info("Max booking number for company %s is %s", booking.company_id.name, max_booking_number)

    #         sequence = self.env['ir.sequence'].search([
    #             ('code', '=', 'room.booking'),
    #             ('company_id', '=', booking.company_id.id)
    #         ], limit=1)

    #         if sequence:
    #             increment = sequence.number_increment or 1
    #             next_number = max_booking_number + increment
    #             sequence.sudo().write({'number_next': next_number})
    #             _logger.info("Updated sequence %s to next number %s", sequence.name, next_number)

    #             date_ranges = self.env['ir.sequence.date_range'].search([
    #                 ('sequence_id', '=', sequence.id)
    #             ])
    #             for date_range in date_ranges:
    #                 if date_range.number_next <= max_booking_number:
    #                     date_range.sudo().write({'number_next': next_number})
    #                     _logger.info("Updated sequence date range %s to next number %s", date_range.name, next_number)

    #     self.env.invalidate_all()
    #     booking.room_line_ids._compute_state()
    #     booking._compute_show_in_tree()
    #     _logger.info("Completed room assignment for booking ID: %s", booking.id)
    #     print("END TIME", datetime.now())

    
    def action_assign_all_rooms(self):
        for booking in self:
            start_time = datetime.now()
            print("START TIME", start_time)
            print("==> Begin assign_all_rooms for Booking %s at %s", booking.name, start_time)

            # 1. State & room_line validations
            if booking.state != 'confirmed':
                _logger.warning("Booking %s is not confirmed", booking.name)
                raise UserError("Booking must be Confirmed first.")
            if not booking.room_line_ids:
                _logger.warning("No room lines found for booking %s", booking.name)
                raise UserError("No room lines to assign.")

            # 2. Divide parent forecasts evenly
            room_count = len(booking.room_line_ids)
            _logger.info("Dividing %s parent forecasts across %s rooms", len(booking.rate_forecast_ids), room_count)

            forecast_data = []
            for fc in booking.rate_forecast_ids:
                divided = {
                    'date':            fc.date,
                    'rate':            fc.rate / room_count,
                    'meals':           fc.meals / room_count,
                    'packages':        fc.packages / room_count,
                    'fixed_post':      fc.fixed_post / room_count,
                    'total':           fc.total / room_count,
                    'before_discount': fc.before_discount / room_count,
                }
                forecast_data.append(divided)
                fc.write(divided)
                _logger.debug("Parent forecast on %s updated to %s", fc.date, divided)

            # 3. Call stored procedure to split booking rows in DB
            print("Calling stored procedure split_confirmed_booking(%s)", booking.id)
            self.env.cr.execute("CALL split_confirmed_booking(%s)", (booking.id,))
            print("Query Executed successfully at", datetime.now())

            # 4. Fetch all child bookings in one go
            child_bookings = self.search([('parent_booking_id', '=', booking.id)])
            _logger.info("Found %s child bookings", len(child_bookings))

            # 5. Batch-create child forecasts
            to_create = []
            for child in child_bookings:
                for data in forecast_data:
                    vals = dict(data, room_booking_id=child.id)
                    to_create.append(vals)

            if to_create:
                _logger.info("Creating %s child forecasts in batch", len(to_create))
                self.env['room.rate.forecast'].create(to_create)

            # 6. Sequence adjustment (so names stay unique & increasing)
            self.env.cr.execute("""
                SELECT MAX(CAST(regexp_replace(name, '.*/', '') AS INT))
                FROM room_booking
                WHERE company_id = %s
            """, (booking.company_id.id,))
            max_num = self.env.cr.fetchone()[0] or 0
            seq = self.env['ir.sequence'].search([
                ('code', '=', 'room.booking'),
                ('company_id', '=', booking.company_id.id),
            ], limit=1)
            if seq:
                increment = seq.number_increment or 1
                next_no = max_num + increment
                seq.sudo().write({'number_next': next_no})
                _logger.info("Sequence %s set to next_number=%s", seq.code, next_no)
                for dr in self.env['ir.sequence.date_range'].search([('sequence_id', '=', seq.id)]):
                    if dr.number_next <= max_num:
                        dr.sudo().write({'number_next': next_no})
                        _logger.debug("Date range %s adjusted to %s", dr, next_no)

            # 7. Final cache clear & UI refresh
            self.env.invalidate_all()
            booking.room_line_ids._compute_state()
            booking._compute_show_in_tree()

            end_time = datetime.now()
            print("END TIME", end_time)
            duration = (end_time - start_time).total_seconds()
            _logger.info("<== Finished assign_all_rooms for Booking %s at %s (%.2fs)",
                         booking.name, end_time, duration)
    
    # def action_assign_all_rooms(self):
    #     for booking in self:
    #         if booking.state != 'confirmed':
    #             raise UserError("Booking must be Confirmed first.")
    #         if not booking.room_line_ids:
    #             raise UserError("No room lines to assign.")

    #         # one fast round-trip to PostgreSQL
    #         self.env.cr.execute("CALL split_confirmed_booking(%s)", (booking.id,))


    #     # ─── cache / UI refresh (Odoo-17 style) ───────────────────────
    #     self.env.invalidate_all()               # clear all ORM caches

    #     booking.room_line_ids._compute_state()
    #     booking._compute_show_in_tree()


    

    def action_clear_rooms(self):
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
            booking.write({'state': 'not_confirmed'})

    def action_split_rooms(self):
        for booking in self:
            if booking.state == "no_show":
                return True
            # Retrieve related room.availability.result records
            availability_results = self.env['room.availability.result'].search(
                [('room_booking_id', '=', booking.id)]
            )


            # Ensure we have availability results to process
            if not availability_results:
                raise UserError(
                    "You have to Search room first then you can split room.")

            all_split = all(result.split_flag for result in availability_results)
            if all_split:
                raise UserError("All rooms have already been split. No new rooms to split.")

            room_line_vals = []
            counter = 1
            adult_inserts = []
            child_inserts = []
            infant_inserts = []
            max_counter = max(booking.room_line_ids.mapped(
                'counter') or [0])  # Use 0 if no lines exist
            counter = max_counter + 1  # Start from the next counter value

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

    def _get_room_search_query(self):
        """
        Get the room search query template that filters rooms based on availability.
        Only returns rooms where free-to-sell quantity >= requested room count
        across the entire date range.
        
        Returns:
            str: SQL query for room search with availability calculations
            
        Modified: 2025-01-09T12:52:13+05:00
        """
        return """
        WITH RECURSIVE
parameters AS (
    SELECT
		%(from_date)s::date AS from_date,
        %(to_date)s::date AS to_date
		),
company_ids AS (
    select CAST(%(company_id)s AS INTEGER) as company_id
),
system_date_company AS (
    SELECT 
        id AS company_id, 
        system_date::date AS system_date,
        create_date::date AS create_date
    FROM res_company rc 
    WHERE rc.id IN (SELECT company_id FROM company_ids)
),
-- 2. Generate report dates from the earliest system_date to the specified to_date
date_series AS (
    SELECT generate_series(
        (SELECT MIN(system_date) FROM system_date_company), 
        (SELECT to_date FROM parameters),
        INTERVAL '1 day'
    )::date AS report_date
),
-- 3. Base data & Latest status per booking line
base_data AS (
        SELECT
            rb.id AS booking_id,
            rb.parent_booking_id,
            rb.company_id,
            rb.checkin_date::date AS checkin_date,
            rb.checkout_date::date AS checkout_date,
            rbl.id AS booking_line_id,
            rbl.sequence,
            rbl.room_id,
            rbl.hotel_room_type AS room_type_id,
            rbls.status,
            rbls.change_time,
            rb.house_use,
            rb.complementary
        FROM room_booking rb
        JOIN room_booking_line rbl ON rb.id = rbl.booking_id
        LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
        WHERE rb.company_id IN (SELECT company_id FROM company_ids) and rb.active = true

),
latest_line_status AS (
    SELECT DISTINCT ON (bd.booking_line_id, ds.report_date)
           bd.booking_line_id,
           ds.report_date,
           bd.checkin_date,
           bd.checkout_date,
           bd.company_id,
           bd.room_type_id,
           bd.status AS final_status,
           bd.change_time,
           bd.house_use,
           bd.complementary
    FROM base_data bd
    JOIN date_series ds 
      ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
    ORDER BY
       bd.booking_line_id,
       ds.report_date DESC,
       bd.change_time DESC NULLS LAST
)
	-- select * from latest_line_status;
	,
-- 4. Compute the system date metrics (anchor values)
-- Actual in_house on system_date (using check_in status)
system_date_in_house AS (
    SELECT
        sdc.system_date AS report_date,
        sdc.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    JOIN system_date_company sdc ON sdc.company_id = lls.company_id
    WHERE lls.final_status = 'check_in'
      AND sdc.system_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
),
-- Expected arrivals on system_date: bookings where checkin_date equals system_date and status is confirmed or block
system_date_expected_arrivals AS (
    SELECT
        sdc.system_date AS report_date,
        sdc.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    JOIN system_date_company sdc ON sdc.company_id = lls.company_id
    WHERE lls.checkin_date = sdc.system_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
),
-- Expected departures on system_date: bookings where checkout_date equals system_date and status in (check_in, confirmed, block)
system_date_expected_departures AS (
    SELECT
        sdc.system_date AS report_date,
        sdc.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    JOIN system_date_company sdc ON sdc.company_id = lls.company_id
    WHERE lls.checkout_date = sdc.system_date
      AND lls.final_status IN ('check_in', 'confirmed', 'block')
    GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
),
-- Compute the anchor expected_in_house on the system_date using the formula:
-- expected_in_house = in_house (from check_in) + expected arrivals – expected departures
system_date_base AS (
  SELECT
    sdc.system_date AS report_date,
    sdc.company_id,
    rt.id AS room_type_id,
    COALESCE(sdih.in_house_count, 0) AS in_house,
    COALESCE(sdea.expected_arrivals_count, 0) AS expected_arrivals,
    COALESCE(sded.expected_departures_count, 0) AS expected_departures,
    (COALESCE(sdih.in_house_count, 0)
     + COALESCE(sdea.expected_arrivals_count, 0)
     - COALESCE(sded.expected_departures_count, 0)) AS expected_in_house
  FROM system_date_company sdc
  CROSS JOIN room_type rt
  LEFT JOIN system_date_in_house sdih 
         ON sdih.company_id = sdc.company_id 
         AND sdih.room_type_id = rt.id 
         AND sdih.report_date = sdc.system_date
  LEFT JOIN system_date_expected_arrivals sdea 
         ON sdea.company_id = sdc.company_id 
         AND sdea.room_type_id = rt.id 
         AND sdea.report_date = sdc.system_date
  LEFT JOIN system_date_expected_departures sded 
         ON sded.company_id = sdc.company_id 
         AND sded.room_type_id = rt.id 
         AND sded.report_date = sdc.system_date
),
-- 5. For subsequent dates, calculate expected arrivals and departures per report_date
expected_arrivals AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed','block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
expected_departures AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status IN ('check_in','confirmed','block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
-- 6. Recursive Calculation for in_house and expected_in_house
-- For days after the system date, set:
--   new in_house = previous day's expected_in_house (i.e. yesterday’s expected in_house)
--   new expected_in_house = new in_house + (today's expected arrivals) - (today's expected departures)
recursive_in_house AS (
    -- Anchor row: system_date_base values
    SELECT 
        sdb.report_date,
        sdb.company_id,
        sdb.room_type_id,
        sdb.in_house,
        sdb.expected_in_house
    FROM system_date_base sdb
    UNION ALL
    -- Recursive step: for each subsequent day
    SELECT
        ds.report_date,
        r.company_id,
        r.room_type_id,
        r.expected_in_house AS in_house,  -- new in_house equals previous expected_in_house
        (r.expected_in_house + COALESCE(ea.expected_arrivals_count, 0)
                              - COALESCE(ed.expected_departures_count, 0)) AS expected_in_house
    FROM recursive_in_house r
    JOIN date_series ds 
         ON ds.report_date = r.report_date + INTERVAL '1 day'
    LEFT JOIN expected_arrivals ea 
         ON ea.report_date = ds.report_date 
         AND ea.company_id = r.company_id 
         AND ea.room_type_id = r.room_type_id
    LEFT JOIN expected_departures ed 
         ON ed.report_date = ds.report_date 
         AND ed.company_id = r.company_id 
         AND ed.room_type_id = r.room_type_id
),
recursive_in_house_distinct AS (
  SELECT
    report_date,
    company_id,
    room_type_id,
    MAX(in_house) AS in_house,
    MAX(expected_in_house) AS expected_in_house
  FROM recursive_in_house
  GROUP BY report_date, company_id, room_type_id
),
-- 7. Additional Metrics (house use, complementary use, inventory, out_of_order, rooms on hold, out_of_service)
house_use_cte AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS house_use_count
    FROM latest_line_status lls
    WHERE lls.house_use = TRUE
      AND lls.final_status IN ('check_in', 'check_out')
      AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
complementary_use_cte AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS complementary_use_count
    FROM latest_line_status lls
    WHERE lls.complementary = TRUE
      AND lls.final_status IN ('check_in', 'check_out')
      AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count,
        SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms,
        BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    GROUP BY hi.company_id, hi.room_type
),
out_of_order AS (
    SELECT
        rt.id AS room_type_id,
        hr.company_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS out_of_order_count
    FROM date_series ds
    JOIN out_of_order_management_fron_desk ooo
      ON ds.report_date BETWEEN ooo.from_date AND ooo.to_date
    JOIN hotel_room hr
      ON hr.id = ooo.room_number
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
rooms_on_hold AS (
    SELECT
        rt.id AS room_type_id,
        hr.company_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS rooms_on_hold_count
    FROM date_series ds
    JOIN rooms_on_hold_management_front_desk roh
      ON ds.report_date BETWEEN roh.from_date AND roh.to_date
    JOIN hotel_room hr
      ON hr.id = roh.room_number
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
out_of_service AS (
    SELECT
        rt.id AS room_type_id,
        hr.company_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS out_of_service_count
    FROM date_series ds
    JOIN housekeeping_management hm
      ON hm.out_of_service = TRUE
      AND (hm.repair_ends_by IS NULL OR ds.report_date <= hm.repair_ends_by)
    JOIN hotel_room hr
      ON hr.room_type_name = hm.room_type
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
-- 8. Final Report (metrics aggregated per report_date, company and room type)
final_report AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rc.name AS company_name,
        rt.id AS room_type_id,
        COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
        COALESCE(inv.total_room_count, 0) AS total_rooms,
        COALESCE(inv.overbooking_rooms, 0) AS overbooking_rooms,
        COALESCE(inv.overbooking_allowed, false) AS overbooking_allowed,
        COALESCE(ooo.out_of_order_count, 0) AS out_of_order,
        COALESCE(roh.rooms_on_hold_count, 0) AS rooms_on_hold,
        COALESCE(oos.out_of_service_count, 0) AS out_of_service,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures,
        COALESCE(hc.house_use_count, 0) AS house_use_count,
        COALESCE(cc.complementary_use_count, 0) AS complementary_use_count,
        (COALESCE(inv.total_room_count, 0)
         - COALESCE(ooo.out_of_order_count, 0)
         - COALESCE(roh.rooms_on_hold_count, 0)) AS available_rooms,
        COALESCE((
          SELECT in_house_count 
          FROM system_date_in_house sdi 
          WHERE sdi.company_id = rc.id 
            AND sdi.room_type_id = rt.id 
            AND sdi.report_date = ds.report_date
        ), 0) AS in_house
    FROM date_series ds
    LEFT JOIN res_company rc
         ON rc.id IN (SELECT company_id FROM company_ids)
    CROSS JOIN room_type rt
    INNER JOIN inventory inv
         ON inv.company_id = rc.id AND inv.room_type_id = rt.id
    LEFT JOIN out_of_order ooo
         ON ooo.company_id = rc.id AND ooo.room_type_id = rt.id AND ooo.report_date = ds.report_date
    LEFT JOIN rooms_on_hold roh
         ON roh.company_id = rc.id AND roh.room_type_id = rt.id AND roh.report_date = ds.report_date
    LEFT JOIN out_of_service oos
         ON oos.company_id = rc.id AND oos.room_type_id = rt.id AND oos.report_date = ds.report_date
    LEFT JOIN expected_arrivals ea
         ON ea.company_id = rc.id AND ea.room_type_id = rt.id AND ea.report_date = ds.report_date
    LEFT JOIN expected_departures ed
         ON ed.company_id = rc.id AND ed.room_type_id = rt.id AND ed.report_date = ds.report_date
    LEFT JOIN house_use_cte hc
         ON hc.company_id = rc.id AND hc.room_type_id = rt.id AND hc.report_date = ds.report_date
    LEFT JOIN complementary_use_cte cc
         ON cc.company_id = rc.id AND cc.room_type_id = rt.id AND cc.report_date = ds.report_date
    LEFT JOIN system_date_company sdc
         ON sdc.company_id = rc.id
    WHERE ds.report_date >= (SELECT from_date FROM parameters)
),
-- 9. Final Output: Join recursive in_house values with aggregated metrics
final_output AS (
    SELECT
      fr.report_date,
      fr.company_id,
      fr.company_name,
      fr.room_type_id,
      fr.room_type_name,
      SUM(fr.total_rooms) AS total_rooms,
      BOOL_OR(fr.overbooking_allowed) AS any_overbooking_allowed,
      SUM(fr.overbooking_rooms) AS total_overbooking_rooms,
      SUM(fr.out_of_order) AS out_of_order,
      SUM(fr.rooms_on_hold) AS rooms_on_hold,
      SUM(fr.out_of_service) AS out_of_service,
      SUM(fr.expected_arrivals) AS expected_arrivals,
      SUM(fr.expected_departures) AS expected_departures,
      SUM(fr.house_use_count) AS house_use_count,
      SUM(fr.complementary_use_count) AS complementary_use_count,
      SUM(fr.available_rooms) AS available_rooms,
      rih.in_house AS in_house,
      rih.expected_in_house AS expected_in_house,
      CASE 
        WHEN BOOL_OR(fr.overbooking_allowed) THEN
          CASE
            WHEN SUM(fr.available_rooms) < 0 
              OR SUM(fr.overbooking_rooms) < 0 
              OR rih.expected_in_house < 0 THEN 0
            ELSE GREATEST(0, SUM(fr.available_rooms) + SUM(fr.overbooking_rooms) - rih.expected_in_house)
          END
        ELSE
          CASE
            WHEN SUM(fr.available_rooms) < 0 THEN 0
            ELSE GREATEST(0, SUM(fr.available_rooms) - rih.expected_in_house)
          END
      END AS free_to_sell,
      GREATEST(0, rih.expected_in_house - SUM(fr.available_rooms)) AS over_booked
    FROM final_report fr
    JOIN recursive_in_house_distinct rih
      ON fr.report_date = rih.report_date
     AND fr.company_id = rih.company_id
     AND fr.room_type_id = rih.room_type_id
    WHERE fr.report_date >= (SELECT from_date FROM parameters)
    GROUP BY
      fr.report_date,
      fr.company_id,
      fr.company_name,
      fr.room_type_id,
      fr.room_type_name,
      rih.in_house,
      rih.expected_in_house
    ORDER BY
      fr.report_date,
      fr.company_name,
      fr.room_type_name
)

SELECT
        room_type_id,
        room_type_name,
        company_id,
        company_name,
        min(free_to_sell) AS min_free_to_sell,
        total_rooms,
        any_overbooking_allowed AS has_overbooking,
        total_overbooking_rooms
    FROM final_output
    WHERE (%(room_type_id)s IS NULL OR room_type_id = %(room_type_id)s)
    GROUP BY room_type_id, room_type_name, company_id, company_name, total_rooms, any_overbooking_allowed, total_overbooking_rooms;
        """

    search_performed = fields.Boolean(default=False)

    # @api.onchange("room_count")
    # def _onchange_room_count(self):
    #     if self.state == "confirmed":
    #         self.search_performed = False

    def action_search_rooms(self):
        self.ensure_one()
        self.action_clear_rooms()

        # Run your existing validation checks and forecast rates
        self._get_forecast_rates()

        # Build the SQL query
        query = self._get_room_search_query()

        # Construct the parameters for the SQL
        params = {
            'company_id': self.env.company.id,
            'from_date': self.checkin_date,
            'to_date': self.checkout_date,
            'room_count': self.room_count,
            'room_type_id': self.hotel_room_type and self.hotel_room_type.id or None,
        }

        # Execute the query
        self.env.cr.execute(query, params)

        # Fetch results
        results = self.env.cr.dictfetchall()

        # If there are no results, trigger the waiting list wizard (total_available_rooms = 0)
        if not results:
            wizard_result = self._trigger_waiting_list_wizard(
                self.room_count,
                0,
                self.hotel_room_type.id
            )
            # Return a tuple with 0 available rooms and the wizard action
            return (0, [wizard_result])

        # If a specific room type is selected, filter the results
        if self.hotel_room_type:
            filtered_results = [res for res in results if res['room_type_id'] == self.hotel_room_type.id]

            # If the filtered list is empty, trigger waiting list wizard (availability = 0)
            if not filtered_results:
                wizard_result = self._trigger_waiting_list_wizard(
                    self.room_count,
                    0,
                    self.hotel_room_type.id
                )
                return (0, [wizard_result])

            selected_result = filtered_results[0]
            available_rooms = selected_result['min_free_to_sell']

            # If the requested room count exceeds available rooms, trigger the waiting list wizard
            if self.room_count > available_rooms:
                return self._trigger_waiting_list_wizard(
                    self.room_count,
                    int(available_rooms),
                    self.hotel_room_type.id
                )
        else:
            # If no specific room type is selected, choose the room type with maximum available rooms
            best_result = max(results, key=lambda x: x['min_free_to_sell'])
            filtered_results = [best_result]

        # Build result lines for available rooms
        result_lines = []
        for res in filtered_results:
            if not isinstance(res, dict):
                raise ValueError(f"Expected a dictionary, but got: {res}")

            available_rooms = res['min_free_to_sell']
            # Only add lines if there is at least one available room
            if available_rooms > 0:
                result_lines.append((0, 0, {
                    'company_id': res['company_id'],
                    'room_type': res['room_type_id'],
                    'rooms_reserved': self.room_count,
                    'available_rooms': available_rooms,
                    'pax': self.adult_count,
                }))

        # Write the result lines back to the record
        self.write({'availability_results': result_lines})
        # self.with_context(ignore_search_guard=True).write({'availability_results': result_lines})

   
   
    # 2nd write sets the flag
        # self.write({'search_performed': True})

        return results

    
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


class ResPartnerDetails(models.Model):
    _name = 'partner.details'
    _description = 'Partner Details'
    _rec_name = 'partner_id' 

    partner_id = fields.Many2one('res.partner', string="Partner", required=False)
    partner_company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company, tracking=True)
    rate_code = fields.Many2one('rate.code', string="Rate Code")
    source_of_business = fields.Many2one('source.business', string="Source of Business")
    market_segments = fields.Many2one('market.segment', string="Market Segment")
    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern")

    # @api.onchange('partner_company_id')
    # def _onchange_company_id(self):
    #     """Update rate_code domain based on the selected Company."""
    #     if self.partner_company_id:
    #         return {
    #             'domain': {
    #                 'rate_code': [('company_id', '=', self.partner_company_id.id)]
    #             }
    #         }
    #     else:
    #         return {
    #             'domain': {
    #                 'rate_code': []
    #             }
    #         }

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create(self, vals):
        # Call the original create method
        # The above code is a comment in Python. Comments are used to provide explanations or notes
        # within the code for better understanding. In this case, the comment "# Python" is likely
        # indicating that the code is written in Python, and "partner" is another comment or
        # placeholder text. Comments in Python are denoted by the "#" symbol, and they are ignored by
        # the Python interpreter when the code is executed.
        partner = super(ResPartner, self).create(vals)

        # Create a record in the new model
        self.env['partner.details'].create({
            'partner_id': partner.id,
            'partner_company_id': self.env.company.id,
            'rate_code': vals.get('rate_code'),
            'source_of_business': vals.get('source_of_business'),
            'market_segments': vals.get('market_segments'),
            'meal_pattern': vals.get('meal_pattern'),
        })

        return partner

    is_vip = fields.Boolean(
        string="VIP", help="Mark this contact as a VIP", tracking=True)
    vip_code = fields.Many2one('vip.code', string="VIP Code",
                                domain=[('obsolete', '=', False)],
                                tracking=True
                            )


    @api.onchange('is_vip')
    def _onchange_is_vip(self):
        if not self.is_vip:
            self.vip_code = False
    
    # partner_details_id = fields.Many2one(
    #     'partner.details',
    #     domain=lambda self: [('company_id', '=', self.env.company.id)],
    #     string="Partner Details",
    #     tracking=True
    # )

    # rate_code = fields.Many2one(
    #     'rate.code',
    #     string="Rate Code",
    #     related="partner_details_id.rate_code",
    #     store=True,
    #     readonly=False,  # Make it editable if needed
    #     domain=lambda self: [('obsolete', '=', False)]
    # )
    # meal_pattern = fields.Many2one(
    #     'meal.pattern',
    #     string="Meal Pattern",
    #     related="partner_details_id.meal_pattern",
    #     store=True,
    #     readonly=False  # Make it editable if needed
    # )
    meal_rate_ids = fields.One2many('partner.details', 'partner_id', string='Meal and Rate',domain=lambda self: [
        ('partner_company_id', '=', self.env.company.id),
    ],)
    @api.constrains('meal_rate_ids')
    def _check_meal_rate_limit(self):
        for record in self:
            if len(record.meal_rate_ids) > 1:
                raise ValidationError("You can only add one meal and rate code entry.")
    

    #   domain=lambda self: [
    #     ('company_id', '=', self.env.company.id),
    # ],
    rate_code = fields.Many2one('rate.code',  domain=lambda self: [
        ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], string="Rate Code", tracking=True)
    # rate_code = fields.Many2one('partner.details',  domain=lambda self: [
    #     ('company_id', '=', self.env.company.id),
    #     # ('obsolete', '=', False)
    # ], string="Rate Code", tracking=True)
    source_of_business = fields.Many2one(
        'source.business', string="Source of Business", 
        domain=lambda self: [
        # ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ],tracking=True)
    nationality = fields.Many2one(
        'res.country', string='Nationality', tracking=True)
    market_segments = fields.Many2one('market.segment', string="Market Segment", 
    domain=lambda self: [
        # ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], tracking=True)
    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern",domain=lambda self: [('company_id', '=', self.env.company.id)], tracking=True)
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
        required=False, help="Select the posting item."
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

    checkin_time = fields.Char(string="Check-in Time 24hrs", help="Select the check-in time")
    checkout_time = fields.Char(string="Check-out Time 24hrs", help="Select the check-out time")

    @api.model
    def get_system_date(self):
        return self.env.company.system_date
    
    
    @api.constrains('checkin_time', 'checkout_time')
    def _check_time_format(self):
        time_pattern = re.compile(r'^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$')  # Regex for HH:MM:SS format
        for record in self:
            if record.checkin_time and not time_pattern.match(record.checkin_time):
                raise ValidationError(f"Invalid check-in time format: {record.checkin_time}. Please use HH:MM:SS.")
            if record.checkout_time and not time_pattern.match(record.checkout_time):
                raise ValidationError(f"Invalid check-out time format: {record.checkout_time}. Please use HH:MM:SS.")


    owner = fields.Char(string='Owner')
    
    system_date = fields.Datetime(
        string="System Date",
        # default=lambda self: fields.Datetime.now(),
        default=lambda self: self._default_system_date(),
        tracking=True,
        required=True,
        help="The current system date and time."
    )

    def action_update_system_date(self):
        """Add 1 day to the system_date for each record in self."""
        for rec in self:
            if rec.system_date:
                rec.system_date = rec.system_date + timedelta(days=1)
            else:
                rec.system_date = fields.Date.context_today(self)

            # Update the cron's nextcall based on system_date
            cron = self.env.ref(
                'hotel_management_odoo.cron_move_to_no_show', raise_if_not_found=False)
            if cron:
                cron.nextcall = datetime.combine(
                    rec.system_date, datetime.min.time())

        self.env['room.booking'].move_to_no_show()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def _default_system_date(self):
        """
        Returns today's date with the time set to 23:30 (11:30 PM) **without timezone info**.
        """
        user_tz = self.env.user.tz or 'UTC'  # Get user timezone or default to UTC
        today_date = fields.Date.context_today(self)  # Today's date in user’s timezone
        default_time = time(20, 00)  # 23:30:00 (11:30 PM)

        # Combine date and time
        user_timezone = pytz.timezone(user_tz)
        local_dt = user_timezone.localize(datetime.combine(today_date, default_time))  # Localized datetime

        # Convert to UTC
        utc_dt = local_dt.astimezone(pytz.utc)

        # **FIX:** Convert to naive datetime (remove timezone info)
        naive_utc_dt = utc_dt.replace(tzinfo=None)

        return naive_utc_dt  # Store as naive datetime


    @api.constrains('system_date')
    def _check_system_date(self):
        """Ensure that system_date is not earlier than the company's creation date."""
        for record in self:
            if record.system_date and record.create_date and record.system_date <= record.create_date:
                raise ValidationError(f"System Date ({record.system_date.date()}) cannot be earlier than the company's creation date ({record.create_date.date()}).")

    

    inventory_ids = fields.One2many('hotel.inventory', 'company_id', string="Inventory")
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
    rate_code = fields.Many2one('rate.code',   domain=lambda self: [('company_id', '=', self.env.company.id)], string="Rate Codes")
    market_segment = fields.Many2one('market.segment', string='Market Segment')
    starting_price = fields.Float(string="Starting Price")
    
    # source_business = fields.Many2one(
    #     'source.business', domain="[('company_id', '=', 2)]", string="Source of Business")
    source_business = fields.Many2one('source.business', string="Source of Business")

    term_and_condition_rc_en = fields.Html(string="English", domain=lambda self: [('company_id', '=', self.env.company.id)])
    term_and_condition_rc_ar = fields.Html(string="Arabic", domain=lambda self: [('company_id', '=', self.env.company.id)])

    term_and_condition_rcgroup_en = fields.Html(string="English", domain=lambda self: [('company_id', '=', self.env.company.id)])
    term_and_condition_rcgroup_ar = fields.Html(string="Arabic", domain=lambda self: [('company_id', '=', self.env.company.id)])

    @api.constrains('rate_code', 'name')
    def _check_company_name(self):
        """Ensure rate_code is only assigned if the name matches the current company."""
        current_company = self.env.company
        for record in self:
            if record.rate_code and record.name != current_company.name:
                record.rate_code = False  # Forcefully set rate_code to False
                raise ValidationError(
                    _(
                        "You cannot assign a Rate Code because your current hotel is '%s', "
                        "but the hotel name is '%s'. Both must be the same. "
                        "or select blank rate code to create new hotel"

                    ) % (current_company.name, record.name)
                )
    # @api.onchange('system_date')
    # def _onchange_system_date(self):
    #     if self.system_date:
    #         # Search for bookings where system_date is between checkin_date and checkout_date
    #         bookings = self.env['room.booking'].search([
    #             ('checkin_date', '<=', self.system_date),
    #             ('checkout_date', '>=', self.system_date)
    #         ])
    #         print("BOOKINGS", len(bookings))
    #         # print("BOOKINGS", bookings)
    #
    #         for booking in bookings:
    #             print("CHECK", booking.checkin_date, booking.checkout_date, booking.state)

    @api.constrains('starting_price')
    def _check_starting_price(self):
        for record in self:
            if record.starting_price < 1: 
                raise ValidationError("Starting Price Cannot be less than 1")

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

    _rec_name = 'room_type'
    # image = fields.Image(string="Image", max_width=128, max_height=128)
    image = fields.Binary(string='Image', attachment=True)
    hotel_name = fields.Integer(string="Hotel Name")
    room_type = fields.Many2one('room.type', string="Room Type")
    total_room_count = fields.Integer(string="Total Room Count", readonly=True)
    pax = fields.Integer(string="Pax")
    age_threshold = fields.Integer(string="Age Threshold")
    web_allowed_reservations = fields.Integer(
        string="Web Allowed Reservations")
    overbooking_allowed = fields.Boolean(string="Overbooking Allowed")
    overbooking_rooms = fields.Integer(string="Overbooking Rooms")
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company)
    
    @api.onchange('web_allowed_reservations')
    def _onchange_web_allowed_reservations(self):
        for record in self:
            if record.web_allowed_reservations > record.total_room_count:
                record.web_allowed_reservations = 0  # Resetting the value
                return {
                    'warning': {
                        'title': "Validation Error",
                        'message': "Web Allowed Reservations cannot be greater than Total Room Count.",
                    }
                }

    
    def write(self, vals):
        result = super().write(vals)
        for record in self:
            if 'overbooking_rooms' in vals:
                room_count = vals.get('overbooking_rooms', record.overbooking_rooms)
                self.env.user.notify_info(
                    message=f"Overbooking allowed with {room_count} room(s).",
                    title="Overbooking Info"
                )
        return result


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
        today = self.env.company.system_date.date()
        get_current_time = datetime.now().time()
        checkin_datetime = datetime.combine(today, get_current_time)
        
        # Track successful and failed bookings
        successful_bookings = []
        
        for booking in self.booking_ids:
            # Skip if the booking has more than one room line
            if len(booking.room_line_ids) > 1:
                continue
            
            # Set the check-in date and perform the check-in
            booking.checkin_date = checkin_datetime
            booking._perform_checkin()
            successful_bookings.append(booking)
            
        
        # Prepare notification message
        if successful_bookings:
            message = f"Booking Checked In Successfully!"
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': message,
                    'next': {'type': 'ir.actions.act_window_close'}
                }
            }


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
        # today = datetime.now()
        today = self.env.company.system_date.date()
        for booking in self.booking_ids:
            if len(booking.room_line_ids) > 1:
                continue
                # raise ValidationError(_("This booking has multiple room lines and cannot be checked out through early checkout."))

            booking.checkout_date = today
            booking._perform_checkout()
            booking._create_invoice()  # Only create invoice if confirmed

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking Checked Out Successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_cancel(self):
        """ Action to cancel the check-in """
        return {'type': 'ir.actions.act_window_close'}


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
            '|', '|', '|',
            ('main_department.charge_group', '!=', False),
            ('main_department.payment_group', '!=', False),
            ('main_department.tax_group', '!=', False),
            ('main_department.adjustment', '!=', False)
        ]""",

        #  domain="""[
        #     ('main_department', '!=', False),
        #     ('main_department.charge_group', '!=', False),
        #     ('main_department.payment_group', '!=', False),
        #     ('main_department.tax_group', '!=', False)
        # ]""",
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
    change_time = fields.Datetime(string="Change Time")


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
        # today = datetime.now()
        today = self.env.company.system_date.date()
        for record in self:
            if record.checkin_date and record.checkin_date.date() < today:
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
                    booking.write({'state': 'confirmed'})
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

    # message = fields.Text(string="Confirmation Message", readonly=True)
    message = fields.Char(
        string="Message",
        translate=True,                                  # ← important
        default=lambda self: _(
            "Room number will be released. Do you want to proceed?")
    )
    title   = fields.Char(string="Title", translate=True, default=lambda self: _("Confirm Booking"))

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        res['message'] = _("Room number will be released. Do you want to proceed?")
        res['title'] = _("Confirm Booking")
        return res


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
        
        if self.booking_id and self.booking_id.state == 'block':
            self.booking_id.state = 'confirmed'
            # Also clear room_id for all related room lines
            for line in self.booking_id.room_line_ids:
                line.room_id = False
                line.state_ = 'confirmed'
                
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

class RoomCountConfirmWizard(models.TransientModel):
    _name = "room.count.confirm.wizard"
    _description = "Ask if we should run Search Rooms"

    # Just a read-only label
    message = fields.Html(
        default=lambda self: _(
            "<h3>Room count changed.</h3>"
            "<p>Do you want to search rooms now?</p>"
        ),
        readonly=True,
    )

    # YES  → call the normal button on the booking
    def action_yes(self):
        booking = self.env["room.booking"].browse(self.env.context.get("active_id"))
        booking.action_search_rooms()
        return {"type": "ir.actions.act_window_close"}

    # NO  → simply close the pop-up
    def action_no(self):
        return {"type": "ir.actions.act_window_close"}
