from odoo import models, fields, tools, api, _
from odoo.exceptions import UserError, ValidationError


class TzCheckout(models.Model):
    _name = 'tz.checkout'
    _description = 'FrontDesk Checkout'
    _auto = False
    _check_company_auto = True

    name = fields.Char('Room')
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

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
                CREATE OR REPLACE VIEW {self._table} AS (
                    SELECT
                        ROW_NUMBER() OVER () AS id,
                        room_id,
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
                        -- 1. Room Booking Records
                        SELECT
                            hr.id AS room_id,
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
                    
                        UNION ALL
                    
                        -- 2. Group Booking Records (filtered by confirmed status and room_booking state check_in)
                        SELECT
                            NULL,
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
                          AND EXISTS (
                              SELECT 1 FROM room_booking rb
                              WHERE rb.group_booking_id = gb.id
                                AND rb.state = 'check_in'
                          )
                    
                        UNION ALL
                    
                        -- 3. Dummy Group Data
                        SELECT
                            NULL,
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

    def search(self, domain, offset=0, limit=None, order=None, count=False):
        lang = self.env.context.get('lang', 'en_US')
        company_id = self.env.company.id

        # Add domain filters
        domain += [('company_id', '=', company_id)]
        return super().search(domain, offset=offset, limit=limit, order=order, count=count)




