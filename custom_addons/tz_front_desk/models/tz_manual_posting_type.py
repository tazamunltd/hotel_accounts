from odoo import models, fields, tools, api
from odoo.exceptions import UserError

class ManualPostingType(models.Model):
    _name = 'tz.manual.posting.type'
    _description = 'Manual Posting Type'

    name = fields.Char(string='Room')
    booking_id = fields.Many2one('room.booking', string='Booking')
    room_id = fields.Many2one('hotel.room', string='Room')
    group_booking_id = fields.Many2one('group.booking', string='Group Booking')
    dummy_id = fields.Many2one('tz.dummy.group', string='Dummy')
    folio_id = fields.Many2one('tz.master.folio', string="Master Folio")
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
        current_company_id = self.env.company.id

        # 1. Create or replace the SQL view
        try:
            tools.drop_view_if_exists(self.env.cr, 'tz_manual_posting_types')
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW tz_manual_posting_types AS (
                     SELECT
                    ROW_NUMBER() OVER () AS id,
                    name,
                    booking_id,
                    room_id,
                    group_booking_id,
                    dummy_id,
                    folio_id,
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
                        COALESCE(hr.name ->> 'en_US', rb.name) AS name,
                        rb.id AS booking_id,
                        hr.id AS room_id,
                        NULL::integer AS group_booking_id,
                        NULL::integer AS dummy_id,
                        folio.id AS folio_id,
                        rb.partner_id,
                        rb.checkin_date,
                        rb.checkout_date,
                        rb.adult_count::integer,
                        rb.child_count::integer,
                        rb.infant_count::integer,
                        rb.rate_code::varchar,
                        rb.meal_pattern::varchar,
                        rb.state::varchar,
                        rb.company_id
                    FROM room_booking rb
                    JOIN room_booking_line rbl ON rbl.booking_id = rb.id
                    JOIN hotel_room hr ON rbl.room_id = hr.id
                    LEFT JOIN tz_master_folio folio ON folio.room_id = rbl.room_id
                    WHERE rb.group_booking IS NULL AND rb.state = 'check_in' AND rb.company_id = %s

                    UNION ALL

                    SELECT
                        COALESCE(gb.group_name ->> 'en_US', 'Unnamed') AS name,
                        NULL::integer AS booking_id,
                        NULL::integer AS room_id,
                        gb.id AS group_booking_id,
                        NULL::integer AS dummy_id,
                        folio.id AS folio_id,
                        gb.company AS partner_id,
                        gb.first_visit AS checkin_date,
                        gb.last_visit AS checkout_date,
                        gb.total_adult_count::integer,
                        gb.total_child_count::integer,
                        gb.total_infant_count::integer,
                        gb.rate_code::varchar,
                        gb.group_meal_pattern::varchar,
                        gb.state::varchar,
                        gb.company_id
                    FROM group_booking gb
                    LEFT JOIN tz_master_folio folio ON folio.group_id = gb.id
                    WHERE gb.status_code = 'confirmed' AND gb.company_id = %s
                      AND EXISTS (
                          SELECT 1 FROM room_booking rb
                          WHERE rb.group_booking = gb.id AND rb.state = 'check_in'
                      )

                    UNION ALL

                    SELECT
                        dg.description::text AS name,
                        NULL::integer AS booking_id,
                        NULL::integer AS room_id,
                        NULL::integer AS group_booking_id,
                        dg.id AS dummy_id,
                        folio.id AS folio_id,
                        dg.partner_id,
                        dg.start_date AS checkin_date,
                        dg.end_date AS checkout_date,
                        NULL::integer AS adult_count,
                        NULL::integer AS child_count,
                        NULL::integer AS infant_count,
                        NULL::varchar AS rate_code,
                        NULL::varchar AS meal_pattern,
                        dg.state::varchar,
                        dg.company_id
                    FROM tz_dummy_group dg
                    LEFT JOIN tz_master_folio folio ON folio.dummy_id = dg.id
                    WHERE dg.obsolete = FALSE AND dg.company_id = %s
                ) AS unified
                );
            """, (current_company_id, current_company_id, current_company_id))
        except Exception as e:
            raise UserError(f"Failed to create view: {str(e)}")

        # 2. Read from the view
        try:
            self.env.cr.execute("SELECT * FROM tz_manual_posting_types")
            rows = self.env.cr.dictfetchall()
        except Exception as e:
            raise UserError(f"Failed to read from view: {str(e)}")

        # 3. Function to get folio_id from domain
        def get_folio_id(booking_id=None, room_id=None, group_booking_id=None, dummy_id=None, company_id=None):
            """Helper function to reliably get folio_id from domain parameters"""
            domain = []

            if booking_id and room_id:
                # For regular bookings - search folios that have this booking_id in their booking_ids
                domain = [('booking_ids', '=', booking_id)]

                # Also include room_id in search if needed
                if room_id:
                    domain.append(('room_id', '=', room_id))

            elif group_booking_id:
                # For group bookings - use the group_id field
                domain = [('group_id', '=', group_booking_id)]
            elif dummy_id:
                # For dummy groups - use the dummy_id field
                domain = [('dummy_id', '=', dummy_id)]

            if domain and company_id:
                domain.append(('company_id', '=', company_id))

            if domain:
                folio = self.env['tz.master.folio'].search(domain, limit=1)
                return folio.id if folio else False
            return False

        # 4. Process each row - create or update
        for row in rows:
            # Build domain based on the key fields
            domain = []
            if row.get('booking_id'):
                domain.append(('booking_id', '=', row['booking_id']))
            if row.get('room_id'):
                domain.append(('room_id', '=', row['room_id']))
            if row.get('group_booking_id'):
                domain.append(('group_booking_id', '=', row['group_booking_id']))
            if row.get('dummy_id'):
                domain.append(('dummy_id', '=', row['dummy_id']))

            # Add company filter
            domain.append(('company_id', '=', current_company_id))

            # Get folio_id - first try from row, then from lookup function
            folio_id = row.get('folio_id')
            if not folio_id:
                folio_id = get_folio_id(
                    booking_id=row.get('booking_id'),
                    room_id=row.get('room_id'),
                    group_booking_id=row.get('group_booking_id'),
                    dummy_id=row.get('dummy_id'),
                    company_id=current_company_id
                )

            # Prepare values for create/update
            values = {
                'name': row.get('name'),
                'folio_id': folio_id,  # Use the validated folio_id
                'partner_id': row.get('partner_id'),
                'checkin_date': row.get('checkin_date'),
                'checkout_date': row.get('checkout_date'),
                'adult_count': row.get('adult_count') or 0,
                'child_count': row.get('child_count') or 0,
                'infant_count': row.get('infant_count') or 0,
                'rate_code': row.get('rate_code'),
                'meal_pattern': row.get('meal_pattern'),
                'state': row.get('state'),
            }

            # Find existing record
            existing = self.search(domain, limit=1)

            if existing:
                # Update existing record
                existing.write(values)
            else:
                # Create new record with all values including the domain fields
                values.update({
                    'booking_id': row.get('booking_id'),
                    'room_id': row.get('room_id'),
                    'group_booking_id': row.get('group_booking_id'),
                    'dummy_id': row.get('dummy_id'),
                    'company_id': current_company_id,
                })
                self.create(values)

        return True

    @api.model
    def generate_manual_postingsXX(self):
        current_company_id = self.env.company.id

        # 1. Create or replace the SQL view
        try:
            tools.drop_view_if_exists(self.env.cr, 'tz_manual_posting_types')
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW tz_manual_posting_types AS (
                    SELECT
                        ROW_NUMBER() OVER () AS id,
                        name,
                        booking_id,
                        room_id,
                        group_booking_id,
                        dummy_id,
                        folio_id,
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
                            COALESCE(hr.name ->> 'en_US', rb.name) AS name,
                            rb.id AS booking_id,
                            hr.id AS room_id,
                            NULL::integer AS group_booking_id,
                            NULL::integer AS dummy_id,
                            folio.id AS folio_id,
                            rb.partner_id,
                            rb.checkin_date,
                            rb.checkout_date,
                            rb.adult_count::integer,
                            rb.child_count::integer,
                            rb.infant_count::integer,
                            rb.rate_code::varchar,
                            rb.meal_pattern::varchar,
                            rb.state::varchar,
                            rb.company_id
                        FROM room_booking rb
                        JOIN room_booking_line rbl ON rbl.booking_id = rb.id
                        JOIN hotel_room hr ON rbl.room_id = hr.id
                        LEFT JOIN tz_master_folio folio ON folio.room_id = rbl.room_id
                        WHERE rb.group_booking IS NULL AND rb.state = 'check_in' AND rb.company_id = %s

                        UNION ALL

                        SELECT
                            COALESCE(gb.group_name ->> 'en_US', 'Unnamed') AS name,
                            NULL::integer AS booking_id,
                            NULL::integer AS room_id,
                            gb.id AS group_booking_id,
                            NULL::integer AS dummy_id,
                            folio.id AS folio_id,
                            gb.company AS partner_id,
                            gb.first_visit AS checkin_date,
                            gb.last_visit AS checkout_date,
                            gb.total_adult_count::integer,
                            gb.total_child_count::integer,
                            gb.total_infant_count::integer,
                            gb.rate_code::varchar,
                            gb.group_meal_pattern::varchar,
                            gb.state::varchar,
                            gb.company_id
                        FROM group_booking gb
                        LEFT JOIN tz_master_folio folio ON folio.group_id = gb.id
                        WHERE gb.status_code = 'confirmed' AND gb.company_id = %s
                          AND EXISTS (
                              SELECT 1 FROM room_booking rb
                              WHERE rb.group_booking = gb.id AND rb.state = 'check_in'
                          )

                        UNION ALL

                        SELECT
                            dg.description::text AS name,
                            NULL::integer AS booking_id,
                            NULL::integer AS room_id,
                            NULL::integer AS group_booking_id,
                            dg.id AS dummy_id,
                            folio.id AS folio_id,
                            dg.partner_id,
                            dg.start_date AS checkin_date,
                            dg.end_date AS checkout_date,
                            NULL::integer AS adult_count,
                            NULL::integer AS child_count,
                            NULL::integer AS infant_count,
                            NULL::varchar AS rate_code,
                            NULL::varchar AS meal_pattern,
                            dg.state::varchar,
                            dg.company_id
                        FROM tz_dummy_group dg
                        LEFT JOIN tz_master_folio folio ON folio.dummy_id = dg.id
                        WHERE dg.obsolete = FALSE AND dg.company_id = %s
                    ) AS unified
                );
            """, (current_company_id, current_company_id, current_company_id))
        except Exception as e:
            raise UserError(f"Failed to create view: {str(e)}")

        # 2. Read from the view
        try:
            self.env.cr.execute("SELECT * FROM tz_manual_posting_types")
            rows = self.env.cr.dictfetchall()
        except Exception as e:
            raise UserError(f"Failed to read from view: {str(e)}")

        # 3. Process each row - create or update
        for row in rows:
            # Build domain based on the key fields
            domain = [('company_id', '=', current_company_id)]

            if row.get('booking_id'):
                domain.append(('booking_id', '=', row['booking_id']))
            if row.get('room_id'):
                domain.append(('room_id', '=', row['room_id']))
            if row.get('group_booking_id'):
                domain.append(('group_booking_id', '=', row['group_booking_id']))
            if row.get('dummy_id'):
                domain.append(('dummy_id', '=', row['dummy_id']))

            # Prepare values for create/update
            values = {
                'name': row.get('name'),
                'folio_id': row.get('folio_id'),
                'partner_id': row.get('partner_id'),
                'checkin_date': row.get('checkin_date'),
                'checkout_date': row.get('checkout_date'),
                'adult_count': row.get('adult_count') or 0,
                'child_count': row.get('child_count') or 0,
                'infant_count': row.get('infant_count') or 0,
                'rate_code': row.get('rate_code'),
                'meal_pattern': row.get('meal_pattern'),
                'state': row.get('state'),
            }

            # Find existing record
            existing = self.search(domain, limit=1)

            if existing:
                # Update existing record
                existing.write(values)
            else:
                # Create new record with all values including the domain fields
                values.update({
                    'booking_id': row.get('booking_id'),
                    'room_id': row.get('room_id'),
                    'group_booking_id': row.get('group_booking_id'),
                    'dummy_id': row.get('dummy_id'),
                    'company_id': current_company_id,
                })
                self.create(values)

        return True

    @api.model
    def generate_manual_postingsX(self):
        # 0. First clear existing records to avoid duplicates
        # self.search([]).unlink()

        # 1. Create the view with optimized queries
        try:
            tools.drop_view_if_exists(self.env.cr, 'tz_manual_posting_types')
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW tz_manual_posting_types AS (
                    SELECT
                        ROW_NUMBER() OVER () AS id,
                        name,
                        booking_id,
                        room_id,
                        group_booking_id,
                        dummy_id,
                        folio_id,
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
                        -- Optimized Room Booking query
                        SELECT
                            COALESCE(NULLIF(hr.name ->> 'en_US', 'Unnamed'), rb.name) AS name,
                            rb.id AS booking_id,
                            hr.id AS room_id,
                            rb.group_booking_id,
                            NULL::integer AS dummy_id,
                            folio.id AS folio_id,
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
                        LEFT JOIN tz_master_folio folio ON folio.room_id = rbl.room_id
                        WHERE rb.group_booking IS NULL
                        AND rb.id IS NOT NULL  -- Ensure we have a booking ID

                        UNION ALL

                        -- Optimized Group Booking query
                        SELECT
                            COALESCE(gb.group_name ->> 'en_US', 'Unnamed') AS name,
                            rb.id AS booking_id,  -- Changed from subquery to join
                            NULL AS room_id,
                            gb.id AS group_booking_id,
                            NULL::integer AS dummy_id,
                            folio.id AS folio_id,
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
                        LEFT JOIN room_booking rb ON rb.group_booking = gb.id AND rb.id IS NOT NULL
                        LEFT JOIN tz_master_folio folio ON folio.group_id = gb.id
                        WHERE gb.status_code = 'confirmed'
                        AND EXISTS (
                            SELECT 1 FROM room_booking
                            WHERE group_booking = gb.id
                        )

                        UNION ALL

                        -- Dummy Group (already optimized)
                        SELECT
                            dg.description::text AS name,
                            NULL AS booking_id,
                            NULL AS room_id,
                            NULL AS group_booking_id,
                            dg.id AS dummy_id,
                            folio.id AS folio_id,
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
                        LEFT JOIN tz_master_folio folio ON folio.dummy_id = dg.id
                        WHERE dg.obsolete = FALSE
                    ) AS unified
                );
            """)
        except Exception as e:
            raise UserError(f"Failed to create view: {str(e)}")

        # 2. Batch read and process records
        try:
            # Use server-side cursor for large datasets
            self.env.cr.execute("SELECT * FROM tz_manual_posting_types")

            # Prepare batch create
            batch_size = 1000
            records_to_create = []

            while True:
                rows = self.env.cr.dictfetchmany(batch_size)
                if not rows:
                    break

                for row in rows:
                    records_to_create.append({
                        'name': row.get('name'),
                        'booking_id': row.get('booking_id'),
                        'room_id': row.get('room_id'),
                        'group_booking_id': row.get('group_booking_id'),
                        'dummy_id': row.get('dummy_id'),
                        'folio_id': row.get('folio_id'),
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

                # Batch create records
                if records_to_create:
                    self.create(records_to_create)
                    records_to_create = []

        except Exception as e:
            raise UserError(f"Failed to process records: {str(e)}")

        return True

