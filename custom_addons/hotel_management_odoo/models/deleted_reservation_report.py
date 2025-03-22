from odoo import models, fields, api, _
import logging
import datetime

_logger = logging.getLogger(__name__)

class DeletedReservationReport(models.Model):
    _name = 'deleted.reservation.report'
    _description = 'Deleted Reservation Report'
    
    id = fields.Integer(string='ID', readonly=True)
    company_id = fields.Many2one('res.company', string='Hotel', required=True)
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
    room_type_name = fields.Char(string='Room Type Name')
    state = fields.Selection([
        ('not_confirmed', 'Not Confirmed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
        ('deleted_reservations', 'Deleted Reservations'),  # Ensure this is included
    ], string='State', required=True)
    original_state = fields.Selection([
        ('not_confirmed', 'Not Confirmed'),
        ('no_show', 'No Show'),
        ('cancel', 'Cancelled'),
    ], string='Original State')
    partner_id = fields.Many2one('res.partner', string='partner_id')    
    partner_company_id = fields.Many2one('res.company', string='Partner Company')
    partner_name = fields.Char(string='Contact')
    write_user =  fields.Integer(string ='Write User')
    write_user_name = fields.Char(string='By')
    ref_id_bk = fields.Char(string='Reference')
    room_name = fields.Integer(string='Room Number')

    @api.model
    def action_run_process_by_deleted_reservation_status(self):
        """Runs the deleted reservation process based on context and returns the action."""
        if self.env.context.get('filtered_date_range'):
            self.env["deleted.reservation.report"].run_process_by_deleted_reservation_status()

            return {
                'name': _('Deleted Reservation Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'deleted.reservation.report',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref('hotel_management_odoo.view_deleted_reservation_report_tree').id, 'tree'),
                    (self.env.ref('hotel_management_odoo.view_deleted_reservation_report_graph').id, 'graph'),
                    (self.env.ref('hotel_management_odoo.view_deleted_reservation_report_pivot').id, 'pivot'),
                ],
                'target': 'current',
            }
        else:
            return {
                'name': _('Deleted Reservation Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'deleted.reservation.report',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref('hotel_management_odoo.view_deleted_reservation_report_tree').id, 'tree'),
                    (self.env.ref('hotel_management_odoo.view_deleted_reservation_report_graph').id, 'graph'),
                    (self.env.ref('hotel_management_odoo.view_deleted_reservation_report_pivot').id, 'pivot'),
                ],
                'domain': [('id', '=', False)],  # Ensures no data is displayed
                'target': 'current',
            }

    @api.model
    def search_available_rooms(self, from_date, to_date):
        self.run_process_by_deleted_reservation_status(from_date, to_date)
        company_ids = [company.id for company in self.env.companies]
        domain = [
            ('date_order', '>=', from_date),
            ('date_order', '<=', to_date),
            ('company_id', 'in', company_ids)
        ]
        results = self.search(domain)
        return results.read([
            'company_id', 'partner_name', 'group_booking', 'ref_id_bk',
            'room_count', 'adult_count', 'room_name',
            'room_type_name', 'checkin_date', 'checkout_date', 'no_of_nights', 'vip',
            'house_use', 'meal_pattern', 'complementary_codes', 'nationality', 'date_order',
            'state', 'original_state', 'write_user_name'
        ])

    # @api.model
    # def action_generate_results(self):
    #     """Generate and update room results by client."""
    #     _logger.info("Starting action_generate_results")
    #     try:
    #         self.run_process_by_deleted_reservation_status()
    #     except Exception as e:
    #         _logger.error(f"Error generating booking results: {str(e)}")
    #         raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_deleted_reservation_status(self, from_date = None, to_date = None):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_deleted_reservation_status")

        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")

        company_ids = [company.id for company in self.env.companies]

        query = f"""
       WITH 
        parameters AS (
        SELECT
            '{from_date}'::date AS from_date,
            '{to_date}'::date AS to_date
    ),
    room_types AS (
    SELECT 
        rt.id AS room_type_id,
        rt.room_type,
        COALESCE(
            jsonb_extract_path_text(rt.description::jsonb, 'en_US'), 
            'N/A'
        ) AS room_type_name
    FROM room_type rt
),
company_ids AS (
    SELECT unnest(ARRAY{company_ids}::int[]) AS company_id
),
system_date_company AS (
        SELECT 
            id AS company_id, 
            system_date::date AS system_date,
            create_date::date AS create_date
        FROM res_company rc 
        WHERE rc.id IN (SELECT company_id FROM company_ids)
    ),
    date_series AS (
        SELECT generate_series(
            GREATEST(p.from_date, c.create_date), 
            p.to_date, 
            INTERVAL '1 day'
        )::date AS report_date
        FROM parameters p
        CROSS JOIN system_date_company c
    ),
    transformed AS (
        SELECT
            rb.id,
            rb.company_id,
            'deleted reservations' AS state,
            rb.state AS original_state,
            COALESCE(jsonb_extract_path_text(gb.name::jsonb, 'en_US'), 'N/A') AS group_booking_name,
            rb.room_count,
            rb.adult_count,
            rb.room_id,
            rb.hotel_room_type,
            rb.checkin_date,
            rb.checkout_date,
            (rb.checkout_date - rb.checkin_date) AS no_of_nights,
            rb.vip,
            rb.house_use,

            /* Use mp.name instead of mp.code here */
            COALESCE(
                jsonb_extract_path_text(mp.meal_pattern::jsonb, 'en_US'),
                'N/A'
            ) AS meal_pattern_code,

            COALESCE(
                jsonb_extract_path_text(cc.code::jsonb, 'en_US'),
                'N/A'
            ) AS complementary_code,
            COALESCE(
                jsonb_extract_path_text(rc_country.name::jsonb, 'en_US'),
                'N/A'
            ) AS nationality,
            rb.date_order,
            rp.id AS partner_id,
            rp.company_id AS partner_company_id,
            rp.name AS partner_name,
            hr.name AS room_name,
            rb.ref_id_bk,
            rb.write_uid AS write_user,
            wp.name AS write_user_name
        FROM room_booking rb
        LEFT JOIN group_booking gb 
               ON rb.group_booking = gb.id
        LEFT JOIN meal_pattern mp  -- changed from meal_code to meal_pattern
               ON rb.meal_pattern = mp.id
        LEFT JOIN complimentary_code cc 
               ON rb.complementary_codes = cc.id
        LEFT JOIN res_country rc_country 
               ON rb.nationality = rc_country.id
        LEFT JOIN res_users ru 
               ON rb.write_uid = ru.id
        LEFT JOIN res_partner rp 
               ON rb.partner_id = rp.id
        LEFT JOIN hotel_room hr 
               ON rb.room_id = hr.id
        LEFT JOIN res_partner wp 
               ON ru.partner_id = wp.id
        WHERE rb.company_id IN (SELECT company_id FROM company_ids) 
          AND rb.date_order BETWEEN (SELECT from_date FROM parameters) 
                               AND (SELECT to_date FROM parameters)
          AND rb.active = FALSE
          AND rb.state IN ('no_show', 'cancel', 'not_confirmed')
    )
SELECT
    t.id,
    t.company_id,
    t.state,
    t.original_state,
    t.group_booking_name,
    t.room_count,
    t.adult_count,
    t.room_id,
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
    t.room_name,
    t.ref_id_bk,
    t.write_user,
    t.write_user_name
FROM transformed t
LEFT JOIN room_types rt
       ON t.hotel_room_type = rt.room_type_id
GROUP BY
    t.id,
    t.company_id,
    t.state,
    t.original_state,
    t.group_booking_name,
    t.room_count,
    t.adult_count,
    t.room_id,
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
    t.room_name,
    t.ref_id_bk,
    t.write_user,
    t.write_user_name
ORDER BY t.date_order;
        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully for Deleted. {len(results)} results fetched")

        records_to_create = []
        valid_states = {'reserved', 'cancelled', 'no_show', 'deleted_reservations'}

        # Define state mapping
        state_mapping = {
            'deleted reservations': 'deleted_reservations',
            # Add other mappings if necessary
        }

        for result in results:
            if len(result) != 25:  # Adjusted to expect 17 values
                _logger.error(f"Unexpected result length: {len(result)}, Data: {result}")
                continue
            # if result[1]:
            #     company_id = result[1]  # Fetch company_id from the result
            #     if company_id != self.env.company.id:  # Skip if company_id doesn't match
            #         continue
            # else:
            #     continue 
            try:
                (
                    id, 
                    company_id, 
                    state, 
                    original_state,
                    group_booking, 
                    room_count,
                    adult_count, 
                    room_id, 
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
                    room_name,
                    ref_id_bk, 
                    write_user, 
                    write_user_name
                ) = result


                # Map the state value using the defined mapping
                state = state_mapping.get(state, state)

                if state not in valid_states:
                    _logger.error(f"Invalid state value: {state} for record: {result}")
                    continue

                records_to_create.append({
                    'id': id,
                    'company_id': company_id,
                    'state': state,
                    'original_state': original_state,
                    'group_booking': group_booking or 'N/A',
                    'room_count': room_count,
                    'adult_count': adult_count,
                    'room_id': room_id,
                    'hotelroom_type': 'N/A',  # Default value since it's not returned by the query
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
                    'write_user_name': write_user_name,
                    'ref_id_bk': ref_id_bk,
                    'room_name': room_name
                })

            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
