from odoo import http, fields
from odoo.http import request, Response
from datetime import timedelta


class WebAppController(http.Controller):
    @http.route('/api/signup', type='json', auth='public', methods=['POST'], csrf=False)
    def custom_web_singup(self, **kwargs):
        email = kwargs.get('email')
        mobile = kwargs.get('mobile')
        password = kwargs.get('password')

        if not password or not (email or mobile):
            return {"status": "error", "message": "Missing email, mobile number, or password"}

        partner_domain = [('email', '=', email)] if email else [('mobile', '=', mobile)]
        partner = request.env['res.partner'].sudo().search(partner_domain, limit=1)

        if partner:
            return {"status": "error", "message": "User already exists"}

        new_partner = request.env['res.partner'].sudo().create({
            'name': email if email else mobile,
            'email': email,
            'mobile': mobile,
        })
        new_partner.set_password(password)

        return {
            "status": "success",
            "message": "Signup successful",
            "partner_id": new_partner.id
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
                "partner_id": partner.id
            }
        else:
            return {"status": "error", "message": "Invalid credentials"}

    @http.route('/api/hotels', type='json', auth='public', methods=['GEt'], csrf=False)
    def get_hotels(self, **kwargs):

        companies = request.env['res.company'].sudo().search([])
        print("COMPANIES", companies)
        print("INVENTORY", len(companies.inventory_ids))

        hotels = []
        for company in companies:
            print("LENGTH", len(company.inventory_ids))
            available_rooms = []
            # for inventory in company.inventory_ids:
            #     # print("I", inventory.company_id.name)
            #     print("P", inventory.pax)
            #     print("T", inventory.total_room_count, inventory.room_type)
            #     rooms = request.env['hotel.room'].sudo().search([
            #         ('room_type_name', '=', inventory.room_type.id)])
            #     print("R", inventory.room_type.description, len(rooms))
            #
            #     for room in rooms:
            #         room_amenities = []
            #         if room.room_amenities_ids:
            #             for amenities in room.room_amenities_ids:
            #                 if amenities not in room_amenities:
            #                     room_amenities.append([amenities.id, amenities.name])
            #             print("RA", room_amenities)
            #
            #         if room.rate_code:
            #             print("RC", room.rate_code)

            hotels.append({
                "id": company.id,
                "name": company.name,
                "age_threshold": company.age_threshold,
                "phone": company.phone,
                "email": company.email,
                "website": company.website,
                "title": company.web_title,
                "star_rating": company.web_star_rating,
                "kaaba_view": company.web_kaaba_view,
                "description": company.web_description,
                "location": company.web_hotel_location,
                "discount": company.web_discount,
                "review": company.web_review,
                # "available_rooms": available_rooms
            })

        services = request.env['hotel.service'].sudo().search([])
        services_data = []
        for service in services:
            _service = {}
            _service['name'] = service.name
            _service['price'] = service.unit_price
            services_data.append(_service)

        return {"status": "success", "hotels": hotels, "services": services_data}

    @http.route('/api/hotel/<int:hotel_id>', type='json', auth='public', methods=['GET'], csrf=False)
    def get_hotel_by_id(self, hotel_id, **kwargs):
        company = request.env['res.company'].sudo().search([('id', '=', hotel_id)], limit=1)

        if not company:
            return {"status": "error", "message": "Hotel not found"}

        hotel = {
            "id": company.id,
            "name": company.name,
            "phone": company.phone,
            "email": company.email,
            "website": company.website,
            "title": company.web_title,
            "star_rating": company.web_star_rating,
            "kaaba_view": company.web_kaaba_view,
            "description": company.web_description,
            "location": company.web_hotel_location,
            "discount": company.web_discount,
            "review": company.web_review
        }

        services = request.env['hotel.service'].sudo().search([])
        services_data = []
        for service in services:
            _service = {}
            _service['name'] = service.name
            _service['price'] = service.unit_price
            services_data.append(_service)

        return {"status": "success", "hotels": hotel, "services": services_data}

    @http.route('/api/room_availability', type='json', auth='public', methods=['POST'], csrf=False)
    def check_room_availability(self, **kwargs):
        hotel_id = kwargs.get('hotel_id')
        check_in_date = kwargs.get('check_in_date')
        check_out_date = kwargs.get('check_out_date')
        person_count = kwargs.get('person_count')
        room_count = kwargs.get('room_count')

        # Validate dates
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
        print("RC", len(rate_codes))
        # for rate in rate_codes:
        #     print("RCI", rate.id)

        room_types = request.env['room.type'].sudo().search([])
        all_hotels_data = []
        for hotel in companies:
            hotel_data = {}
            hotel_data["hotel_id"] = hotel.id
            hotel_data["age_threshold"] = hotel.age_threshold

            all_rooms = []
            for room_type in room_types:
                print("CHECK", room_type.description)
                available_rooms_dict = {}
                available_rooms = request.env['room.booking'].sudo()._get_available_rooms(check_in, check_out,
                                                                                          room_type.id,
                                                                                          room_count, True)
                # print("AV", len(available_rooms))
                available_rooms_dict['type'] = room_type.description
                available_rooms_dict['pax'] = person_count
                available_rooms_dict['room_count'] = len(available_rooms)
                # all_rooms.append(available_rooms_dict)

                rate_code_found = True
                for room in available_rooms:
                    if room.rate_code:
                        print("RCI", room.rate_code.id)
                        for day in days:
                            pax_number = person_count // room_count
                            rate_var = f"{day.lower()}_pax_{pax_number}"
                            print("RATE VAR", rate_var)

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

        return {"status": "success", "data": all_hotels_data}

    @http.route('/api/confirm_room_availability', type='json', auth='public', methods=['POST'], csrf=False)
    def confirm_room_availability(self, **kwargs):
        booking_id = kwargs.get('booking_id')

        # Check if booking_id is provided
        if not booking_id:
            return {"status": "error", "message": "Booking ID is required"}

        # Retrieve the booking
        booking = request.env['room.booking'].sudo().browse(booking_id)
        if not booking.exists():
            return {"status": "error", "message": "Booking not found"}

        # Check if room is still available by checking dates and current state
        if booking.state != 'not_confirmed':  # Assuming 'available' is the state for open bookings
            return {"status": "error", "message": "Room is no longer available"}

        # Update the state to 'ready_for_payment'
        booking.sudo().write({'state': 'not_confirmed'})

        return {
            "status": "success",
            "message": "Room availability confirmed. Ready for payment.",
            "booking_id": booking.id,
            "new_state": booking.state
        }

    @http.route('/api/update_room_status_after_payment', type='json', auth='public', methods=['POST'], csrf=False)
    def update_room_status_after_payment(self, **kwargs):
        booking_id = kwargs.get('booking_id')
        payment_status = kwargs.get('payment_status')

        # Validate input
        if not booking_id or payment_status != 'successful':
            return {"status": "error", "message": "Invalid booking ID or payment status"}

        # Find the booking record
        booking = request.env['room.booking'].sudo().browse(booking_id)
        if not booking.exists():
            return {"status": "error", "message": "Booking not found"}

        # Check if the booking is ready for payment confirmation
        if booking.state != 'not_confirmed':
            return {"status": "error", "message": "Room booking is not in a payable state"}

        # Update booking state to 'confirmed' or the next appropriate state
        booking.sudo().write({'state': 'block'})

        return {
            "status": "success",
            "message": "Room status updated to confirmed",
            "booking_id": booking.id,
            "new_state": booking.state
        }
