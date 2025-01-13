from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class ReservationStatusReport(models.Model):
    _name = 'reservation.status.report'
    _description = 'Reservation Status Report'

    id = fields.Integer(string='ID', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True)
    client_id = fields.Many2one('res.partner', string='Client')
    group_booking = fields.Char(string='Group')
    room_count = fields.Integer(string='Rooms')
    adult_count = fields.Integer(string='Pax')
    room_id = fields.Char(string='Room no')
    hotelroom_type = fields.Char(string='Room Type')
    checkin_date = fields.Date(string='Arrival')
    checkout_date = fields.Date(string='Departure')
    no_of_nights = fields.Integer(string='Number of Nights')
    vip = fields.Boolean(string='VIP')
    house_use = fields.Boolean(string='House Use')
    meal_pattern = fields.Char(string='Meal Pattern')
    complementary_codes = fields.Char(string='Complementary Codes')
    nationality = fields.Char(string='Nationality')
    date_order = fields.Date(string='Made on')
    room_type_name = fields.Char(string='Room Type Name')
    state = fields.Selection([
        ('reserved', 'Reserved'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ], string='State', required=True)
    original_state = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('block', 'Blocked'),
    ], string='Original State')
    partner_id = fields.Many2one('res.partner', string='partner_id')    
    partner_company_id = fields.Many2one('res.company', string='Partner Company')
    partner_name = fields.Char(string='company')
    write_user =  fields. Integer(string ='Write User')
    write_user_name = fields.Char(string='By')
    ref_id_bk = fields.Integer(string='Reference')
    room_name = fields.Integer(string='Room Number')


    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_reservation_status()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_reservation_status(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_reservation_status")

        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")

        query = """
        WITH 
    room_types AS (
        SELECT 
            rt.id AS room_type_id,
            rt.room_type,
            rt.description AS room_type_name
        FROM room_type rt
    ),
    transformed AS (
        SELECT
            rb.company_id,
            rb.ref_id_bk, -- Including ref_id_bk
            CASE
                WHEN rb.state IN ('confirmed', 'block') THEN 'reserved'
                WHEN rb.state IN ('cancel') THEN 'cancelled'
                ELSE rb.state
            END AS state,
            rb.state AS original_state, 
            COALESCE(gb.name, 'N/A') AS group_booking_name,
            rb.room_count,
            rb.adult_count,
            rbl.room_id, -- Fetching room_id from room_booking_line_status
            rb.hotel_room_type,
            rb.checkin_date,
            rb.checkout_date,
            (rb.checkout_date - rb.checkin_date) AS no_of_nights,
            rb.vip,
            rb.house_use,
            COALESCE(mc.meal_code, 'N/A') AS meal_pattern_code,
            COALESCE(cc.code, 'N/A') AS complementary_code,
            COALESCE(jsonb_extract_path_text(rc_country.name::jsonb, 'en_US'), 'N/A') AS nationality,
            rb.date_order,
            rp.id AS partner_id,
            rp.company_id AS partner_company_id,
            rp.name AS partner_name,
            rb.write_uid AS write_user,
			wp.name AS write_user_name
        FROM
            room_booking rb
        LEFT JOIN
            room_booking_line rbl ON rb.id = rbl.booking_id -- Joining room_booking_line_status
        LEFT JOIN
            group_booking gb ON rb.group_booking = gb.id
        LEFT JOIN
            meal_code mc ON rb.meal_pattern = mc.id
        LEFT JOIN
            complimentary_code cc ON rb.complementary_codes = cc.id
        LEFT JOIN
            res_country rc_country ON rb.nationality = rc_country.id
        LEFT JOIN
            res_users ru ON rb.write_uid = ru.id
        LEFT JOIN
            res_partner rp ON rb.partner_id = rp.id
		LEFT JOIN 
            res_partner wp ON ru.partner_id = wp.id 
    )
SELECT
    t.company_id,
    t.ref_id_bk, -- Including ref_id_bk
    t.state,
    t.original_state,
    t.group_booking_name,
    t.room_count,
    t.adult_count,
    t.room_id,
    hr.name AS room_name, -- Displaying name field from hotel_room
    t.hotel_room_type,
    rt.room_type_name,
    t.checkin_date,
    t.checkout_date,
    t.no_of_nights,
    t.vip,
    t.house_use,
    t.meal_pattern_code,
    t.complementary_code,
    t.nationality,
    t.date_order,
    t.partner_id,
    t.partner_company_id,
    t.partner_name,
    t.write_user,
    t.write_user_name -- Adding write_name from res_partner
FROM
    transformed t
LEFT JOIN
    room_types rt ON t.hotel_room_type = rt.room_type_id
LEFT JOIN
    hotel_room hr ON t.room_id = hr.id -- Joining hotel_room to get room name
LEFT JOIN
    res_partner wp ON t.write_user = wp.id -- Joining res_partner to get write_name
WHERE
    t.state IN ('reserved', 'cancelled', 'no_show') 
GROUP BY
    t.ref_id_bk, -- Grouping by ref_id_bk
    t.company_id,
    t.state,
    t.original_state,
    t.group_booking_name,
    t.room_count,
    t.adult_count,
    t.room_id,
    hr.name, -- Grouping by room name
    t.hotel_room_type,
    rt.room_type_name,
    t.checkin_date,
    t.checkout_date,
    t.no_of_nights,
    t.vip,
    t.house_use,
    t.meal_pattern_code,
    t.complementary_code,
    t.nationality,
    t.date_order,
    t.partner_id,
    t.partner_company_id,
    t.partner_name,
    t.write_user,
    t.write_user_name -- Adding write_name to GROUP BY
ORDER BY
    t.state;


        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        records_to_create = []
        valid_states = {'reserved', 'cancelled', 'no_show'}

        for result in results:
            try:
                if result[0]:  # Ensure company_id is present
                    company_id = result[0]
                    if company_id != self.env.company.id:  # Skip if company_id doesn't match
                        continue
                else:
                    continue
                (
                    company_id,
                    ref_id_bk,
                    state,
                    original_state,
                    group_booking,
                    room_count,
                    adult_count,
                    room_id,
                    room_name,
                    hotelroom_type,
                    room_type_name,
                    checkin_date,
                    checkout_date,
                    no_of_nights,
                    vip,
                    house_use,
                    meal_pattern,
                    complementary_codes,
                    nationality,
                    date_order,
                    partner_id,
                    partner_company_id,
                    partner_name,
                    write_user,
                    write_user_name,
                ) = result

                if state not in valid_states:
                    _logger.error(f"Invalid state value: {state} for record: {result}")
                    continue

                records_to_create.append({
                    'company_id': company_id,
                    'ref_id_bk': ref_id_bk,
                    'state': state,
                    'original_state': original_state if state == 'reserved' else False,
                    'group_booking': group_booking or 'N/A',
                    'room_count': room_count,
                    'adult_count': adult_count,
                    'room_id': room_id,
                    'room_name': room_name,
                    'hotelroom_type': hotelroom_type,
                    'room_type_name': room_type_name,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'no_of_nights': no_of_nights.days if isinstance(no_of_nights, datetime.timedelta) else no_of_nights,
                    'vip': vip,
                    'house_use': house_use,
                    'meal_pattern': meal_pattern,
                    'complementary_codes': complementary_codes,
                    'nationality': nationality,
                    'date_order': date_order,
                    'partner_id': partner_id,
                    'partner_company_id': partner_company_id,
                    'partner_name': partner_name,
                    'write_user': write_user,
                    'write_user_name': write_user_name
                })

            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
 