from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class ReservationSummaryReport(models.Model):
    _name = 'reservation.summary.report'
    _description = 'Reservation Summary Report'

    
    # company_id = fields.Many2one('res.company', string='Company', required=True)
    company_name = fields.Char(string='Company')
    group_booking_name = fields.Char(string='Group')
    rms = fields.Integer(string='RMS')
    dlx = fields.Integer(string='DLX')
    dbl =  fields.Integer(string='DBL')
    qud =  fields.Integer(string='QUD')
    oth =  fields.Integer(string='OTH')
    first_arrival = fields.Date(string='First Arrival')
    last_departure = fields.Date(string='Last Departure')
    

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_reservation_summary_report()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_reservation_summary_report(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_reservation_summary_report")

        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")

        query = """
        WITH filtered_bookings AS (
    SELECT
        rbls.booking_line_id,
        MIN(CASE WHEN rbls.status = 'check_in'  THEN rbls.change_time END) AS first_check_in,
        MAX(CASE WHEN rbls.status = 'check_out' THEN rbls.change_time END) AS last_check_out,
        rb.partner_id,
        rb.group_booking,
        rb.hotel_room_type
    FROM room_booking_line_status rbls
    INNER JOIN room_booking rb
        ON rbls.id = rb.id
    GROUP BY
        rbls.booking_line_id,
        rb.partner_id,
        rb.group_booking,
        rb.hotel_room_type
),
final_report AS (
    SELECT
        fb.booking_line_id,
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
)
SELECT
    company_name,
    group_booking_name,

    -- Total Rms
    COUNT(booking_line_id) AS rms,

    -- Pivoted room-type columns
    SUM(
      CASE WHEN COALESCE(room_type::text, '') ILIKE '%DELX%' THEN 1 ELSE 0 END
    ) AS dlx,
    SUM(
      CASE WHEN COALESCE(room_type::text, '') ILIKE '%DUBL%' THEN 1 ELSE 0 END
    ) AS dbl,
    SUM(
      CASE WHEN COALESCE(room_type::text, '') ILIKE '%QUAD%' THEN 1 ELSE 0 END
    ) AS qud,
    SUM(
      CASE WHEN 
        COALESCE(room_type::text, '') NOT ILIKE '%DELX%'
        AND COALESCE(room_type::text, '') NOT ILIKE '%DUBL%'
        AND COALESCE(room_type::text, '') NOT ILIKE '%QUAD%'
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
    company_name,
    group_booking_name
ORDER BY
    company_name,
    group_booking_name;

        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        records_to_create = []

        for result in results:
            try:
                (
                    company_name,
                    group_booking_name,
                    rms,
                    dlx,
                    dbl,
                    qud,
                    oth,
                    first_arrival,
                    last_departure
                ) = result


                records_to_create.append({
                    'company_name': company_name,
                    'group_booking_name': group_booking_name,
                    'rms': rms,
                    'dlx': dlx,
                    'dbl': dbl,
                    'qud': qud,
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
 