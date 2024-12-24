from odoo import models, fields, api
import logging
import datetime
_logger = logging.getLogger(__name__)

class ReservationStatusReport(models.Model):
    _name = 'reservation.status.report'
    _description = 'Reservation Status Report'

    company_id = fields.Many2one('res.company',string='company', required = True)
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
    date_order = fields.Date(string='Date Order')
    state = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('not_confirmed', 'Not Confirmed'),
        ('block', 'Blocked'),
        ('waiting', 'Waiting'),
        ('canceled', 'Canceled'),
        ('no_show', 'No show'),
        ('check_in', 'check_in'),
        ('check_out', 'check_out'),
        ('done', 'confirmed'),
        ('cancel', 'cancelled'),
        ('reserved', 'reserved'),
    ], string='State')


    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        print("line 34")
        try:
            # Call the run_process method to execute the query and process results
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
       SELECT
    rb.company_id,
    CASE
        WHEN rb.state IN ('confirmed', 'block') THEN 'reserved'
        WHEN rb.state IN ('no_show', 'cancel') THEN 'cancelled'
        ELSE rb.state
    END AS state, -- Apply the state transformation logic
    COALESCE(gb.name, 'N/A') AS group_booking_name, -- Replaces NULL with 'N/A' for group_booking_name
    rb.room_count,
    rb.adult_count,
    rb.room_id,
    rb.hotel_room_type,
    rb.checkin_date,
    rb.checkout_date,
    (rb.checkout_date - rb.checkin_date) AS no_of_nights,
    rb.vip,
    rb.house_use,
    COALESCE(mc.meal_code, 'N/A') AS meal_pattern_code, -- Show meal code instead of ID
    COALESCE(cc.code, 'N/A') AS complementary_code, -- Show complementary code instead of ID
    COALESCE(jsonb_extract_path_text(rc_country.name::jsonb, 'en_US'), 'N/A') AS nationality, -- Extract nationality name
    rb.date_order
FROM
    room_booking rb
LEFT JOIN
    group_booking gb ON rb.group_booking = gb.id -- Join to get the 'name' field
LEFT JOIN
    meal_code mc ON rb.meal_pattern = mc.id -- Join to get the meal_code
LEFT JOIN
    complimentary_code cc ON rb.complementary_codes = cc.id -- Join to get the complementary code
LEFT JOIN
    res_country rc_country ON rb.nationality = rc_country.id -- Join to get nationality name
WHERE
    rb.state IS NOT NULL 
    AND rb.state IN ('confirmed', 'not_confirmed', 'block', 'waiting', 'canceled', 'no_show', 
                     'check_in', 'check_out', 'done', 'cancel', 'reserved')
GROUP BY
    rb.company_id,
    CASE
        WHEN rb.state IN ('confirmed', 'block') THEN 'reserved'
        WHEN rb.state IN ('no_show', 'cancel') THEN 'cancelled'
        ELSE rb.state
    END,
    COALESCE(gb.name, 'N/A'),
    rb.room_count,
    rb.adult_count,
    rb.room_id,
    rb.hotel_room_type,
    rb.checkin_date,
    rb.checkout_date,
    rb.vip,
    rb.house_use,
    COALESCE(mc.meal_code, 'N/A'),
    COALESCE(cc.code, 'N/A'),
    COALESCE(jsonb_extract_path_text(rc_country.name::jsonb, 'en_US'), 'N/A'),
    rb.date_order
ORDER BY
    state;


        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
        records_to_create = []
        valid_states = dict(self._fields['state'].selection).keys()

        for result in results:
            try:
                # Unpack the result tuple based on the query's output
                company_id = result[0]
                state = result[1]
                group_booking = result[2]
                room_count = result[3]
                adult_count = result[4]
                room_id = result[5]
                hotelroom_type = result[6]
                checkin_date = result[7]
                checkout_date = result[8]
                no_of_nights = result[9]
                vip = result[10]
                house_use = result[11]
                meal_pattern = result[12]
                complementary_codes = result[13]
                nationality = result[14]
                date_order = result[15]
                

                # Check if the state is valid
                if state not in valid_states:
                    _logger.error(f"Invalid state value: {state} for record: {result}")
                    continue

                _logger.info(f"Processing record: {result}")

                records_to_create.append({
                    'company_id': company_id,
                    'state': state,
                    'group_booking': group_booking or 'N/A',
                    'room_count': room_count,
                    'adult_count': adult_count,
                    'room_id': room_id,
                    'hotelroom_type': hotelroom_type,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'no_of_nights': no_of_nights.days if isinstance(no_of_nights, datetime.timedelta) else no_of_nights,
                    'vip': vip,
                    'house_use': house_use,
                    'meal_pattern': meal_pattern,
                    'complementary_codes': complementary_codes,
                    'nationality': nationality,
                    'date_order': date_order,
                })

            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
