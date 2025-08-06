from odoo import models, fields, tools, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

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
    folio_id = fields.Many2one('tz.master.folio', string="Master Folio")

    def create_or_replace_view(self):
        self.env.cr.execute("DROP MATERIALIZED VIEW IF EXISTS tz_checkout CASCADE")

        # Get the company ID first
        company_id = self.env.company.id

        # Use string formatting to insert the company_id directly into the query
        query = f"""
            CREATE MATERIALIZED VIEW tz_checkout AS (
                SELECT
                    (rb.id * 10 + 1) AS id,
                    COALESCE(NULLIF(hr.name ->> 'en_US', 'Unnamed'), rb.name) AS name,
                    rb.id AS booking_id,
                    hr.id AS room_id,
                    rb.group_booking_id,
                    NULL::integer AS dummy_id,
                    mf.id AS folio_id,
                    rb.partner_id,
                    rb.checkin_date AS checkin_date,
                    rb.checkout_date AS checkout_date,
                    rb.adult_count::integer,
                    rb.child_count::integer,
                    rb.infant_count::integer,
                    rc.id AS rate_code,
                    mp.id AS meal_pattern,
                    rb.company_id,
                    rb.state AS state
                FROM room_booking rb
                LEFT JOIN room_booking_line rbl ON rbl.booking_id = rb.id
                LEFT JOIN hotel_room hr ON rbl.room_id = hr.id
                LEFT JOIN tz_master_folio mf ON mf.room_id = rbl.room_id 
                LEFT JOIN rate.code rc ON rc.code = rb.rate_code
                LEFT JOIN meal.pattern mp ON mp.code = rb.meal_pattern
                WHERE rb.company_id = {company_id}
                  AND rb.state = 'check_in'
                  AND rb.group_booking IS NULL

                UNION ALL

                SELECT
                    (gb.id * 10 + 2) AS id,
                    COALESCE(gb.group_name ->> 'en_US', 'Unnamed') AS name,
                    NULL AS booking_id,
                    NULL AS room_id,
                    gb.id AS group_booking_id,
                    NULL::integer AS dummy_id,
                    mf.id AS folio_id,
                    gb.company AS partner_id,
                    gb.first_visit AS checkin_date,
                    gb.last_visit AS checkout_date,
                    gb.total_adult_count::integer,
                    gb.total_child_count::integer,
                    gb.total_infant_count::integer,
                    rc.id AS rate_code,
                    mp.id AS meal_pattern,
                    gb.company_id,
                    gb.status_code AS state
                FROM group_booking gb
                LEFT JOIN tz_master_folio mf ON mf.group_id = gb.id
                LEFT JOIN rate.code rc ON rc.code = gb.rate_code
                LEFT JOIN meal.pattern mp ON mp.code = gb.group_meal_pattern
                WHERE gb.status_code = 'confirmed'
                  AND gb.id IN (
                      SELECT rb.group_booking FROM room_booking rb
                      WHERE rb.state = 'check_in'
                        AND rb.company_id = {company_id}
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
                    dg.partner_id,
                    dg.start_date AS checkin_date,
                    dg.end_date AS checkout_date,
                    NULL::integer AS adult_count,
                    NULL::integer AS child_count,
                    NULL::integer AS infant_count,
                    NULL AS rate_code,
                    NULL AS meal_pattern,
                    dg.company_id,
                    dg.state AS state
                FROM tz_dummy_group dg
                LEFT JOIN (
                    SELECT DISTINCT ON (dummy_id) id, dummy_id 
                    FROM tz_master_folio 
                    WHERE dummy_id IS NOT NULL
                    ORDER BY dummy_id, id
                ) mf ON mf.dummy_id = dg.id
                WHERE dg.obsolete = FALSE
                  AND dg.company_id = {company_id}
            )
        """

        self.env.cr.execute(query)

        # Refresh the view immediately after creation
        self.env.cr.execute("REFRESH MATERIALIZED VIEW tz_checkout")

    def _setup_change_triggers(self):
        """Setup automatic refresh triggers on source tables"""
        try:
            for table in ['room_booking', 'group_booking', 'tz_dummy_group', 'hotel_room', 'tz_master_folio',
                          'rate.code', 'meal.pattern']:
                try:
                    # First drop the trigger if it exists
                    self.env.cr.execute(f"""
                        DROP TRIGGER IF EXISTS tz_checkout_refresh_trigger ON {table};
                    """)
                    # Then create the new trigger
                    self.env.cr.execute(f"""
                        CREATE TRIGGER tz_checkout_refresh_trigger
                        AFTER INSERT OR UPDATE OR DELETE ON {table}
                        FOR EACH STATEMENT EXECUTE FUNCTION tz_refresh_checkout();
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
        """Public method to manually refresh the view"""
        self.create_or_replace_view()
        return True

    def schedule_refresh_materialized_view(self):
        """Called by scheduled action to refresh the view"""
        self.env.cr.execute("REFRESH MATERIALIZED VIEW tz_checkout")
        self.env.cr.commit()


# class TzCheckout(models.Model):
#     _name = 'tz.checkout'
#     _description = 'FrontDesk Checkout'
#     _auto = False
#     _check_company_auto = True
#
#     name = fields.Char('Room')
#     all_name = fields.Char('Room', compute='_compute_name', store=False)
#     booking_id = fields.Many2one('room.booking', string='Booking Id')
#     group_booking_id = fields.Many2one('group.booking', string='Group Booking')
#     dummy_id = fields.Many2one('tz.dummy.group', string='Dummy')
#     room_id = fields.Many2one('hotel.room', string='Room')
#     partner_id = fields.Many2one('res.partner', string='Guest')
#     checkin_date = fields.Datetime('Check-in Date')
#     checkout_date = fields.Datetime('Check-out Date')
#     adult_count = fields.Integer('Adults')
#     child_count = fields.Integer('Children')
#     infant_count = fields.Integer('Infants')
#     rate_code = fields.Many2one('rate.code', string='Rate Code')
#     meal_pattern = fields.Many2one('meal.pattern', string='Meal Pattern')
#     state = fields.Char('Status')
#     company_id = fields.Many2one('res.company', string='Company')
#     folio_id = fields.Many2one('tz.master.folio', string="Master Folio")
#
#
#     # def _compute_name(self):
#     #     for record in self:
#     #         if record.partner_id:
#     #             # Check if this is a group booking
#     #             group_booking = self.env['group.booking'].search([
#     #                 ('company', '=', record.partner_id.id),
#     #                 ('status_code', '=', 'confirmed')
#     #             ], limit=1)
#     #             if group_booking:
#     #                 # Handle group name which might be a translation dictionary
#     #                 if isinstance(group_booking.group_name, dict):
#     #                     record.all_name = group_booking.group_name.get('en_US', 'Unnamed')
#     #                 else:
#     #                     record.all_name = group_booking.group_name or 'Unnamed'
#     #             elif record.room_id:
#     #                 # Handle room name which might be a string or translation dict
#     #                 if isinstance(record.room_id.name, dict):
#     #                     record.all_name = record.room_id.name.get('en_US', 'Unnamed')
#     #                 else:
#     #                     record.all_name = record.room_id.name or 'Unnamed'
#     #             else:
#     #                 record.all_name = 'Unnamed'
#     #         elif not record.room_id and not record.partner_id:
#     #             # For dummy groups, use the name from the view
#     #             record.all_name = record.name
#     #         else:
#     #             record.all_name = record.name
#     #
#     # def _compute_v_state(self):
#     #     for record in self:
#     #         # If it's from room_booking (has room_id)
#     #         if record.room_id:
#     #             record.v_state = 'In' if record.state == 'check_in' else 'Out'
#     #         # If it's from group_booking (no room_id but has partner_id)
#     #         elif record.partner_id:
#     #             # We need to check if it's confirmed and has room bookings
#     #             group_booking = self.env['group.booking'].search([
#     #                 ('company', '=', record.partner_id.id),
#     #                 ('status_code', '=', 'confirmed')
#     #             ], limit=1)
#     #             if group_booking and group_booking.room_booking_ids:
#     #                 record.v_state = 'In'
#     #             else:
#     #                 record.v_state = 'Out'
#     #         # If it's from dummy group (no room_id and no partner_id)
#     #         else:
#     #             record.v_state = 'In' if record.state == 'in' else 'Out'
#     #
#     # def search(self, domain, offset=0, limit=None, order=None):
#     #     return super().search(domain, offset=offset, limit=limit, order=order)


