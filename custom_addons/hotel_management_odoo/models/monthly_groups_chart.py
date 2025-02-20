from datetime import timedelta
from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class MonthlyGroupsCharts(models.Model):
    _name = 'monthly.groups.charts'
    _description = 'Monthly Groups Charts'

    report_date = fields.Date(string='Report Date', required=True)
    company_id = fields.Many2one('res.company',string='Hotel', required = True)
    room_type = fields.Char(string='Room Type', required=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True)
    available = fields.Integer(string='Available', readonly=True)
    expected_inhouse = fields.Integer(string='Exp.Inhouse', readonly=True)
    group_booking = fields.Char(string='Group Booking',readonly=True)
    inhouse = fields.Integer(string='In-House', readonly=True)


    @api.model
    def action_run_process_by_monthly_groups_charts(self):
        """Runs the monthly groups charts process based on context and returns the action."""
        if self.env.context.get('filtered_date_range'):
            self.env["monthly.groups.charts"].run_process_by_monthly_groups_charts()

            return {
                'name': _('Monthly Groups Chart'),
                'type': 'ir.actions.act_window',
                'res_model': 'monthly.groups.charts',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref('hotel_management_odoo.view_monthly_groups_charts_tree').id, 'tree'),
                    (self.env.ref('hotel_management_odoo.view_monthly_groups_charts_graph').id, 'graph'),
                    (self.env.ref('hotel_management_odoo.view_monthly_groups_charts_pivot').id, 'pivot'),
                ],
                'target': 'current',
            }
        else:
            return {
                'name': _('Monthly Groups Chart'),
                'type': 'ir.actions.act_window',
                'res_model': 'monthly.groups.charts',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref('hotel_management_odoo.view_monthly_groups_charts_tree').id, 'tree'),
                    (self.env.ref('hotel_management_odoo.view_monthly_groups_charts_graph').id, 'graph'),
                    (self.env.ref('hotel_management_odoo.view_monthly_groups_charts_pivot').id, 'pivot'),
                ],
                'domain': [('id', '=', False)],  # Ensures no data is displayed
                'target': 'current',
            }


    @api.model
    def search_available_rooms(self, from_date, to_date):
        self.run_process_by_monthly_groups_charts(from_date, to_date)
        company_ids = [company.id for company in self.env.companies]
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
            ('company_id', 'in', company_ids)
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

    def run_process_by_monthly_groups_charts(self, from_date = None, to_date = None):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_monthly_groups_charts")
        
        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")
        # system_date = self.env.company.system_date.date()
        # from_date = system_date - timedelta(days=7)
        # to_date = system_date + timedelta(days=7)
        # get_company = self.env.company.id
        company_ids = [company.id for company in self.env.companies] 


        query = f"""
         WITH parameters AS (
    SELECT
        '{from_date}'::date AS from_date,
        '{to_date}'::date AS to_date
),
company_ids AS (
    SELECT unnest(ARRAY{company_ids}::int[]) AS company_id
),
system_date_company AS (
    SELECT id as company_id, system_date::date 
    FROM res_company rc 
    WHERE rc.id IN (SELECT company_id FROM company_ids)
), 
    date_series AS (
    SELECT DISTINCT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
    FROM parameters p
),

room_type_data AS (
    SELECT
        rt.id AS room_type_id,
        COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'), 'N/A') AS room_type_name
    FROM room_type rt
),
base_data AS (
    SELECT
          rb.id AS booking_id
        , rb.company_id
        , sdc.system_date::date AS system_date
        , gb.name AS group_booking_name
        , rb.checkin_date::date AS checkin_date
        , rb.checkout_date::date AS checkout_date
        , rbl.id AS booking_line_id
        , rbl.room_id
        , rbl.hotel_room_type AS room_type_id
        , rbls.status
        , rbls.change_time
        , rb.house_use
        , rb.complementary
    FROM room_booking rb
    JOIN room_booking_line rbl 
          ON rb.id = rbl.booking_id
    LEFT JOIN room_booking_line_status rbls 
          ON rbl.id = rbls.booking_line_id
    LEFT JOIN res_partner rp 
          ON rb.partner_id = rp.id
    LEFT JOIN system_date_company sdc
          ON sdc.company_id = rb.company_id
	LEFT JOIN group_booking gb ON rb.group_booking = gb.id
    WHERE rb.company_id IN (SELECT company_id FROM company_ids)
),
inventory AS (
    SELECT
          hi.company_id
        , hi.room_type AS room_type_id
        , SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count
        , SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms
        , BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    GROUP BY hi.company_id, hi.room_type
),
latest_line_status AS (
    SELECT
          bd.booking_line_id
        , ds.report_date
        , bd.system_date
        , bd.checkin_date
        , bd.checkout_date
        , bd.company_id
        , bd.room_type_id
        , bd.group_booking_name
        , bd.status AS final_status
        , bd.change_time
        , bd.house_use
        , bd.complementary
    FROM base_data bd
    JOIN date_series ds 
          ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
),
in_house AS (
    SELECT
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.group_booking_name
        , COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
      AND lls.checkin_date = lls.report_date
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.group_booking_name
),
yesterday_in_house AS (
    SELECT
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.group_booking_name
        , COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
      AND (lls.report_date - INTERVAL '1 day')
          BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.group_booking_name
),
expected_arrivals AS (
    SELECT 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.group_booking_name
        , COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.group_booking_name
),
expected_departures AS (
    SELECT
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.group_booking_name
        , COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.group_booking_name
),
master_keys AS (
    SELECT report_date, company_id, system_date, room_type_id,group_booking_name
      FROM in_house
    UNION
    SELECT report_date, company_id, system_date, room_type_id, group_booking_name
      FROM expected_arrivals
    UNION
    SELECT report_date, company_id, system_date, room_type_id,group_booking_name
      FROM expected_departures
    UNION
    SELECT report_date, company_id, system_date, room_type_id,group_booking_name
      FROM yesterday_in_house
),
final_report AS (
    SELECT
          mk.report_date
        , mk.system_date
        , mk.company_id
        , mk.room_type_id
        , mk.group_booking_name
        , CASE WHEN mk.report_date <= mk.system_date THEN
            ih.in_house_count
          ELSE
            GREATEST(
                COALESCE(yh.in_house_count, 0)
                + COALESCE(ea.expected_arrivals_count, 0)
                - COALESCE(ed.expected_departures_count, 0),
                0
            )
          END AS in_house_count
        , COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count
        , COALESCE(ed.expected_departures_count, 0) AS expected_departures_count
        , GREATEST(
            COALESCE(yh.in_house_count, 0)
            + COALESCE(ea.expected_arrivals_count, 0)
            - COALESCE(ed.expected_departures_count, 0),
            0
          ) AS expected_in_house
    FROM master_keys mk
    LEFT JOIN in_house ih
          ON mk.report_date = ih.report_date
         AND mk.company_id = ih.company_id
         AND mk.room_type_id = ih.room_type_id
         AND mk.group_booking_name= ih.group_booking_name
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
)
SELECT
      fr.report_date
    , fr.company_id
    , rc.name AS company_name
    , rtd.room_type_name AS room_type
    , COALESCE(jsonb_extract_path_text(fr.group_booking_name::jsonb, 'en_US'),'N/A') AS group_booking
    , SUM(fr.expected_in_house) AS expected_inhouse
FROM final_report fr
LEFT JOIN res_company rc 
       ON rc.id = fr.company_id
LEFT JOIN room_type_data rtd
       ON rtd.room_type_id = fr.room_type_id
WHERE fr.group_booking_name IS NOT NULL AND fr.company_id IN (SELECT company_id FROM company_ids)
GROUP BY
      fr.report_date
    , fr.company_id
    , rc.name
    , rtd.room_type_name
    , fr.group_booking_name
ORDER BY
      fr.report_date
    , rc.name
    , rtd.room_type_name
    , fr.group_booking_name;

        """
        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        # params = (from_date, to_date, get_company)
        self.env.cr.execute(query)
        # self.env.cr.execute(query, (get_company, get_company, get_company))
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
        records_to_create = []

        for result in results:
            try:
                # if result[1]:
                    
                #     company_id = result[1]
                #     if company_id != self.env.company.id:
                #         continue  
                #     # print(result[1])  
                # else:
                #     continue
                records_to_create.append({
                    'report_date': result[0],               # Date
                    'company_id': result[1],
                    'group_booking': result[4],             # group_booking_name
                    'room_type': result[3],                 # room_type_name
                    'expected_inhouse': int(result[5] or 0),# expected_in_house
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
