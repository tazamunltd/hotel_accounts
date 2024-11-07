# from odoo import http, fields
# from odoo.http import request, Response
#
# class WebAppController(http.Controller):
#     @http.route('/api/signup', type='json', auth='public', methods=['POST'], csrf=False)
#     def custom_web_singup(self, **kwargs):
#         email = kwargs.get('email')
#         mobile = kwargs.get('mobile')
#         password = kwargs.get('password')
#
#         if not password or not (email or mobile):
#             return {"status": "error", "message": "Missing email, mobile number, or password"}
#
#         partner_domain = [('email', '=', email)] if email else [('mobile', '=', mobile)]
#         partner = request.env['res.partner'].sudo().search(partner_domain, limit=1)
#
#         if partner:
#             return {"status": "error", "message": "User already exists"}
#
#         new_partner = request.env['res.partner'].sudo().create({
#             'name': email if email else mobile,  # Use email or mobile as a placeholder name
#             'email': email,
#             'mobile': mobile,
#         })
#         new_partner.set_password(password)
#
#         return {
#             "status": "success",
#             "message": "Signup successful",
#             "partner_id": new_partner.id
#         }
#
#     @http.route('/api/signin', type='json', auth='public', methods=['POST'], csrf=False)
#     def custom_web_signin(self, **kwargs):
#         email = kwargs.get('email')
#         mobile = kwargs.get('mobile')
#         password = kwargs.get('password')
#
#         if not password or not (email or mobile):
#             return {"status": "error", "message": "Missing email, mobile number, or password"}
#
#         # Search by email or mobile
#         domain = [('email', '=', email)] if email else [('mobile', '=', mobile)]
#         partner = request.env['res.partner'].sudo().search(domain, limit=1)
#
#         if partner and partner.check_password(password):
#             session_token = request.session.sid
#             return {
#                 "status": "success",
#                 "message": "Login successful",
#                 "session_token": session_token,
#                 "partner_id": partner.id
#             }
#         else:
#             return {"status": "error", "message": "Invalid credentials"}
#
#     @http.route('/api/hotels', type='json', auth='public', methods=['GEt'], csrf=False)
#     def get_hotels(self, **kwargs):
#
#         companies = request.env['res.company'].sudo().search([])
#         print("COMPANIES", companies)
#
#         hotels = []
#         for company in companies:
#             hotels.append({
#                 "id": company.id,
#                 "name": company.name,
#                 "phone": company.phone,
#                 "email": company.email,
#                 "website": company.website,
#                 "title": company.web_title,
#                 "star_rating": company.web_star_rating,
#                 "kaaba_view": company.web_kaaba_view,
#                 "description": company.web_description,
#                 "location": company.web_hotel_location,
#                 "discount": company.web_discount,
#                 "review": company.web_review
#             })
#         return {"status": "success", "hotels": hotels}
#
#     @http.route('/api/hotel/<int:hotel_id>', type='json', auth='public', methods=['GET'], csrf=False)
#     def get_hotel_by_id(self, hotel_id, **kwargs):
#         company = request.env['res.company'].sudo().search([('id', '=', hotel_id)], limit=1)
#
#         if not company:
#             return {"status": "error", "message": "Hotel not found"}
#
#         hotel = {
#             "id": company.id,
#             "name": company.name,
#             "phone": company.phone,
#             "email": company.email,
#             "website": company.website,
#             "title": company.web_title,
#             "star_rating": company.web_star_rating,
#             "kaaba_view": company.web_kaaba_view,
#             "description": company.web_description,
#             "location": company.web_hotel_location,
#             "discount": company.web_discount,
#             "review": company.web_review
#         }
#
#         return {"status": "success", "hotel": hotel}
#
#     @http.route('/api/room_availability', type='json', auth='public', methods=['POST'], csrf=False)
#     def check_room_availability(self, **kwargs):
#         check_in_date = kwargs.get('check_in_date')
#         check_out_date = kwargs.get('check_out_date')
#
#         # Validate dates
#         if not check_in_date or not check_out_date:
#             return {"status": "error", "message": "Check-in and check-out dates are required"}
#
#         try:
#             check_in = fields.Date.from_string(check_in_date)
#             check_out = fields.Date.from_string(check_out_date)
#         except ValueError:
#             return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}
#
#         # Search for rooms that do not overlap with existing bookings
#         booked_rooms = request.env['room.booking'].sudo().search([
#             ('check_in_date', '<', check_out),
#             ('check_out_date', '>', check_in)
#         ]).mapped('room_id')
#
#         available_rooms = request.env['hotel.room'].sudo().search([
#             ('id', 'not in', booked_rooms.ids)
#         ])
#
#         # Prepare response data
#         rooms_data = []
#         for room in available_rooms:
#             rooms_data.append({
#                 "id": room.id,
#                 "name": room.name,
#                 "room_type": room.room_type,
#                 # Add any other relevant fields
#             })
#
#         return {"status": "success", "available_rooms": rooms_data}
#
#     @http.route('/api/confirm_room_availability', type='json', auth='public', methods=['POST'], csrf=False)
#     def confirm_room_availability(self, **kwargs):
#         booking_id = kwargs.get('booking_id')
#
#         # Check if booking_id is provided
#         if not booking_id:
#             return {"status": "error", "message": "Booking ID is required"}
#
#         # Retrieve the booking
#         booking = request.env['room.booking'].sudo().browse(booking_id)
#         if not booking.exists():
#             return {"status": "error", "message": "Booking not found"}
#
#         # Check if room is still available by checking dates and current state
#         if booking.state != 'not_confirmed':  # Assuming 'available' is the state for open bookings
#             return {"status": "error", "message": "Room is no longer available"}
#
#         # Update the state to 'ready_for_payment'
#         booking.sudo().write({'state': 'not_confirmed'})
#
#         return {
#             "status": "success",
#             "message": "Room availability confirmed. Ready for payment.",
#             "booking_id": booking.id,
#             "new_state": booking.state
#         }
#
#     @http.route('/api/update_room_status_after_payment', type='json', auth='public', methods=['POST'], csrf=False)
#     def update_room_status_after_payment(self, **kwargs):
#         booking_id = kwargs.get('booking_id')
#         payment_status = kwargs.get('payment_status')
#
#         # Validate input
#         if not booking_id or payment_status != 'successful':
#             return {"status": "error", "message": "Invalid booking ID or payment status"}
#
#         # Find the booking record
#         booking = request.env['room.booking'].sudo().browse(booking_id)
#         if not booking.exists():
#             return {"status": "error", "message": "Booking not found"}
#
#         # Check if the booking is ready for payment confirmation
#         if booking.state != 'not_confirmed':
#             return {"status": "error", "message": "Room booking is not in a payable state"}
#
#         # Update booking state to 'confirmed' or the next appropriate state
#         booking.sudo().write({'state': 'block'})
#
#         return {
#             "status": "success",
#             "message": "Room status updated to confirmed",
#             "booking_id": booking.id,
#             "new_state": booking.state
#         }