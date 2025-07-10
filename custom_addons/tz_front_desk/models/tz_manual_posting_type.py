from odoo import models, fields, api
from odoo.exceptions import UserError

class ManualPostingType(models.Model):
    _name = 'tz.manual.posting.type'
    _description = 'Manual Posting Type'

    name = fields.Char(string='Room')
    booking_id = fields.Many2one('room.booking', string='Booking')
    room_id = fields.Many2one('hotel.room', string='Room')
    group_booking_id = fields.Many2one('group.booking', string='Group Booking')
    dummy_id = fields.Many2one('tz.dummy.group', string='Dummy')
    partner_id = fields.Many2one('res.partner', string='Customer')
    checkin_date = fields.Date(string='Check-in')
    checkout_date = fields.Date(string='Check-out')
    adult_count = fields.Integer(string='Adults')
    child_count = fields.Integer(string='Children')
    infant_count = fields.Integer(string='Infants')
    rate_code = fields.Char(string='Rate Code')
    meal_pattern = fields.Char(string='Meal Pattern')
    state = fields.Char(string='State')
    company_id = fields.Many2one('res.company', string='Company')

    @api.model
    def generate_manual_postings(self):
        # 1. Ensure the view exists
        try:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW tz_manual_posting_types AS (
                    SELECT
                        ROW_NUMBER() OVER () AS id,
                        name,
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
                        company_id
                    FROM (
                        SELECT
                            COALESCE(NULLIF(hr.name ->> 'en_US', 'Unnamed'), rb.name) AS name,
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
                            rb.company_id
                        FROM room_booking rb
                        LEFT JOIN room_booking_line rbl ON rbl.booking_id = rb.id
                        LEFT JOIN hotel_room hr ON rbl.room_id = hr.id

                        UNION ALL

                        SELECT
                            COALESCE(gb.group_name ->> 'en_US', 'Unnamed') AS name,
                            (SELECT id FROM room_booking rb2 WHERE rb2.group_booking = gb.id LIMIT 1) AS booking_id,
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
                            gb.state::varchar,
                            gb.company_id
                        FROM group_booking gb
                        WHERE gb.status_code = 'confirmed'
                          AND gb.id IN (SELECT rb.group_booking FROM room_booking rb WHERE rb.group_booking IS NOT NULL)

                        UNION ALL

                        SELECT
                            dg.description::text AS name,
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
                            dg.company_id
                        FROM tz_dummy_group dg
                        WHERE dg.obsolete = FALSE
                    ) AS unified
                )
            """)
        except Exception as e:
            raise UserError(f"Failed to create view: {str(e)}")

        # 2. Read from the view
        try:
            self.env.cr.execute("SELECT * FROM tz_manual_posting_types")
            results = self.env.cr.dictfetchall()
        except Exception as e:
            raise UserError(f"Failed to read from view: {str(e)}")

        # 3. Create records in the model
        for row in results:
            domain = []

            # booking_id is present unless dummy_id has a value
            if row.get('dummy_id'):
                if row.get('dummy_id'):
                    domain.append(('dummy_id', '=', row['dummy_id']))
            else:
                if row.get('booking_id'):
                    domain.append(('booking_id', '=', row['booking_id']))
                if row.get('room_id'):
                    domain.append(('room_id', '=', row['room_id']))
                if row.get('group_booking_id'):
                    domain.append(('group_booking_id', '=', row['group_booking_id']))

            existing = self.search(domain, limit=1)

            if not existing:
                self.create({
                    'name': row.get('name'),
                    'booking_id': row.get('booking_id'),
                    'room_id': row.get('room_id'),
                    'group_booking_id': row.get('group_booking_id'),
                    'dummy_id': row.get('dummy_id'),
                    'partner_id': row.get('partner_id'),
                    'checkin_date': row.get('checkin_date'),
                    'checkout_date': row.get('checkout_date'),
                    'adult_count': row.get('adult_count'),
                    'child_count': row.get('child_count'),
                    'infant_count': row.get('infant_count'),
                    'rate_code': row.get('rate_code'),
                    'meal_pattern': row.get('meal_pattern'),
                    'state': row.get('state'),
                    'company_id': row.get('company_id'),
                })

        return True
