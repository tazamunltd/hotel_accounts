from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ManualPostingRoom(models.Model):
    _name = 'tz.manual.posting.room'
    _auto = False
    _description = 'Manual Posting Room'

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
    company_id = fields.Many2one('res.company', string='Company')
    state = fields.Selection(selection=[
        ('confirmed', 'Confirmed'),
        ('no_show', 'No Show'),
        ('block', 'Block'),
        ('check_in', 'Check In'),
        ('dummy', 'Dummy'),
        ('posted', 'Posted'),
    ], string='State')

    def _create_or_replace_view(self):
        self.env.cr.execute("DROP MATERIALIZED VIEW IF EXISTS tz_manual_posting_room CASCADE")

        # Get the company ID first
        company_id = self.env.company.id

        # Use string formatting to insert the company_id directly into the query
        query = f"""
            CREATE MATERIALIZED VIEW tz_manual_posting_room AS (
                SELECT
                    (rb.id * 10 + 1) AS id,
                    COALESCE(NULLIF(hr.name ->> 'en_US', 'Unnamed'), rb.name) AS name,
                    rb.id AS booking_id,
                    hr.id AS room_id,
                    rb.group_booking_id,
                    NULL::integer AS dummy_id,
                    mf.id AS folio_id,
                    rb.partner_id,
                    rb.checkin_date,
                    rb.checkout_date,
                    rb.adult_count::integer,
                    rb.child_count::integer,
                    rb.infant_count::integer,
                    rb.rate_code,
                    rb.meal_pattern,
                    rb.company_id,
                    rb.checkout_date AS last_visit_date,
                    rb.checkout_date AS end_date,
                    rb.state AS state
                FROM room_booking rb
                LEFT JOIN room_booking_line rbl ON rbl.booking_id = rb.id
                LEFT JOIN hotel_room hr ON rbl.room_id = hr.id
                LEFT JOIN tz_master_folio mf ON mf.room_id = rbl.room_id 
                WHERE rb.company_id = {company_id}
                  AND rb.state IN ('confirmed', 'no_show', 'block', 'check_in')

                UNION ALL

                SELECT
                    (gb.id * 10 + 2) AS id,
                    COALESCE(gb.group_name ->> 'en_US', 'Unnamed') AS name,
                    (SELECT id FROM room_booking rb2 WHERE rb2.group_booking = gb.id AND rb2.state != 'check_out' LIMIT 1) AS booking_id,
                    NULL AS room_id,
                    gb.id AS group_booking_id,
                    NULL::integer AS dummy_id,
                    mf.id AS folio_id,
                    gb.company,
                    gb.first_visit,
                    gb.last_visit,
                    gb.total_adult_count::integer,
                    gb.total_child_count::integer,
                    gb.total_infant_count::integer,
                    gb.rate_code,
                    gb.group_meal_pattern,
                    gb.company_id,
                    gb.last_visit AS last_visit_date,
                    gb.last_visit AS end_date,
                    (SELECT rb3.state FROM room_booking rb3 WHERE rb3.group_booking = gb.id AND rb3.state != 'check_out' LIMIT 1) AS state
                FROM group_booking gb
                LEFT JOIN tz_master_folio mf ON mf.group_id = gb.id  
                WHERE gb.status_code = 'confirmed'
                  AND gb.id IN (
                      SELECT rb.group_booking FROM room_booking rb
                      WHERE rb.group_booking IS NOT NULL 
                        AND rb.company_id = {company_id}
                        AND rb.state IN ('confirmed', 'no_show', 'block', 'check_in')
                  )
                  AND gb.company_id = {company_id}

                UNION ALL

                SELECT
                    (dg.id * 10 + 3) AS id,
                    dg.description::text AS name,
                    NULL AS booking_id,
                    NULL AS room_id,
                    NULL AS group_booking_id,
                    dg.id AS dummy_id,
                    mf.id AS folio_id,
                    NULL,
                    dg.start_date,
                    dg.end_date,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    dg.company_id,
                    dg.end_date AS last_visit_date,
                    dg.end_date AS end_date,
                    'dummy' AS state
                FROM tz_dummy_group dg
                LEFT JOIN tz_master_folio mf ON mf.dummy_id = dg.id  
                WHERE dg.obsolete = FALSE
                  AND dg.company_id = {company_id}
            )
        """

        self.env.cr.execute(query)

        # Refresh the view immediately after creation
        self.env.cr.execute("REFRESH MATERIALIZED VIEW tz_manual_posting_room")

    def _setup_change_triggers(self):
        """Setup automatic refresh triggers on source tables"""
        try:
            # Create triggers on all source tables
            for table in ['room_booking', 'group_booking', 'tz_dummy_group', 'hotel_room', 'tz_master_folio']:
                try:
                    # First drop the trigger if it exists
                    self.env.cr.execute(f"""
                        DROP TRIGGER IF EXISTS tz_manual_posting_room_refresh_trigger ON {table};
                    """)
                    # Then create the new trigger
                    self.env.cr.execute(f"""
                        CREATE TRIGGER tz_manual_posting_room_refresh_trigger
                        AFTER INSERT OR UPDATE OR DELETE ON {table}
                        FOR EACH STATEMENT EXECUTE FUNCTION tz_refresh_manual_posting_room();
                    """)
                except Exception as trigger_error:
                    _logger.warning("Failed to create trigger on %s: %s", table, str(trigger_error))
                    continue

            _logger.info("Successfully created all refresh triggers")
        except Exception as e:
            _logger.error("Failed to setup change triggers: %s", str(e))
            raise UserError(_("Failed to setup automatic refresh triggers. Check logs for details."))

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Ensure fresh data when dropdown is opened"""
        self.refresh_view()
        return super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)

    def refresh_view(self):
        """Public method to manually refresh the view and sync type model"""
        self._create_or_replace_view()
        self.env['tz.manual.posting.type'].sync_with_materialized_view()
        return True


class ManualPostingType(models.Model):
    """Replacement for the cache model with state synchronization"""
    _name = 'tz.manual.posting.type'
    _description = 'Manual Posting Type'

    source_id = fields.Integer(string="Source ID", index=True)
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
    company_id = fields.Many2one('res.company', string='Company')

    state = fields.Selection(selection=[
        ('confirmed', 'Confirmed'),
        ('no_show', 'No Show'),
        ('block', 'Block'),
        ('check_in', 'Check In'),
        ('dummy', 'Dummy'),
        ('posted', 'Posted'),
    ], string='State')

    def sync_with_materialized_view(self):
        """Sync with the materialized view using ORM."""
        company_id = self.env.company.id

        # Fetch all relevant rows from the materialized view
        view_records = self.env['tz.manual.posting.room'].search([
            ('company_id', '=', company_id),
        ])

        room_type = self.env['tz.manual.posting.type']

        for view in view_records:

            domain = [
                ('source_id', '=', view.id),
                ('booking_id', '=', view.booking_id.id if view.booking_id else False),
            ]

            existing = room_type.search(domain, limit=1)


            vals = {
                'source_id': view.id,
                'name': view.name,
                'booking_id': view.booking_id.id,
                'room_id': view.room_id.id if view.room_id else False,
                'group_booking_id': view.group_booking_id.id if view.group_booking_id else False,
                'dummy_id': view.dummy_id.id if view.dummy_id else False,
                'folio_id': view.folio_id.id if view.folio_id else False,
                'partner_id': view.partner_id.id if view.partner_id else False,
                'checkin_date': view.checkin_date,
                'checkout_date': view.checkout_date,
                'adult_count': view.adult_count,
                'child_count': view.child_count,
                'infant_count': view.infant_count,
                'rate_code': view.rate_code,
                'meal_pattern': view.meal_pattern,
                'company_id': company_id,
                'state': view.state,
            }

            if existing:
                existing.write(vals)
            else:
                room_type.create(vals)

        _logger.info("Manual posting type successfully synced with materialized view for company_id %s", company_id)


