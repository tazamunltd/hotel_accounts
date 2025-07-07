from odoo import models, fields, tools, api, _
from odoo.exceptions import UserError, ValidationError


class TzCheckout(models.Model):
    _name = 'tz.checkout'
    _description = 'FrontDesk Checkout'
    _auto = False
    _check_company_auto = True

    name = fields.Char('Room')
    all_name = fields.Char('Room', compute='_compute_name', store=False)
    booking_id = fields.Many2one('room.booking', string='Booking Id')
    group_booking_id = fields.Many2one('group.booking', string='Group Booking')
    dummy_id = fields.Many2one('tz.dummy.group', string='Dummy')
    room_id = fields.Many2one('hotel.room', string='Room')
    partner_id = fields.Many2one('res.partner', string='Guest')
    checkin_date = fields.Datetime('Check-in Date')
    checkout_date = fields.Datetime('Check-out Date')
    adult_count = fields.Integer('Adults')
    child_count = fields.Integer('Children')
    infant_count = fields.Integer('Infants')
    rate_code = fields.Many2one('rate.code', string='Rate Code')
    meal_pattern = fields.Many2one('meal.pattern', string='Meal Pattern')
    state = fields.Char('Status')
    company_id = fields.Many2one('res.company', string='Company')
    v_state = fields.Char('Status', compute='_compute_v_state', store=False)

    def _compute_name(self):
        for record in self:
            if record.partner_id:
                # Check if this is a group booking
                group_booking = self.env['group.booking'].search([
                    ('company', '=', record.partner_id.id),
                    ('status_code', '=', 'confirmed')
                ], limit=1)
                if group_booking:
                    # Handle group name which might be a translation dictionary
                    if isinstance(group_booking.group_name, dict):
                        record.all_name = group_booking.group_name.get('en_US', 'Unnamed')
                    else:
                        record.all_name = group_booking.group_name or 'Unnamed'
                elif record.room_id:
                    # Handle room name which might be a string or translation dict
                    if isinstance(record.room_id.name, dict):
                        record.all_name = record.room_id.name.get('en_US', 'Unnamed')
                    else:
                        record.all_name = record.room_id.name or 'Unnamed'
                else:
                    record.all_name = 'Unnamed'
            elif not record.room_id and not record.partner_id:
                # For dummy groups, use the name from the view
                record.all_name = record.name
            else:
                record.all_name = record.name

    def _compute_v_state(self):
        for record in self:
            # If it's from room_booking (has room_id)
            if record.room_id:
                record.v_state = 'In' if record.state == 'check_in' else 'Out'
            # If it's from group_booking (no room_id but has partner_id)
            elif record.partner_id:
                # We need to check if it's confirmed and has room bookings
                group_booking = self.env['group.booking'].search([
                    ('company', '=', record.partner_id.id),
                    ('status_code', '=', 'confirmed')
                ], limit=1)
                if group_booking and group_booking.room_booking_ids:
                    record.v_state = 'In'
                else:
                    record.v_state = 'Out'
            # If it's from dummy group (no room_id and no partner_id)
            else:
                record.v_state = 'In' if record.state == 'in' else 'Out'

    # @api.model
    # def init(self):
    #     tools.drop_view_if_exists(self.env.cr, self._table)
    #     self.env.cr.execute(f"""
    #                     CREATE OR REPLACE VIEW tz_checkout AS (
    #                         SELECT
    #                             ROW_NUMBER() OVER () AS id,
    #                             booking_id,
    #                             room_id,
    #                             group_booking_id,
    #                             dummy_id,
    #                             partner_id,
    #                             checkin_date,
    #                             checkout_date,
    #                             adult_count,
    #                             child_count,
    #                             infant_count,
    #                             rate_code,
    #                             meal_pattern,
    #                             state,
    #                             company_id,
    #                             name
    #                         FROM (
    #                             SELECT
    #                                 rb.id AS booking_id,
    #                                 hr.id AS room_id,
    #                                 rb.group_booking_id,
    #                                 NULL::integer AS dummy_id,
    #                                 rb.partner_id,
    #                                 rb.checkin_date,
    #                                 rb.checkout_date,
    #                                 rb.adult_count::integer,
    #                                 rb.child_count::integer,
    #                                 rb.infant_count::integer,
    #                                 rb.rate_code,
    #                                 rb.meal_pattern,
    #                                 rb.state,
    #                                 rb.company_id,
    #                                 COALESCE(hr.name ->> 'en_US', 'Unnamed') AS name
    #                             FROM room_booking rb
    #                             JOIN room_booking_line rbl ON rbl.booking_id = rb.id
    #                             JOIN hotel_room hr ON rbl.room_id = hr.id
    #                             WHERE rb.state = 'check_in' AND rb.group_booking IS NULL
    #
    #                             UNION ALL
    #
    #                             SELECT
    #                                 NULL AS booking_id,
    #                                 NULL AS room_id,
    #                                 gb.id AS group_booking_id,
    #                                 NULL::integer AS dummy_id,
    #                                 gb.company,
    #                                 gb.first_visit,
    #                                 gb.last_visit,
    #                                 gb.total_adult_count::integer,
    #                                 gb.total_child_count::integer,
    #                                 gb.total_infant_count::integer,
    #                                 gb.rate_code,
    #                                 gb.group_meal_pattern,
    #                                 gb.status_code::varchar,
    #                                 gb.company_id,
    #                                 COALESCE(gb.group_name ->> 'en_US', 'Unnamed')
    #                             FROM group_booking gb
    #                             WHERE gb.status_code = 'confirmed'
    #                               AND gb.id in (SELECT rb.group_booking from room_booking rb WHERE rb.state = 'check_in')
    #
    #                             UNION ALL
    #
    #                             SELECT
    #                                 NULL AS booking_id,
    #                                 NULL AS room_id,
    #                                 NULL AS group_booking_id,
    #                                 dg.id AS dummy_id,
    #                                 NULL,
    #                                 dg.start_date,
    #                                 dg.end_date,
    #                                 NULL,
    #                                 NULL,
    #                                 NULL,
    #                                 NULL,
    #                                 NULL,
    #                                 dg.state,
    #                                 dg.company_id,
    #                                 dg.description::text
    #                             FROM tz_dummy_group dg
    #                             WHERE dg.obsolete = FALSE
    #                         ) AS unified
    #                     );
    #             """)

    def search(self, domain, offset=0, limit=None, order=None):
        return super().search(domain, offset=offset, limit=limit, order=order)

    def generate_data(self, date_from=None, date_to=None, company_id=None):
        where_clauses = []
        if date_from:
            where_clauses.append(f"rb.checkin_date >= '{date_from}'")
        if date_to:
            where_clauses.append(f"rb.checkout_date <= '{date_to}'")
        if company_id:
            where_clauses.append(f"rb.company_id = {company_id}")

        where_filter = ' AND '.join(where_clauses) or 'TRUE'

        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
                        CREATE OR REPLACE VIEW tz_checkout AS (
                            SELECT
                                ROW_NUMBER() OVER () AS id,
                                booking_id,
                                room_id,
                                group_booking_id,
                                dummy_id,
                                partner_id,
                                checkin_date,
                                checkout_date,
                                adult_count,
                                child_count,
                                infant_count,
                                rate_code,
                                meal_pattern,
                                state,
                                company_id,
                                name
                            FROM (
                                SELECT
                                    rb.id AS booking_id,
                                    hr.id AS room_id,
                                    rb.group_booking_id,
                                    NULL::integer AS dummy_id,
                                    rb.partner_id,
                                    rb.checkin_date,
                                    rb.checkout_date,
                                    rb.adult_count::integer,
                                    rb.child_count::integer,
                                    rb.infant_count::integer,
                                    rb.rate_code,
                                    rb.meal_pattern,
                                    rb.state,
                                    rb.company_id,
                                    COALESCE(hr.name ->> 'en_US', 'Unnamed') AS name
                                FROM room_booking rb
                                JOIN room_booking_line rbl ON rbl.booking_id = rb.id
                                JOIN hotel_room hr ON rbl.room_id = hr.id
                                WHERE rb.state = 'check_in' AND rb.group_booking IS NULL

                                UNION ALL

                                SELECT
                                    NULL AS booking_id,
                                    NULL AS room_id,
                                    gb.id AS group_booking_id,
                                    NULL::integer AS dummy_id,
                                    gb.company,
                                    gb.first_visit,
                                    gb.last_visit,
                                    gb.total_adult_count::integer,
                                    gb.total_child_count::integer,
                                    gb.total_infant_count::integer,
                                    gb.rate_code,
                                    gb.group_meal_pattern,
                                    gb.status_code::varchar,
                                    gb.company_id,
                                    COALESCE(gb.group_name ->> 'en_US', 'Unnamed')
                                FROM group_booking gb
                                WHERE gb.status_code = 'confirmed'
                                  AND gb.id in (SELECT rb.group_booking from room_booking rb WHERE rb.state = 'check_in')

                                UNION ALL

                                SELECT
                                    NULL AS booking_id,
                                    NULL AS room_id,
                                    NULL AS group_booking_id,
                                    dg.id AS dummy_id,
                                    NULL,
                                    dg.start_date,
                                    dg.end_date,
                                    NULL,
                                    NULL,
                                    NULL,
                                    NULL,
                                    NULL,
                                    dg.state,
                                    dg.company_id,
                                    dg.description::text
                                FROM tz_dummy_group dg
                                WHERE dg.obsolete = FALSE
                            ) AS unified
                        );
                """)
