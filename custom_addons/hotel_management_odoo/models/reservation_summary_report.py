from odoo import models, fields, api, _
import logging
import datetime

_logger = logging.getLogger(__name__)

class ReservationSummaryReport(models.Model):
    _name = 'reservation.summary.report'
    _description = 'Reservation Summary Report'

    
    company_id = fields.Many2one('res.company', string='Hotel', required=True)
    company_name = fields.Char(string='Booking Type')
    group_booking_name = fields.Char(string='Group')
    rms = fields.Integer(string='RMS')
    sng = fields.Integer(string='SNG')
    dbl =  fields.Integer(string='DBL')
    tpl =  fields.Integer(string='TPL')
    oth =  fields.Integer(string='OTH')
    first_arrival = fields.Date(string='First Arrival')
    last_departure = fields.Date(string='Last Departure')

    @api.model
    def action_run_process_by_reservation_summary_report(self):
        """Runs the reservation summary process based on context and returns the action."""
        if self.env.context.get('filtered_date_range'):
            self.env["reservation.summary.report"].run_process_by_reservation_summary_report()

            return {
                'name': _('Reservation Summary Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'reservation.summary.report',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_summary_report_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_summary_report_graph').id, 'graph'),
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_summary_report_pivot').id, 'pivot'),
                ],
                'target': 'current',
            }
        else:
            return {
                'name': _('Reservation Summary Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'reservation.summary.report',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_summary_report_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_summary_report_graph').id, 'graph'),
                    (self.env.ref(
                        'hotel_management_odoo.view_reservation_summary_report_pivot').id, 'pivot'),
                ],
                'domain': [('id', '=', False)],  # Ensures no data is displayed
                'target': 'current',
            }

    @api.model
    def search_available_rooms(self, from_date, to_date):
        
        self.run_process_by_reservation_summary_report(from_date, to_date)
        company_ids = [company.id for company in self.env.companies]
        domain = [
            ('first_arrival', '>=', from_date),
            ('last_departure', '<=', to_date),
            ('company_id', 'in', company_ids)
        ]

        results = self.search(domain)
        return results.read([
            'company_name', 'group_booking_name', 'rms', 'sng', 'dbl', 'tpl', 'oth', 'first_arrival', 'last_departure'
        ])

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_reservation_summary_report()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_reservation_summary_report(self, from_date=None, to_date=None):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_reservation_summary_report")

        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")
        company_ids = [company.id for company in self.env.companies]

        # get_company = self.env.company.id

        query = f"""
WITH 
parameters AS (
        SELECT
            '{from_date}'::date AS from_date,
            '{to_date}'::date AS to_date
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

filtered_bookings AS (
    SELECT
		rb.company_id,  
		rb.hotel_room_type,
		rb.group_booking,
		rb.partner_id,
        rbls.booking_line_id,
        MIN(CASE WHEN rbls.status = 'check_in'  THEN rbls.change_time END) AS first_check_in,
        MAX(CASE WHEN rbls.status = 'check_out' THEN rbls.change_time END) AS last_check_out
-- 		MIN(rbls.change_time) FILTER (WHERE rbls.status = 'check_in') AS first_check_in,
--         MAX(rbls.change_time) FILTER (WHERE rbls.status = 'check_out') AS last_check_out

        
        
        
    FROM room_booking_line_status rbls
	
	INNER JOIN room_booking_line as rbl
	ON rbls.booking_line_id = rbl.id
	
    INNER JOIN room_booking rb
--         ON rbls.id = rb.id
	ON rbl.booking_id = rb.id
	
	
	
    GROUP BY
        rb.company_id,  -- Added company_id
		rb.hotel_room_type,
		rb.group_booking,
		rb.partner_id,
        rbls.booking_line_id
),
final_report AS (
    SELECT
        fb.booking_line_id,
        fb.company_id,  -- Added company_id
        rp.name AS partner_name,
        CASE
            WHEN rp.is_company THEN rp.name
            ELSE 'Individual Booking'
        END AS company_name,
        COALESCE(jsonb_extract_path_text(gb.name::jsonb, 'en_US'),'N/A') AS group_booking_name,
        fb.first_check_in,
        fb.last_check_out,
        rt.room_type
    FROM filtered_bookings fb
    LEFT JOIN res_partner rp
        ON rp.id = fb.partner_id
    LEFT JOIN group_booking gb
        ON gb.id = fb.group_booking
    LEFT JOIN room_type rt
        ON rt.id = fb.hotel_room_type
    WHERE
        fb.company_id IN (SELECT company_id FROM company_ids) 
        AND fb.first_check_in BETWEEN (SELECT from_date FROM parameters) 
        AND (SELECT to_date FROM parameters)
        AND fb.last_check_out BETWEEN (SELECT from_date FROM parameters) 
        AND (SELECT to_date FROM parameters)
)
SELECT
    company_id,  -- Added in SELECT
    company_name,
    group_booking_name,

    -- Total Rooms
    COUNT(booking_line_id) AS rms,

    -- Pivoted room-type columns
    SUM(
      CASE WHEN COALESCE(room_type::text, '') ILIKE '%SNG%' THEN 1 ELSE 0 END
    ) AS sng,
    SUM(
      CASE WHEN COALESCE(room_type::text, '') ILIKE '%DBL%' THEN 1 ELSE 0 END
    ) AS dbl,
    SUM(
      CASE WHEN COALESCE(room_type::text, '') ILIKE '%TPL%' THEN 1 ELSE 0 END
    ) AS tpl,
    SUM(
      CASE WHEN 
        COALESCE(room_type::text, '') NOT ILIKE '%SNG%'
        AND COALESCE(room_type::text, '') NOT ILIKE '%DBL%'
        AND COALESCE(room_type::text, '') NOT ILIKE '%TPL%'
      THEN 1
      ELSE 0
      END
    ) AS oth,

    MIN(first_check_in) AS first_arrival,
    MAX(last_check_out) AS last_departure

FROM final_report
WHERE
    first_check_in IS NOT NULL
    OR last_check_out IS NOT NULL
GROUP BY
    company_id,  -- Added in GROUP BY
    company_name,
    group_booking_name
ORDER BY
    company_id,  -- Added in ORDER BY
    company_name,
    group_booking_name;
        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        records_to_create = []

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
                    company_name,
                    group_booking_name,
                    rms,
                    sng,
                    dbl,
                    tpl,
                    oth,
                    first_arrival,
                    last_departure
                ) = result

        # for result in results:
        #     try:
        #         (
        #             company_name,
        #             group_booking_name,
        #             rms,
        #             dlx,
        #             dbl,
        #             qud,
        #             oth,
        #             first_arrival,
        #             last_departure
        #         ) = result


                records_to_create.append({
                    'company_id': company_id,
                    'company_name': company_name,
                    'group_booking_name': group_booking_name,
                    'rms': rms,
                    'sng': sng,
                    'dbl': dbl,
                    'tpl': tpl,
                    'oth': oth,
                    'first_arrival': first_arrival,
                    'last_departure': last_departure
                })


            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
 