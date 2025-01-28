from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class MonthlyAllotmentCharts(models.Model):
    _name = 'monthly.allotment.charts'
    _description = 'Monthly Allotment Charts'
    _inherit = ['mail.thread', 'mail.activity.mixin']



    report_date = fields.Date(string='Report Date', required=True,tracking=True)
    company_id = fields.Many2one('res.company',string='company', required = True,tracking=True)
    client_id = fields.Many2one('res.partner', string='Client',tracking=True)  
    region = fields.Char(string='Region',tracking=True)  
    nationality = fields.Char(string='Nationality',tracking=True)  
    room_type = fields.Char(string='Room Type', required=True,tracking=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True,tracking=True)
    available = fields.Integer(string='Available', readonly=True,tracking=True)
    inhouse = fields.Integer(string='In-House', readonly=True,tracking=True)
    expected_arrivals = fields.Integer(string='Exp.Arrivals', readonly=True,tracking=True)
    expected_departures = fields.Integer(string='Exp.Departures', readonly=True,tracking=True)
    expected_inhouse = fields.Integer(string='Exp.Inhouse', readonly=True,tracking=True)
    reserved = fields.Integer(string='Reserved', readonly=True,tracking=True)
    expected_occupied_rate = fields.Float(string='Exp.Occupied Rate (%)', readonly=True,tracking=True)  
    out_of_order = fields.Integer(string='Out of Order', readonly=True,tracking=True)
    overbook = fields.Integer(string='Overbook', readonly=True,tracking=True)
    free_to_sell = fields.Integer(string='Free to sell', readonly=True,tracking=True)
    sort_order = fields.Integer(string='Sort Order', readonly=True,tracking=True)
    source_of_business = fields.Char(string='Source of Business',tracking=True)
    

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        print("line 34")
        try:
            # Call the run_process method to execute the query and process results
            self.run_process_by_monthly_allotment()

        except Exception as e:
            _logger.error(f"Error generating room results: {str(e)}")
            raise ValueError(f"Error generating room results: {str(e)}")

    def run_process_by_monthly_allotment(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_monthly_allotment")
        
        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")

        query = """
        WITH parameters AS (
    SELECT
        COALESCE((SELECT MIN(rb.checkin_date::date) FROM room_booking rb), CURRENT_DATE) AS from_date,
        COALESCE((SELECT MAX(rb.checkout_date::date) FROM room_booking rb), CURRENT_DATE) AS to_date
),
date_series AS (
    SELECT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
    FROM parameters p
),
latest_line_status AS (
    SELECT DISTINCT ON (rbl.id, ds.report_date)
           rbl.id AS booking_line_id,
           ds.report_date,
           rb.checkin_date::date   AS checkin_date,
           rb.checkout_date::date  AS checkout_date,
           hr.company_id,
           rt.id                   AS room_type_id,
           rbls.status             AS final_status,
           rbls.change_time,
           rb.house_use            AS house_use,
           rb.complementary        AS complementary,
           sb.description           AS source_of_business
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb    ON rb.id = rbl.booking_id
    JOIN hotel_room hr      ON hr.id = rbl.room_id
    JOIN room_type rt       ON rt.id = hr.room_type_name
    JOIN source_business sb      ON rb.source_of_business = sb.id
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
           AND rbls.change_time::date <= ds.report_date
    ORDER BY
       rbl.id,
       ds.report_date,
       rbls.change_time DESC NULLS LAST
),
in_house AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        sub.source_of_business,
        COUNT(DISTINCT sub.booking_line_number) AS in_house_count
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type   rt

    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number,
               qry.source_of_business
             
        FROM (
            SELECT 
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rbl.checkin_date,
                rbl.checkout_date,
                rbl.id              AS booking_line_number,
                rbls.status,
                rbls.change_time,
                sb.description           AS source_of_business
            FROM room_booking rb
            JOIN room_booking_line rbl
                  ON rbl.booking_id = rb.id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
            JOIN res_partner rp
                  ON rb.partner_id = rp.id
				  JOIN source_business sb      ON rb.source_of_business = sb.id
        ) AS qry
        WHERE qry.company_id     = rc.id
          AND qry.room_type_id   = rt.id
          AND qry.checkin_date::date <= ds.report_date
          AND qry.checkout_date::date > ds.report_date
          AND qry.status = 'check_in'
          AND qry.change_time::date <= ds.report_date
        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE

    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id,
        sub.source_of_business
),
expected_arrivals AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        sub.source_of_business,
        COUNT(DISTINCT sub.booking_line_number) AS expected_arrivals_count
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type   rt

    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number,
               qry.source_of_business
        FROM (
            SELECT 
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rbl.checkin_date    AS checkin_dt,
                rb.name,
                rbls.status,
                rbl.id              AS booking_line_number,
                rbls.change_time,
                sb.description           AS source_of_business
            FROM room_booking rb
            JOIN room_booking_line rbl 
                  ON rbl.booking_id = rb.id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
            JOIN res_partner rp
                  ON rb.partner_id = rp.id
			JOIN source_business sb      ON rb.source_of_business = sb.id
        ) AS qry
        WHERE qry.company_id    = rc.id
          AND qry.room_type_id  = rt.id
          AND qry.status        IN ('confirmed','block')
          AND qry.change_time::date <= ds.report_date
          AND qry.checkin_dt::date   = ds.report_date
        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE
    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id,
        sub.source_of_business
),
expected_departures AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        sub.source_of_business,
        COUNT(DISTINCT sub.booking_line_number) AS expected_departures_count
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type   rt

    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number,
               qry.source_of_business
        FROM (
            SELECT 
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rbl.checkin_date,
                rbl.checkout_date,
                rbl.id              AS booking_line_number,
                rbls.status,
                rbls.change_time,
                sb.description      AS source_of_business
            FROM room_booking rb
            JOIN room_booking_line rbl
                  ON rbl.booking_id = rb.id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
            JOIN res_partner rp
                  ON rb.partner_id = rp.id
			JOIN source_business sb      ON rb.source_of_business = sb.id
        ) AS qry
        WHERE qry.company_id    = rc.id
          AND qry.room_type_id  = rt.id
          AND qry.checkout_date::date = ds.report_date
          AND qry.status = 'check_in'
          AND qry.change_time::date <= ds.report_date
        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE
    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id,
        sub.source_of_business
),
master_keys AS (
    SELECT report_date, company_id, room_type_id, source_of_business
    FROM in_house
    UNION
    SELECT report_date, company_id, room_type_id, source_of_business
    FROM expected_arrivals
    UNION
    SELECT report_date, company_id, room_type_id, source_of_business
    FROM expected_departures
),
final_report AS (
    SELECT
        mk.report_date,
        mk.company_id,
        mk.room_type_id,
        mk.source_of_business,
        COALESCE(ih.in_house_count, 0) AS in_house_count,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures_count,
        GREATEST(
            COALESCE(ih.in_house_count, 0)
            + COALESCE(ea.expected_arrivals_count, 0)
            - COALESCE(ed.expected_departures_count, 0),
            0
        ) AS expected_in_house
    FROM master_keys mk
    LEFT JOIN in_house ih
        ON mk.report_date = ih.report_date
       AND mk.company_id = ih.company_id
       AND mk.room_type_id = ih.room_type_id
       AND mk.source_of_business = ih.source_of_business
    LEFT JOIN expected_arrivals ea
        ON mk.report_date = ea.report_date
       AND mk.company_id = ea.company_id
       AND mk.room_type_id = ea.room_type_id
       AND mk.source_of_business = ea.source_of_business
    LEFT JOIN expected_departures ed
        ON mk.report_date = ed.report_date
       AND mk.company_id = ed.company_id
       AND mk.room_type_id = ed.room_type_id
       AND mk.source_of_business = ed.source_of_business
)
SELECT
    fr.report_date,
    fr.company_id,
    rc.name AS company_name,
    fr.room_type_id,
    COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
	COALESCE(jsonb_extract_path_text(fr.source_of_business::jsonb, 'en_US'),'N/A') AS source_of_business,
    fr.expected_in_house
FROM final_report fr
JOIN res_company rc ON fr.company_id = rc.id
JOIN room_type rt ON fr.room_type_id = rt.id
WHERE fr.source_of_business IS NOT NULL
ORDER BY
    fr.report_date,
    rc.name,
    rt.room_type,
    fr.source_of_business;


        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
        records_to_create = []

        for result in results:
            try:
                if result[1]:
                    
                    company_id = result[1]
                    if company_id != self.env.company.id:
                        continue  
                    # print(result[1])  
                else:
                    continue
                # Unpack the result tuple
                (
                    report_date,
                    company_id,
                    company_name,
                    room_type_id,
                    room_type_name,
                    source_of_business,
                    expected_in_house
                ) = result

                record = {
                    'company_id': company_id,                     # Integer
                    'report_date': report_date,                   # Date
                    'source_of_business': source_of_business,     # String
                    'room_type': room_type_name,                  # String
                    'expected_inhouse': int(expected_in_house or 0),  # Integer
                }
                _logger.debug(f"Creating record: {record}")
                records_to_create.append(record)
            except ValueError as ve:
                _logger.error(f"ValueError processing record: {ve}, Data: {result}")
                continue
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            try:
                self.create(records_to_create)
                _logger.info(f"{len(records_to_create)} records created")
            except Exception as e:
                _logger.error(f"Error creating records: {str(e)}")
                raise
        else:
            _logger.info("No records to create")
        _logger.info("Completed run_process_by_monthly_allotment")