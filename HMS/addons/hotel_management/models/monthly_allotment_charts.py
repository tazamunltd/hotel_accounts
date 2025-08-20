from datetime import timedelta
from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class MonthlyAllotmentCharts(models.Model):
    _name = 'monthly.allotment.charts'
    _description = 'Monthly Allotment Charts'
    _inherit = ['mail.thread', 'mail.activity.mixin']



    report_date = fields.Date(string='Report Date', required=True,tracking=True)
    company_id = fields.Many2one('res.company',string='Hotel', required = True,tracking=True)
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
    def action_run_process_by_monthly_allotment(self):
        """Runs the monthly allotment process based on context and returns the action."""
        system_date = self.env.company.system_date.date()  # or fields.Date.today() if needed
        default_from_date = system_date
        default_to_date = system_date + timedelta(days=30)
        if self.env.context.get('filtered_date_range'):
            self.env["monthly.allotment.charts"].run_process_by_monthly_allotment()

            return {
                'name': _('Monthly Allotment Chart Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'monthly.allotment.charts',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref(
                        'hotel_management.view_monthly_allotment_charts_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management.view_monthly_allotment_charts_graph').id, 'graph'),
                    (self.env.ref(
                        'hotel_management.view_monthly_allotment_charts_pivot').id, 'pivot'),
                ],
                'target': 'current',
            }
        else:
            self.env["monthly.allotment.charts"].run_process_by_monthly_allotment(
                from_date=default_from_date,
                to_date=default_to_date
            )

            # 3) Show only records for that 30-day window by specifying a domain
            domain = [
                ('report_date', '>=', default_from_date),
                ('report_date', '<=', default_to_date),
            ]
            return {
                'name': _('Monthly Allotment Chart Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'monthly.allotment.charts',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref(
                        'hotel_management.view_monthly_allotment_charts_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management.view_monthly_allotment_charts_graph').id, 'graph'),
                    (self.env.ref(
                        'hotel_management.view_monthly_allotment_charts_pivot').id, 'pivot'),
                ],
                'domain': domain,  # Ensures no data is displayed
                'target': 'current',
            }
    
    @api.model
    def search_available_rooms(self, from_date, to_date):
        self.run_process_by_monthly_allotment(from_date, to_date)
        company_ids = [company.id for company in self.env.companies]
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
             ('company_id', 'in', company_ids)
        ]
        results = self.search(domain)
        return results.read([
            'report_date', 'room_type', 'source_of_business', 'inhouse', 'expected_inhouse'
        ])

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

    def run_process_by_monthly_allotment(self, from_date = None, to_date = None):
        """Execute the SQL query and process the results."""
        _logger.debug("Started run_process_by_monthly_allotment")
        
        # Delete existing records
        self.search([]).unlink()
        _logger.debug("Existing records deleted")
        if not from_date or not to_date:
            # Fallback if the method is called without parameters
            system_date = self.env.company.system_date.date()
            from_date = system_date
            to_date = system_date + timedelta(days=30)
        # system_date = self.env.company.system_date.date()
        # from_date = system_date - timedelta(days=7)
        # to_date = system_date + timedelta(days=7)
        # get_company = self.env.company.id
        company_ids = [company.id for company in self.env.companies]


#         """
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
        , sb.description AS source_of_business
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
	LEFT JOIN source_business sb ON rb.source_of_business = sb.id
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
        , bd.source_of_business
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
        , lls.source_of_business
        , COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
      AND lls.checkin_date = lls.report_date
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.source_of_business
),
yesterday_in_house AS (
    SELECT
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.source_of_business
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
        , lls.source_of_business
),
expected_arrivals AS (
    SELECT 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.source_of_business
        , COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.source_of_business
),
expected_departures AS (
    SELECT
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.source_of_business
        , COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.source_of_business
),
master_keys AS (
    SELECT report_date, company_id, system_date, room_type_id,source_of_business
      FROM in_house
    UNION
    SELECT report_date, company_id, system_date, room_type_id, source_of_business
      FROM expected_arrivals
    UNION
    SELECT report_date, company_id, system_date, room_type_id, source_of_business
      FROM expected_departures
    UNION
    SELECT report_date, company_id, system_date, room_type_id,source_of_business
      FROM yesterday_in_house
),
final_report AS (
    SELECT
          mk.report_date
        , mk.system_date
        , mk.company_id
        , mk.room_type_id
        , mk.source_of_business
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
         AND mk.source_of_business= ih.source_of_business
    LEFT JOIN yesterday_in_house yh
          ON mk.report_date = yh.report_date
         AND mk.company_id = yh.company_id
         AND mk.room_type_id = yh.room_type_id
         AND mk.source_of_business = yh.source_of_business
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
      fr.report_date
    , fr.company_id
    , rc.name AS company_name
    , rtd.room_type_name AS room_type
    , COALESCE(jsonb_extract_path_text(fr.source_of_business::jsonb, 'en_US'),'N/A') AS source_of_business
    , SUM(fr.expected_in_house) AS expected_in_house
FROM final_report fr
LEFT JOIN res_company rc 
       ON rc.id = fr.company_id
LEFT JOIN room_type_data rtd
       ON rtd.room_type_id = fr.room_type_id
WHERE fr.source_of_business IS NOT NULL
GROUP BY
      fr.report_date
    , fr.company_id
    , rc.name
    , rtd.room_type_name
    , fr.source_of_business
ORDER BY
      fr.report_date
    , rc.name
    , rtd.room_type_name
    , fr.source_of_business;

"""
        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        # params = (from_date, to_date, get_company)
        self.env.cr.execute(query)
        # self.env.cr.execute(query, (get_company, get_company, get_company))
        results = self.env.cr.fetchall()
        _logger.debug(f"Query executed successfully. {len(results)} results fetched")

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
                # Unpack the result tuple
                (
                    report_date,
                    company_id,
                    company_name,
                    # company_name,
                    room_type_name,
                    source_of_business,
                    expected_in_house
                ) = result

                record = {
                    'company_id': company_id,                     # Integer
                    'report_date': report_date,                   # Date
                    # 'company_name': company_name,
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
                _logger.debug(f"{len(records_to_create)} records created")
            except Exception as e:
                _logger.error(f"Error creating records: {str(e)}")
                raise
        else:
            _logger.debug("No records to create")
        _logger.debug("Completed run_process_by_monthly_allotment")