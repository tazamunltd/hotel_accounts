from odoo import models, fields, api, _
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)


class HotelRoomResult(models.Model):
    _name = 'hotel.room.result'
    _description = 'Hotel Room Result'

    company_name = fields.Char(string="company_name")
    room_type_name = fields.Char(string="room_type_name")

    room_type_id = fields.Integer(string='room_type_id', readonly=True)
    available_rooms = fields.Integer(string='available_rooms', readonly=True)

    # Fields definition
    report_date = fields.Date(string='Report Date', required=True)
    room_type = fields.Char(string='Room Type', required=True)
    company_id = fields.Many2one(
        'res.company', string='Hotel', required=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True)
    available = fields.Integer(string='Available', readonly=True)
    inhouse = fields.Integer(string='In-House', readonly=True)
    expected_arrivals = fields.Integer(string='Exp.Arrivals', readonly=True)
    expected_departures = fields.Integer(
        string='Exp.Departures', readonly=True)
    expected_inhouse = fields.Integer(string='Exp.In House', readonly=True)
    reserved = fields.Integer(string='Reserved', readonly=True)
    expected_occupied_rate = fields.Integer(
        string='Exp.Occupied Rate (%)', readonly=True)
    out_of_order = fields.Integer(string='Out of Order', readonly=True)
    overbook = fields.Integer(string='Overbook', readonly=True)
    free_to_sell = fields.Integer(string='Free to sell', readonly=True)
    sort_order = fields.Integer(string='Sort Order', readonly=True)
    house_use_count = fields.Integer(string='House Use Count', readonly=True)
    complementary_use_count = fields.Integer(
        string='Complementar Use Count', readonly=True)
    any_overbooking_allowed = fields.Boolean(
        string='Any Overbooking Allowed', readonly=True)
    total_overbooking_rooms = fields.Integer(
        string='total_overbooking_rooms', readonly=True)
    rooms_on_hold = fields.Integer(string='Rooms On Hold', readonly=True)
    out_of_service = fields.Integer(string='Out of Service', readonly=True)
    # in_progress = fields.Integer(string='In Progress', readonly=True)
    # dirty_rooms = fields.Integer(string='Dirty Rooms', readonly=True)

    @api.model
    def action_run_process_room_availability(self):
        """Runs the room availability process based on context."""
        system_date = self.env.company.system_date.date()  # or fields.Date.today() if needed
        default_from_date = system_date
        default_to_date = system_date + timedelta(days=30)

        if self.env.context.get('filtered_date_range'):
            self.env["hotel.room.result"].run_process_room_availability()

            return {
                'name': _('Room Availability Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'hotel.room.result',
                'view_mode': 'tree,pivot,graph',
                'views': [
                    (self.env.ref(
                        'hotel_management.view_hotel_room_result_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management.view_hotel_room_result_pivot').id, 'pivot'),
                    (self.env.ref(
                        'hotel_management.view_hotel_room_result_graph').id, 'graph'),
                ],
                'target': 'current',
            }
        else:
            # 2) If no filtered date range, run the process using the default dates
            self.env["hotel.room.result"].run_process_room_availability(
                from_date=default_from_date,
                to_date=default_to_date
            )

            # 3) Show only records for that 30-day window by specifying a domain
            domain = [
                ('report_date', '>=', default_from_date),
                ('report_date', '<=', default_to_date),
            ]
            return {
                'name': _('Room Availability Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'hotel.room.result',
                'view_mode': 'tree,pivot,graph',
                'views': [
                    (self.env.ref(
                        'hotel_management.view_hotel_room_result_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management.view_hotel_room_result_pivot').id, 'pivot'),
                    (self.env.ref(
                        'hotel_management.view_hotel_room_result_graph').id, 'graph'),
                ],
                # 'domain': [('id', '=', False)],  # Ensures no data is displayed
                'domain': domain,
                'target': 'current',
            }

    is_today = fields.Boolean(
        string='Is Today', compute='_compute_date_filters', store=False, search='_search_is_today')
    is_this_week = fields.Boolean(
        string='Is This Week', compute='_compute_date_filters', store=False, search='_search_is_this_week')
    is_this_month = fields.Boolean(
        string='Is This Month', compute='_compute_date_filters', store=False, search='_search_is_this_month')

    @api.depends('report_date')
    def _compute_date_filters(self):
        system_date = self.env.company.system_date.date()
        start_of_week = system_date - timedelta(days=system_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        start_of_month = system_date.replace(day=1)
        if system_date.month == 12:
            end_of_month = system_date.replace(
                year=system_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = system_date.replace(
                month=system_date.month + 1, day=1) - timedelta(days=1)

        for record in self:
            record.is_today = record.report_date == system_date
            record.is_this_week = start_of_week <= record.report_date <= end_of_week
            record.is_this_month = start_of_month <= record.report_date <= end_of_month

    def _search_is_today(self, operator, value):
        system_date = self.env.company.system_date.date()
        if operator == '=' and value:
            return [('report_date', '=', system_date)]
        elif operator == '!=' or not value:
            return [('report_date', '!=', system_date)]
        return []

    def _search_is_this_week(self, operator, value):
        system_date = self.env.company.system_date.date()
        start_of_week = system_date - timedelta(days=system_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        if operator == '=' and value:
            return [('report_date', '>=', start_of_week), ('report_date', '<=', end_of_week)]
        elif operator == '!=' or not value:
            return ['|', ('report_date', '<', start_of_week), ('report_date', '>', end_of_week)]
        return []

    def _search_is_this_month(self, operator, value):
        system_date = self.env.company.system_date.date()
        start_of_month = system_date.replace(day=1)
        if system_date.month == 12:
            end_of_month = system_date.replace(
                year=system_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = system_date.replace(
                month=system_date.month + 1, day=1) - timedelta(days=1)
        if operator == '=' and value:
            return [('report_date', '>=', start_of_month), ('report_date', '<=', end_of_month)]
        elif operator == '!=' or not value:
            return ['|', ('report_date', '<', start_of_month), ('report_date', '>', end_of_month)]
        return []

    @api.model
    def get_today_domain(self):
        """Get domain for today's records based on system date"""
        system_date = self.env.company.system_date.date()
        return [('report_date', '=', system_date)]

    @api.model
    def get_week_domain(self):
        """Get domain for this week's records based on system date"""
        system_date = self.env.company.system_date.date()
        start_of_week = system_date - timedelta(days=system_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return [('report_date', '>=', start_of_week), ('report_date', '<=', end_of_week)]

    @api.model
    def get_month_domain(self):
        """Get domain for this month's records based on system date"""
        system_date = self.env.company.system_date.date()
        start_of_month = system_date.replace(day=1)
        if system_date.month == 12:
            end_of_month = system_date.replace(
                year=system_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = system_date.replace(
                month=system_date.month + 1, day=1) - timedelta(days=1)
        return [('report_date', '>=', start_of_month), ('report_date', '<=', end_of_month)]

    
    @api.model
    def search_available_rooms(self, from_date, to_date):
        # print("SEARCH AVAILABLE ROOMS")
        """
        Search for available rooms based on the provided criteria.
        """
        self.run_process_room_availability(from_date, to_date)
        company_ids = [company.id for company in self.env.companies]
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
            ('company_id', 'in', company_ids)
        ]

        results = self.search(domain)

        return results.read([
            'report_date',
            'room_type',
            'total_rooms',
            'available',
            'inhouse',
            'expected_arrivals',
            'expected_departures',
            'expected_inhouse',
            'expected_occupied_rate',
            'out_of_order',
            'overbook',
            'free_to_sell',
            'company_id'
        ])

    @api.model
    def action_generate_results(self):
        """Generate and update room results."""
        try:
            # print("Generating room results")
            self.run_process_room_availability()
        except Exception as e:
            print(f"Error generating room results: {str(e)}")
            raise ValueError(f"Error generating room results: {str(e)}")

    def run_process_room_availability(self, from_date=None, to_date=None):
        """Execute the SQL query and process the results."""
        # print("Starting run_process")

        # Clear existing records
        self.env.cr.execute("DELETE FROM hotel_room_result")
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

        query = f"""
WITH RECURSIVE
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
        id               AS company_id, 
        system_date::date AS system_date,
        create_date::date AS create_date
    FROM res_company rc 
    WHERE rc.id IN (SELECT company_id FROM company_ids)
),
date_series AS (
    SELECT generate_series(
        (SELECT MIN(system_date) FROM system_date_company), 
        (SELECT to_date FROM parameters),
        INTERVAL '1 day'
    )::date AS report_date
),
base_data AS (
    SELECT
        rb.id                   AS booking_id,
        rb.parent_booking_id,
        rb.company_id,
        rb.checkin_date::date   AS checkin_date,
        rb.checkout_date::date  AS checkout_date,
        rbl.id                  AS booking_line_id,
        rbl.sequence,
        rbl.room_id,
        rbl.hotel_room_type     AS room_type_id,
        rbls.status,
        rbls.change_time,
        rb.house_use,
        rb.complementary
    FROM room_booking rb
    JOIN room_booking_line rbl ON rb.id = rbl.booking_id
    LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
    WHERE rb.company_id IN (SELECT company_id FROM company_ids)
      AND rb.active = TRUE
),
latest_line_status AS (
    SELECT DISTINCT ON (bd.booking_line_id, ds.report_date)
           bd.booking_line_id,
           ds.report_date,
           bd.checkin_date,
           bd.checkout_date,
           bd.company_id,
           bd.room_type_id,
           bd.status     AS final_status,
           bd.change_time,
           bd.house_use,
           bd.complementary
    FROM base_data bd
    JOIN date_series ds 
      ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
    ORDER BY
       bd.booking_line_id,
       ds.report_date DESC,
       bd.change_time DESC NULLS LAST
),
system_date_in_house AS (
    SELECT
        sdc.system_date AS report_date,
        sdc.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    JOIN system_date_company sdc ON sdc.company_id = lls.company_id
    WHERE lls.final_status = 'check_in'
      AND sdc.system_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
),
system_date_expected_arrivals AS (
    SELECT
        sdc.system_date AS report_date,
        sdc.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    JOIN system_date_company sdc ON sdc.company_id = lls.company_id
    WHERE lls.checkin_date = sdc.system_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
),
system_date_expected_departures AS (
    SELECT
        sdc.system_date AS report_date,
        sdc.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    JOIN system_date_company sdc ON sdc.company_id = lls.company_id
    WHERE lls.checkout_date = sdc.system_date
      AND lls.final_status IN ('check_in', 'confirmed', 'block')
    GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
),
system_date_base AS (
    SELECT
        sdc.system_date      AS report_date,
        sdc.company_id,
        rt.id                AS room_type_id,
        COALESCE(sdih.in_house_count,0)        AS in_house,
        COALESCE(sdea.expected_arrivals_count,0)   AS expected_arrivals,
        COALESCE(sded.expected_departures_count,0) AS expected_departures,
        (COALESCE(sdih.in_house_count,0)
         + COALESCE(sdea.expected_arrivals_count,0)
         - COALESCE(sded.expected_departures_count,0)
        ) AS expected_in_house
    FROM system_date_company sdc
    CROSS JOIN room_type rt
    LEFT JOIN system_date_in_house sdih 
      ON sdih.company_id   = sdc.company_id 
     AND sdih.room_type_id = rt.id 
     AND sdih.report_date  = sdc.system_date
    LEFT JOIN system_date_expected_arrivals sdea 
      ON sdea.company_id   = sdc.company_id 
     AND sdea.room_type_id = rt.id 
     AND sdea.report_date  = sdc.system_date
    LEFT JOIN system_date_expected_departures sded 
      ON sded.company_id   = sdc.company_id 
     AND sded.room_type_id = rt.id 
     AND sded.report_date  = sdc.system_date
),
expected_arrivals AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed','block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
expected_departures AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status IN ('check_in','confirmed','block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
recursive_in_house AS (
    SELECT 
        sdb.report_date,
        sdb.company_id,
        sdb.room_type_id,
        sdb.in_house,
        sdb.expected_in_house
    FROM system_date_base sdb
  UNION ALL
    SELECT
        ds.report_date,
        r.company_id,
        r.room_type_id,
        r.expected_in_house        AS in_house,
        (r.expected_in_house
         + COALESCE(ea.expected_arrivals_count,0)
         - COALESCE(ed.expected_departures_count,0)
        ) AS expected_in_house
    FROM recursive_in_house r
    JOIN date_series ds 
      ON ds.report_date = r.report_date + INTERVAL '1 day'
    LEFT JOIN expected_arrivals ea 
      ON ea.report_date   = ds.report_date 
     AND ea.company_id    = r.company_id 
     AND ea.room_type_id  = r.room_type_id
    LEFT JOIN expected_departures ed 
      ON ed.report_date   = ds.report_date 
     AND ed.company_id    = r.company_id 
     AND ed.room_type_id  = r.room_type_id
),
recursive_in_house_distinct AS (
    SELECT
        report_date,
        company_id,
        room_type_id,
        MAX(in_house)          AS in_house,
        MAX(expected_in_house) AS expected_in_house
    FROM recursive_in_house
    GROUP BY report_date, company_id, room_type_id
),
house_use_cte AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS house_use_count
    FROM latest_line_status lls
    WHERE lls.house_use = TRUE
      AND lls.final_status IN ('check_in','check_out')
      AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
complementary_use_cte AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS complementary_use_count
    FROM latest_line_status lls
    WHERE lls.complementary = TRUE
      AND lls.final_status IN ('check_in','check_out')
      AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
-- inventory AS (
    --     SELECT
    --         hi.company_id,
    --         hi.room_type AS room_type_id,
    --         COUNT(DISTINCT hr.id) AS total_room_count,
    --         SUM(COALESCE(hi.overbooking_rooms,0)) AS overbooking_rooms,
    --         BOOL_OR(COALESCE(hi.overbooking_allowed,false)) AS overbooking_allowed
    --     FROM hotel_inventory hi
    --     JOIN hotel_room hr
    --       ON hr.company_id = hi.company_id
    --      AND hr.room_type_name = hi.room_type
    --      AND hr.active = TRUE
    --     GROUP BY hi.company_id, hi.room_type
    -- )
	inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        COUNT(DISTINCT hr.id) AS total_room_count,
        SUM(DISTINCT COALESCE(hi.overbooking_rooms,0)) AS overbooking_rooms,
        BOOL_OR(COALESCE(hi.overbooking_allowed,false)) AS overbooking_allowed
    FROM hotel_inventory hi
    JOIN hotel_room hr
      ON hr.company_id = hi.company_id
     AND hr.room_type_name = hi.room_type
     AND hr.active = TRUE
    GROUP BY hi.company_id, hi.room_type
),
out_of_order AS (
    SELECT
        rt.id       AS room_type_id,
        hr.company_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS out_of_order_count
    FROM date_series ds
    JOIN out_of_order_management_front_desk ooo
      ON ds.report_date BETWEEN ooo.from_date AND ooo.to_date
    JOIN hotel_room hr
      ON hr.id = ooo.room_number
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
rooms_on_hold AS (
    SELECT
        rt.id       AS room_type_id,
        hr.company_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS rooms_on_hold_count
    FROM date_series ds
    JOIN rooms_on_hold_management_front_desk roh
      ON ds.report_date BETWEEN roh.from_date AND roh.to_date
    JOIN hotel_room hr
      ON hr.id = roh.room_number
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
out_of_service AS (
    SELECT
        rt.id       AS room_type_id,
        hr.company_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS out_of_service_count
    FROM date_series ds
    JOIN housekeeping_management hm
      ON hm.out_of_service = TRUE
     AND (hm.repair_ends_by IS NULL OR ds.report_date <= hm.repair_ends_by)
    JOIN hotel_room hr
      ON hr.room_type_name = hm.room_type
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
final_report AS (
    SELECT
        ds.report_date,
        rc.id               AS company_id,
        rc.name             AS company_name,
        rt.id               AS room_type_id,
        COALESCE(jsonb_extract_path_text(rt.room_type::jsonb,'en_US'),'N/A') AS room_type_name,
        COALESCE(inv.total_room_count,0)       AS total_rooms,
        COALESCE(inv.overbooking_rooms,0)      AS overbooking_rooms,
        COALESCE(inv.overbooking_allowed,false) AS overbooking_allowed,
        COALESCE(ooo.out_of_order_count,0)     AS out_of_order,
        COALESCE(roh.rooms_on_hold_count,0)    AS rooms_on_hold,
        COALESCE(oos.out_of_service_count,0)   AS out_of_service,
        COALESCE(ea.expected_arrivals_count,0)   AS expected_arrivals,
        COALESCE(ed.expected_departures_count,0)  AS expected_departures,
        COALESCE(hc.house_use_count,0)         AS house_use_count,
        COALESCE(cc.complementary_use_count,0)  AS complementary_use_count,
        (COALESCE(inv.total_room_count,0)
         - COALESCE(ooo.out_of_order_count,0)
         - COALESCE(roh.rooms_on_hold_count,0)
        )                                       AS available_rooms,
        COALESCE((
          SELECT in_house_count 
          FROM system_date_in_house sdi 
          WHERE sdi.company_id   = rc.id 
            AND sdi.room_type_id = rt.id 
            AND sdi.report_date  = ds.report_date
        ),0)                                    AS in_house
    FROM date_series ds
    LEFT JOIN res_company rc
      ON rc.id IN (SELECT company_id FROM company_ids)
    CROSS JOIN room_type rt
    INNER JOIN inventory inv
      ON inv.company_id   = rc.id
     AND inv.room_type_id = rt.id
    LEFT JOIN out_of_order ooo
      ON ooo.company_id   = rc.id
     AND ooo.room_type_id = rt.id
     AND ooo.report_date  = ds.report_date
    LEFT JOIN rooms_on_hold roh
      ON roh.company_id   = rc.id
     AND roh.room_type_id = rt.id
     AND roh.report_date  = ds.report_date
    LEFT JOIN out_of_service oos
      ON oos.company_id   = rc.id
     AND oos.room_type_id = rt.id
     AND oos.report_date  = ds.report_date
    LEFT JOIN expected_arrivals ea
      ON ea.company_id    = rc.id
     AND ea.room_type_id  = rt.id
     AND ea.report_date   = ds.report_date
    LEFT JOIN expected_departures ed
      ON ed.company_id    = rc.id
     AND ed.room_type_id  = rt.id
     AND ed.report_date   = ds.report_date
    LEFT JOIN house_use_cte hc
      ON hc.company_id    = rc.id
     AND hc.room_type_id  = rt.id
     AND hc.report_date   = ds.report_date
    LEFT JOIN complementary_use_cte cc
      ON cc.company_id    = rc.id
     AND cc.room_type_id  = rt.id
     AND cc.report_date   = ds.report_date
    LEFT JOIN system_date_company sdc
      ON sdc.company_id   = rc.id
    WHERE ds.report_date >= (SELECT from_date FROM parameters)
),
final_output AS (
    SELECT
      fr.report_date,
      fr.company_id,
      fr.company_name,
      fr.room_type_id,
      fr.room_type_name,
      SUM(fr.total_rooms)            AS total_rooms,
      BOOL_OR(fr.overbooking_allowed) AS any_overbooking_allowed,
      SUM(fr.overbooking_rooms)       AS total_overbooking_rooms,
      SUM(fr.out_of_order)            AS out_of_order,
      SUM(fr.rooms_on_hold)           AS rooms_on_hold,
      SUM(fr.out_of_service)          AS out_of_service,
      SUM(fr.expected_arrivals)       AS expected_arrivals,
      SUM(fr.expected_departures)     AS expected_departures,
      SUM(fr.house_use_count)         AS house_use_count,
      SUM(fr.complementary_use_count) AS complementary_use_count,
      SUM(fr.available_rooms)         AS available_rooms,
      rih.in_house                    AS in_house,
      rih.expected_in_house           AS expected_in_house,
      CASE 
        WHEN BOOL_OR(fr.overbooking_allowed) THEN
          CASE
            WHEN SUM(fr.available_rooms) < 0 
              OR SUM(fr.overbooking_rooms) < 0 
              OR rih.expected_in_house < 0 THEN 0
            ELSE GREATEST(
              0,
              SUM(fr.available_rooms)
--              + SUM(fr.overbooking_rooms)
              - rih.expected_in_house
            )
          END
        ELSE
          CASE
            WHEN SUM(fr.available_rooms) < 0 THEN 0
            ELSE GREATEST(
              0,
              SUM(fr.available_rooms)
              - rih.expected_in_house
            )
          END
      END                         AS free_to_sell,
      GREATEST(
        0,
        rih.expected_in_house
        - SUM(fr.available_rooms)
      )                             AS over_booked
    FROM final_report fr
    JOIN recursive_in_house_distinct rih
      ON fr.report_date    = rih.report_date
     AND fr.company_id     = rih.company_id
     AND fr.room_type_id   = rih.room_type_id
    WHERE fr.report_date >= (SELECT from_date FROM parameters)
    GROUP BY
      fr.report_date,
      fr.company_id,
      fr.company_name,
      fr.room_type_id,
      fr.room_type_name,
      rih.in_house,
      rih.expected_in_house
    ORDER BY
      fr.report_date,
      fr.company_name,
      fr.room_type_name
)
SELECT * FROM final_output;

"""

        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date), get_company)
        # params = (from_date, to_date, company_ids, company_ids)
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()

        records_to_create = []

        for row in results:
            # row is a tuple with indexes 0..19
            try:
                # Check if the company_id is present and matches the current company
                if row[1]:  # Assuming row[1] is the company_id
                    company_id = row[1]
                    # if company_id != self.env.company.id:
                    if company_id not in self.env.context.get('allowed_company_ids'):
                        continue
                else:
                    continue

                report_date = row[0]
                company_id = row[1]
                company_name = row[2]    # (not used directly, but available)
                room_type_id = row[3]    # (not used directly, but available)
                room_type_name = row[4]    # char/string like 'QUAD'
                total_rooms = row[5]
                any_overbooking_allowed = row[6]
                total_overbooking_rooms = row[7]
                out_of_order = row[8]
                rooms_on_hold = row[9]
                out_of_service = row[10]
                in_house = row[16]
                expected_arrivals = row[11]
                expected_departures = row[12]
                house_use_count = row[13]
                complementary_use_count = row[14]
                available_rooms = row[15]
                expected_in_house = row[17]
                free_to_sell = row[18]
                over_booked = row[19]

                # Only create records if there's a valid company_id or date, etc.
                if company_id and report_date:
                    records_to_create.append({
                        'report_date': report_date,
                        'company_id': company_id,
                        'room_type': room_type_name,  # This is a Char field

                        'total_rooms': int(total_rooms or 0),
                        'any_overbooking_allowed': bool(any_overbooking_allowed),
                        'total_overbooking_rooms': int(total_overbooking_rooms or 0),

                        'out_of_order': int(out_of_order or 0),
                        'rooms_on_hold': int(rooms_on_hold or 0),
                        'out_of_service': int(out_of_service or 0),

                        'inhouse': int(in_house or 0),
                        'expected_arrivals': int(expected_arrivals or 0),
                        'expected_departures': int(expected_departures or 0),
                        'house_use_count': int(house_use_count or 0),
                        'complementary_use_count': int(complementary_use_count or 0),
                        'expected_occupied_rate': int(int(expected_in_house or 0)/int(available_rooms or 1) * 100),
                        'available': int(available_rooms or 0),
                        'expected_inhouse': int(expected_in_house or 0),
                        'free_to_sell': int(free_to_sell or 0),

                        # 'reserved' was not actually returned by this query,
                        # so either remove it or set it to 0
                        'reserved': 0,

                        'overbook': int(over_booked or 0),
                    })
            except Exception as e:
                _logger.error(
                    f"Error processing record: {str(e)}, Data: {row}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.debug(f"{len(records_to_create)} records created")

        # _logger.debug("Completed run_process_room_availability")

        return

    def debug_room_results(self, company_id=None, report_date=None):
        """
        Comprehensive diagnostic method to print out room result records.

        :param company_id: Optional company ID to filter results
        :param report_date: Optional report date to filter results
        :return: Detailed debug information
        """
        domain = []
        if company_id:
            domain.append(('company_id', '=', company_id))
        if report_date:
            domain.append(('report_date', '=', report_date))

        results = self.search(domain)

        _logger.debug("Debug Room Results - Search Parameters:")
        _logger.debug("Company ID Filter: %s", company_id)
        _logger.debug("Report Date Filter: %s", report_date)
        _logger.debug("Total Matching Records: %s", len(results))

        for record in results:
            _logger.debug("Detailed Record:")
            _logger.debug("- Record ID: %s", record.id)
            _logger.debug("- Company: %s (ID: %s)",
                          record.company_id.name, record.company_id.id)
            _logger.debug("- Report Date: %s", record.report_date)
            _logger.debug("- Room Type: %s", record.room_type)
            _logger.debug("- Expected Arrivals: %s", record.expected_arrivals)
            _logger.debug("- Total Rooms: %s", record.total_rooms)
            _logger.debug("- Available Rooms: %s", record.available)
            _logger.debug("- In-House: %s", record.inhouse)
            _logger.debug("-------------------")

        return {
            'total_records': len(results),
            'records_details': [
                {
                    'id': r.id,
                    'company_name': r.company_id.name,
                    'company_id': r.company_id.id,
                    'report_date': str(r.report_date),
                    'expected_arrivals': r.expected_arrivals
                } for r in results
            ]
        }

    @api.model
    def get_expected_arrivals_for_dashboard(self, company_id, report_date):
        """
        Retrieve sum of expected arrivals for different room types for a specific date and company.

        :param company_id: Company ID to filter records
        :param report_date: Date for which expected arrivals are to be calculated
        :return: Sum of expected arrivals across all room types or 0

        Modification Date: 2025-01-12
        Modification Time: 21:47:58
        """
        try:
            # Search for all records matching company and date
            records = self.search([
                ('company_id', '=', company_id),
                ('report_date', '=', report_date)
            ])

            if records:
                # Sum the expected quantities across all matching records
                total_expected_arrivals = sum(
                    record.expected_arrivals for record in records)
                return total_expected_arrivals
            else:
                _logger.warning("No records found for given company and date")
                return 0
        except Exception as e:
            _logger.error("Error retrieving expected arrivals: %s", str(e))
            return 0

    @api.model
    def get_dashboard_room_metrics(self, company_id, report_date):
        """
        Retrieve aggregated dashboard metrics for rooms for a specific date and company.

        :param company_id: Company ID to filter records
        :param report_date: Date for which room metrics are to be calculated
        :return: Dictionary of aggregated room metrics

        Modification Date: 2025-01-12
        Modification Time: 22:40:00
        """
        try:
            # Search for all records matching company and date
            records = self.search([
                ('company_id', '=', company_id),
                ('report_date', '=', report_date)
            ])

            _logger.debug(
                f"Found {len(records)} records for company {company_id} on {report_date}")

            if not records:
                _logger.warning("No records found for given company and date")
                return {
                    'out_of_order': 0,
                    'rooms_on_hold': 0,
                    'out_of_service': 0,
                    'inhouse': 0,
                    'expected_arrivals': 0,
                    'expected_departures': 0,
                    'house_use_count': 0,
                    'complementary_use_count': 0,
                    'expected_occupied_rate': 0,
                    'available': 0,
                    'expected_inhouse': 0,
                    'free_to_sell': 0,
                    'total_rooms': 0
                }

            # Detailed logging for each record
            _logger.debug("Record Details:")
            for record in records:
                _logger.debug(f"Room Type: {record.room_type}, "
                              f"In-House: {record.inhouse}, "
                              f"Available: {record.available}, "
                              f"Expected In-House: {record.expected_inhouse}")

            # Calculate aggregated metrics
            metrics = {
                'out_of_order': sum(record.out_of_order for record in records),
                'rooms_on_hold': sum(record.rooms_on_hold for record in records),
                'out_of_service': sum(record.out_of_service for record in records),
                'inhouse': sum(record.inhouse for record in records),
                'expected_arrivals': sum(record.expected_arrivals for record in records),
                'expected_departures': sum(record.expected_departures for record in records),
                'house_use_count': sum(record.house_use_count for record in records),
                'complementary_use_count': sum(record.complementary_use_count for record in records),
                'available': sum(record.available for record in records),
                'expected_inhouse': sum(record.expected_inhouse for record in records),
                'free_to_sell': sum(record.free_to_sell for record in records),
                'total_rooms': sum(record.total_rooms for record in records)
            }

            # Log the final metrics
            _logger.debug(f"Aggregated Metrics: {metrics}")

            # Calculate expected occupied rate
            total_available_rooms = metrics['available'] or 1
            metrics['expected_occupied_rate'] = int(
                (metrics['expected_inhouse'] / total_available_rooms) * 100)

            return metrics

        except Exception as e:
            _logger.error(f"Error retrieving dashboard room metrics: {str(e)}")
            return {
                'out_of_order': 0,
                'rooms_on_hold': 0,
                'out_of_service': 0,
                'inhouse': 0,
                'expected_arrivals': 0,
                'expected_departures': 0,
                'house_use_count': 0,
                'complementary_use_count': 0,
                'expected_occupied_rate': 0,
                'available': 0,
                'expected_inhouse': 0,
                'free_to_sell': 0,
                'total_rooms': 0
            }

    @api.model
    def get_occupancy_history(self, company_id, days=7):
        """
        Get occupancy rate history for the last N days.

        Args:
            company_id (int): ID of the company
            days (int): Number of days of history to fetch (default: 7)

        Returns:
            dict: Dictionary containing dates and corresponding occupancy rates
        """
        try:
            end_date = fields.Date.today()
            start_date = end_date - timedelta(days=days)

            domain = [
                ('company_id', '=', company_id),
                ('report_date', '>=', start_date),
                ('report_date', '<=', end_date)
            ]

            results = self.search(domain, order='report_date asc')

            # Group results by date and calculate average occupancy rate
            dates = []
            rates = []

            for date in (start_date + timedelta(n) for n in range(days + 1)):
                day_results = results.filtered(lambda r: r.report_date == date)

                if day_results:
                    total_rooms = sum(day_results.mapped('total_rooms'))
                    occupied_rooms = sum(day_results.mapped('inhouse'))

                    # Calculate occupancy rate
                    rate = round((occupied_rooms / total_rooms * 100)
                                 if total_rooms else 0, 2)

                    dates.append(date.strftime('%Y-%m-%d'))
                    rates.append(rate)

            return {
                'dates': dates,
                'rates': rates
            }

        except Exception as e:
            _logger.error(f"Error fetching occupancy history: {str(e)}")
            return {
                'dates': [],
                'rates': []
            }

    @api.model
    def get_arrivals_departures_history(self, company_id, days=7):
        """
        Get arrivals and departures history for the last N days.

        Args:
            company_id (int): ID of the company
            days (int): Number of days of history to fetch (default: 7)

        Returns:
            dict: Dictionary containing dates, arrivals, and departures lists
        """
        try:
            end_date = fields.Date.today()
            start_date = end_date - timedelta(days=days)

            domain = [
                ('company_id', '=', company_id),
                ('report_date', '>=', start_date),
                ('report_date', '<=', end_date)
            ]

            results = self.search(domain, order='report_date asc')

            dates = []
            arrivals = []
            departures = []

            for date in (start_date + timedelta(n) for n in range(days + 1)):
                day_results = results.filtered(lambda r: r.report_date == date)

                dates.append(date.strftime('%Y-%m-%d'))
                arrivals.append(sum(day_results.mapped('expected_arrivals')))
                departures.append(
                    sum(day_results.mapped('expected_departures')))

            return {
                'dates': dates,
                'arrivals': arrivals,
                'departures': departures
            }

        except Exception as e:
            _logger.error(
                f"Error fetching arrivals vs departures history: {str(e)}")
            return {
                'dates': [],
                'arrivals': [],
                'departures': []
            }

    @api.model
    def get_room_type_distribution(self, company_id):
        """
        Get room distribution by room type.

        Args:
            company_id (int): ID of the company

        Returns:
            dict: Dictionary containing room types and their counts
        """
        try:
            today = fields.Date.today()
            domain = [
                ('company_id', '=', company_id),
                ('report_date', '=', today)
            ]

            results = self.search(domain)
            room_types = []
            counts = []

            for result in results:
                if result.room_type not in room_types:
                    room_types.append(result.room_type)
                    counts.append(result.total_rooms)

            return {
                'types': room_types,
                'counts': counts
            }

        except Exception as e:
            _logger.error(f"Error fetching room type distribution: {str(e)}")
            return {
                'types': [],
                'counts': []
            }

    @api.model
    def get_room_status_by_type(self, company_id):
        """
        Get room status breakdown by room type.

        Args:
            company_id (int): ID of the company

        Returns:
            dict: Dictionary containing room types and their status counts
        """
        try:
            today = fields.Date.today()
            domain = [
                ('company_id', '=', company_id),
                ('report_date', '=', today)
            ]

            results = self.search(domain)
            types = []
            available = []
            occupied = []
            reserved = []
            out_of_order = []

            for result in results:
                types.append(result.room_type)
                available.append(result.available)
                occupied.append(result.inhouse)
                reserved.append(result.reserved)
                out_of_order.append(result.out_of_order)

            return {
                'types': types,
                'available': available,
                'occupied': occupied,
                'reserved': reserved,
                'outOfOrder': out_of_order
            }

        except Exception as e:
            _logger.error(f"Error fetching room status by type: {str(e)}")
            return {
                'types': [],
                'available': [],
                'occupied': [],
                'reserved': [],
                'outOfOrder': []
            }

    @api.model
    def get_availability_timeline(self, company_id, days=30):
        """
        Get room availability timeline for the next N days.

        Args:
            company_id (int): ID of the company
            days (int): Number of days to look ahead (default: 30)

        Returns:
            dict: Dictionary containing dates, available rooms, and total rooms
        """
        try:
            start_date = fields.Date.today()
            end_date = start_date + timedelta(days=days)

            domain = [
                ('company_id', '=', company_id),
                ('report_date', '>=', start_date),
                ('report_date', '<=', end_date)
            ]

            results = self.search(domain, order='report_date asc')

            dates = []
            available = []
            total = []

            for date in (start_date + timedelta(n) for n in range(days + 1)):
                day_results = results.filtered(lambda r: r.report_date == date)

                dates.append(date.strftime('%Y-%m-%d'))
                available.append(sum(day_results.mapped('available')))
                total.append(sum(day_results.mapped('total_rooms')))

            return {
                'dates': dates,
                'available': available,
                'total': total
            }

        except Exception as e:
            _logger.error(f"Error fetching availability timeline: {str(e)}")
            return {
                'dates': [],
                'available': [],
                'total': []
            }
