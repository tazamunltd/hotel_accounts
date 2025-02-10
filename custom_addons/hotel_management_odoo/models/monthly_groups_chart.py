from datetime import timedelta
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class MonthlyGroupsCharts(models.Model):
    _name = 'monthly.groups.charts'
    _description = 'Monthly Groups Charts'

    report_date = fields.Date(string='Report Date', required=True)
    company_id = fields.Many2one('res.company',string='company', required = True)
    room_type = fields.Char(string='Room Type', required=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True)
    available = fields.Integer(string='Available', readonly=True)
    expected_inhouse = fields.Integer(string='Exp.In House', readonly=True)
    group_booking = fields.Char(string='Group Booking',readonly=True)
    inhouse = fields.Integer(string='In-House', readonly=True)

    @api.model
    def search_available_rooms(self, from_date, to_date):
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
        ]
        results = self.search(domain)
        return results.read([
            'report_date', 'room_type', 'company_id', 'group_booking', 'expected_inhouse'
        ])


    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        print("line 34")
        try:
            # Call the run_process method to execute the query and process results
            self.run_process_by_monthly_groups_charts()

        except Exception as e:
            _logger.error(f"Error generating room results: {str(e)}")
            raise ValueError(f"Error generating room results: {str(e)}")

    def run_process_by_monthly_groups_charts(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_monthly_groups_charts")
        
        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")
        system_date = self.env.company.system_date.date()
        from_date = system_date - timedelta(days=7)
        to_date = system_date + timedelta(days=7)
        get_company = self.env.company.id


        query = """
         WITH parameters AS (
    SELECT
        COALESCE(
          (SELECT MIN(rb.checkin_date::date) 
           FROM room_booking rb 
           WHERE rb.company_id = %s), 
          CURRENT_DATE
        ) AS from_date,
        COALESCE(
          (SELECT MAX(rb.checkout_date::date) 
           FROM room_booking rb 
           WHERE rb.company_id = %s), 
          CURRENT_DATE
        ) AS to_date,
        %s AS company_id
),
date_series AS (
    SELECT DISTINCT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
    FROM parameters p
),
system_date_company AS (
	select id as company_id 
	, system_date::date	from res_company rc where  rc.id = (SELECT company_id FROM parameters)
),
room_type_data AS (
    SELECT
        id AS room_type_id,
        COALESCE(jsonb_extract_path_text(room_type::jsonb, 'en_US'),'N/A') AS room_type_name
    FROM room_type
),
base_data AS (
    SELECT
        rb.id AS booking_id,
        rb.company_id,
        rb.partner_id AS customer_id,
        rp.name AS customer_name,
        rb.checkin_date::date AS checkin_date,
        rb.checkout_date::date AS checkout_date,
        rbl.id AS booking_line_id,
        rbl.room_id,
        rbl.hotel_room_type AS room_type_id,
        rbls.status,
        rbls.change_time,
        rb.house_use,
        rb.complementary,
        gb.name AS group_booking_name
    FROM room_booking rb
    JOIN room_booking_line rbl ON rb.id = rbl.booking_id
    LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
    LEFT JOIN res_partner rp ON rb.partner_id = rp.id
    LEFT JOIN group_booking gb ON rb.group_booking = gb.id
),
latest_line_status AS (
    SELECT DISTINCT ON (bd.booking_line_id, ds.report_date)
           bd.booking_line_id,
           ds.report_date,
           bd.checkin_date,
           bd.checkout_date,
           bd.company_id,
           bd.room_type_id,
           bd.status AS final_status,
           bd.change_time,
           bd.house_use,
           bd.complementary,
           bd.group_booking_name
    FROM base_data bd
    JOIN date_series ds 
      ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
    ORDER BY
       bd.booking_line_id,
       ds.report_date,
       bd.change_time DESC NULLS LAST
),
in_house AS (
	select 
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.group_booking_name,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
	AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.group_booking_name
),
yesterday_in_house AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.group_booking_name,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
	 AND lls.report_date - interval '1 day' BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.group_booking_name
),
expected_arrivals AS (
    SELECT
        bd.checkin_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.group_booking_name,
        COUNT(DISTINCT bd.booking_line_id) AS expected_arrivals_count
    FROM base_data bd
    WHERE bd.status IN ('confirmed', 'block')
    GROUP BY bd.checkin_date, bd.company_id, bd.room_type_id, bd.group_booking_name
),
expected_departures AS (
    SELECT
        bd.checkout_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.group_booking_name,
        COUNT(DISTINCT bd.booking_line_id) AS expected_departures_count
    FROM base_data bd
    WHERE bd.status = 'check_in'
    GROUP BY bd.checkout_date, bd.company_id, bd.room_type_id, bd.group_booking_name
),
master_keys AS (
    SELECT report_date, company_id, room_type_id, group_booking_name
    FROM in_house
    UNION
    SELECT report_date, company_id, room_type_id, group_booking_name
    FROM expected_arrivals
    UNION
    SELECT report_date, company_id, room_type_id, group_booking_name
    FROM expected_departures
),
final_report AS (
    SELECT
        mk.report_date,
        mk.company_id,
        mk.room_type_id,
        mk.group_booking_name,
        COALESCE(ih.in_house_count, 0) AS in_house_count,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures_count,
        GREATEST(0, 
      -- Use ih.in_house_count when system_date is today, otherwise use yh.in_house_count
      COALESCE(
          CASE 
              WHEN sdc.system_date = mk.report_date THEN ih.in_house_count 
              ELSE yh.in_house_count 
          END, 0
      ) 
      + COALESCE(ea.expected_arrivals_count, 0)
      - LEAST(COALESCE(ed.expected_departures_count, 0), 
              COALESCE(
                  CASE 
                      WHEN sdc.system_date = mk.report_date THEN ih.in_house_count 
                      ELSE yh.in_house_count 
                  END, 0
              )
      )
    ) AS expected_in_house
    FROM master_keys mk
    LEFT JOIN in_house ih
        ON mk.report_date = ih.report_date
       AND mk.company_id = ih.company_id
       AND mk.room_type_id = ih.room_type_id
       AND mk.group_booking_name = ih.group_booking_name
	LEFT JOIN yesterday_in_house yh
        ON mk.report_date = yh.report_date
       AND mk.company_id = yh.company_id
       AND mk.room_type_id = yh.room_type_id
       AND mk.group_booking_name = yh.group_booking_name
    
    LEFT JOIN expected_arrivals ea
        ON mk.report_date = ea.report_date
       AND mk.company_id = ea.company_id
       AND mk.room_type_id = ea.room_type_id
       AND mk.group_booking_name = ea.group_booking_name
    LEFT JOIN expected_departures ed
        ON mk.report_date = ed.report_date
       AND mk.company_id = ed.company_id
       AND mk.room_type_id = ed.room_type_id
       AND mk.group_booking_name = ed.group_booking_name

    LEFT JOIN system_date_company sdc on sdc.company_id = mk.company_id
)
SELECT
    fr.report_date,
    fr.company_id,
    rc.name AS company_name,
    fr.room_type_id,
    COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
    COALESCE(jsonb_extract_path_text(fr.group_booking_name::jsonb, 'en_US'),'N/A') AS group_booking_name,
    fr.expected_in_house
FROM final_report fr
JOIN res_company rc ON fr.company_id = rc.id
JOIN room_type rt ON fr.room_type_id = rt.id
WHERE fr.group_booking_name IS NOT NULL
ORDER BY
    fr.report_date,
    rc.name,
    rt.room_type,
    fr.group_booking_name;
        """
        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        self.env.cr.execute(query, (get_company, get_company, get_company))
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
                records_to_create.append({
                    'report_date': result[0],               # Date
                    'company_id': company_id,
                    'group_booking': result[5],             # group_booking_name
                    'room_type': result[4],                 # room_type_name
                    'expected_inhouse': int(result[6] or 0),# expected_in_house
                })
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
        _logger.info("Completed run_process_by_monthly_groups_charts")
