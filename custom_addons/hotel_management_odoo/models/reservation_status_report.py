from odoo import models, fields, api, _
import logging
import datetime

_logger = logging.getLogger(__name__)

class ReservationStatusReport(models.Model):
    _name = 'reservation.status.report'
    _description = 'Reservation Status Report'

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
    partner_name = fields.Char(string='Contact')
    write_user =  fields. Integer(string ='Write User')
    write_user_name = fields.Char(string='By')
    ref_id_bk = fields.Char(string='Reference')
    room_name = fields.Integer(string='Room Number')

    @api.model
    def action_run_process_by_reservation_status(self):
        """Runs the reservation status process based on context and returns the action."""
        if self.env.context.get('filtered_date_range'):
            self.env["reservation.status.report"].run_process_by_reservation_status()

            return {
                'name': _('Reservation Status Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'reservation.status.report',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_status_report_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_status_report_graph').id, 'graph'),
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_status_report_pivot').id, 'pivot'),
                ],
                'target': 'current',
            }
        else:
            return {
                'name': _('Reservation Status Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'reservation.status.report',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_status_report_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_status_report_graph').id, 'graph'),
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_status_report_pivot').id, 'pivot'),
                ],
                'domain': [('id', '=', False)],  # Ensures no data is displayed
                'target': 'current',
            }

    @api.model
    def search_available_rooms(self, from_date, to_date):

        self.run_process_by_reservation_status(from_date, to_date)
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


    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_reservation_status()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_reservation_status(self, from_date=None, to_date=None):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_reservation_status")

        # Delete existing records
        self.search([]).unlink()
        system_date = self.env.company.system_date.date()
        # from_date = system_date - datetime.timedelta(days=7)
        # to_date = system_date + datetime.timedelta(days=7)
        company_ids = [company.id for company in self.env.companies]
        _logger.info("Existing records deleted")

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
            rb.company_id,
            rb.ref_id_bk,
            CASE
                WHEN rb.state IN ('confirmed', 'block') THEN 'reserved'
                WHEN rb.state IN ('cancel') THEN 'cancelled'
                ELSE rb.state
            END AS state,
            rb.state AS original_state, 
            COALESCE(jsonb_extract_path_text(gb.name::jsonb, 'en_US')) AS group_booking_name,
            rb.room_count,
            rb.adult_count,
            rbl.room_id,
            rb.hotel_room_type,
            rb.checkin_date,
            rb.checkout_date,
            (rb.checkout_date - rb.checkin_date) AS no_of_nights,
            rb.vip,
            rb.house_use,
            COALESCE(jsonb_extract_path_text(mp.meal_pattern::jsonb, 'en_US'),'N/A') AS meal_pattern_code,

            -- IMPORTANT: make sure the table name and field match your DB exactly
            COALESCE(jsonb_extract_path_text(cc.code::jsonb, 'en_US'), 'N/A') AS complementary_code,
            
            COALESCE(jsonb_extract_path_text(rc_country.name::jsonb, 'en_US'), 'N/A') AS nationality,
            rb.date_order,
            rp.id AS partner_id,
            rp.company_id AS partner_company_id,
            rp.name AS partner_name,
            rb.write_uid AS write_user,
            wp.name AS write_user_name
        FROM room_booking rb
        LEFT JOIN room_booking_line rbl 
               ON rb.id = rbl.booking_id
        LEFT JOIN group_booking gb 
               ON rb.group_booking = gb.id
        LEFT JOIN meal_pattern mp 
               ON rb.meal_pattern = mp.id

        -- FIX:  The table is spelled “complimentary_code” while the FK field in room_booking is spelled “complementary_codes.”
        LEFT JOIN complimentary_code cc 
               ON rb.complementary_codes = cc.id

        LEFT JOIN res_country rc_country 
               ON rb.nationality = rc_country.id
        LEFT JOIN res_users ru 
               ON rb.write_uid = ru.id
        LEFT JOIN res_partner rp 
               ON rb.partner_id = rp.id
        LEFT JOIN res_partner wp 
               ON ru.partner_id = wp.id
        WHERE
            rb.company_id IN (SELECT company_id FROM company_ids) 
            AND rb.date_order BETWEEN (SELECT from_date FROM parameters) 
                                AND (SELECT to_date FROM parameters)
    )
SELECT
    t.company_id,
    t.ref_id_bk,
    t.state,
    t.original_state,
    t.group_booking_name,
    t.room_count,
    t.adult_count,
    t.room_id,
    COALESCE(jsonb_extract_path_text(hr.name::jsonb, 'en_US')) AS room_name,
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
    t.write_user_name
FROM transformed t
LEFT JOIN room_types rt 
       ON t.hotel_room_type = rt.room_type_id
LEFT JOIN hotel_room hr 
       ON t.room_id = hr.id
-- Already have t.write_user_name from “t” – no need to re-join res_partner again
WHERE
    t.state IN ('reserved', 'cancelled', 'no_show') 
GROUP BY
    t.ref_id_bk,
    t.company_id,
    t.state,
    t.original_state,
    t.group_booking_name,
    t.room_count,
    t.adult_count,
    t.room_id,
    hr.name,
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
    t.write_user_name
ORDER BY t.state;
        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        records_to_create = []
        valid_states = {'reserved', 'cancelled', 'no_show'}

        for result in results:
            try:
                # if result[0]:  # Ensure company_id is present
                #     company_id = result[0]
                #     if company_id != self.env.company.id:  # Skip if company_id doesn't match
                #         continue
                # else:
                #     continue
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
 