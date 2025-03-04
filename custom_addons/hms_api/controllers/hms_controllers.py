from ast import pattern
from email.policy import default
import random, string
from decorator import append

from odoo import http, fields
import base64
from odoo.http import request, Response
from datetime import timedelta
from decimal import Decimal
from datetime import datetime
import redis
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from io import BytesIO
from zipfile import ZipFile
import arabic_reshaper
from bidi.algorithm import get_display
import platform
from hijri_converter import convert
from textwrap import wrap
from reportlab.pdfbase.pdfmetrics import stringWidth
import logging
import io
import base64
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

REDIS_CONFIG = {
    'host': 'redis',
    'port': 6379
}


def check_space_and_new_page(
        c,
        needed_height,
        y_position,
        bottom_margin,
        top_margin,
        page_width,
        page_height,
        font_name="Helvetica",
        font_size=10
):
    """
    Checks if there's enough space on the current page for the needed_height.
    If not, starts a new page (c.showPage()) and resets y_position.
    """
    if (y_position - needed_height) < bottom_margin:
        # Not enough space on this page -> finish current page
        c.showPage()
        # Reset y_position at top of new page
        y_position = page_height - top_margin
        # Reset the font on the new page
        c.setFont(font_name, font_size)

    return c, y_position


def draw_table_with_page_break(
        c,
        x_left,
        y_top,
        table_width,
        header_height,
        row_height,
        table_headers,
        row_data_list,
        line_height,
        bottom_margin,
        top_margin,
        page_width,
        page_height,
        font_name="Helvetica",
        font_size=10
):
    """
    Draws a table which can span multiple pages if needed.
    - Each row of 'row_data_list' is a list of cell values (strings).
    - 'table_headers' is a list of (eng_text, arabic_text) for the column headers.
    - Returns the updated y_position after drawing the table.
    """

    # Quick guard: if no rows, skip drawing
    if not row_data_list:
        return y_top  # No change to y_top

    # Safety check: if row_height is bigger than usable page height,
    # each row may occupy its own page. That may be intentional, but be aware.
    usable_height = page_height - top_margin - bottom_margin - header_height
    if row_height > usable_height:
        print("Warning: row_height is larger than the usable page space.")
        # It will still work but each row might trigger a new page.

    c.setFont(font_name, font_size)
    num_cols = len(table_headers)
    col_width = table_width / num_cols

    def draw_header(header_y):
        """
        Draws the header row (rectangle + column lines + text).
        """
        # Draw outer rectangle for the header row
        c.rect(x_left, header_y - header_height, table_width, header_height)

        # Draw vertical column lines for the header
        x_cursor = x_left
        for col_index in range(num_cols + 1):
            c.line(x_cursor, header_y, x_cursor, header_y - header_height)
            x_cursor += col_width

        # Write the header text (English left, Arabic right)
        text_y = header_y - header_height + 8
        x_cursor = x_left
        for eng_label, ar_label in table_headers:
            # Center the header text horizontally within the column
            c.drawCentredString(x_cursor + (col_width / 2), text_y + 4, eng_label)  # English
            reshaped_ar = arabic_reshaper.reshape(ar_label)
            bidi_ar = get_display(reshaped_ar)
            c.drawCentredString(x_cursor + (col_width / 2), text_y - 4, bidi_ar)  # Arabic
            x_cursor += col_width

    # 1) Draw the initial header
    draw_header(y_top)
    current_y = y_top - header_height

    # 2) Iterate each row
    for row_idx, row_data in enumerate(row_data_list):

        if row_data[-1] == '':
            continue
        # Calculate needed height for this row
        needed_height = row_height + 10  # 10 is a small buffer

        # Check if we have enough space on this page
        c, current_y = check_space_and_new_page(
            c,
            needed_height,
            current_y,
            bottom_margin,
            top_margin,
            page_width,
            page_height,
            font_name,
            font_size
        )

        # If we started a new page, draw the header again
        # (Because after showPage(), the old header is gone)
        if current_y == (page_height - top_margin):
            draw_header(current_y)
            current_y -= header_height

        # Draw rectangle for the current row
        c.rect(x_left, current_y - row_height, table_width, row_height)

        # Draw vertical lines for the row
        x_cursor = x_left
        for col_index in range(num_cols + 1):
            c.line(x_cursor, current_y, x_cursor, current_y - row_height)
            x_cursor += col_width

        # Write data into each cell
        cell_x = x_left
        for cell_text in row_data:
            cell_text = str(cell_text) if cell_text is not None else ""
            c.drawCentredString(
                cell_x + (col_width / 2),
                current_y - (row_height / 2) - 2,  # Lower by 2 points
                cell_text
            )
            cell_x += col_width

        # After drawing this row, move current_y up
        current_y -= row_height

    # Return final Y position (with a bit of spacing below the table)
    return current_y - 20


def draw_footer_details(
        c,
        y_position,
        footer_details,
        left_margin,
        right_margin,
        page_width,
        page_height,
        bottom_margin,
        top_margin,
        font_name="Helvetica",
        font_size=8,
        line_spacing=15,  # Line spacing
        english_to_arabic_spacing=50  # Adjust spacing between English and Arabic
):
    """
    Draws the footer details section with proper alignment and a border.
    Handles longer English values with increased spacing and ensures the layout stays within the bounds.
    """
    if not footer_details:
        return y_position  # No data to draw

    needed_height = len(footer_details) * line_spacing + 20  # Include buffer space

    # Check if there's enough space, otherwise create a new page
    c, y_position = check_space_and_new_page(
        c,
        needed_height,
        y_position,
        bottom_margin,
        top_margin,
        page_width,
        page_height,
        font_name,
        font_size
    )

    # Set font
    c.setFont(font_name, font_size)

    # Define column positions
    col_width = (page_width - left_margin - right_margin) / 2  # Two equal columns
    LEFT_LABEL_X = left_margin + 10
    LEFT_VALUE_X = LEFT_LABEL_X + 100  # Extra spacing for longer English values
    LEFT_ARABIC_X = LEFT_VALUE_X + english_to_arabic_spacing

    RIGHT_LABEL_X = col_width + LEFT_LABEL_X
    RIGHT_VALUE_X = RIGHT_LABEL_X + 100  # Extra spacing for longer English values
    RIGHT_ARABIC_X = RIGHT_VALUE_X + english_to_arabic_spacing

    # Record the initial top Y position for the border
    border_top = y_position + 10

    # Iterate through the footer details and draw them
    for eng_label1, eng_value1, ar_label1, eng_label2, eng_value2, ar_label2 in footer_details:
        # Left column
        c.drawString(LEFT_LABEL_X, y_position, eng_label1)  # English label
        c.drawString(LEFT_VALUE_X, y_position, eng_value1)  # English value
        reshaped_ar_label1 = arabic_reshaper.reshape(ar_label1)
        bidi_ar_label1 = get_display(reshaped_ar_label1)
        c.drawRightString(LEFT_ARABIC_X, y_position, bidi_ar_label1)  # Arabic label

        # Right column
        c.drawString(RIGHT_LABEL_X, y_position, eng_label2)  # English label
        c.drawString(RIGHT_VALUE_X, y_position, eng_value2)  # English value
        reshaped_ar_label2 = arabic_reshaper.reshape(ar_label2)
        bidi_ar_label2 = get_display(reshaped_ar_label2)
        c.drawRightString(RIGHT_ARABIC_X, y_position, bidi_ar_label2)  # Arabic label

        # Move to the next line
        y_position -= line_spacing

    # Draw the border around the footer details section
    border_height = (border_top - y_position) + 10
    c.rect(
        left_margin - 10,  # Adjust for padding
        y_position - 5,  # Extend slightly below the last line
        page_width - left_margin - right_margin + 20,  # Extend the width for padding
        border_height
    )

    return y_position


def send_email(to_email, subject, body):
    """Helper function to send an email."""
    mail_values = {
        'subject': subject,
        'email_to': to_email,
        'body_html': body,
    }
    request.env['mail.mail'].sudo().create(mail_values).send()


class WebAppController(http.Controller):

    def dump_data_to_redis(self, key, data, expiry=3600):
        redis_client = self.get_redis_connections()
        redis_client.set(f"{key}_data", json.dumps(data, default=self.custom_serializer), ex=expiry)
        # redis_client.json().set(f"{key}_data", '.', data)
        print(f"Dumped all data on {key} to Redis.")

    def custom_serializer(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)  # Convert Decimal to float
        elif isinstance(obj, datetime):
            return obj.isoformat()  # Convert datetime to ISO 8601 string
        raise TypeError(f"Type {type(obj)} not serializable")

    def get_redis_connections(self):
        try:
            redis_client = redis.Redis(**REDIS_CONFIG)
            return redis_client
        except Exception as e:
            return None

    def get_model_data(self, model, hotel_id=None, columns=None):
        if columns is None:
            columns = []

        if hotel_id != None:
            records = request.env[model].sudo().search([
                ('company_id', '=', hotel_id),
            ])
        else:
            records = request.env[model].sudo().search([])
        data = []

        if len(columns) > 1:
            for record in records:
                record_data = {col: getattr(record, col, None) for col in columns}
                data.append(record_data)

        else:
            data = records

        return data

    def get_posting_items(self, hotel_id):
        posting_items_data = self.get_model_data('posting.item',
                                                 hotel_id,
                                                 ['id', 'description', 'default_value', 'posting_item_selection',
                                                  'show_in_website', 'website_desc', 'company_id'])

        posting_items = [item for item in posting_items_data if item["show_in_website"]]
        meal_data = self.get_model_data('meal.code',
                                        hotel_id,
                                        ['id', 'posting_item', 'description', 'price_pax', 'price_child',
                                         'price_infant', 'type'])

        # print("POSTING ITEM", posting_items)
        # print("MEAL DATA", meal_data)

        # Extract posting_item IDs from meal_data
        meal_posting_item_ids = {meal['posting_item']['id'] for meal in meal_data if 'posting_item' in meal}

        # Filter posting_items to exclude items whose id is in meal_posting_item_ids
        filtered_posting_items = [item for item in posting_items if item['id'] not in meal_posting_item_ids]

        posting_item_ids = {item["id"] for item in posting_items if item["show_in_website"]}
        # print("POSTING ITEM IDS", posting_item_ids)

        filtered_meals = [
            meal for meal in meal_data
            if 'posting_item' not in meal or meal['posting_item']['id'] in posting_item_ids
        ]

        # Print the filtered posting items
        # print("FILTERED POSTING ITEMS", filtered_posting_items, len(filtered_posting_items))
        return filtered_posting_items, filtered_meals

    @http.route('/api/signup', type='json', auth='public', methods=['POST'], csrf=False)
    def custom_web_singup(self, **kwargs):
        email = kwargs.get('email')
        mobile = kwargs.get('mobile')
        password = kwargs.get('password')
        name = kwargs.get('name')

        if not password or not (email or mobile):
            return {"status": "error", "message": "Missing email, mobile number, or password"}

        partner_domain = [('email', '=', email)] if email else [('mobile', '=', mobile)]
        partner = request.env['res.partner'].sudo().search(partner_domain, limit=1)

        if partner:
            return {"status": "error", "message": "User already exists"}

        new_partner = request.env['res.partner'].sudo().create({
            'name': name,
            'email': email,
            'mobile': mobile,
        })
        new_partner.set_password(password)

        return {
            "status": "success",
            "message": "Signup successful",
            "partner_id": new_partner.id,
            "email": new_partner.email,
        }

    @http.route('/api/signin', type='json', auth='public', methods=['POST'], csrf=False)
    def custom_web_signin(self, **kwargs):
        email = kwargs.get('email')
        mobile = kwargs.get('mobile')
        password = kwargs.get('password')

        if not password or not (email or mobile):
            return {"status": "error", "message": "Missing email, mobile number, or password"}

        # Search by email or mobile
        domain = [('email', '=', email)] if email else [('mobile', '=', mobile)]
        partner = request.env['res.partner'].sudo().search(domain, limit=1)

        if partner and partner.check_password(password):
            session_token = request.session.sid
            return {
                "status": "success",
                "message": "Login successful",
                "session_token": session_token,
                "partner_id": partner.id,
                "email": partner.email
            }
        else:
            return {"status": "error", "message": "Invalid credentials"}

    @http.route('/api/forget_password', type='json', auth='public', methods=['POST'], csrf=False)
    def forget_password(self, **kwargs):
        email = kwargs.get('email')
        if not email:
            return {"status": "error", "message": "Email is required"}
        # Search for the partner with the given email
        partner = request.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
        if not partner:
            return {"status": "error", "message": "User not found"}
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        partner.set_password(new_password)
        print("NEW RESET PASSWORD", new_password)
        subject = "Password Reset Notification"
        body = f"""
                <p>Dear {partner.name},</p>
                <p>Your password has been reset. Your new password is:</p>
                <p><strong>{new_password}</strong></p>
                <p>Please log in and change your password as soon as possible.</p>
                <p>Thank you!</p>
            """
        send_email(to_email=email, subject=subject, body=body)
        return {
            "status": "success",
            "message": "Password has been reset and emailed to the user",
        }

    @http.route('/api/change_contact_password', type='json', auth='public', methods=['POST'], csrf=False)
    def change_contact_password(self, **kwargs):
        email = kwargs.get('email')
        old_password = kwargs.get('old_password')
        new_password = kwargs.get('new_password')
        if not email or not old_password or not new_password:
            return {
                "status": "error",
                "message": "Email, old password, and new password are required"
            }
        # Search for the partner with the given email
        partner = request.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
        if not partner:
            return {"status": "error", "message": "User not found"}
        if not partner.check_password(old_password):
            return {"status": "error", "message": "Old password is incorrect"}
        # Set the new password
        partner.set_password(new_password)
        return {
            "status": "success",
            "message": "Password changed successfully"
        }

    @http.route('/api/hotels/list', type='json', auth='public', methods=['POST'], csrf=False)
    def get_hotels_list(self, **kwargs):
        companies = request.env['res.company'].sudo().search([])

        all_hotels = []
        for hotel in companies:
            if hotel.rate_code:
                all_hotels.append({
                    "id": hotel.id,
                    "name": hotel.name,
                    "logo": f"data:image/png;base64,{hotel.logo.decode('utf-8')}" if hotel.logo else None,
                    'review': hotel.web_review,
                    'star_rating': hotel.web_star_rating,
                    'starting_price': hotel.starting_price,
                })

        return {"status": "success", "hotels": all_hotels}

    @http.route('/api/country/state/list', type='json', auth='public', methods=['GET'], csrf=False)
    def get_country_state_list(self, **kwargs):
        countries = request.env['res.country'].sudo().search([])
        country_list = []

        for country in countries:
            states = [
                {"id": state.id, "name": state.name}
                for state in country.state_ids
            ]
            country_list.append({
                "id": country.id,
                "country": country.name,
                "states": states
            })

        return {"status": "success", "countries": country_list}

    @http.route('/api/update_contact_data', type='json', auth='public', methods=['POST'], csrf=False)
    def update_contact_data(self, **kwargs):
        partner_id = kwargs.get('partner_id')
        if not partner_id:
            return {"status": "error", "message": "partner_id is required."}

        partner = request.env['res.partner'].sudo().browse(partner_id)

        if not partner.exists():
            return {"status": "error", "message": "Partner not found."}

        # Allowed fields to update
        update_fields = {
            'name': kwargs.get('name'),
            'complete_name': kwargs.get('name'),
            'state_id': kwargs.get('state_id'),
            'country_id': kwargs.get('country_id'),
            'website': kwargs.get('website'),
            'street': kwargs.get('street'),
            'street2': kwargs.get('street2'),
            'zip': kwargs.get('zip'),
            'city': kwargs.get('city'),
        }

        # Remove None values to prevent overwriting with NULL
        update_fields = {key: value for key, value in update_fields.items() if
                         value is not None or value != "" or value != 0}

        if update_fields:
            partner.sudo().write(update_fields)
            return {"status": "success", "message": "Partner updated successfully", "partner_id": partner.id}
        else:
            return {"status": "error", "message": "No valid fields provided for update."}

    @http.route('/api/get/partner', type='json', auth='public', methods=['GET'], csrf=False)
    def get_partner(self, partner_id=None):
        if not partner_id:
            return {"status": "error", "message": "partner_id is required."}

        partner = request.env['res.partner'].sudo().browse(partner_id)

        if not partner.exists():
            return {"status": "error", "message": "Partner not found."}

        partner_data = {
            "partner_id": partner.id,
            "name": partner.name,
            "complete_name": partner.complete_name,
            "state_id": partner.state_id.id if partner.state_id else None,
            "country_id": partner.country_id.id if partner.country_id else None,
            "website": partner.website,
            "street": partner.street,
            "street2": partner.street2,
            "zip": partner.zip,
            "city": partner.city,
        }

        return {"status": "success", "partner_data": partner_data}

    @http.route('/api/hotels', type='json', auth='public', methods=['POST'], csrf=False)
    def get_hotels(self, **kwargs):
        check_in_date = kwargs.get('checkin_date')
        check_out_date = kwargs.get('checkout_date')
        room_count = kwargs.get('room_count')
        person_count = kwargs.get('adult_count')

        if check_in_date == "" or check_out_date == "":
            return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}

        if room_count <= 0 or person_count <= 0:
            return {"status": "error", "message": "Invalid count. Provide proper counts"}

        redis_keys = ["hotels", "services", "meals"]
        redis_client = self.get_redis_connections()
        # print("REDIS CLIENT", redis_client)

        if redis_client:
            try:
                redis_data = {"status": "success"}
                for key in redis_keys:
                    # print("KEY", key)
                    cached_data = redis_client.get(f"{key}_data")
                    # print("CACHE DATA", cached_data)
                    if cached_data:
                        # print("Data found in Redis")
                        redis_data[key] = json.loads(cached_data)
                        # return json.loads(cached_data)

                # print("LENGTH REDIS", redis_data.keys())
                if len(redis_data.keys()) == 4:
                    return redis_data

            except Exception as e:
                pass

        companies = request.env['res.company'].sudo().search([])
        # print("COMPANIES", companies)
        # print("INVENTORY", len(companies.inventory_ids))
        # room_types = self.get_model_data('room.type')
        # print("ROOM TYPES", room_types)

        try:
            check_in = fields.Date.from_string(check_in_date)
            check_out = fields.Date.from_string(check_out_date)
        except ValueError:
            return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}

        days = []
        current_date = check_in
        while current_date < check_out:
            days.append(current_date.strftime('%A'))
            current_date += timedelta(days=1)

        default_rate_code = request.env['rate.code'].sudo().search([('id', '=', 12)])

        all_hotels_data = []
        for hotel in companies:
            if hotel.rate_code:
                rate_code = hotel.rate_code
                print("HOTEL RATE CODE", rate_code.code)
            else:
                continue
                # rate_code = default_rate_code
                # print("DEFAULT RATE CODE", rate_code.code)

            rate_details = request.env['rate.detail'].sudo().search([
                ('rate_code_id', '=', rate_code.id),
                ('from_date', '<=', check_in),
                ('to_date', '>=', check_in)
            ])

            if len(rate_details) == 0:
                print("DATE RANGE NOT FOUND, TAKING THE DEFAULT RATE CODE")
                rate_details = request.env['rate.detail'].sudo().search([
                    ('rate_code_id', '=', rate_code.id)
                ])

            try:
                rate_detail = rate_details[0]
            except Exception as e:
                rate_code = default_rate_code
                rate_details = request.env['rate.detail'].sudo().search([
                    ('rate_code_id', '=', rate_code.id),
                    ('from_date', '<=', check_in),
                    ('to_date', '>=', check_in)
                ])
                rate_detail = rate_details[0]

            hotel_data = {
                "id": hotel.id,
                "name": hotel.name,
                "age_threshold": hotel.age_threshold,
                "phone": hotel.phone,
                "email": hotel.email,
                "website": hotel.website,
                "title": hotel.web_title,
                "star_rating": hotel.web_star_rating,
                "kaaba_view": hotel.web_kaaba_view,
                "description": hotel.web_description,
                "location": hotel.web_hotel_location,
                "discount": hotel.web_discount,
                "review": hotel.web_review,
                "total_available_rooms": 0,
                "min_pay": hotel.web_payment,
                "payment": rate_detail.rate_detail_dicsount,
                "amount_payment": rate_detail.is_amount,
                "percent_payment": rate_detail.is_percentage,
                "logo": f"data:image/png;base64,{hotel.logo.decode('utf-8')}" if hotel.logo else None,
                "starting_price": hotel.starting_price,
            }

            all_rooms = []
            room_types = request.env['room.type'].sudo().search([
                ('company_id', '=', hotel.id)
            ])
            for room_type in room_types:
                # print("CHECK", room_type.description)
                available_rooms_dict = {}
                # available_rooms = request.env[
                #     'room.booking'].sudo().check_room_availability_all_hotels_split_across_type(
                #     check_in,
                #     check_out,
                #     room_count,
                #     person_count,
                #     room_type.id
                # )
                available_rooms = request.env['room.booking'].sudo().get_available_rooms_for_hotel_api(check_in,
                                                                                                       check_out,
                                                                                                       room_type.id,
                                                                                                       room_count, True,
                                                                                                       hotel.id)

                # print("AV", len(available_rooms), room_type.description, hotel.name)
                available_rooms_dict['id'] = room_type.id
                available_rooms_dict['type'] = room_type.description
                available_rooms_dict['pax'] = person_count
                available_rooms_dict['room_count'] = len(available_rooms)
                hotel_data['total_available_rooms'] += len(available_rooms)
                # all_rooms.append(available_rooms_dict)

                # rate_code_found = True
                # for room in available_rooms:
                #     if room.rate_code:
                #         print("RCI", room.rate_code.id)
                #         for day in days:
                #             pax_number = person_count // room_count
                #             rate_var = f"{day.lower()}_pax_{pax_number}"
                #             print("RATE VAR", rate_var)

                all_rooms.append(available_rooms_dict)

            hotel_data['room_types'] = all_rooms
            if hotel_data['total_available_rooms'] <= 0:
                continue
            all_hotels_data.append(hotel_data)

        services_data = self.get_model_data('hotel.service', None, ['id', 'name', 'unit_price'])
        posting_items, meals = self.get_posting_items(hotel_id=1)
        meal_data = self.get_model_data('meal.pattern', ['id', 'meal_pattern', 'description', 'abbreviation'])

        for meal in meal_data:
            meal_pattern = request.env['meal.pattern'].search([('id', '=', meal['id'])])

            # Initialize a list to store meal prices for this meal pattern
            meal_prices = []
            total_meal_price = 0

            for meal_item in meal_pattern.meals_list_ids:
                meal_prices.append({
                    "meal_rate_pax": meal_item.meal_code.price_pax,
                    "meal_rate_child": meal_item.meal_code.price_child,
                    "meal_rate_infant": meal_item.meal_code.price_infant,
                })
                total_meal_price += meal_item.meal_code.price_pax
                total_meal_price += meal_item.meal_code.price_child
                total_meal_price += meal_item.meal_code.price_infant

            # Add the prices list to the current meal dictionary
            meal['prices'] = meal_prices
            meal['total_price'] = total_meal_price

        # for posting_item in posting_items:
        #     print("POSTING ITEM", posting_item, not posting_item["show_in_website"])
        #     if not posting_item["show_in_website"]:
        #         posting_items.remove(posting_item)

        # posting_items = [item for item in posting_items if item["show_in_website"]]

        if redis_client:
            try:
                self.dump_data_to_redis("hotels:0", all_hotels_data)
                self.dump_data_to_redis("services", services_data)
                self.dump_data_to_redis("meals", meal_data)
            except Exception as e:
                pass

        return {"status": "success", "hotels": all_hotels_data, "services": services_data, "meals": meal_data,
                "posting_item": posting_items}

    @http.route('/api/hotel/<int:hotel_id>', type='json', auth='public', methods=['POST'], csrf=False)
    def get_hotel_by_id(self, hotel_id, **kwargs):
        check_in_date = kwargs.get('checkin_date')
        check_out_date = kwargs.get('checkout_date')
        room_count = kwargs.get('room_count')
        person_count = kwargs.get('adult_count')

        redis_keys = ["hotels", "services", "meals"]
        redis_client = self.get_redis_connections()

        if check_in_date == "" or check_out_date == "":
            return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}

        if room_count <= 0 or person_count <= 0:
            return {"status": "error", "message": "Invalid count. Provide proper counts"}

        if redis_client:
            try:
                redis_data = {"status": "success"}
                for key in redis_keys:
                    # print("KEY", key)
                    cached_data = redis_client.get(f"{key}_data")
                    # print("CACHE DATA", cached_data)
                    # print("CACHE DATA", cached_data)
                    if cached_data:
                        # print("Data found in Redis")
                        redis_data[key] = json.loads(cached_data)

                # print("LENGTH REDIS", redis_data.keys())
                if len(redis_data.keys()) == 4:
                    return redis_data

            except Exception as e:
                pass

        hotel = request.env['res.company'].sudo().search([('id', '=', hotel_id)], limit=1)
        default_rate_code = request.env['rate.code'].sudo().search([
            # ('id', '=', 12),
            ('company_id', '=', hotel.id)
        ])

        if not hotel:
            return {"status": "error", "message": "Hotel not found"}

        if not default_rate_code:
            return {"status": "error", "message": "Rate code error"}

        try:
            check_in = fields.Date.from_string(check_in_date)
            check_out = fields.Date.from_string(check_out_date)
        except ValueError:
            return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}

        days = []
        current_date = check_in
        while current_date < check_out:
            days.append(current_date.strftime('%A'))
            current_date += timedelta(days=1)

        # room_types = self.get_model_data('room.type')

        room_types = request.env['room.type'].sudo().search([
            ('company_id', '=', hotel.id)
        ])

        if hotel.rate_code:
            rate_code = hotel.rate_code
            print("HOTEL RATE CODE", rate_code.code)
        else:
            rate_code = default_rate_code
            print("DEFAULT RATE CODE", rate_code.code)
            return {"status": "error", "message": "Rate Code not found"}

        rate_details = request.env['rate.detail'].sudo().search([
            ('rate_code_id', '=', rate_code.id),
            ('from_date', '<=', check_in),
            ('to_date', '>=', check_in)
        ])

        if len(rate_details) == 0:
            print("DATE RANGE NOT FOUND, TAKING THE DEFAULT RATE CODE")
            rate_details = request.env['rate.detail'].sudo().search([
                ('rate_code_id', '=', rate_code.id)
            ])

        rate_detail = rate_details[0]

        hotel_data = {
            "id": hotel.id,
            "name": hotel.name,
            "age_threshold": hotel.age_threshold,
            "phone": hotel.phone,
            "email": hotel.email,
            "website": hotel.website,
            "title": hotel.web_title,
            "star_rating": hotel.web_star_rating,
            "kaaba_view": hotel.web_kaaba_view,
            "description": hotel.web_description,
            "location": hotel.web_hotel_location,
            "discount": hotel.web_discount,
            "review": hotel.web_review,
            "total_available_rooms": 0,
            "min_pay": hotel.web_payment,
            "payment": rate_detail.rate_detail_dicsount,
            "amount_payment": rate_detail.is_amount,
            "percent_payment": rate_detail.is_percentage,
            "logo": f"data:image/png;base64,{hotel.logo.decode('utf-8')}" if hotel.logo else None,
            "starting_price": hotel.starting_price,
        }

        all_rooms = []
        for room_type in room_types:
            available_rooms_dict = {}
            # available_rooms = request.env['room.booking'].sudo()._get_available_rooms(check_in, check_out,
            #                                                                           room_type.id,
            #                                                                           room_count, True)
            available_rooms = request.env['room.booking'].sudo().get_available_rooms_for_hotel_api(check_in,
                                                                                                   check_out,
                                                                                                   room_type.id,
                                                                                                   room_count, True,
                                                                                                   hotel.id)
            print("CHECK", room_type.description, len(available_rooms))
            # print("AV", len(available_rooms), available_rooms)
            available_rooms_dict['id'] = room_type.id
            available_rooms_dict['type'] = room_type.description
            available_rooms_dict['pax'] = person_count
            available_rooms_dict['room_count'] = len(available_rooms)
            hotel_data['total_available_rooms'] += len(available_rooms)
            all_rooms.append(available_rooms_dict)

        hotel_data['room_types'] = all_rooms
        if hotel_data['total_available_rooms'] <= 0:
            return {"status": "error", "hotels": "No rooms available"}

        posting_items, meal_data2 = self.get_posting_items(hotel_id=hotel_id)
        # services_data = self.get_model_data('hotel.service', ['id', 'name', 'unit_price'])
        # meal_data = self.get_model_data('meal.pattern', ['id', 'meal_pattern', 'description', 'abbreviation'])

        meal_data = []
        meal_data_ids = set()
        for meal_line in rate_details.meal_pattern_id.meals_list_ids:
            meal = meal_line.meal_code
            meal_data.append({
                "id": meal.id,
                # "meal_pattern": meal.meal_code,
                "description": meal.description,
                "unit_price": meal.price_pax,
                "posting_item": meal.posting_item.id,
                "default": True,
                "child_price": meal.price_child,
                "meal_type": meal.type
            })
            meal_data_ids.add(meal.id)

        # Add additional meals not in rate details
        # all_meals = self.get_model_data('meal.code', ['id', 'meal_pattern', 'description', 'posting_item', 'price_pax',
        #                                               'price_child', 'type'])
        for meal in meal_data2:
            # print("MEAL", meal)
            if meal['id'] not in meal_data_ids:
                meal_data.append({
                    "id": meal['id'],
                    # "meal_pattern": meal['meal_pattern'],
                    "description": meal['description'],
                    "unit_price": meal['price_pax'],
                    "posting_item": meal['posting_item'].id,
                    "child_price": meal['price_child'],
                    "meal_type": meal['type'],
                    "default": False
                })

        hotel_data['meals'] = meal_data

        # Fetch services
        services_data = [
            {
                "id": line.id,
                "name": line.hotel_services_config.display_name,
                "unit_price": line.packages_value,
                "rhythm": line.packages_rhythm,
            }
            for line in rate_details.line_ids
        ]

        hotel_data['services'] = services_data

        # for posting_item in posting_items:
        #     if not posting_item["show_in_website"]:
        #         posting_items.remove(posting_item)

        posting_items = [item for item in posting_items if item["show_in_website"]]

        if redis_client:
            try:
                self.dump_data_to_redis(f"hotels:{hotel_id}", hotel)
                self.dump_data_to_redis("services", services_data)
                self.dump_data_to_redis("meals", meal_data)

            except Exception as e:
                pass

        return {"status": "success", "hotels": hotel_data, "services": services_data, "meals": meal_data,
                "posting_item": posting_items}

    @http.route('/api/room_availability', type='json', auth='public', methods=['POST'], csrf=False)
    def check_room_availability(self, **kwargs):
        hotel_id = kwargs.get('hotel_id')
        check_in_date = kwargs.get('check_in_date')
        check_out_date = kwargs.get('check_out_date')
        person_count = kwargs.get('person_count')
        room_count = kwargs.get('room_count')
        redis_key = f"data:{hotel_id}:{check_in_date}:{check_out_date}:{person_count}:{room_count}"

        redis_client = self.get_redis_connections()

        if redis_client:
            try:
                redis_data = {"status": "success"}
                cached_data = redis_client.get(redis_key)
                if cached_data:
                    redis_data[redis_key] = json.loads(cached_data)

                if len(redis_data.keys()) == 2:
                    return redis_data

            except Exception as e:
                pass

        if not check_in_date or not check_out_date:
            return {"status": "error", "message": "Check-in and check-out dates are required"}

        try:
            check_in = fields.Date.from_string(check_in_date)
            check_out = fields.Date.from_string(check_out_date)
        except ValueError:
            return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}

        days = []
        current_date = check_in
        while current_date < check_out:
            days.append(current_date.strftime('%A'))
            current_date += timedelta(days=1)

        print("D", days)

        if hotel_id == 0:
            companies = request.env['res.company'].sudo().search([])
        else:
            companies = request.env['res.company'].sudo().search([('id', '=', hotel_id)])

        print("H", companies)

        # booked_rooms = request.env['room.booking'].sudo().
        rate_codes = request.env['rate.code'].sudo().search([])
        # room_type_specific_rates = request.env['room.type.specific.rate'].sudo().search([])
        # print(room_type_specific_rates)

        # print("RC", len(rate_codes))
        # for rate in rate_codes:
        #     print("RCI", rate.id)
        # rate_details = request.env['rate.detail'].sudo().search([('rate_code_id', '=', rate.id)])

        all_hotels_data = []
        for hotel in companies:
            hotel_data = {"hotel_id": hotel.id, "age_threshold": hotel.age_threshold}

            all_rooms = []
            room_types = request.env['room.type'].sudo().search([
                ('company_id', '=', hotel.id)
            ])
            for room_type in room_types:
                # print("CHECK", room_type.description)
                available_rooms_dict = {}
                available_rooms = request.env[
                    'room.booking'].sudo().check_room_availability_all_hotels_split_across_type(
                    check_in,
                    check_out,
                    room_count,
                    person_count,
                    room_type.id
                )
                # available_rooms = request.env['room.booking'].sudo()._get_available_rooms(check_in, check_out,
                #                                                                           room_type.id,
                #                                                                           room_count, True)
                # print("AV", len(available_rooms), available_rooms)
                available_rooms_dict['id'] = room_type.id
                available_rooms_dict['type'] = room_type.description
                available_rooms_dict['pax'] = person_count
                available_rooms_dict['room_count'] = len(available_rooms)
                # all_rooms.append(available_rooms_dict)

                # rate_code_found = True
                # for room in available_rooms:
                #     if room.rate_code:
                #         print("RCI", room.rate_code.id)
                #         for day in days:
                #             pax_number = person_count // room_count
                #             rate_var = f"{day.lower()}_pax_{pax_number}"
                #             print("RATE VAR", rate_var)

                all_rooms.append(available_rooms_dict)

            hotel_data['room_types'] = all_rooms
            all_hotels_data.append(hotel_data)

        # rooms_data = []
        # for room in available_rooms:
        #     rooms_data.append({
        #         "id": room.id,
        #         "name": room.name,
        #         "room_type": room.room_type,
        #         # Add any other relevant fields
        #     })
        # rooms_data.append({"room_type": all_rooms})
        if redis_client:
            try:
                self.dump_data_to_redis(redis_key, {"status": "success", "data": all_hotels_data})
            except Exception as e:
                pass

        return {"status": "success", "data": all_hotels_data}

    @http.route('/api/room_availability_multiple', type='json', auth='public', methods=['POST'], csrf=False)
    def check_multiple_room_availability(self, **kwargs):
        hotel_id = kwargs.get('hotel_id')
        person_id = kwargs.get('person_id', '')
        person_email = kwargs.get('person_email', '')
        check_in_date = kwargs.get('check_in_date')
        check_out_date = kwargs.get('check_out_date')
        pax_data = kwargs.get('options')

        # redis_key = f"data:{hotel_id}:{check_in_date}:{check_out_date}:{person_count}:{room_count}"

        # redis_client = self.get_redis_connections()
        #
        # if redis_client:
        #     try:
        #         redis_data = {"status": "success"}
        #         cached_data = redis_client.get(redis_key)
        #         if cached_data:
        #             redis_data[redis_key] = json.loads(cached_data)
        #
        #         if len(redis_data.keys()) == 2:
        #             return redis_data
        #
        #     except Exception as e:
        #         pass

        if not check_in_date or not check_out_date:
            return {"status": "error", "message": "Check-in and check-out dates are required"}

        try:
            check_in = fields.Date.from_string(check_in_date)
            check_out = fields.Date.from_string(check_out_date)
        except ValueError:
            return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}

        days = []
        current_date = check_in
        while current_date < check_out:
            days.append(current_date.strftime('%A').lower())
            current_date += timedelta(days=1)

        # print("D", days)

        if hotel_id == 0:
            companies = request.env['res.company'].sudo().search([])
        else:
            companies = request.env['res.company'].sudo().search([('id', '=', hotel_id)])

        default_rate_code = request.env['rate.code'].sudo().search([('id', '=', 12)])

        partner_rate_code = None
        partner_domain = [('email', '=', person_email)] if person_email else [
            ('id', '=', person_id)] if person_id else []
        # print("PARTNER DOMAIN", partner_domain, len(partner_domain))
        if len(partner_domain) > 0:
            partner = request.env['res.partner'].sudo().search(partner_domain, limit=1)
            partner_detail = request.env['partner.details'].sudo().search([
                ('partner_id', '=', partner.id),
                ('partner_company_id', '=', hotel_id),
            ], limit=1)

            partner_rate_code = partner_detail.rate_code

        # print("H", companies, pax_data)

        # room_types = request.env['room.type'].sudo().search([])
        # all_hotels_data = []
        #
        # # hotels_data = []
        # for hotel in companies:
        #     hotel_data = {}
        #     hotel_data["hotel_id"] = hotel.id
        #     hotel_data["age_threshold"] = hotel.age_threshold
        #
        #     all_rooms = {}
        #     for room_type in room_types:
        #         room_type_specific_rates = request.env['room.type.specific.rate'].sudo().search(
        #             [('room_type_id', '=', room_type.id)])
        #         all_rooms["id"] = room_type.id
        #         all_rooms["type"] = room_type.description
        #
        #         room_data_list = []
        #         for pax in pax_data:
        #             adult_price = 0
        #             child_price = 0
        #             room_data =  {}
        #
        #             for day in days:
        #                 _var = f"room_type_{day}_pax_1"
        #                 adult_price += room_type_specific_rates[_var] * pax["person_count"]
        #                 child_price += room_type_specific_rates.child * pax["room_count"]
        #
        #             price = {"adult": adult_price, "child": child_price}
        #             room_data["adult"] = adult_price
        #             room_data["child"] = child_price
        #
        #             print("CHECK", room_type.description)
        #             available_rooms_dict = {}
        #             available_rooms = (request.env['room.booking'].sudo().
        #                                get_available_rooms_for_api(check_in, check_out, room_type.id,
        #                                                             pax["room_count"], True, pax["person_count"]))
        #             print("AV", len(available_rooms), pax['person_count'])
        #             # if room_type.id in all_rooms:
        #             #     all_rooms[room_type.id]['room_count'] = max(all_rooms[room_type.id]['room_count'],
        #             #                                                 len(available_rooms))
        #             # else:
        #                 # Initialize the entry for this room type
        #             room_data["room_count"] = len(available_rooms)
        #             room_data["pax"] = pax["person_count"]
        #             all_rooms[room_type.id] = room_data
        #             # room_data_list.append(room_data)
        #             # all_rooms[room_type.id] = {
        #             #     'id': room_type.id,
        #             #     'type': room_type.description,
        #             #     # 'room_count': len(available_rooms),
        #             #     # 'price': price
        #             #     'room_data': [],
        #             #
        #             # }
        #
        #     # hotel_data["room_types"] = list(all_rooms.values())
        #     hotel_data['room_types'] = list(all_rooms.values())
        #     all_hotels_data.append(hotel_data)
        #
        #     # all_hotels_data.append(hotels_data)
        #
        # if redis_client:
        #     try:
        #         self.dump_data_to_redis(redis_key, {"status": "success", "data": all_hotels_data})
        #     except Exception as e:
        #         pass

        # posting_items_data = self.get_model_data('posting.item',
        #                                          ['id', 'description', 'default_value', 'posting_item_selection',
        #                                           'show_in_website', 'website_desc'])
        #
        # posting_items = [item for item in posting_items_data if item["show_in_website"]]
        posting_items, meal_data2 = self.get_posting_items(hotel_id=hotel_id)

        # room_types = request.env['room.type'].sudo().search([])
        all_hotels_data = []

        for hotel in companies:
            if partner_rate_code:
                rate_code = partner_rate_code
                print("PARTNER RATE CODE", rate_code.code)
            elif hotel.rate_code:
                rate_code = hotel.rate_code
                print("HOTEL RATE CODE", rate_code.code)
            else:
                # rate_code = default_rate_code
                # print("DEFAULT RATE CODE", rate_code.code)
                if hotel_id != 0:
                    return {"status": "error", "message": "Rate code not found"}
                continue

            hotel_data = {"hotel_id": hotel.id, "name": hotel.name, "age_threshold": hotel.age_threshold}

            amenities = request.env['hotel.amenity'].search([('company_id', '=', hotel.id)])
            amenities_data = []
            for amenity in amenities:
                amenities_data.append({
                    "id": amenity.id,
                    "name": amenity.name,
                    "icon": f"data:image/png;base64,{amenity.icon.image.decode('utf-8')}",
                    "description": amenity.description,
                    "frequency": amenity.frequency
                })

            hotel_data["amenities"] = amenities_data

            rate_details = request.env['rate.detail'].sudo().search([
                ('rate_code_id', '=', rate_code.id),
                ('from_date', '<=', check_in),
                ('to_date', '>=', check_in)
            ])

            if len(rate_details) == 0:
                print("DATE RANGE NOT FOUND, TAKING THE DEFAULT RATE CODE")
                rate_details = request.env['rate.detail'].sudo().search([
                    ('rate_code_id', '=', rate_code.id)
                ])
            try:
                rate_detail = rate_details[0]
                print("RATE DETAIL ID", rate_detail.id)
            except Exception as e:
                return {"status": "error", "message": "No rate code found on provided date range"}
                # rate_code = default_rate_code
                # rate_details = request.env['rate.detail'].sudo().search([
                #     ('rate_code_id', '=', rate_code.id),
                #     ('from_date', '<=', check_in),
                #     ('to_date', '>=', check_in)
                # ])
                # rate_detail = rate_details[0]

            # print("RATE DETAILS", rate_detail)
            # print("DETAILS", rate_detail.rate_detail_dicsount, rate_detail.is_amount, rate_detail.is_percentage)
            # hotel_data['rate_discount'] = rate_detail.rate_detail_dicsount
            # hotel_data['is_amount'] = rate_detail.is_amount
            # hotel_data['is_percentage'] = rate_detail.is_percentage

            meal_data = []
            meal_data_ids = []
            services_data = []

            # if len(partner_rate_code) >= 1:
            if partner_rate_code != None:
                for meal_line in partner_detail.meal_pattern['meals_list_ids']:
                    meal_data.append({
                        "id": meal_line['meal_code']['id'],
                        # "meal_pattern": meal_line['meal_code']['meal_code'],
                        "description": meal_line['meal_code']['description'],
                        "unit_price": meal_line['meal_code']['price_pax'],
                        "default": True,
                        "child_price": meal_line['meal_code']['price_child'],
                        "meal_type": meal_line['meal_code']['type']
                    })
                    meal_data_ids.append(meal_line['meal_code']['id'])
            else:
                for meal_line in rate_detail['meal_pattern_id']['meals_list_ids']:
                    meal_data.append({
                        "id": meal_line['meal_code']['id'],
                        # "meal_pattern": meal_line['meal_code']['meal_code'],
                        "description": meal_line['meal_code']['description'],
                        "unit_price": meal_line['meal_code']['price_pax'],
                        "default": True,
                        "child_price": meal_line['meal_code']['price_child'],
                        "meal_type": meal_line['meal_code']['type']
                    })
                    meal_data_ids.append(meal_line['meal_code']['id'])

            # all_meal_data = self.get_model_data('meal.code',
            #                                     ['id', 'description', 'meal_pattern', 'posting_item', 'price_pax',
            #                                      'price_child', 'price_infant', 'type'])
            print("MEAL DATA 2", meal_data2)

            for meal in meal_data2:
                if meal['id'] not in meal_data_ids:
                    meal_data.append({
                        "id": meal['id'],
                        # "meal_pattern": meal['meal_pattern'],
                        "description": meal['description'],
                        "unit_price": meal['price_pax'],
                        "posting_item": meal['posting_item'].id,
                        "child_price": meal['price_child'],
                        "meal_type": meal['type'],
                        "default": False
                    })

            hotel_data['meals'] = meal_data

            for service_line in rate_detail['line_ids']:
                services_data.append({
                    "id": service_line['id'],
                    "name": service_line['hotel_services_config']['display_name'],
                    "unit_price": service_line['packages_value'],
                    "rhythm": service_line['packages_rhythm'],
                    "value_type": service_line['packages_value_type'],
                })

            hotel_data['services'] = services_data
            hotel_data['posting_item'] = posting_items

            room_types_data = []
            room_types = request.env['room.type'].sudo().search([
                ('company_id', '=', hotel.id)
            ])
            for room_type in room_types:
                room_type_specific_rates = request.env['room.type.specific.rate'].sudo().search(
                    [('room_type_id', '=', room_type.id), ('rate_code_id', '=', rate_code.id)])
                # print("ROOM TYPE SPECIFIC RATE", room_type_specific_rates, room_type.id, hotel.id)

                images = [
                    f"data:image/png;base64,{img.image.decode('utf-8')}"
                    for img in room_type.image_ids if img.image
                ]

                room_type_data = {
                    "id": room_type.id,
                    "type": room_type.description,
                    "room_data": [],
                    "images": images
                }

                for pax in pax_data:
                    adult_price = 0
                    child_price = 0
                    infant_price = 0

                    if len(room_type_specific_rates) > 0:
                        for day in days:
                            if pax["person_count"] < 6 and pax['person_count'] > 0:
                                _var = f"room_type_{day}_pax_{pax['person_count']}"
                                adult_price += room_type_specific_rates[_var]
                                child_price += room_type_specific_rates["child_pax_1"] * pax["room_count"]
                                infant_price += room_type_specific_rates["infant_pax_1"] * pax["room_count"]
                            else:
                                _var = f"room_type_{day}_pax_1"
                                adult_price += room_type_specific_rates[_var] * pax["person_count"]
                                child_price += room_type_specific_rates["child_pax_1"] * pax["room_count"]
                                infant_price += room_type_specific_rates["infant_pax_1"] * pax["room_count"]

                    else:
                        for day in days:
                            # print("DAY PAX", day, pax['person_count'])
                            if pax["person_count"] < 6:
                                _var1 = f"{day}_pax_{pax['person_count']}"
                                # _var2 = f"room_type_{day}_pax_1"
                                adult_price += rate_detail[_var1]
                                child_price += rate_detail['child_pax_1']
                                infant_price += rate_detail['infant_pax_1']
                            else:
                                _var1 = f"{day}_pax_1"
                                adult_price += rate_detail[_var1] * pax["person_count"]
                                child_price += rate_detail['child_pax_1']
                                infant_price += rate_detail['infant_pax_1']
                        # if len(rate_details) >= 1:
                        #     # adult_price += room_type_specific_rates[0][_var] * pax["person_count"]
                        #     # adult_price += rate_details[_var1] * pax["person_count"]
                        #     adult_price += rate_details[0][_var1] * pax["person_count"]
                        # # child_price += room_type_specific_rates.child * pax["room_count"]

                        # if room_type_specific_rates:
                        #     # adult_price += room_type_specific_rates[_var2] * pax["person_count"]
                        #     adult_price += room_type_specific_rates[0][_var2] * pax["person_count"]

                    available_rooms = request.env['room.booking'].sudo().get_available_rooms_for_api(
                        check_in, check_out, room_type.id, pax["room_count"], True, pax["person_count"], hotel.id
                    )

                    room_data = {
                        "room_count": len(available_rooms),
                        "adult": adult_price,
                        "child": child_price,
                        "infant": infant_price,
                        "pax": pax["person_count"]
                    }

                    room_type_data["room_data"].append(room_data)

                room_types_data.append(room_type_data)

            hotel_data['room_types'] = room_types_data
            all_hotels_data.append(hotel_data)

        return {"status": "success", "data": all_hotels_data}

        # return {"status": "success", "data": all_hotels_data}

    @http.route('/api/room_rates', type='json', auth='public', methods=['POST'], csrf=False)
    def get_room_rates(self, **kwargs):
        room_type_id = kwargs.get('room_type_id')
        total_person_count = kwargs.get('total_person_count')
        total_child_count = kwargs.get('total_child_count')
        check_in_date = kwargs.get('check_in_date')
        check_out_date = kwargs.get('check_out_date')

        if not check_in_date or not check_out_date:
            return {"status": "error", "message": "Check-in and check-out dates are required"}

        try:
            check_in = fields.Date.from_string(check_in_date)
            check_out = fields.Date.from_string(check_out_date)
        except ValueError:
            return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}

        days = []
        current_date = check_in
        while current_date < check_out:
            days.append(current_date.strftime('%A').lower())
            current_date += timedelta(days=1)

        # print("D", days)

        room_type_specific_rates = request.env['room.type.specific.rate'].sudo().search(
            [('room_type_id', '=', room_type_id)])
        # print(room_type_specific_rates)
        adult_price = 0
        child_price = 0

        for day in days:
            _var = f"room_type_{day}_pax_1"
            adult_price += room_type_specific_rates[_var] * total_person_count
            child_price += room_type_specific_rates.child * total_child_count

            # print("room_type_specific_rates[_var]", room_type_specific_rates[_var])

        price = {"adult": adult_price, "child": child_price}
        # print(price)

        result = []
        for rate in room_type_specific_rates:
            result.append({
                'id': rate.id,
                'pax_1': rate.pax_1,
                'pax_2': rate.pax_2,
                'pax_3': rate.pax_3,
                'pax_4': rate.pax_4,
                'pax_5': rate.pax_5,
                'pax_6': rate.pax_6,
                'price': price
            })

        return {'status': 'success', 'rates': result}

    @http.route('/api/confirm_room_availability', type='json', auth='public', methods=['POST'], csrf=False)
    def confirm_room_availability(self, **kwargs):
        checkin_date = kwargs.get('check_in_date')
        checkout_date = kwargs.get('check_out_date')
        hotel_id = kwargs.get('hotel_id')
        customer_details = kwargs.get('customer_details')
        services = kwargs.get('services')
        rooms = kwargs.get('rooms')
        reference_number = kwargs.get('reference_number')
        payment_details = kwargs.get('payment_details')
        reference_booking = kwargs.get('reference_booking')
        additional_notes = kwargs.get('additional_notes')
        special_request = kwargs.get('special_request')

        # Check if booking_id is provided
        if not customer_details:
            return {"status": "error", "message": "Customer details is required"}

        partner_domain = [('email', '=', customer_details['email'])] if customer_details['email'] else [
            ('mobile', '=', customer_details['mobile'])]
        partner = request.env['res.partner'].sudo().search(partner_domain, limit=1)

        if not partner:
            _customer_name = f"{customer_details['first_name']} {customer_details['last_name']}"
            partner = request.env['res.partner'].sudo().create({
                'name': _customer_name.strip(),
                'email': customer_details['email'],
                'mobile': customer_details['contact'],
            })

        sob = request.env['source.business'].sudo().search([
            '|', '|',
            ('source', '=', 'web'),
            ('source', '=', 'Web'),
            ('source', '=', 'WEB')
        ], limit=1)

        try:
            rate_code = partner.rate_code
            # print("RATE CODE ID", rate_code.id)
            if not rate_code.id:
                hotel = request.env['res.company'].sudo().search([('id', '=', hotel_id)])
                rate_code = hotel.rate_code
                # print("RATECODE ID", rate_code.id)
        except Exception as e:
            return {"status": "error", "message": "No rate code found on provided hotel"}
        # print("RATE CODE")
        _adult_count = 0
        _child_count = 0
        availability_results_data = []
        created_booking_ids = []

        now = datetime.now()
        formatted_datetime = now.strftime("%d %m %Y %H %M")
        partner_group_id = False

        if len(rooms) > 1:
            _group_name = f"{customer_details['first_name']} {customer_details['last_name']} GRP {formatted_datetime}"
            partner_group = request.env['group.booking'].sudo().search([
                ('name', '=', _group_name),
                ('company', '=', partner.id),
            ], limit=1)

            if not partner_group:
                partner_group = request.env['group.booking'].sudo().create({
                    'name': _group_name,
                    'profile_id': customer_details['first_name'],
                    'company': partner.id,
                    'source_of_business': sob.id if hasattr(sob, 'id') else sob,
                })
            partner_group_id = partner_group.id

        adult_room_sequence = 0
        child_room_sequence = 0
        for room in rooms:
            # availability_results_data.append({
            #     'room_type': room['room_type_id'],
            #     'pax': room['pax'],
            #     'company_id': hotel_id,
            #     'rooms_reserved': 1,
            #     'available_rooms': 1,
            # })
            # _adult_count += room['adults']
            # _child_count += room['children']

            new_booking = request.env['room.booking'].sudo().create({
                'company_id': hotel_id,
                'partner_id': partner.id,
                'source_of_business': sob.id,
                'checkin_date': checkin_date,
                'ref_id_bk': reference_number,
                'checkout_date': checkout_date,
                'rate_code': rate_code.id,
                'room_count': 1,
                'reference_contact_': reference_booking,
                'is_offline_search': False,
                'notes': additional_notes,
                'special_request': special_request,
                'availability_results': [(0, 0, {
                    'room_type': room['room_type_id'],
                    'pax': room['pax'],
                    'company_id': hotel_id,
                    'rooms_reserved': 1,
                    'available_rooms': 1,
                })],
                'adult_count': room['adults'],
                'child_count': room['children'],
                'show_in_tree': True,
                'group_booking': partner_group_id,
            })
            # print("RATE CODE", rate_code)

            new_booking.action_split_rooms()
            created_booking_ids.append(new_booking.id)

            # adult_room_sequence += 1
            for adult in room.get('adult_details', []):
                nationality = request.env['res.country'].sudo().search([
                    ('name', '=', adult.get('nationality', '')),
                ])

                existing_adult = request.env['reservation.adult'].sudo().search([
                    ('reservation_id', '=', new_booking.id),
                    ('room_sequence', '=', 1),
                    ('first_name', '=', ''),
                    ('room_type_id', '!=', ''),
                ], limit=1)
                # print('existing_adult', existing_adult)

                adult_data = {
                    'room_sequence': 1,
                    'reservation_id': new_booking.id,
                    'first_name': adult.get('firstName', '').strip(),
                    'last_name': adult.get('lastName', '').strip(),
                    'id_type': adult.get('idType', ''),
                    'id_number': adult.get('id', ''),
                    'nationality': nationality.id if nationality else '',
                    'relation': adult.get('relation', ''),
                    'phone_number': adult.get('phone', ''),
                }

                if existing_adult:
                    existing_adult.write(adult_data)
                else:
                    request.env['reservation.adult'].sudo().create(adult_data)

            for child in room.get('children_age', []):
                # nationality = request.env['res.country'].sudo().search([
                #     ('name', '=', child.get('nationality', '')),
                # ])
                # print("CHILD", child)

                existing_child = request.env['reservation.child'].sudo().search([
                    ('reservation_id', '=', new_booking.id),
                    ('room_sequence', '=', 1),
                    ('profile', '=', child),
                    ('room_type_id', '=', room['room_type_id']),
                ], limit=1)

                child_data = {
                    'room_sequence': 1,
                    'reservation_id': new_booking.id,
                    'profile': child
                    # 'first_name': child.get('firstName', '').strip(),
                    # 'last_name': child.get('lastName', '').strip(),
                    # 'id_type': child.get('idType', ''),
                    # 'id_number': child.get('id', ''),
                    # 'nationality': nationality.id if nationality else '',
                    # 'relation': child.get('relation', ''),
                    # 'phone_number': child.get('phone', ''),
                }

                if existing_child:
                    existing_child.write(child_data)
                else:
                    request.env['reservation.child'].sudo().create(child_data)
                # print("DONE", child_data)

            for item in services:
                # print("ITEM", item)
                if item.get('type', 0) == 1 or item.get('type', 0) == 3:
                    posting_item = request.env['posting.item'].sudo().search([
                        '|',
                        ('item_code', '=', item['title']),
                        ('website_desc', '=', item['title'])
                    ], limit=1)
                    # print("Posting Item", posting_item)

                    if posting_item.exists():
                        # print("list entry", posting_item.id)
                        request.env['room.booking.posting.item'].sudo().create({
                            'booking_id': new_booking.id,
                            'posting_item_id': posting_item.id,
                            'item_code': posting_item.item_code,
                            'description': posting_item.description,
                            'posting_item_selection': item['option'],
                            'default_value': posting_item.default_value,
                        })
                    else:
                        print(f"No posting item found for title: {item['title']}")

        return {
            "status": "success",
            "booking_id": created_booking_ids,
        }

        # Prepare availability results and calculate adults and children
        # for room in rooms:
        #     availability_results_data.append({
        #         'room_type': room['room_type_id'],  # Replace with actual room type ID
        #         'pax': room['pax'],  # Replace with actual pax value
        #         'company_id': hotel_id,  # Pass company ID
        #         'rooms_reserved': 1,
        #         'available_rooms': 1,
        #     })
        #     _adult_count += room['pax']
        #     _child_count += room['children']
        #
        # # Check if we need to handle group booking
        # partner_group_id = False
        # now = datetime.now()
        # formatted_datetime = now.strftime("%d %m %Y %H %M")
        # if len(rooms) > 1:
        #     _group_name = f"{customer_details['first_name']} {customer_details['last_name']} GRP {formatted_datetime}"
        #     # Search for an existing group booking
        #     partner_group = request.env['group.booking'].sudo().search([
        #         ('name', '=', _group_name),
        #         ('company', '=', partner.id),
        #     ], limit=1)
        #
        #     # Create group booking if it doesn't exist
        #     if not partner_group:
        #         partner_group = request.env['group.booking'].sudo().create({
        #             'name': _group_name,
        #             'profile_id': customer_details['first_name'],
        #             'company': partner.id,
        #             'source_of_business': sob.id if hasattr(sob, 'id') else sob,
        #         })
        #     partner_group_id = partner_group.id
        #
        # # Create the room booking
        # new_booking = request.env['room.booking'].sudo().create({
        #     'company_id': hotel_id,  # Assuming `hotel_id` is the correct company ID
        #     'partner_id': partner.id,  # Ensure `partner` is a valid `res.partner` record
        #     'source_of_business': sob.id,  # Ensure `sob` is a valid `source.business` record
        #     'checkin_date': checkin_date,  # Ensure `checkin_date` is a valid date or datetime object
        #     'checkout_date': checkout_date,  # Ensure `checkout_date` is a valid date or datetime object
        #     'room_count': len(rooms),
        #     'availability_results': [(0, 0, availability_result) for availability_result in availability_results_data],
        #     'adult_count': _adult_count,
        #     'child_count': _child_count,
        #     'show_in_tree': True,
        #     # Only include group_booking if we created/found a group
        #     'group_booking': partner_group_id if partner_group_id else False,
        # })
        #
        # # new_booking.sudo().write({
        # #     'name': f"WEB_BOOKING/{new_booking.id}"
        # # })
        #
        # # if payment_details:
        # #     new_booking.state = 'confirmed'
        # #
        # # else:
        # new_booking.state = 'not_confirmed'
        #
        # # Return the result
        # print("BOOKING", new_booking)
        # return {
        #     "status": "success",
        #     "booking_id": new_booking.id,
        #     "booking_name": new_booking.name
        # }

    @http.route('/api/retrieve_room_booking', type='json', auth='public', methods=['POST'], csrf=False)
    def retrieve_room_booking(self, **kwargs):
        partner_email = kwargs.get('partner_email')
        partner_id = kwargs.get('partner_id')

        # print("Partner", partner_id, partner_email)

        if partner_id:
            partner = request.env['res.partner'].sudo().search([('id', '=', partner_id)])
        elif partner_email:
            partner = request.env['res.partner'].sudo().search([('email', '=', partner_email)])
        else:
            return {"status": "error", "message": "provide Partner email or Partner ID"}

        partner_group = request.env['group.booking'].sudo().search([('company', '=', partner.id)])
        all_bookings = request.env['room.booking'].sudo().search([
            ('state', 'not in', ['cancel', 'no_show']),
        ])
        group_bookings_data = []
        group_booking_id_list = []

        for group in partner_group:
            # Get the bookings for the current group
            # group_bookings = request.env['group.booking'].sudo().search([('group_booking', '=', group.id)])

            # Loop through each booking for the current group
            for booking in all_bookings:
                if group.id == booking.group_booking.id:
                    group_booking_id_list.append(booking.id)
                    group_bookings_data.append({
                        "booking_id": booking.id,
                        "booking_name": booking.name,
                        "reference_number": booking.ref_id_bk,
                        "company_id": booking.company_id.id if booking.company_id else None,
                        "partner_name": booking.partner_id.name if booking.partner_id else None,
                        "room_count": booking.room_count,
                        "state": booking.state,
                        "adult_count": booking.adult_count,
                        "child_count": booking.child_count,
                        "checkin_date": booking.checkin_date,
                        "checkout_date": booking.checkout_date,
                        "parent_booking_name": booking.parent_booking_name if booking.parent_booking_name else None,
                        "room_line_ids": [{
                            "id": result.id,
                            "room_type": result.hotel_room_type.description if result.hotel_room_type.description else None,
                            "state": result.state,
                            "room": result.room_id.name if result.room_id.name else None,
                            "house_keeping_status": result.housekeeping_status.display_name if result.housekeeping_status.display_name else None,
                        } for result in booking.room_line_ids]
                    })

        # Retrieve individual bookings
        bookings = request.env['room.booking'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', 'not in', ['cancel', 'no_show']),
        ])
        bookings_data = []

        for booking in bookings:
            if booking.id not in group_booking_id_list:
                booking_entry = {
                    "booking_id": booking.id,
                    "booking_name": booking.name,
                    "reference_number": booking.ref_id_bk,
                    "company_id": booking.company_id.id if booking.company_id else None,
                    "partner_name": booking.partner_id.name if booking.partner_id else None,
                    "room_count": booking.room_count,
                    "state": booking.state,
                    "adult_count": booking.adult_count,
                    "child_count": booking.child_count,
                    "checkin_date": booking.checkin_date,
                    "checkout_date": booking.checkout_date,
                    "parent_booking_name": booking.parent_booking_name if booking.parent_booking_name else None,
                    "room_line_ids": []
                }

                for result in booking.room_line_ids:
                    room_line_entry = {
                        "id": result.id,
                        "room_type": result.hotel_room_type.description if result.hotel_room_type.description else None,
                        "state": result.state,
                        "room": result.room_id.name if result.room_id.name else None,
                        "house_keeping_status": result.housekeeping_status.display_name if result.housekeeping_status.display_name else None,
                    }
                    booking_entry["room_line_ids"].append(room_line_entry)

                bookings_data.append(booking_entry)

        # bookings_data = [{
        #     "booking_id": booking.id,
        #     "booking_name": booking.name,
        #     "company_id": booking.company_id.id if booking.company_id else None,
        #     "partner_name": booking.partner_id.name if booking.partner_id else None,
        #     "room_count": booking.room_count,
        #     "state": booking.state,
        #     "adult_count": booking.adult_count,
        #     "child_count": booking.child_count,
        #     "checkin_date": booking.checkin_date,
        #     "checkout_date": booking.checkout_date,
        #     "parent_booking_name": booking.parent_booking_name if booking.parent_booking_name else None,
        #     "room_line_ids": [{
        #         "id": result.id,
        #         "room_type": result.hotel_room_type.description if result.hotel_room_type.description else None,
        #         "state": result.state,
        #         "room": result.room_id.name if result.room_id.name else None,
        #         "house_keeping_status": result.housekeeping_status.display_name if result.housekeeping_status.display_name else None,
        #     } for result in booking.room_line_ids]
        # } for booking in bookings]

        # group_booking_ids = {entry['booking_id'] for entry in group_bookings_data}
        # booking_ids = {entry['booking_id'] for entry in bookings_data}
        #
        # common_ids = group_booking_ids.intersection(booking_ids)
        #
        # unique_group_bookings_data = [entry for entry in group_bookings_data if entry['booking_id'] not in common_ids]
        # unique_bookings_data = [entry for entry in bookings_data if entry['booking_id'] not in common_ids]
        # print("LENGTH", len(bookings_data), len(group_bookings_data))

        return {
            "status": "success",
            "bookings": bookings_data,
            "group_bookings": group_bookings_data
        }

    @http.route('/api/cancel_room_booking', type='json', auth='public', methods=['POST'], csrf=False)
    def cancel_room_booking(self, **kwargs):
        booking_id = kwargs.get('booking_id')

        if not booking_id:
            return {"status": "error", "message": "provide Booking ID"}

        booking = request.env['room.booking'].sudo().search([('id', '=', booking_id)], limit=1)
        if booking:
            booking.state = 'cancel'

        return {
            "status": "success"
        }

    @http.route('/api/update_room_payment', type='json', auth='none', methods=['POST'], csrf=False)
    def update_room_payment(self, **kwargs):
        record_id = kwargs.get('payment_id')
        booking_id = kwargs.get('booking_id')
        payment_type = kwargs.get('payment_type')
        payment_status = kwargs.get('payment_status')
        print("PAYMENT LOGGER", record_id, booking_id, payment_type, payment_status)
        # state = kwargs.get('state')

        # Validate required parameters
        if not record_id or not booking_id or not payment_status:
            return {"status": "error", "message": "Missing required parameters"}

        state = 'confirmed' if payment_status == 'paid' else 'not_confirmed'

        payment_record = request.env['room.payment'].sudo().search([('id', '=', record_id)], limit=1)
        if not payment_record:
            return {"status": "error", "message": f"Room payment record with ID {record_id} does not exist"}

        # Search for room.booking record
        booking_record = request.env['room.booking'].sudo().search([('id', '=', booking_id)], limit=1)
        if not booking_record:
            return {"status": "error", "message": f"Room booking record with ID {booking_id} does not exist"}

        # Search for room.payment record
        payment_record = request.env['room.payment'].sudo().search([('id', '=', record_id)], limit=1)
        if not payment_record:
            return {"status": "error", "message": f"Room payment record with ID {record_id} does not exist"}

        # Search for room.booking record
        # booking_record = request.env['room.booking'].sudo().search([('id', '=', booking_id)], limit=1)
        # if not booking_record:
        #     return {"status": "error", "message": f"Room booking record with ID {booking_id} does not exist"}

        # Update room.payment record
        try:
            payment_record.sudo().write({
                'payment_type': payment_type.lower() if payment_type else None,
                'payment_status': payment_status
            })
        except Exception as e:
            return {"status": "error", "message": f"Failed to update room.payment: {str(e)}"}

        # Update room.booking record
        try:
            booking_record.sudo().write({
                'state': state,
                'payment_type': 'prepaid_credit'
            })
        except Exception as e:
            return {"status": "error", "message": f"Failed to update room.booking: {str(e)}"}

        return {
            "status": "success",
            "message": "Room payment and booking updated successfully"
        }

    @http.route('/generate/bookings_pdf', type='http', auth='user')
    def generate_bookings_pdf(self, booking_ids=None):
        if not booking_ids:
            return request.not_found()

        booking_ids = [int(id) for id in booking_ids.split(',')]

        # If there's only one booking, return a single PDF
        if len(booking_ids) == 1:
            booking = request.env['room.booking'].browse(booking_ids[0])
            if not booking.exists():
                return request.not_found()
            pdf_buffer = self._generate_pdf_for_booking(booking)
            return request.make_response(pdf_buffer.getvalue(), headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="booking_{booking.id}.pdf"')
            ])

        # If multiple bookings, create a ZIP file
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            for booking_id in booking_ids:
                booking = request.env['room.booking'].browse(booking_id)
                if not booking.exists():
                    continue
                # forecast_lines = request.env['room.rate.forecast'].search([
                #     ('room_booking_id', '=', booking.id)
                # ])
                print("this booking called", booking)
                pdf_buffer = self._generate_pdf_for_booking(booking)
                pdf_filename = f'booking_{booking.id}.pdf'
                zip_file.writestr(pdf_filename, pdf_buffer.getvalue())

        zip_buffer.seek(0)
        return request.make_response(zip_buffer.getvalue(), headers=[
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', 'attachment; filename="bookings.zip"')
        ])

    def _generate_pdf_for_booking(self, booking, forecast_lines=None):
        if forecast_lines is None:
            # fetch them here or set them to an empty list
            forecast_lines = request.env["room.rate.forecast"].search([
                ("room_booking_id", "=", booking.id)
            ])
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        left_margin = 40
        right_margin = 40
        top_margin = 50
        bottom_margin = 50

        # Register a font that supports Arabic
        if platform.system() == "Windows":
            font_path = "C:/Windows/Fonts/arial.ttf"
        else:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Or "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf"

            # Register the font
        try:
            pdfmetrics.registerFont(TTFont('CustomFont', font_path))
            font_name = 'CustomFont'
        except Exception as e:
            print(f"Font registration failed: {e}")
            font_name = 'Helvetica'  # Fallback font

        c.setFont(font_name, 8)  # Ensure this path is correct for your system
        # pdfmetrics.registerFont(TTFont('Arial', font_path))
        # c.setFont('Arial', 12)

        current_date = datetime.now()
        gregorian_date = current_date.strftime('%Y-%m-%d')
        hijri_date = convert.Gregorian(current_date.year, current_date.month, current_date.day).to_hijri()
        # Define the number of rows based on the number of pax
        num_rows = (booking.adult_count if booking.adult_count else 0) + \
                   (booking.child_count if booking.child_count else 0) + \
                   (booking.infant_count if booking.infant_count else 0)  # Default to 1 row if pax is not defined
        checkin_hijri_str = ""

        if booking.checkin_date:
            g_date_in = convert.Gregorian(
                booking.checkin_date.year,
                booking.checkin_date.month,
                booking.checkin_date.day
            )
        # Convert to Hijri and cast to string (e.g., '1445-10-05')
        arrival_hijri = g_date_in.to_hijri()
        checkin_hijri_str = str(arrival_hijri)  # or arrival_hijri.isoformat() if you want a standard format

        checkout_hijri_str = ""
        if booking.checkout_date:
            g_date_out = convert.Gregorian(
                booking.checkout_date.year,
                booking.checkout_date.month,
                booking.checkout_date.day
            )
        departure_hijri = g_date_out.to_hijri()
        checkout_hijri_str = str(departure_hijri)
        # arrival_hijri = convert_to_hijri(booking.checkin_date)
        # departure_hijri = convert_to_hijri(booking.checkout_date)
        max_address_width = 18

        # active_user = self.env.user

        # Function to draw Arabic text
        def draw_arabic_text(x, y, text):
            if text:
                reshaped_text = arabic_reshaper.reshape(text)  # Fix Arabic letter shapes
                bidi_text = get_display(reshaped_text)  # Fix RTL direction
                c.drawString(x, y, bidi_text)
            else:
                c.drawString(x, y, "")  # Draw empty string if the text is None

        y_position = height - 50  # Starting Y position
        line_height = 15  # Line height for vertical spacing

        def draw_company_logo(c, x, y, max_width, max_height, logo_data):
            """Draw company logo from Odoo binary field data"""
            try:
                logger.debug("Attempting to draw company logo from binary data")

                # Check if logo data exists
                if not logo_data:
                    logger.warning("No logo data found in company record")
                    return 0

                # Decode base64 logo data
                try:
                    logo_binary = base64.b64decode(logo_data)
                    logo_stream = io.BytesIO(logo_binary)
                    logger.debug("Successfully decoded logo binary data")

                    # Use PIL to open and identify the image
                    with PILImage.open(logo_stream) as img:
                        img_format = img.format.lower()
                        logger.debug(f"Detected image format: {img_format}")

                        # Create a new BytesIO for the image with proper format
                        final_image = io.BytesIO()
                        if img_format != 'png':  # Convert to PNG if it's not already
                            img = img.convert('RGBA')
                        img.save(final_image, format='PNG')
                        final_image.seek(0)

                        # Get image dimensions
                        img_width, img_height = img.size
                        logger.debug(f"Original image dimensions - Width: {img_width}, Height: {img_height}")

                except Exception as e:
                    logger.error(f"Error processing logo data: {str(e)}")
                    return 0

                # Calculate aspect ratio
                aspect = img_width / float(img_height)
                logger.debug(f"Image aspect ratio: {aspect}")

                # Calculate new dimensions
                if img_width > max_width:
                    new_width = max_width
                    new_height = new_width / aspect
                    if new_height > max_height:
                        new_height = max_height
                        new_width = new_height * aspect
                elif img_height > max_height:
                    new_height = max_height
                    new_width = new_height * aspect
                else:
                    new_width = img_width
                    new_height = img_height

                logger.debug(f"Final image dimensions - Width: {new_width}, Height: {new_height}")

                # Create temp file path based on OS
                if os.name == 'nt':  # Windows
                    temp_image_path = os.path.join(os.environ['TEMP'], 'temp_logo.png')
                else:  # Linux/Unix
                    temp_image_path = '/tmp/temp_logo.png'

                try:
                    with open(temp_image_path, 'wb') as temp_file:
                        temp_file.write(final_image.getvalue())

                    # Draw the image using the temporary file
                    c.drawImage(temp_image_path, x, y, width=new_width, height=new_height)
                    logger.info(
                        f"Successfully drew logo at position ({x}, {y}) with dimensions {new_width}x{new_height}")

                    # Clean up the temporary file
                    if os.path.exists(temp_image_path):
                        os.remove(temp_image_path)
                        logger.debug("Temporary logo file removed")

                except Exception as e:
                    logger.error(f"Error drawing image: {str(e)}")
                    if os.path.exists(temp_image_path):
                        try:
                            os.remove(temp_image_path)
                            logger.debug("Cleaned up temporary file after error")
                        except:
                            pass
                    return 0

                return new_height

            except Exception as e:
                logger.error(f"Error drawing logo: {str(e)}", exc_info=True)
                return 0

        # Main PDF generation code
        try:
            y_position = height - 10
            line_height = 15

            # Get logo directly from company_id.logo field
            logo_data = booking.company_id.logo
            logger.info(f"Company ID: {booking.company_id.id}")
            logger.info(f"Company Name: {booking.company_id.name}")
            logger.debug("Retrieved logo data from company record")

            # Adjusted smaller logo dimensions for icon-like appearance
            logo_max_width = 40  # Reduced from 150 to 60
            logo_max_height = 40  # Made square for icon-like appearance

            # Center the logo horizontally and place it at the top with some padding
            logo_x = 20  # Center horizontally
            logo_y = height - 35  # Place near top with 70px padding

            # Draw logo
            logger.debug("Starting logo drawing process")
            logo_height = draw_company_logo(c, logo_x, logo_y, logo_max_width, logo_max_height, logo_data)
            logger.debug(f"Returned logo height: {logo_height}")

            # Adjust position for text with smaller offset since logo is smaller
            if logo_height > 0:
                logger.debug(f"Adjusting y_position for smaller logo")
                y_position = logo_y - logo_height - 5  # Reduced padding after logo from 20 to 10
            else:
                logger.warning("No logo was drawn, continuing with original y_position")

        except Exception as e:
            logger.error("Error in main PDF generation:", exc_info=True)
            raise

        # Line 1: Hijri Date and Hotel Name
        # Hijri Date
        c.drawString(50, y_position, "Hijri Date:")
        c.drawString(150, y_position, f"{hijri_date}")  # Replace with the actual Hijri date variable
        draw_arabic_text(width - 350, y_position, "التاريخ الهجري:")
        # Hotel Name
        c.drawString(width / 2 + 50, y_position, "Hotel Name:")
        c.drawString(width / 2 + 150, y_position, f"{booking.company_id.name}")  # Replace with the actual booking field
        draw_arabic_text(width - 50, y_position, "اسم الفندق:")
        y_position -= line_height

        # Line 2: Gregorian Date and Address
        # Gregorian Date
        c.drawString(50, y_position, "Gregorian Date:")
        c.drawString(150, y_position, f"{gregorian_date}")  # Replace with the actual Gregorian date variable
        draw_arabic_text(width - 350, y_position, "التاريخ الميلادي:")

        c.drawString(width / 2 + 50, y_position, "Address:")
        address = f"{booking.company_id.street}"  # Replace with the actual address field from booking
        wrapped_address = wrap(address, max_address_width)  # Wrap the address text into lines

        # Draw each wrapped line of the address
        line_offset = 0  # To handle multiple lines
        for line in wrapped_address:
            c.drawString(width / 2 + 150, y_position - line_offset, line)  # Adjusted for each line
            line_offset += line_height  # Move down for the next line

        draw_arabic_text(width - 50, y_position, "العنوان:")
        y_position -= (line_offset + (line_height * 0.5))  # Move Y-position based on wrapped lines

        # y_position -= line_height
        # Line 3: User and Tel
        # User
        c.drawString(50, y_position, "User:")
        c.drawString(150, y_position, f"{booking.partner_id.name}")  # Replace with the actual user field if needed
        draw_arabic_text(width - 350, y_position, "اسم المستخدم:")
        # Tel
        c.drawString(width / 2 + 50, y_position, "Tel:")
        c.drawString(width / 2 + 150, y_position,
                     f"{booking.company_id.phone}")  # Replace with the actual booking field
        draw_arabic_text(width - 50, y_position, "تليفون:")
        y_position -= line_height  # Extra spacing after this section
        y_position -= line_height
        # Registration Card Title

        c.drawString(width / 2 - 80, y_position, f"Registration Card #{booking.id}")

        draw_arabic_text(width / 2 + 60, y_position, f"عقد سكني:")
        y_position -= 35

        # if booking.reservation_adult:
        #     first_adult = booking.reservation_adult[0]  # Get the first record
        #     full_name = f"{first_adult.first_name} {first_adult.last_name}"  # Concatenate first and last name
        # else:
        #     full_name = "No Name"  # Default value if no records exist

        # Convert check-in and checkout dates to Hijri

        guest_payment_border_top = y_position + 30

        LEFT_LABEL_X = left_margin
        LEFT_VALUE_X = LEFT_LABEL_X + 80
        LEFT_ARABIC_X = LEFT_VALUE_X + 90

        # Right column starts sooner
        RIGHT_LABEL_X = LEFT_ARABIC_X + 90
        RIGHT_VALUE_X = RIGHT_LABEL_X + 100
        # Keep Arabic close to the value
        RIGHT_ARABIC_X = RIGHT_VALUE_X + 70
        str_checkin_date = booking.checkin_date.strftime('%Y-%m-%d %H:%M:%S') if booking.checkin_date else ""
        str_checkout_date = booking.checkout_date.strftime('%Y-%m-%d %H:%M:%S') if booking.checkout_date else ""
        # line_height = 20
        pax_count = booking.adult_count + booking.child_count + booking.infant_count
        booking_type = "Company" if booking.is_agent else "Individual"
        if booking.use_price or booking.use_meal_price:
            # Determine display codes based on which flags are set
            if booking.use_price:
                display_rate_code = "Manual"
            else:
                display_rate_code = booking.rate_code.description if booking.rate_code else ""

            if booking.use_meal_price:
                display_meal_code = "Manual"
            else:
                display_meal_code = booking.meal_pattern.description if booking.meal_pattern else ""

            # Calculate Room Discount if use_price is selected
            if booking.use_price:
                if booking.room_is_amount:
                    room_discount = f"{booking.room_discount} SAR"  # Adjust currency as needed
                elif booking.room_is_percentage:
                    room_discount = f"{booking.room_discount * 100}%"
                else:
                    room_discount = 'N/A'  # Or any default value you prefer
            else:
                room_discount = ""  # No discount to display if use_price is not selected

            # Calculate Meal Discount if use_meal_price is selected
            if booking.use_meal_price:
                if booking.meal_is_amount:
                    meal_discount = f"{booking.meal_discount} SAR"  # Adjust currency as needed
                elif booking.meal_is_percentage:
                    meal_discount = f"{booking.meal_discount * 100}%"
                else:
                    meal_discount = 'N/A'  # Or any default value you prefer
            else:
                meal_discount = ""  # No discount to display if use_meal_price is not selected

        else:
            # Neither use_price nor use_meal_price is selected
            display_rate_code = booking.rate_code.description if booking.rate_code else ""
            display_meal_code = booking.meal_pattern.description if booking.meal_pattern else ""
            room_discount = ""
            meal_discount = ""

        # Guest Details: Add all fields dynamically
        guest_details = [
            ("Arrival Date:", f"{str_checkin_date}", "تاريخ الوصول:", "Full Name:", f"{booking.partner_id.name}",
             "الاسم الكامل:"),
            ("Departure Date:", f"{str_checkout_date}", "تاريخ المغادرة:", "Company:", booking_type, "ﺷَﺮِﻛَﺔ:"),
            ("Arrival (Hijri):", checkin_hijri_str, "تاريخ الوصول (هجري):", "Nationality:",
             f"{booking.partner_id.nationality.name or 'N/A'}", "الجنسية:"),
            ("Departure (Hijri):", checkout_hijri_str, "تاريخ المغادرة (هجري):", "Mobile No:",
             f"{booking.partner_id.mobile or 'N/A'}", "رقم الجوال:"),
            ("No. of Nights:", f"{booking.no_of_nights}", "عدد الليالي:", "Passport No:", "", "رقم جواز السفر:"),
            ("Room Number:", f"{booking.room_ids_display}", "رقم الغرفة:", "ID No:", "", "رقم الهوية:"),
            ("Room Type:", f"{booking.room_type_display}", "نوع الغرفة:", "No. of pax:", f"{booking.adult_count}",
             "عدد الأشخاص:"),
            ("Rate Code:", f"{display_rate_code}", "رمز السعر:", "No.of child:",
             f"{booking.child_count}", "عدد الأشخاص:"),
            ("Meal Plan:", f"{display_meal_code}", "نظام الوجبات:", "No. of infants:",
             f"{booking.infant_count}", "عدد الرضع:"),
            ("Room Disc:", f"{room_discount}", "خصم الغرفة:", "Meal Disc:", f"{meal_discount}", "خصم الوجبة:"),
        ]

        # Iterate through guest details and draw strings
        for l_label, l_value, l_arabic, r_label, r_value, r_arabic in guest_details:
            # Left column
            c.drawString(LEFT_LABEL_X, y_position, l_label)
            c.drawString(LEFT_VALUE_X, y_position, l_value)
            draw_arabic_text(LEFT_ARABIC_X, y_position, l_arabic)

            # Right column
            c.drawString(RIGHT_LABEL_X, y_position, r_label)
            c.drawString(RIGHT_VALUE_X, y_position, r_value)
            draw_arabic_text(RIGHT_ARABIC_X, y_position, r_arabic)

            y_position -= line_height

        avg_rate = 0.0
        avg_meals = 0.0
        if forecast_lines:
            total_rate = sum(line.rate for line in forecast_lines)
            total_meals = sum(line.meals for line in forecast_lines)
            line_count = len(forecast_lines)
            if line_count > 0:
                avg_rate = round(total_rate / line_count, 2)
                avg_meals = round(total_meals / line_count, 2)
        pay_type = dict(booking.fields_get()['payment_type']['selection']).get(booking.payment_type, "")
        # Payment Details
        payment_details = [
            ("Payment Method:", f"{pay_type}", "نظام الدفع:", "Room Rate(Avg):", f"{avg_rate}",
             "السعر اليومي للغرفة:"),
            ("VAT:", "", "القيمة المضافة:", "Meals Rate(Avg):", f"{avg_meals}", "سعر الوجبات اليومي:"),
            ("Municipality:", "", "رسوم البلدية:", "Total Fixed Post:", f"{booking.total_fixed_post_forecast}",
             "إجمالي المشاركات الثابتة:"),
            ("Total Taxes:", "", "إجمالي الضرائب:", "Total Packages:", f"{booking.total_package_forecast}",
             "إجمالي الحزم:"),
            ("VAT ID:", "", "الرقم الضريبي:", "Remaining:", "", "المبلغ المتبقي:"),
            ("Payments:", "", "المدفوعات:", "Total Amount:", f"{booking.total_total_forecast}", "المبلغ الإجمالي:")
        ]

        for l_label, l_value, l_arabic, r_label, r_value, r_arabic in payment_details:
            # Left column
            c.drawString(LEFT_LABEL_X, y_position, l_label)
            c.drawString(LEFT_VALUE_X, y_position, l_value)
            draw_arabic_text(LEFT_ARABIC_X, y_position, l_arabic)

            # Right column
            c.drawString(RIGHT_LABEL_X, y_position, r_label)
            c.drawString(RIGHT_VALUE_X, y_position, r_value)
            draw_arabic_text(RIGHT_ARABIC_X, y_position, r_arabic)

            y_position -= line_height

        guest_payment_border_bottom = y_position - 20  # A little extra space below
        # Draw the border for Guest + Payment details
        c.rect(
            left_margin - 10,
            guest_payment_border_bottom,
            (width - left_margin - right_margin) + 20,
            guest_payment_border_top - guest_payment_border_bottom
        )
        y_position -= 40

        table_top = y_position

        # Table Headers (Combined English and Arabic Labels)
        table_headers = [
            ("Nationality", "الجنسية"),
            ("Passport No.", "رقم جواز السفر"),
            ("Tel No.", "رقم الهاتف"),
            ("ID No.", "رقم الهوية"),
            ("Joiner Name", "اسم المرافق"),
        ]

        # Basic sizing (same as before)
        table_left_x = left_margin - 10
        table_width = (width - left_margin - right_margin) + 20

        # Header & body row heights
        header_height = 25
        row_height = 20
        font_size = 8
        c.setFont(font_name, font_size)

        adult_records = list(booking.adult_ids)
        child_records = list(booking.child_ids)
        infant_records = list(booking.infant_ids)
        adult_child_records = adult_records + child_records + infant_records

        # Number of rows = booking.adult_count or 0
        num_rows = len(adult_child_records)

        # 1) Calculate total table height (header + rows)
        table_height = header_height + (row_height * num_rows)

        # 2) Draw one big outer rectangle for the entire table
        c.rect(
            table_left_x,
            table_top - table_height,
            table_width,
            table_height
        )

        # 3) Draw horizontal lines
        #    Top/bottom lines are from c.rect(), so we just add the
        #    interior horizontal line below the header, plus one line per row.

        header_bottom = table_top - header_height
        # Line below header
        c.line(table_left_x, header_bottom, table_left_x + table_width, header_bottom)

        current_y = header_bottom
        # One line per body row
        for i in range(num_rows):
            current_y -= row_height
            c.line(table_left_x, current_y, table_left_x + table_width, current_y)

        # 4) Draw vertical column lines (so they span from table_top down to table_top - table_height)
        num_cols = len(table_headers)
        col_width = table_width / num_cols

        x_cursor = table_left_x
        for col_index in range(num_cols + 1):  # +1 to include the far-right edge
            c.line(x_cursor, table_top, x_cursor, table_top - table_height)
            x_cursor += col_width

        # 5) Write the header text inside the header row
        text_y = table_top - header_height + 8  # small padding inside header
        x_cursor = table_left_x

        for eng_label, ar_label in table_headers:
            # English left
            c.drawString(x_cursor + 3, text_y, eng_label)
            # Arabic right
            reshaped_ar = arabic_reshaper.reshape(ar_label)
            bidi_ar = get_display(reshaped_ar)
            c.drawRightString(x_cursor + col_width - 3, text_y, bidi_ar)
            x_cursor += col_width

        # 6) Optionally, write data inside the body rows
        #    (If you have actual row data, loop over each row/column and place text)
        current_y = header_bottom
        for person in adult_child_records:
            row_bottom = current_y - row_height
            x_cursor = table_left_x

            # We assume each 'person' (adult or child) has:
            #   nationality: Many2one to a country, or similar
            #   passport_no: Char
            #   mobile or phone: Char
            #   id_no: Char
            #   joiner_name: Char
            # Adapt if your child model fields differ!
            nationality_name = ""
            if getattr(person, 'nationality', False):
                nationality_name = person.nationality.name or ""

            passport_no = getattr(person, 'passport_number', "") or ""
            # If you store phone in "mobile" or "phone" (pick whichever is correct):
            tel_no = getattr(person, 'mobile', "") or getattr(person, 'phone_number', "") or 'N/A'
            id_no = getattr(person, 'id_number', "") or 'N/A'
            joiner_name = f"{getattr(person, 'first_name', '')} {getattr(person, 'last_name', '')}".strip()

            row_cells = [
                nationality_name,
                passport_no,
                tel_no,
                id_no,
                joiner_name,
            ]
            # print(row_cells, ' row cells')
            for cell_text in row_cells:
                cell_text = str(cell_text) if cell_text is not None else ""
                adjustment = 2  # experiment with 1, 2, 3, etc.
                c.drawCentredString(
                    x_cursor + (col_width / 2),
                    row_bottom + (row_height / 2) - adjustment,
                    cell_text
                )
                x_cursor += col_width

            current_y -= row_height

        # Finally, update y_position if needed for subsequent sections
        y_position = table_top - table_height - 20

        # If num_rows > 0, we have multiple rectangles stacked below the header
        # If num_rows == 0, we only have the header rectangle

        # Adjust y_position for Terms and Conditions section
        y_position -= 60
        c, y_position = check_space_and_new_page(
            c=c,
            needed_height=200,  # approximate space for T&C
            y_position=y_position,
            bottom_margin=bottom_margin,
            top_margin=top_margin,
            page_width=width,
            page_height=height,
            font_name=font_name,
            font_size=8
        )
        terms_top = y_position
        y_position -= 20

        terms = [
            "Terms:",
            "Departure at 2:00 PM, in case of late checkout, full day rate will be charged.",
            "Guests should notify front desk in case of extension or early checkout.",
            "Refund is not applicable after 30 minutes from signing RC.",
            "Administration is not responsible for lost valuables inside the room.",
            "In case of damage, appropriate compensation will be charged.",
            "In the event of absence, belongings will be moved to the warehouse.",
            "Commitment to Islamic instructions and not to disturb others."
        ]
        arabic_terms = [
            "شروط:",
            "موعد المغادرة في تمام الساعة الثانية ظهراً، في حال تأخير المغادرة سيتم احتساب رسوم يوم كامل.",
            "يجب على النزلاء إبلاغ مكتب الاستقبال في حال تمديد الإقامة أو المغادرة المبكرة.",
            "لا يحق للنزيل استرداد أي مبلغ بعد 30 دقيقة من توقيع العقد.",
            "الإدارة غير مسؤولة عن فقدان الأشياء الثمينة داخل الغرفة.",
            "في حال حدوث أي ضرر، سيتم فرض تعويض مناسب.",
            "في حالة الغياب، سيتم نقل المتعلقات إلى المستودع.",
            "الالتزام بالتعليمات الإسلامية وعدم إزعاج الآخرين."
        ]

        # Wrap text to fit within the defined width
        max_width = 60  # Max characters per line for English
        max_width_arabic = 60  # Adjust for Arabic wrapping

        for eng_term, ar_term in zip(terms, arabic_terms):
            # Wrap the English and Arabic text into multiple lines
            eng_lines = wrap(eng_term, max_width)
            ar_lines = wrap(ar_term, max_width_arabic)

            # Ensure both English and Arabic text have the same number of lines
            max_lines = max(len(eng_lines), len(ar_lines))
            eng_lines += [""] * (max_lines - len(eng_lines))  # Pad English lines
            ar_lines += [""] * (max_lines - len(ar_lines))  # Pad Arabic lines

            # Draw each line
            for eng_line, ar_line in zip(eng_lines, ar_lines):
                c.drawString(50, y_position, eng_line)  # English text on the left
                draw_arabic_text(width - 250, y_position, ar_line)  # Arabic text on the right
                y_position -= 15  # Adjust line spacing

        # Draw Border Around Terms and Conditions Section
        terms_bottom = y_position - 10
        c.rect(
            left_margin - 10,
            terms_bottom,
            (width - left_margin - right_margin) + 20,
            terms_top - terms_bottom + 20
        )

        # Save the PDF
        c.save()
        buffer.seek(0)
        return buffer

    @http.route('/generate_rc_guest/bookings_pdf', type='http', auth='user')
    def generate_rc_guest_bookings_pdf(self, booking_ids=None):
        if not booking_ids:
            return request.not_found()

        booking_ids = [int(id) for id in booking_ids.split(',')]

        # If there's only one booking, return a single PDF
        if len(booking_ids) == 1:
            booking = request.env['room.booking'].browse(booking_ids[0])
            if not booking.exists():
                return request.not_found()
            pdf_buffer = self._generate_rc_guest_pdf_for_booking(booking)
            return request.make_response(pdf_buffer.getvalue(), headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition',
                 f'attachment; filename="booking Rc guest_{booking.group_booking.name or ""}.pdf"')
            ])

        # If multiple bookings, create a ZIP file
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            for booking_id in booking_ids:
                booking = request.env['room.booking'].browse(booking_id)
                if not booking.exists():
                    continue
                # forecast_lines = request.env['room.rate.forecast'].search([
                #     ('room_booking_id', '=', booking.id)
                # ])
                print("this booking called", booking)
                pdf_buffer = self._generate_rc_guest_pdf_for_booking(booking)
                pdf_filename = f'booking_Rc_guest_group_{booking.group_booking.name}.pdf'
                zip_file.writestr(pdf_filename, pdf_buffer.getvalue())

        zip_buffer.seek(0)
        return request.make_response(zip_buffer.getvalue(), headers=[
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', 'attachment; filename="bookings.zip"')
        ])

    def _generate_rc_guest_pdf_for_booking(self, booking, forecast_lines=None):

        if forecast_lines is None:
            # fetch them here or set them to an empty list
            forecast_lines = request.env["room.rate.forecast"].search([
                ("room_booking_id", "=", booking.id)
            ])
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        left_margin = 40
        right_margin = 40
        top_margin = 50
        bottom_margin = 50
        line_height = 15
        y_position = height - top_margin

        # Register a font that supports Arabic
        if platform.system() == "Windows":
            font_path = "C:/Windows/Fonts/arial.ttf"
        else:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Or "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf"

            # Register the font
        try:
            pdfmetrics.registerFont(TTFont('CustomFont', font_path))
            font_name = 'CustomFont'
        except Exception as e:
            print(f"Font registration failed: {e}")
            font_name = 'Helvetica'  # Fallback font

        c.setFont(font_name, 8)  # Ensure this path is correct for your system
        # pdfmetrics.registerFont(TTFont('Arial', font_path))
        # c.setFont('Arial', 12)

        current_date = datetime.now()
        gregorian_date = current_date.strftime('%Y-%m-%d')
        hijri_date = convert.Gregorian(current_date.year, current_date.month, current_date.day).to_hijri()
        # Define the number of rows based on the number of pax
        num_rows = booking.adult_count if booking.adult_count else 0  # Default to 1 row if pax is not defined
        checkin_hijri_str = ""

        if booking.checkin_date:
            g_date_in = convert.Gregorian(
                booking.checkin_date.year,
                booking.checkin_date.month,
                booking.checkin_date.day
            )
        # Convert to Hijri and cast to string (e.g., '1445-10-05')
        arrival_hijri = g_date_in.to_hijri()
        checkin_hijri_str = str(arrival_hijri)  # or arrival_hijri.isoformat() if you want a standard format

        checkout_hijri_str = ""
        if booking.checkout_date:
            g_date_out = convert.Gregorian(
                booking.checkout_date.year,
                booking.checkout_date.month,
                booking.checkout_date.day
            )
        departure_hijri = g_date_out.to_hijri()
        checkout_hijri_str = str(departure_hijri)
        # arrival_hijri = convert_to_hijri(booking.checkin_date)
        # departure_hijri = convert_to_hijri(booking.checkout_date)
        max_address_width = 18

        # active_user = self.env.user

        # Function to draw Arabic text
        def draw_arabic_text(x, y, text):
            if text:
                reshaped_text = arabic_reshaper.reshape(text)  # Fix Arabic letter shapes
                bidi_text = get_display(reshaped_text)  # Fix RTL direction
                c.drawString(x, y, bidi_text)
            else:
                c.drawString(x, y, "")  # Draw empty string if the text is None

        y_position = height - 50  # Starting Y position
        line_height = 15  # Line height for vertical spacing

        def draw_company_logo(c, x, y, max_width, max_height, logo_data):
            """Draw company logo from Odoo binary field data"""
            try:
                logger.debug("Attempting to draw company logo from binary data")

                # Check if logo data exists
                if not logo_data:
                    logger.warning("No logo data found in company record")
                    return 0

                # Decode base64 logo data
                try:
                    logo_binary = base64.b64decode(logo_data)
                    logo_stream = io.BytesIO(logo_binary)
                    logger.debug("Successfully decoded logo binary data")

                    # Use PIL to open and identify the image
                    with PILImage.open(logo_stream) as img:
                        img_format = img.format.lower()
                        logger.debug(f"Detected image format: {img_format}")

                        # Create a new BytesIO for the image with proper format
                        final_image = io.BytesIO()
                        if img_format != 'png':  # Convert to PNG if it's not already
                            img = img.convert('RGBA')
                        img.save(final_image, format='PNG')
                        final_image.seek(0)

                        # Get image dimensions
                        img_width, img_height = img.size
                        logger.debug(f"Original image dimensions - Width: {img_width}, Height: {img_height}")

                except Exception as e:
                    logger.error(f"Error processing logo data: {str(e)}")
                    return 0

                # Calculate aspect ratio
                aspect = img_width / float(img_height)
                logger.debug(f"Image aspect ratio: {aspect}")

                # Calculate new dimensions
                if img_width > max_width:
                    new_width = max_width
                    new_height = new_width / aspect
                    if new_height > max_height:
                        new_height = max_height
                        new_width = new_height * aspect
                elif img_height > max_height:
                    new_height = max_height
                    new_width = new_height * aspect
                else:
                    new_width = img_width
                    new_height = img_height

                logger.debug(f"Final image dimensions - Width: {new_width}, Height: {new_height}")

                # Create temp file path based on OS
                if os.name == 'nt':  # Windows
                    temp_image_path = os.path.join(os.environ['TEMP'], 'temp_logo.png')
                else:  # Linux/Unix
                    temp_image_path = '/tmp/temp_logo.png'

                try:
                    with open(temp_image_path, 'wb') as temp_file:
                        temp_file.write(final_image.getvalue())

                    # Draw the image using the temporary file
                    c.drawImage(temp_image_path, x, y, width=new_width, height=new_height)
                    logger.info(
                        f"Successfully drew logo at position ({x}, {y}) with dimensions {new_width}x{new_height}")

                    # Clean up the temporary file
                    if os.path.exists(temp_image_path):
                        os.remove(temp_image_path)
                        logger.debug("Temporary logo file removed")

                except Exception as e:
                    logger.error(f"Error drawing image: {str(e)}")
                    if os.path.exists(temp_image_path):
                        try:
                            os.remove(temp_image_path)
                            logger.debug("Cleaned up temporary file after error")
                        except:
                            pass
                    return 0

                return new_height

            except Exception as e:
                logger.error(f"Error drawing logo: {str(e)}", exc_info=True)
                return 0

        # Main PDF generation code
        try:
            y_position = height
            line_height = 15

            # Get logo directly from company_id.logo field
            logo_data = booking.company_id.logo
            logger.info(f"Company ID: {booking.company_id.id}")
            logger.info(f"Company Name: {booking.company_id.name}")
            logger.debug("Retrieved logo data from company record")

            # Adjusted smaller logo dimensions for icon-like appearance
            logo_max_width = 60  # Reduced from 150 to 60
            logo_max_height = 60  # Made square for icon-like appearance

            # Center the logo horizontally and place it at the top with some padding
            logo_x = 20  # Center horizontally
            logo_y = height - 50  # Place near top with 70px padding

            # Draw logo
            logger.debug("Starting logo drawing process")
            logo_height = draw_company_logo(c, logo_x, logo_y, logo_max_width, logo_max_height, logo_data)
            logger.debug(f"Returned logo height: {logo_height}")

            # Adjust position for text with smaller offset since logo is smaller
            if logo_height > 0:
                logger.debug(f"Adjusting y_position for smaller logo")
                y_position = logo_y - logo_height - 5  # Reduced padding after logo from 20 to 10
            else:
                logger.warning("No logo was drawn, continuing with original y_position")

        except Exception as e:
            logger.error("Error in main PDF generation:", exc_info=True)
            raise

        # Line 1: Hijri Date and Hotel Name
        # Hijri Date
        c.drawString(50, y_position, "Hijri Date:")
        c.drawString(150, y_position, f"{hijri_date}")  # Replace with the actual Hijri date variable
        draw_arabic_text(width - 350, y_position, "التاريخ الهجري:")
        # Hotel Name
        c.drawString(width / 2 + 50, y_position, "Hotel Name:")
        c.drawString(width / 2 + 150, y_position, f"{booking.company_id.name}")  # Replace with the actual booking field
        draw_arabic_text(width - 50, y_position, "اسم الفندق:")
        y_position -= line_height

        # Line 2: Gregorian Date and Address
        # Gregorian Date
        c.drawString(50, y_position, "Gregorian Date:")
        c.drawString(150, y_position, f"{gregorian_date}")  # Replace with the actual Gregorian date variable
        draw_arabic_text(width - 350, y_position, "التاريخ الميلادي:")

        c.drawString(width / 2 + 50, y_position, "Address:")
        address = f"{booking.company_id.street}"  # Replace with the actual address field from booking
        wrapped_address = wrap(address, max_address_width)  # Wrap the address text into lines

        # Draw each wrapped line of the address
        line_offset = 0  # To handle multiple lines
        for line in wrapped_address:
            c.drawString(width / 2 + 150, y_position - line_offset, line)  # Adjusted for each line
            line_offset += line_height  # Move down for the next line

        draw_arabic_text(width - 50, y_position, "العنوان:")
        y_position -= (line_offset + (line_height * 0.5))  # Move Y-position based on wrapped lines

        # y_position -= line_height
        # Line 3: User and Tel
        # User
        c.drawString(50, y_position, "User:")
        c.drawString(150, y_position, f"{booking.partner_id.name}")  # Replace with the actual user field if needed
        draw_arabic_text(width - 350, y_position, "اسم المستخدم:")
        # Tel
        c.drawString(width / 2 + 50, y_position, "Tel:")
        c.drawString(width / 2 + 150, y_position,
                     f"{booking.company_id.phone}")  # Replace with the actual booking field
        draw_arabic_text(width - 50, y_position, "تليفون:")
        y_position -= line_height  # Extra spacing after this section
        y_position -= line_height
        # Registration Card Title

        c.drawString(width / 2 - 200, y_position, f"Group Booking/Registration Card -{booking.group_booking.name}")

        draw_arabic_text(width / 2 + 60, y_position, f"حجز جماعي /بطاقة التسجيل - {booking.group_booking.name}")
        y_position -= 35

        # if booking.reservation_adult:
        #     first_adult = booking.reservation_adult[0]  # Get the first record
        #     full_name = f"{first_adult.first_name} {first_adult.last_name}"  # Concatenate first and last name
        # else:
        #     full_name = "No Name"  # Default value if no records exist

        # Convert check-in and checkout dates to Hijri

        guest_payment_border_top = y_position + 30

        LEFT_LABEL_X = left_margin
        LEFT_VALUE_X = LEFT_LABEL_X + 100
        LEFT_ARABIC_X = LEFT_VALUE_X + 100

        # Right column starts sooner
        RIGHT_LABEL_X = LEFT_ARABIC_X + 90
        RIGHT_VALUE_X = RIGHT_LABEL_X + 90
        # Keep Arabic close to the value
        RIGHT_ARABIC_X = RIGHT_VALUE_X + 70
        str_checkin_date = booking.checkin_date.strftime('%Y-%m-%d %H:%M:%S') if booking.checkin_date else ""
        str_checkout_date = booking.checkout_date.strftime('%Y-%m-%d %H:%M:%S') if booking.checkout_date else ""
        # line_height = 20
        pax_count = booking.adult_count  # + booking.child_count
        booking_type = "Company" if booking.is_agent else "Individual"
        group_booking_id = booking.group_booking.id
        group_bookings = request.env['room.booking'].search([('group_booking', '=', group_booking_id)])
        print('1977', group_bookings)
        rate_list = []
        meal_list = []
        table_row = []
        person_count = []
        booking_rows = []

        # Initialize a dictionary to group by room_type
        room_type_summary = {}

        for gb in group_bookings:
            # print('2617', gb, gb.rate_forecast_ids)

            # Safely access 'room_type' with a default of 'N/A'
            room_type = getattr(gb.hotel_room_type, 'room_type', 'N/A') if gb.hotel_room_type else 'N/A'

            # Safely access 'room_count' with a default of 0
            room_count = getattr(gb, 'room_count', 0) if gb else 0

            # Safely access 'adult_count', 'child_count', 'infant_count' with defaults of 0
            adult_count = getattr(gb, 'adult_count', 0) if gb else 0
            child_count = getattr(gb, 'child_count', 0) if gb else 0
            infant_count = getattr(gb, 'infant_count', 0) if gb else 0

            # Calculate total count
            total_count = adult_count + child_count + infant_count

            # Add data to room_type_summary
            if room_type in room_type_summary:
                room_type_summary[room_type]['total_count'] += total_count
                room_type_summary[room_type]['room_count'] += room_count
            else:
                room_type_summary[room_type] = {
                    'total_count': total_count,
                    'room_count': room_count
                }

            # Convert the dictionary into a table format
            table_row = []
            for room_type, data in room_type_summary.items():
                table_row.append([
                    room_type,
                    data['room_count'],
                    data['total_count']
                ])

            for rate_detail_line in gb.rate_forecast_ids:
                # print('2174', rate_detail_line, rate_detail_line.rate, rate_detail_line.meals)
                rate_list.append(rate_detail_line.rate)
                meal_list.append(rate_detail_line.meals)
            for adult_line in gb.adult_ids:
                joiner_name = f"{adult_line.first_name or ''} {adult_line.last_name or ''}".strip()
                booking_rows.append([
                    adult_line.nationality.name if adult_line.nationality else "",  # Handle nationality
                    adult_line.passport_number or "",  # Handle blank passport number
                    adult_line.phone_number or "",  # Handle blank phone number
                    adult_line.id_number or "",  # Handle blank ID number
                    joiner_name  # Already handled
                ])

            for child_line in gb.child_ids:
                joiner_name = f"{child_line.first_name or ''} {child_line.last_name or ''}".strip()
                booking_rows.append([
                    child_line.nationality.name if child_line.nationality else "",  # Handle nationality
                    child_line.passport_number or "",  # Handle blank passport number
                    child_line.phone_number or "",  # Handle blank phone number
                    child_line.id_number or "",  # Handle blank ID number
                    joiner_name  # Already handled
                ])

            for infant_line in gb.infant_ids:
                joiner_name = f"{infant_line.first_name or ''} {infant_line.last_name or ''}".strip()
                booking_rows.append([
                    infant_line.nationality.name if infant_line.nationality else "",  # Handle nationality
                    infant_line.passport_number or "",  # Handle blank passport number
                    infant_line.phone_number or "",  # Handle blank phone number
                    infant_line.id_number or "",  # Handle blank ID number
                    joiner_name  # Already handled
                ])

        # booking_data = [adult_row, child_row, infant_row]
        person_count.append(booking_rows)
        avg_rate = sum(rate_list) / len(rate_list)
        avg_rate = round(avg_rate, 2)
        avg_meal = sum(meal_list) / len(meal_list)
        avg_meal = round(avg_meal, 2)
        # print('2185', table_row)
        # print('2185', adult_row)
        # print('2629', person_count)
        if booking.use_price or booking.use_meal_price:
            # Determine display codes based on which flags are set
            if booking.use_price:
                display_rate_code = "Manual"
            else:
                display_rate_code = booking.rate_code.description if booking.rate_code else ""

            if booking.use_meal_price:
                display_meal_code = "Manual"
            else:
                display_meal_code = booking.meal_pattern.description if booking.meal_pattern else ""

            # Calculate Room Discount if use_price is selected
            if booking.use_price:
                if booking.room_is_amount:
                    room_discount = f"{booking.room_discount} SAR"  # Adjust currency as needed
                elif booking.room_is_percentage:
                    room_discount = f"{booking.room_discount * 100}%"
                else:
                    room_discount = 'N/A'  # Or any default value you prefer
            else:
                room_discount = ""  # No discount to display if use_price is not selected

            # Calculate Meal Discount if use_meal_price is selected
            if booking.use_meal_price:
                if booking.meal_is_amount:
                    meal_discount = f"{booking.meal_discount} SAR"  # Adjust currency as needed
                elif booking.meal_is_percentage:
                    meal_discount = f"{booking.meal_discount * 100}%"
                else:
                    meal_discount = 'N/A'  # Or any default value you prefer
            else:
                meal_discount = ""  # No discount to display if use_meal_price is not selected

        else:
            # Neither use_price nor use_meal_price is selected
            display_rate_code = booking.rate_code.description if booking.rate_code else ""
            display_meal_code = booking.meal_pattern.description if booking.meal_pattern else ""
            room_discount = ""
            meal_discount = ""

        # Guest Details: Add all fields dynamically
        guest_details = [
            ("Arrival Date:", f"{str_checkin_date}", "تاريخ الوصول:", "Full Name:", f"{booking.partner_id.name}",
             "الاسم الكامل:"),
            ("Departure Date:", f"{str_checkout_date}", "تاريخ المغادرة:", "Company:", booking_type, "ﺷَﺮِﻛَﺔ:"),
            ("Arrival (Hijri):", checkin_hijri_str, "تاريخ الوصول (هجري):", "Nationality:",
             f"{booking.partner_id.nationality.name or 'N/A'}", "الجنسية:"),
            ("Departure (Hijri):", checkout_hijri_str, "تاريخ المغادرة (هجري):", "Mobile No:",
             f"{booking.partner_id.mobile or 'N/A'}", "رقم الجوال:"),

            ("Rate Code:", f"{display_rate_code}", "رمز السعر:", "No. of child:",
             f"{booking.child_count}", "عدد الأشخاص:"),
            ("Meal Plan:", f"{display_meal_code}", "نظام الوجبات:", "No. of infants:",
             f"{booking.infant_count}", "عدد الرضع:"),
            ("Room Disc Avg:", f"{avg_rate}", "خصم الغرفة:", "Meal Disc Avg:", f"{avg_meal}", "خصم الوجبة:"),
            ("Room Disc Min:", f"{min(rate_list)}", "خصم الغرفة الأدنى:", "Meal Disc Min:", f"{min(meal_list)}",
             "خصم الوجبة الأدنى:"),
            ("Room Disc Max:", f"{max(rate_list)}", "خصم الغرفة الأعلى:", "Meal Disc Max:", f"{max(meal_list)}",
             "خصم الوجبة الأعلى:"),

        ]

        # Iterate through guest details and draw strings
        for l_label, l_value, l_arabic, r_label, r_value, r_arabic in guest_details:
            # Left column
            c.drawString(LEFT_LABEL_X, y_position, l_label)
            c.drawString(LEFT_VALUE_X, y_position, l_value)
            draw_arabic_text(LEFT_ARABIC_X, y_position, l_arabic)

            # Right column
            c.drawString(RIGHT_LABEL_X, y_position, r_label)
            c.drawString(RIGHT_VALUE_X, y_position, r_value)
            draw_arabic_text(RIGHT_ARABIC_X, y_position, r_arabic)

            y_position -= line_height

        avg_rate = 0.0
        avg_meals = 0.0
        if forecast_lines:
            total_rate = sum(line.rate for line in forecast_lines)
            total_meals = sum(line.meals for line in forecast_lines)
            line_count = len(forecast_lines)
            if line_count > 0:
                avg_rate = round(total_rate / line_count, 2)
                avg_meals = round(total_meals / line_count, 2)
        pay_type = dict(booking.fields_get()['payment_type']['selection']).get(booking.payment_type, "")
        # Payment Details
        payment_details = [
            ("VAT:", "", "القيمة المضافة:", "Total Meals Rate:", f"{booking.total_meal_forecast}",
             "إجمالي سعر الوجبات:"),
            ("Municipality:", "", "رسوم البلدية:", "Total Room rate:", f"{booking.total_rate_forecast}",
             "إجمالي سعر الغرفة:"),
            ("Total Taxes:", "", "إجمالي الضرائب:", "Total Fixed Post:", f"{booking.total_fixed_post_forecast}",
             "إجمالي المشاركات الثابتة:"),
            ("VAT ID:", "", "الرقم الضريبي:", "Total Packages:", f"{booking.total_package_forecast}", "إجمالي الحزم:"),
            ("Remaining:", "", "المبلغ المتبقي:", "Payments:", "", "المدفوعات:"),
            ("Payment Method:", f"{pay_type}", "نظام الدفع:", "Total Amount:", f"{booking.total_total_forecast}",
             "المبلغ الإجمالي:")

        ]

        for l_label, l_value, l_arabic, r_label, r_value, r_arabic in payment_details:
            # Adjust English label and value positioning
            c.drawString(LEFT_LABEL_X, y_position, f"{l_label}")
            c.drawString(LEFT_LABEL_X + 100, y_position, f"{l_value}")  # Add spacing (adjust 150 as needed)

            # Draw Arabic label and value
            draw_arabic_text(LEFT_ARABIC_X, y_position, l_arabic)

            c.drawString(RIGHT_LABEL_X, y_position, f"{r_label}")
            c.drawString(RIGHT_LABEL_X + 90, y_position, f"{r_value}")  # Add spacing (adjust 150 as needed)

            draw_arabic_text(RIGHT_ARABIC_X, y_position, r_arabic)

            y_position -= line_height  # Move to the next line

        guest_payment_border_bottom = y_position - 20  # A little extra space below
        # Draw the border for Guest + Payment details
        c.rect(
            left_margin - 10,
            guest_payment_border_bottom,
            (width - left_margin - right_margin) + 20,
            guest_payment_border_top - guest_payment_border_bottom
        )
        y_position -= 40
        table_width = (width - left_margin - right_margin) + 20  # Adjust table width as needed
        x_left = (width - table_width) / 2

        table_top = y_position
        table_headers_1 = [
            ("Room Type", "نوع الغرفة"),
            ("Room Count", "عدد الغرف"),
            ("Number of pax", "عدد باكس"),
        ]

        row_data_list_1 = table_row
        # Move y_position below first table
        # y_position = table_top - table_height - 20
        # First table drawing
        row_height = 20
        table_left_x = left_margin  # Adjust as needed
        number_of_columns = 5  # Example value; set based on your table
        col_width = (width - left_margin - right_margin) / number_of_columns
        y_position = draw_table_with_page_break(
            c=c,
            x_left=x_left,
            y_top=y_position,
            table_width=(width - left_margin - right_margin) + 20,
            header_height=25,
            row_height=20,
            table_headers=table_headers_1,
            row_data_list=row_data_list_1,
            line_height=line_height,
            bottom_margin=bottom_margin,
            top_margin=top_margin,
            page_width=width,
            page_height=height,
            font_name=font_name,
            font_size=8
        )

        c, y_position = check_space_and_new_page(
            c=c,
            needed_height=200,  # approximate space for T&C
            y_position=y_position,
            bottom_margin=bottom_margin,
            top_margin=top_margin,
            page_width=width,
            page_height=height,
            font_name=font_name,
            font_size=8
        )
        # Initialize current_y
        current_y = y_position

        y_position = current_y
        adult_child_data = booking_rows

        table_headers_2 = [
            ("Nationality", "الجنسية"),
            ("Passport No.", "رقم جواز السفر"),
            ("Tel No.", "رقم الهاتف"),
            ("ID No.", "رقم الهوية"),
            ("Joiner Name", "اسم المرافق"),
        ]

        # Draw the second table
        y_position = draw_table_with_page_break(
            c=c,
            x_left=x_left,
            y_top=y_position,
            table_width=(width - left_margin - right_margin) + 20,
            header_height=25,
            row_height=20,
            table_headers=table_headers_2,
            row_data_list=adult_child_data,  # entire list, not just one row!
            line_height=line_height,
            bottom_margin=bottom_margin,
            top_margin=top_margin,
            page_width=width,
            page_height=height,
            font_name=font_name,
            font_size=8
        )

        # Adjust y_position for Terms and Conditions section
        y_position -= 60
        c, y_position = check_space_and_new_page(
            c=c,
            needed_height=200,  # approximate space for T&C
            y_position=y_position,
            bottom_margin=bottom_margin,
            top_margin=top_margin,
            page_width=width,
            page_height=height,
            font_name=font_name,
            font_size=8
        )
        terms_top = y_position
        y_position -= 20

        terms = [
            "Terms:",
            "Departure at 2:00 PM, in case of late checkout, full day rate will be charged.",
            "Guests should notify front desk in case of extension or early checkout.",
            "Refund is not applicable after 30 minutes from signing RC.",
            "Administration is not responsible for lost valuables inside the room.",
            "In case of damage, appropriate compensation will be charged.",
            "In the event of absence, belongings will be moved to the warehouse.",
            "Commitment to Islamic instructions and not to disturb others."
        ]
        arabic_terms = [
            "شروط:",
            "موعد المغادرة في تمام الساعة الثانية ظهراً، في حال تأخير المغادرة سيتم احتساب رسوم يوم كامل.",
            "يجب على النزلاء إبلاغ مكتب الاستقبال في حال تمديد الإقامة أو المغادرة المبكرة.",
            "لا يحق للنزيل استرداد أي مبلغ بعد 30 دقيقة من توقيع العقد.",
            "الإدارة غير مسؤولة عن فقدان الأشياء الثمينة داخل الغرفة.",
            "في حال حدوث أي ضرر، سيتم فرض تعويض مناسب.",
            "في حالة الغياب، سيتم نقل المتعلقات إلى المستودع.",
            "الالتزام بالتعليمات الإسلامية وعدم إزعاج الآخرين."
        ]

        # Wrap text to fit within the defined width
        max_width = 60  # Max characters per line for English
        max_width_arabic = 60  # Adjust for Arabic wrapping

        for eng_term, ar_term in zip(terms, arabic_terms):
            # Wrap the English and Arabic text into multiple lines
            eng_lines = wrap(eng_term, max_width)
            ar_lines = wrap(ar_term, max_width_arabic)

            # Ensure both English and Arabic text have the same number of lines
            max_lines = max(len(eng_lines), len(ar_lines))
            eng_lines += [""] * (max_lines - len(eng_lines))  # Pad English lines
            ar_lines += [""] * (max_lines - len(ar_lines))  # Pad Arabic lines

            # Draw each line
            for eng_line, ar_line in zip(eng_lines, ar_lines):
                c.drawString(50, y_position, eng_line)  # English text on the left
                draw_arabic_text(width - 250, y_position, ar_line)  # Arabic text on the right
                y_position -= 15  # Adjust line spacing

        # Draw Border Around Terms and Conditions Section
        terms_bottom = y_position - 10
        c.rect(
            left_margin - 10,
            terms_bottom,
            (width - left_margin - right_margin) + 20,
            terms_top - terms_bottom + 20
        )

        # Save the PDF
        c.save()
        buffer.seek(0)
        return buffer

    @http.route('/generate_rc/bookings_pdf', type='http', auth='user')
    def generate_rc_bookings_pdf(self, booking_ids=None):
        if not booking_ids:
            return request.not_found()

        booking_ids = [int(id) for id in booking_ids.split(',')]

        # If there's only one booking, return a single PDF
        if len(booking_ids) == 1:
            booking = request.env['group.booking'].browse(booking_ids[0])
            if not booking.exists():
                return request.not_found()
            pdf_buffer = self._generate_rc_pdf_for_booking(booking)
            return request.make_response(pdf_buffer.getvalue(), headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="booking Rc_{booking.name or ""}.pdf"')
            ])

        # If multiple bookings, create a ZIP file
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            for booking_id in booking_ids:
                booking = request.env['group.booking'].browse(booking_id)
                if not booking.exists():
                    continue
                # forecast_lines = request.env['room.rate.forecast'].search([
                #     ('room_booking_id', '=', booking.id)
                # ])
                print("this booking called", booking)
                pdf_buffer = self._generate_rc_pdf_for_booking(booking)
                pdf_filename = f'booking_Rc{booking.name}.pdf'
                zip_file.writestr(pdf_filename, pdf_buffer.getvalue())

        zip_buffer.seek(0)
        return request.make_response(zip_buffer.getvalue(), headers=[
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', 'attachment; filename="bookings.zip"')
        ])

    def _generate_rc_pdf_for_booking(self, booking, forecast_lines=None):

        if forecast_lines is None:
            # fetch them here or set them to an empty list
            forecast_lines = request.env["room.rate.forecast"].search([
                ("room_booking_id", "=", booking.id)
            ])
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        left_margin = 40
        right_margin = 40
        top_margin = 50
        bottom_margin = 50

        # Register a font that supports Arabic
        if platform.system() == "Windows":
            font_path = "C:/Windows/Fonts/arial.ttf"
        else:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Or "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf"

            # Register the font
        try:
            pdfmetrics.registerFont(TTFont('CustomFont', font_path))
            font_name = 'CustomFont'
        except Exception as e:
            print(f"Font registration failed: {e}")
            font_name = 'Helvetica'  # Fallback font

        c.setFont(font_name, 8)  # Ensure this path is correct for your system
        # pdfmetrics.registerFont(TTFont('Arial', font_path))
        # c.setFont('Arial', 12)

        current_date = datetime.now()
        gregorian_date = current_date.strftime('%Y-%m-%d')
        hijri_date = convert.Gregorian(current_date.year, current_date.month, current_date.day).to_hijri()

        max_address_width = 18

        group_bookings = request.env['room.booking'].search([('group_booking', '=', booking.id)])
        room_types = []
        room_data = {}
        meal_data = {}
        meal_patterns = []

        # Collect data for each room type
        for gb in group_bookings:
            room_type = gb.hotel_room_type.room_type if gb.hotel_room_type else 'N/A'
            if room_type not in room_types:
                room_types.append(room_type)

            if room_type not in room_data:
                room_data[room_type] = {'Rooms': 0, 'PAX': 0, 'Price': 0}
            room_data[room_type]['Rooms'] += gb.room_count or 0
            room_data[room_type]['PAX'] += gb.adult_count or 0
            room_data[room_type]['Price'] += sum(line.rate for line in gb.rate_forecast_ids)

            meal_pattern = gb.meal_pattern.meal_pattern if gb.meal_pattern else 'N/A'
            if meal_pattern not in meal_patterns:
                meal_patterns.append(meal_pattern)  # Append unique meal pattern to the list

            if meal_pattern not in meal_data:
                meal_data[meal_pattern] = {'Meals': 0, 'PAX': 0, 'Price': 0}
            meal_data[meal_pattern]['PAX'] += gb.adult_count or 0
            meal_data[meal_pattern]['Price'] += sum(line.meals for line in gb.rate_forecast_ids)
        print('line 3766', meal_pattern)

        # Prepare headers and data
        # Prepare headers with Arabic translations
        table_headers = ['Room Types'] + room_types + ['غرفة']  # Add Arabic column at the end
        meal_headers = ['Meals'] + meal_patterns + ['وجبة']  # Arabic for "Meals"
        print('line 3722', meal_patterns)

        # Add data rows with Arabic translations
        table_data = [
            ['Rooms'] + [room_data[room_type]['Rooms'] for room_type in room_types] + ['الغرف'],  # Arabic for "Rooms"
            ['PAX'] + [room_data[room_type]['PAX'] for room_type in room_types] + ['عدد الأفراد'],  # Arabic for "PAX"
            ['Price'] + ["{:.2f}".format(room_data[room_type]['Price']) for room_type in room_types] + ['السعر']
            # Arabic for "Price"
        ]
        meal_table_data = [
            ['PAX'] + [meal_data[pattern]['PAX'] for pattern in meal_patterns] + ['عدد الأفراد'],  # Arabic for "PAX"
            ['Price'] + ["{:.2f}".format(meal_data[pattern]['Price']) for pattern in meal_patterns] + ['السعر']
            # Arabic for "Price"
        ]
        print('meal_table_data', meal_table_data)

        avg_rate_report = 0.0
        avg_meals_report = 0.0
        total_rate_report = 0.0
        total_meals_report = 0.0
        total_lines = 0

        total_room_rate = 0.0
        total_meal_rate = 0.0

        if group_bookings:
            # Fetch all bookings with the same group_id
            group_bookings_data = request.env['room.booking'].search([('group_booking', '=', booking.id)])

            for booking_ in group_bookings_data:
                # Collect all room rate forecast lines for the current booking
                room_rate_forecast = request.env["room.rate.forecast"].search([
                    ("room_booking_id", "=", booking_.id)
                ])

                if room_rate_forecast:
                    # Calculate total rate and total meals from room rate forecast lines
                    total_rate = sum(line.rate for line in room_rate_forecast if line.rate)
                    total_meals = sum(line.meals for line in room_rate_forecast if line.meals)
                    line_count = len(room_rate_forecast)

                    total_rate_report += total_rate
                    total_meals_report += total_meals
                    total_lines += line_count

                    # Add total room rate and meal rate
                    total_room_rate += total_rate
                    total_meal_rate += total_meals

            # Ensure total_lines is greater than 0 to avoid division by zero
            if total_lines > 0:
                avg_rate_report = round(total_rate_report / total_lines, 2)
                avg_meals_report = round(total_meals_report / total_lines, 2)

            # Use avg_rate_report and avg_meals_report for the report output
            report_data = {
                'avg_rate': avg_rate_report,
                'avg_meals': avg_meals_report,
                'total_room_rate': total_room_rate,
                'total_meal_rate': total_meal_rate
            }
            print("Report Data:", report_data)

        # active_user = self.env.user

        # Function to draw Arabic text
        def draw_arabic_text(x, y, text):
            if text:
                reshaped_text = arabic_reshaper.reshape(text)  # Fix Arabic letter shapes
                bidi_text = get_display(reshaped_text)  # Fix RTL direction
                c.drawString(x, y, bidi_text)
            else:
                c.drawString(x, y, "")  # Draw empty string if the text is None

        y_position = height - 50  # Starting Y position
        line_height = 15  # Line height for vertical spacing

        def draw_company_logo(c, x, y, max_width, max_height, logo_data):
            """Draw company logo from Odoo binary field data"""
            try:
                logger.debug("Attempting to draw company logo from binary data")

                # Check if logo data exists
                if not logo_data:
                    logger.warning("No logo data found in company record")
                    return 0

                # Decode base64 logo data
                try:
                    logo_binary = base64.b64decode(logo_data)
                    logo_stream = io.BytesIO(logo_binary)
                    logger.debug("Successfully decoded logo binary data")

                    # Use PIL to open and identify the image
                    with PILImage.open(logo_stream) as img:
                        img_format = img.format.lower()
                        logger.debug(f"Detected image format: {img_format}")

                        # Create a new BytesIO for the image with proper format
                        final_image = io.BytesIO()
                        if img_format != 'png':  # Convert to PNG if it's not already
                            img = img.convert('RGBA')
                        img.save(final_image, format='PNG')
                        final_image.seek(0)

                        # Get image dimensions
                        img_width, img_height = img.size
                        logger.debug(f"Original image dimensions - Width: {img_width}, Height: {img_height}")

                except Exception as e:
                    logger.error(f"Error processing logo data: {str(e)}")
                    return 0

                # Calculate aspect ratio
                aspect = img_width / float(img_height)
                logger.debug(f"Image aspect ratio: {aspect}")

                # Calculate new dimensions
                if img_width > max_width:
                    new_width = max_width
                    new_height = new_width / aspect
                    if new_height > max_height:
                        new_height = max_height
                        new_width = new_height * aspect
                elif img_height > max_height:
                    new_height = max_height
                    new_width = new_height * aspect
                else:
                    new_width = img_width
                    new_height = img_height

                logger.debug(f"Final image dimensions - Width: {new_width}, Height: {new_height}")

                # Create temp file path based on OS
                if os.name == 'nt':  # Windows
                    temp_image_path = os.path.join(os.environ['TEMP'], 'temp_logo.png')
                else:  # Linux/Unix
                    temp_image_path = '/tmp/temp_logo.png'

                try:
                    with open(temp_image_path, 'wb') as temp_file:
                        temp_file.write(final_image.getvalue())

                    # Draw the image using the temporary file
                    c.drawImage(temp_image_path, x, y, width=new_width, height=new_height)
                    logger.info(
                        f"Successfully drew logo at position ({x}, {y}) with dimensions {new_width}x{new_height}")

                    # Clean up the temporary file
                    if os.path.exists(temp_image_path):
                        os.remove(temp_image_path)
                        logger.debug("Temporary logo file removed")

                except Exception as e:
                    logger.error(f"Error drawing image: {str(e)}")
                    if os.path.exists(temp_image_path):
                        try:
                            os.remove(temp_image_path)
                            logger.debug("Cleaned up temporary file after error")
                        except:
                            pass
                    return 0

                return new_height

            except Exception as e:
                logger.error(f"Error drawing logo: {str(e)}", exc_info=True)
                return 0

        # Main PDF generation code
        try:
            y_position = height
            line_height = 15

            # Get logo directly from company_id.logo field
            logo_data = booking.company_id.logo
            logger.info(f"Company ID: {booking.company_id.id}")
            logger.info(f"Company Name: {booking.company_id.name}")
            logger.debug("Retrieved logo data from company record")

            # Adjusted smaller logo dimensions for icon-like appearance
            logo_max_width = 60  # Reduced from 150 to 60
            logo_max_height = 60  # Made square for icon-like appearance

            # Center the logo horizontally and place it at the top with some padding
            logo_x = 20
            logo_y = height - 50  # Place near top with 70px padding

            # Draw logo
            logger.debug("Starting logo drawing process")
            logo_height = draw_company_logo(c, logo_x, logo_y, logo_max_width, logo_max_height, logo_data)
            logger.debug(f"Returned logo height: {logo_height}")

            # Adjust position for text with smaller offset since logo is smaller
            if logo_height > 0:
                logger.debug(f"Adjusting y_position for smaller logo")
                y_position = logo_y - logo_height  # Reduced padding after logo from 20 to 10
            else:
                logger.warning("No logo was drawn, continuing with original y_position")

        except Exception as e:
            logger.error("Error in main PDF generation:", exc_info=True)
            raise

        # Line 1: Hijri Date and Hotel Name
        # Hijri Date
        c.drawString(50, y_position, "Hijri Date:")
        c.drawString(150, y_position, f"{hijri_date}")  # Replace with the actual Hijri date variable
        draw_arabic_text(width - 350, y_position, "التاريخ الهجري:")
        # Hotel Name
        c.drawString(width / 2 + 50, y_position, "Hotel Name:")
        c.drawString(width / 2 + 150, y_position, f"{booking.company_id.name}")  # Replace with the actual booking field
        draw_arabic_text(width - 50, y_position, "اسم الفندق:")
        y_position -= line_height

        # Line 2: Gregorian Date and Address
        # Gregorian Date
        c.drawString(50, y_position, "Gregorian Date:")
        c.drawString(150, y_position, f"{gregorian_date}")  # Replace with the actual Gregorian date variable
        draw_arabic_text(width - 350, y_position, "التاريخ الميلادي:")

        c.drawString(width / 2 + 50, y_position, "Address:")
        address = f"{booking.company_id.street}"  # Replace with the actual address field from booking
        wrapped_address = wrap(address, max_address_width)  # Wrap the address text into lines

        # Draw each wrapped line of the address
        line_offset = 0  # To handle multiple lines
        for line in wrapped_address:
            c.drawString(width / 2 + 150, y_position - line_offset, line)  # Adjusted for each line
            line_offset += line_height  # Move down for the next line

        draw_arabic_text(width - 50, y_position, "العنوان:")
        y_position -= (line_offset + (line_height * 0.5))  # Move Y-position based on wrapped lines

        # y_position -= line_height
        # Line 3: User and Tel
        # User
        c.drawString(50, y_position, "User:")
        c.drawString(150, y_position,
                     f"{booking.contact_leader.name or 'N/A'}")  # Replace with the actual user field if needed
        draw_arabic_text(width - 350, y_position, "اسم المستخدم:")
        # Tel
        c.drawString(width / 2 + 50, y_position, "Tel:")
        c.drawString(width / 2 + 150, y_position,
                     f"{booking.company_id.phone or 'N/A'}")  # Replace with the actual booking field
        draw_arabic_text(width - 50, y_position, "تليفون:")
        y_position -= line_height  # Extra spacing after this section
        y_position -= line_height
        # Registration Card Title

        c.drawString(width / 2 - 80, y_position, f"Group no#{booking.name}")

        draw_arabic_text(width / 2 + 60, y_position, f"مجموعة:")

        y_position -= 35
        guest_payment_border_top = y_position + 30

        LEFT_LABEL_X = left_margin
        LEFT_VALUE_X = LEFT_LABEL_X + 100
        LEFT_ARABIC_X = LEFT_VALUE_X + 100

        # Right column starts sooner
        RIGHT_LABEL_X = LEFT_ARABIC_X + 90
        RIGHT_VALUE_X = RIGHT_LABEL_X + 90
        # Keep Arabic close to the value
        RIGHT_ARABIC_X = RIGHT_VALUE_X + 70

        guest_details = [
            ("Arrival Date:", f"{booking.first_visit or 'N/A'}", "تاريخ الوصول:", "Group Name:",
             f"{booking.name or 'N/A'}", "اسم المجموعة:"),
            ("Departure Date:", f"{booking.last_visit or 'N/A'}", "تاريخ المغادرة:", "Company Name:",
             f"{booking.company_id.name or 'N/A'}", "اسم الشركة:"),
            ("Nights:", f"{booking.total_nights or 'N/A'}", "عدد الليالي:", "Nationality:",
             f"{booking.nationality.name or 'N/A'}", "جنسية المجموعة:"),
            ("No. of Rooms:", f"{booking.total_room_count or 'N/A'}", "عدد الغرف:", "Contact:",
             f"{booking.phone_1 or 'N/A'}", "مسؤول المجموعة:"),
            ("No. of Paxs:", f"{booking.total_adult_count or 'N/A'}", "عدد الأفراد:", "Mobile No.:",
             f"{booking.mobile or 'N/A'}", "رقم الجوال:"),
            ("Rate Code:", f"{booking.rate_code.code or 'N/A'}", "كود التعاقد:", "Status:", "", "حالة الحجز:"),
            ("Meal Pattern:", f"{booking.group_meal_pattern.meal_pattern or 'N/A'}", "نظام الوجبات:", "Date Created:",
             "", "تاريخ إنشاء الحجز:"),
        ]

        # Iterate through guest details and draw strings
        for l_label, l_value, l_arabic, r_label, r_value, r_arabic in guest_details:
            # Left column
            c.drawString(LEFT_LABEL_X, y_position, l_label)
            c.drawString(LEFT_VALUE_X, y_position, l_value)
            draw_arabic_text(LEFT_ARABIC_X, y_position, l_arabic)

            # Right column
            c.drawString(RIGHT_LABEL_X, y_position, r_label)
            c.drawString(RIGHT_VALUE_X, y_position, r_value)
            draw_arabic_text(RIGHT_ARABIC_X, y_position, r_arabic)

            y_position -= line_height

        payment_details = [
            ("Total VAT:", "", "القيمة المضافة:", "Payment Method:", f"{booking.payment_type or 'N/A'}", "نظام الدفع:"),
            ("Total Municipality:", "", "رسوم البلدية:", "Daily Room Rate:", f"{report_data['avg_rate']}",
             "اليومي للغرف:"),
            ("Total Amount:", "", "المبلغ المطلوب:", "Daily Meals Rate:", f"{report_data['avg_meals']}",
             "اليومي للوجبات:"),
            ("Payments:", "", "المبلغ المدفوع:", "Total Room Rate:", f"{report_data['total_room_rate']}",
             "إجمالي الغرف:"),
            ("Remaining:", "", "المبلغ المتبقي:", "Total Meals Rate:", f"{report_data['total_meal_rate']}",
             "إجمالي الوجبات:"),
        ]

        for l_label, l_value, l_arabic, r_label, r_value, r_arabic in payment_details:
            # Adjust English label and value positioning
            c.drawString(LEFT_LABEL_X, y_position, f"{l_label}")
            c.drawString(LEFT_LABEL_X + 90, y_position, f"{l_value}")  # Add spacing (adjust 150 as needed)

            # Draw Arabic label and value
            draw_arabic_text(LEFT_ARABIC_X, y_position, l_arabic)

            c.drawString(RIGHT_LABEL_X, y_position, f"{r_label}")
            c.drawString(RIGHT_LABEL_X + 90, y_position, f"{r_value}")  # Add spacing (adjust 150 as needed)

            draw_arabic_text(RIGHT_ARABIC_X, y_position, r_arabic)

            y_position -= line_height  # Move to the next line

        guest_payment_border_bottom = y_position - 20  # A little extra space below
        # Draw the border for Guest + Payment details
        c.rect(
            left_margin - 10,
            guest_payment_border_bottom,
            (width - left_margin - right_margin) + 20,
            guest_payment_border_top - guest_payment_border_bottom
        )

        y_position -= (line_height)

        # y_position -= 40

        # y_position = height - top_margin

        # def draw_arabic_text(x, y, text):
        #     if text:
        #         reshaped_text = arabic_reshaper.reshape(text)
        #         bidi_text = get_display(reshaped_text)
        #         c.drawString(x, y, bidi_text)

        # Helper function to draw tables
        def draw_in_cell(row_idx, col_idx, text):
            center_x = table_left_x + (col_idx * col_width) + (col_width / 2)
            center_y = table_top_y - (row_idx * row_height) - (row_height / 2)

            reshaped = arabic_reshaper.reshape(text)
            bidi_txt = get_display(reshaped)

            # Simply draw the text here, WITHOUT calling draw_in_cell again
            c.drawCentredString(center_x, center_y, bidi_txt)

        def draw_transposed_table(data, headers, table_top_y, left_margin, right_margin, row_height=20):
            table_left_x = left_margin - 10
            table_width = (width - left_margin - right_margin) + 20
            num_cols = len(headers)
            num_rows = len(data) + 1  # +1 for the header row
            table_height = row_height * num_rows
            col_width = table_width / num_cols
            # table_left_x = left_margin

            # Draw grid
            c.rect(table_left_x, table_top_y - table_height, table_width, table_height)
            # Horizontal lines
            for r in range(num_rows + 1):
                line_y = table_top_y - (r * row_height)
                c.line(table_left_x, line_y, table_left_x + table_width, line_y)

            # Vertical lines
            for col in range(num_cols + 1):
                line_x = table_left_x + (col * col_width)
                c.line(line_x, table_top_y, line_x, table_top_y - table_height)

            # Draw headers (top row)
            for col_idx, header in enumerate(headers):
                center_x = table_left_x + (col_idx * col_width) + (col_width / 2)
                center_y = table_top_y - (row_height / 2)
                reshaped_header = arabic_reshaper.reshape(header)
                bidi_header = get_display(reshaped_header)
                c.drawCentredString(center_x, center_y, bidi_header)

            # Draw the data rows
            for row_idx, row_data in enumerate(data):
                for col_idx, cell_value in enumerate(row_data):
                    center_x = table_left_x + (col_idx * col_width) + (col_width / 2)
                    center_y = table_top_y - ((row_idx + 1) * row_height) - (row_height / 2)
                    if isinstance(cell_value, str) and any("\u0600" <= char <= "\u06FF" for char in cell_value):
                        reshaped_cell = arabic_reshaper.reshape(cell_value)
                        bidi_cell = get_display(reshaped_cell)
                        c.drawCentredString(center_x, center_y, bidi_cell)
                    else:
                        c.drawCentredString(center_x, center_y, str(cell_value))

            # Return how tall the table was, in case you need to adjust y_position
            return table_height

        # Group booking data preparation

        # Draw the table
        # 3) Draw the table
        table_top_y = y_position - 20  # Start a bit above
        t_height = draw_transposed_table(
            data=table_data,
            headers=table_headers,
            table_top_y=table_top_y,
            left_margin=left_margin,
            right_margin=right_margin,
            row_height=20
        )

        def draw_arabic_text(x, y, text):
            reshaped_text = arabic_reshaper.reshape(text)  # Reshape Arabic text
            bidi_text = get_display(reshaped_text)  # Apply bidirectional rendering
            c.drawRightString(x, y, bidi_text)  # Draw right-aligned Arabic text

        # 4) Move y_position below the newly drawn table
        y_position -= (t_height + 30)

        meal_headers = ['Meals'] + meal_patterns + ['وجبة']
        # 1) Decide rows & columns:
        num_rows = len(meal_table_data)
        num_cols = len(meal_headers)
        print('line 3874', num_rows, num_cols)

        row_height = 20

        # Dynamically calculate column width based on the number of columns
        col_width = (width - left_margin - right_margin) / num_cols
        table_width = col_width * num_cols
        table_width = (width - left_margin - right_margin) + 20
        table_height = row_height * (num_rows + 1)

        table_left_x = left_margin - 10
        table_top_y = y_position
        # Draw the outer rectangle
        c.rect(table_left_x, table_top_y - table_height, table_width, table_height)

        # Horizontal lines
        for r in range(num_rows + 1):
            line_y = table_top_y - (r * row_height)
            c.line(table_left_x, line_y, table_left_x + table_width, line_y)

        # Vertical lines
        col_width = table_width / num_cols
        for col in range(num_cols + 1):
            line_x = table_left_x + (col * col_width)
            c.line(line_x, table_top_y, line_x, table_top_y - table_height)

        # Draw headers
        # Draw headers
        for col_idx, header_text in enumerate(meal_headers):
            # Calculate the position of the header cell
            x_pos = table_left_x + (col_idx * col_width)
            y_pos = table_top_y  # Header row is at the top of the table

            # Center-align the text in the header cell
            text_x = x_pos + (col_width / 2)
            text_y = y_pos - (row_height / 2)  # Adjust to vertically center the text
            if header_text.isascii():  # English or numeric text
                c.drawCentredString(text_x, text_y, str(header_text))
            else:  # Arabic text
                draw_arabic_text(x_pos + col_width - 5, text_y, str(header_text))  # Align Arabic to the right
        # Iterating and drawing the meal_table_data
        for row_idx, row in enumerate(meal_table_data):
            for col_idx, cell in enumerate(row):
                # Calculate the position of the cell
                x_pos = table_left_x + (col_idx * col_width)
                y_pos = table_top_y - ((row_idx + 1) * row_height)  # Row index starts after header

                # Draw the cell content (center-aligned)
                text_x = x_pos + (col_width / 2)
                text_y = y_pos - (row_height / 2)  # Adjust to vertically center the text
                if isinstance(cell, str) and not cell.isascii():  # Arabic text
                    draw_arabic_text(x_pos + col_width - 5, text_y, str(cell))  # Align Arabic to the right
                else:  # English or numeric text
                    c.drawCentredString(text_x, text_y, str(cell))

        # Finally, move below this table
        y_position -= (table_height + 10)
        y_position -= 20
        terms_top = y_position
        y_position -= 10

        terms = [
            "Terms & Conditions:",
            "Check-in time is at 16:00 PM, checkout time is at 12:00 PM.",
            "Reservation is tentative until the payment is transferred.",
            "Reservation will be canceled automatically if the option date is exceeded.",
            "After depositing the amount, kindly send a copy of the bank transfer receipt.",
            "All payments are non-refundable."
            "No Show Policy:",
            "In case of no-show during the low season, one night will be charged.",
            "In case of no-show during the high season, the total stay will be charged.",
            "Family Policy:",
            "A maximum of one child under 6 years old is free of charge."
        ]

        arabic_terms = [
            "الشروط والأحكام:",
            "موعد الدخول الساعة الرابعة عصراً، والخروج الساعة الثانية عشرة ظهراً.",
            "الحجز يعتبر غير مؤكد حتى يتم تحويل قيمة الدفعة.",
            "سيتم إلغاء الحجز تلقائياً إذا انتهى تاريخ الخيار.",
            "يرجى إرسال نسخة من إيصال التحويل البنكي بعد دفع المبلغ.",
            "جميع المدفوعات غير قابلة للاسترداد.",
            "سياسة عدم الحضور:",
            "في حال عدم الحضور خلال الموسم المنخفض يتم احتساب ليلة واحدة.",
            "في حال عدم الحضور خلال الموسم المرتفع يتم احتساب كامل الإقامة.",
            "سياسة العائلة:",
            "يُسمح بطفل واحد بحد أقصى أقل من 6 سنوات مجاناً."
        ]

        # Set maximum width for wrapping text
        max_width_english = 60  # Maximum width for wrapping English text
        max_width_arabic = 60  # Maximum width for Arabic text

        # Iterate through English and Arabic terms
        for eng_term, ar_term in zip(terms, arabic_terms):
            # Wrap the English and Arabic text into multiple lines
            eng_lines = wrap(eng_term, max_width_english)
            ar_lines = wrap(ar_term, max_width_arabic)

            # Ensure both English and Arabic text have the same number of lines
            max_lines = max(len(eng_lines), len(ar_lines))
            eng_lines += [""] * (max_lines - len(eng_lines))  # Pad English lines
            ar_lines += [""] * (max_lines - len(ar_lines))  # Pad Arabic lines

            # Draw each line
            for eng_line, ar_line in zip(eng_lines, ar_lines):
                # Draw English text on the left side
                c.drawString(50, y_position, eng_line)

                # Draw Arabic text on the right side, properly reshaped and aligned
                draw_arabic_text(width - 50, y_position, ar_line)

                # Move to the next line
                y_position -= 12  # Adjust line spacing

        # Draw Border Around Terms and Conditions Section
        # Define page bottom margin (e.g., 20 units above the page's bottom edge)
        page_bottom_margin = 15
        extra_space = 10  # Additional space to add below the content

        # Calculate bottom of the rectangle with respect to the page bottom margin
        terms_bottom = max(page_bottom_margin, y_position - 10 - extra_space)  # Add extra space

        # Debugging: Print the adjusted bottom value
        # print(f"Adjusted terms_bottom with extra space: {terms_bottom}, terms_top: {terms_top}, section height: {terms_top - terms_bottom}")

        # Draw the border
        c.rect(
            left_margin - 10,  # Adjust left margin
            terms_bottom,  # Adjusted bottom boundary with extra space
            (width - left_margin - right_margin) + 20,  # Width of the rectangle
            terms_top - terms_bottom  # Height of the rectangle
        )
        # Search for bank details linked to the partner
        bank_details = request.env['res.partner.bank'].search([('partner_id', '=', booking.contact_leader.id)])

        # Convert bank details to a dictionary
        bank_data = bank_details.read()  # This retrieves all fields of the records
        # print('line 3991',bank_data , booking.contact_leader.id,)
        # Extracting acc_number and bank_name

        y_position -= 20
        if bank_data:
            for detail in bank_data:
                acc_number = detail.get('acc_number')
                bank_name = detail.get('bank_name')
                # print(f"Account Number: {acc_number}, Bank Name: {bank_name}")

            footer_details = [
                ("VAT ID:", "", "الرقم الضريبي:", "Bank Name:", f"{bank_name}", "اسم البنك:"),
                ("E-Mail:", "", "البريد الإلكتروني:", "Account Name:", "", "اسم الحساب:"),
                ("Web Site:", "", "الموقع الإلكتروني:", "Account NO:", f"{acc_number}", "رقم الحساب:"),
                ("Tel/Fax:", "", "تليفون/فاكس:", "IBAN:", "", "آيبان:"),
                ("Address:", "", "العنوان:", "Swift Code:", "", "سويفت كود:"),
            ]
        else:
            footer_details = [
                ("VAT ID:", "", "الرقم الضريبي:", "Bank Name:", 'N/A', "اسم البنك:"),
                ("E-Mail:", "", "البريد الإلكتروني:", "Account Name:", 'N/A', "اسم الحساب:"),
                ("Web Site:", "", "الموقع الإلكتروني:", "Account NO:", 'N/A', "رقم الحساب:"),
                ("Tel/Fax:", "", "تليفون/فاكس:", "IBAN:", "", "آيبان:"),
                ("Address:", "", "العنوان:", "Swift Code:", "", "سويفت كود:"),
            ]

        if footer_details:
            y_position = draw_footer_details(
                c,
                y_position,
                footer_details,
                left_margin,
                right_margin,
                width,
                height,
                bottom_margin,
                top_margin,
                font_name,
                8,  # Font size
                line_spacing=18,  # Line height spacing
                english_to_arabic_spacing=120  # Adjusted spacing for longer English values
            )

            line_spacing = 20  # Adjust line spacing between the rows
            x_positions = [
                left_margin,  # Position for Reservation Manager
                width / 2 - 50,  # Position for Sales Manager
                width - right_margin - 150  # Position for Front Office Manager
            ]

            y_text = y_position - 40  # Start position for text

            # Arabic text reshaping and bidi conversion
            reservation_manager_ar = get_display(arabic_reshaper.reshape("مدير الحجوزات"))
            sales_manager_ar = get_display(arabic_reshaper.reshape("مدير المبيعات"))
            front_office_manager_ar = get_display(arabic_reshaper.reshape("مدير المكتب الأمامية"))

            # Draw text for each manager with proper Arabic and English
            c.drawString(x_positions[0], y_text, f"{reservation_manager_ar} / Reservation Manager")
            c.drawString(x_positions[1], y_text, f"{sales_manager_ar} / Sales Manager")
            c.drawString(x_positions[2], y_text, f"{front_office_manager_ar} / Front Office Manager")

            # Draw dotted lines
            # Add some space between the text and the line
            space_between_text_and_line = 30  # Adjust this value as needed
            line_y_position = y_text - space_between_text_and_line

            line_length = 120  # Length of dotted lines
            for x in x_positions:
                c.line(x, line_y_position, x + line_length, line_y_position)

            y_position = line_y_position - line_spacing
            # Adjust y_position for next elements
            # Save the PDF
        c.save()
        buffer.seek(0)
        return buffer
