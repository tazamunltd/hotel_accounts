from email.policy import default

from decorator import append

from odoo import http, fields
from odoo.http import request, Response
from datetime import timedelta
from decimal import Decimal
from datetime import datetime
import redis
import json

REDIS_CONFIG = {
    'host': 'redis',
    'port': 6379
}


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

    def get_model_data(self, model, columns=None):
        if columns is None:
            columns = []

        records = request.env[model].sudo().search([])
        data = []

        if len(columns) > 1:
            for record in records:
                record_data = {col: getattr(record, col, None) for col in columns}
                data.append(record_data)

        else:
            data = records

        return data

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
        room_types = self.get_model_data('room.type')
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

        all_hotels_data = []
        for hotel in companies:
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
                "payment": hotel.web_payment
            }

            all_rooms = []
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
            all_hotels_data.append(hotel_data)

        services_data = self.get_model_data('hotel.service', ['id', 'name', 'unit_price'])
        posting_items = self.get_model_data('posting.item',
                                            ['id', 'description', 'default_value', 'posting_item_selection',
                                             'show_in_website', 'website_desc'])
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

        posting_items = [item for item in posting_items if item["show_in_website"]]

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
                    if cached_data:
                        # print("Data found in Redis")
                        redis_data[key] = json.loads(cached_data)

                # print("LENGTH REDIS", redis_data.keys())
                if len(redis_data.keys()) == 4:
                    return redis_data

            except Exception as e:
                pass

        hotel = request.env['res.company'].sudo().search([('id', '=', hotel_id)], limit=1)

        if not hotel:
            return {"status": "error", "message": "Hotel not found"}

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

        room_types = self.get_model_data('room.type')

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
            "payment": hotel.web_payment
        }

        all_rooms = []
        for room_type in room_types:
            # print("CHECK", room_type.description)
            available_rooms_dict = {}
            available_rooms = request.env['room.booking'].sudo()._get_available_rooms(check_in, check_out,
                                                                                      room_type.id,
                                                                                      room_count, True)
            # print("AV", len(available_rooms), available_rooms)
            available_rooms_dict['id'] = room_type.id
            available_rooms_dict['type'] = room_type.description
            available_rooms_dict['pax'] = person_count
            available_rooms_dict['room_count'] = len(available_rooms)
            hotel_data['total_available_rooms'] += len(available_rooms)
            all_rooms.append(available_rooms_dict)

        hotel_data['room_types'] = all_rooms

        posting_items = self.get_model_data('posting.item',
                                            ['id', 'description', 'default_value', 'posting_item_selection',
                                             'show_in_website', 'website_desc'])
        # services_data = self.get_model_data('hotel.service', ['id', 'name', 'unit_price'])
        # meal_data = self.get_model_data('meal.pattern', ['id', 'meal_pattern', 'description', 'abbreviation'])
        meal_data = []
        services_data = []
        try:
            rate_details = request.env['rate.detail'].sudo().search([('rate_code_id', '=', hotel.rate_code.id)])[0]
        except Exception as e:
            rate_details = request.env['rate.detail'].sudo().search([('rate_code_id', '=', 12)])[0]

        for meal_line in rate_details['meal_pattern_id']['meals_list_ids']:
            meal_data.append({
                "id": meal_line['meal_code']['id'],
                "meal_pattern": meal_line['meal_code']['meal_code'],
                "description": meal_line['meal_code']['description'],
                "unit_price": meal_line['meal_code']['price_pax'],
            })

        for service_line in rate_details['line_ids']:
            services_data.append({
                "id": service_line['id'],
                "name": service_line['hotel_services_config']['display_name'],
                "unit_price": service_line['packages_value'],
                "rhythm": service_line['packages_rhythm'],
            })

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

        room_types = request.env['room.type'].sudo().search([])
        all_hotels_data = []
        for hotel in companies:
            hotel_data = {"hotel_id": hotel.id, "age_threshold": hotel.age_threshold}

            all_rooms = []
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
        pax_data = kwargs.get('data')

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
            partner_rate_code = partner.rate_code

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
        room_types = request.env['room.type'].sudo().search([])
        all_hotels_data = []

        for hotel in companies:
            if partner_rate_code:
                rate_code = partner_rate_code
            elif hotel.rate_code:
                rate_code = hotel.rate_code
            else:
                rate_code = default_rate_code

            hotel_data = {"hotel_id": hotel.id, "age_threshold": hotel.age_threshold}

            room_types_data = []
            for room_type in room_types:
                # todo: check singleton room type specific rates
                room_type_specific_rates = request.env['room.type.specific.rate'].sudo().search(
                    [('room_type_id', '=', room_type.id)])
                # rate_details = request.env['rate.detail'].sudo().search([('id', '=', '4')])
                rate_details = request.env['rate.detail'].sudo().search([('rate_code_id', '=', rate_code.id)])

                # print("room_type_specific_rates", room_type_specific_rates, room_type.id)
                room_type_data = {
                    "id": room_type.id,
                    "type": room_type.description,
                    "room_data": []
                }

                for pax in pax_data:
                    adult_price = 0
                    child_price = 0

                    for day in days:
                        _var1 = f"{day}_pax_1"
                        _var2 = f"room_type_{day}_pax_1"
                        if len(rate_details) >= 1:
                            # adult_price += room_type_specific_rates[0][_var] * pax["person_count"]
                            # adult_price += rate_details[_var1] * pax["person_count"]
                            adult_price += rate_details[0][_var1] * pax["person_count"]
                        # child_price += room_type_specific_rates.child * pax["room_count"]

                        if room_type_specific_rates:
                            # adult_price += room_type_specific_rates[_var2] * pax["person_count"]
                            adult_price += room_type_specific_rates[0][_var2] * pax["person_count"]

                    available_rooms = request.env['room.booking'].sudo().get_available_rooms_for_api(
                        check_in, check_out, room_type.id, pax["room_count"], True, pax["person_count"], hotel.id
                    )

                    room_data = {
                        "room_count": len(available_rooms),
                        "adult": adult_price,
                        # "child": 0,
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
        payment_details = kwargs.get('payment_details')

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

        sob = request.env['source.business'].sudo().search([('id', '=', '4')])

        try:
            rate_code = partner.rate_code
            # print("RATE CODE ID", rate_code.id)
            if not rate_code.id:
                rate_code = request.env['rate.code'].sudo().search([
                    ('id', '=', 12)
                ])
                # print("RATECODE ID", rate_code.id)
        except Exception as e:
            rate_code = request.env['rate.code'].sudo().search([
                ('id', '=', 12)
            ])
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
                'checkout_date': checkout_date,
                'rate_code': rate_code.id,
                'room_count': 1,
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

            posting_item_ids = []
            for item in services:
                # print("ITEM", item)
                if item.get('type', 0) == 1:
                    posting_item = request.env['posting.item'].sudo().search([('item_code', '=', item['title'])],
                                                                             limit=1)
                    # print("POSTING ITEM", posting_item, item['title'], item['option'])
                    if posting_item:
                        posting_item_ids.append(posting_item.id)

            if posting_item_ids:
                new_booking.sudo().write({
                    'posting_item_ids': [(6, 0, posting_item_ids)]
                })

            # print("POSTING ITEM IDS", posting_item_ids)

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
        all_bookings = request.env['room.booking'].sudo().search([])
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
        bookings = request.env['room.booking'].sudo().search([('partner_id', '=', partner.id)])
        bookings_data = []

        for booking in bookings:
            if booking.id not in group_booking_id_list:
                booking_entry = {
                    "booking_id": booking.id,
                    "booking_name": booking.name,
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
        booking_record = request.env['room.booking'].sudo().search([('id', '=', booking_id)], limit=1)
        if not booking_record:
            return {"status": "error", "message": f"Room booking record with ID {booking_id} does not exist"}

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
                'state': state
            })
        except Exception as e:
            return {"status": "error", "message": f"Failed to update room.booking: {str(e)}"}

        return {
            "status": "success",
            "message": "Room payment and booking updated successfully"
        }
