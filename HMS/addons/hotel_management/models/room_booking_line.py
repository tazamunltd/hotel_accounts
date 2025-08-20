from odoo import api, models
from odoo.exceptions import ValidationError
import time
from datetime import timedelta, datetime
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.models import NewId
import logging

_logger = logging.getLogger(__name__)

class RoomBookingLine(models.Model):
    """Model that handles the room booking form"""
    _name = "room.booking.line"
    _description = "Hotel Folio Line"
    _rec_name = 'room_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    sequence = fields.Integer(
        string='Sequence', compute='_compute_sequence', store=True,tracking=True, index=True)

    

    # @api.depends("booking_id.room_line_ids")
    # def _compute_sequence(self):
    #     """Bulk assign sequence numbers – one DB write per booking."""
    #     for booking in self.mapped("booking_id"):
    #         lines = booking.room_line_ids.sorted("create_date")
    #         for i, line in enumerate(lines, start=1):
    #             line.sequence = i
    @api.depends("booking_id.room_line_ids")
    def _compute_sequence(self):
        """Bulk assign sequence numbers using SQL for maximum performance."""
        # Skip computation if context flag is set
        if self.env.context.get('skip_sequence_computation'):
            return
        
        # Filter out unsaved records (NewId) - only process saved records
        saved_lines = self.filtered(lambda l: l.id and l.booking_id and not isinstance(l.booking_id.id, models.NewId))
        
        if not saved_lines:
            # Skip unsaved records entirely to avoid infinite loops
            return
        
        # Group saved lines by booking_id to process each booking separately
        booking_groups = {}
        for line in saved_lines:
            booking_id = line.booking_id.id
            if booking_id not in booking_groups:
                booking_groups[booking_id] = []
            booking_groups[booking_id].append(line.id)
        
        # Process each booking with bulk SQL update
        for booking_id, line_ids in booking_groups.items():
            if not line_ids:
                continue
                
            # Get lines sorted by create_date for this booking
            booking_lines = self.env['room.booking.line'].search([
                ('id', 'in', line_ids)
            ], order='create_date ASC')
            
            if len(booking_lines) <= 1:
                # Single line - direct update
                if booking_lines:
                    self.env.cr.execute(
                        "UPDATE room_booking_line SET sequence = 1 WHERE id = %s",
                        (booking_lines[0].id,)
                    )
            else:
                # Multiple lines - bulk update with CASE statement
                case_statements = []
                line_ids_tuple = []
                
                for i, line in enumerate(booking_lines, start=1):
                    case_statements.append(f"WHEN id = %s THEN %s")
                    line_ids_tuple.extend([line.id, i])
                
                if case_statements:
                    sql = f"""
                        UPDATE room_booking_line 
                        SET sequence = CASE 
                            {' '.join(case_statements)}
                        END 
                        WHERE id IN %s
                    """
                    line_ids_tuple.append(tuple(booking_lines.ids))
                    
                    self.env.cr.execute(sql, line_ids_tuple)
        
        # Invalidate cache to ensure computed values are refreshed
        self.env.invalidate_all()
    

    counter = fields.Integer(string="Counter", default=0,tracking=True,index=True)

    housekeeping_status = fields.Many2one(
        'housekeeping.status', string="Housekeeping Status", compute="_compute_room_statuses", store=False
    ,tracking=True,index=True)
    maintenance_status = fields.Many2one(
        'maintenance.status', string="Maintenance Status", compute="_compute_room_statuses", store=False
    ,tracking=True,index=True)
    housekeeping_staff_status = fields.Many2one(
        'housekeeping.staff.status', string="Housekeeping Staff Status", compute="_compute_room_statuses", store=False
    ,tracking=True,index=True)

    

    @api.depends("room_id")
    def _compute_room_statuses(self):
        for rec in self:
            room = rec.room_id
            rec.housekeeping_status = room.housekeeping_status.id if room else False
            rec.maintenance_status = room.maintenance_status.id if room else False
            rec.housekeeping_staff_status = (
                room.housekeeping_staff_status.id if room else False
            )

    hide_fields = fields.Boolean(string="Hide Fields", default=False,tracking=True,index=True)

    @tools.ormcache()
    def _set_default_uom_id(self):
        return self.env.ref('uom.product_uom_day')

    booking_id = fields.Many2one("room.booking", string="Booking",
                                 help="Indicates the Room",
                                 ondelete="cascade",tracking=True,index=True)

    state_ = fields.Selection([
        ('not_confirmed', 'Not Confirmed'),
        ('block', 'Block'),
        ('no_show', 'No Show'),
        ('confirmed', 'Confirmed'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('done', 'done'),
        ('cancel', 'Cancel'),
    ], default='not_confirmed', string="Status", compute='_compute_state', store=True,tracking=True,index=True)

    
    #Working Code 12/12/2024
    # @api.depends('booking_id', 'booking_id.state', 'sequence')
    # def _compute_state(self):
    #     for record in self:
    #         if record.booking_id.state == 'not_confirmed':
    #             record.state_ = 'not_confirmed'
    #             continue
    #         if not record.room_id:
    #             record.state_ = 'confirmed'
    #             continue
    #         if record.booking_id.state == 'block':
    #             record.state_ = 'block'
    #             continue
    #         # Search for a child booking with parent_booking_id matching the current booking

    #         # Step 1: Get all child bookings for the current booking_id
    #         child_bookings_ = self.env['room.booking'].search([
    #             ('parent_booking_id', '=', record.booking_id.id)
    #         ])
    #         if child_bookings_:
    #             # Step 2: Find a matching booking line under any of the child bookings
    #             matching_line = self.env['room.booking.line'].search([
    #                 ('booking_id', 'in', child_bookings_.ids),
    #                 ('counter', '=', record.counter)
    #             ], limit=1)
    #             # _logger.debug('matching_',matching_line,matching_line.booking_id)

    #             child_bookings = self.env['room.booking'].search([
    #                 ('id', '=', matching_line.booking_id.id)
    #             ], limit=1)

    #             # _logger.debug("compute called",child_bookings)
    #             # Assign the state of the child booking if found, else use the parent's state
    #             if child_bookings:
    #                 record.state_ = child_bookings.state
    #                 # _logger.debug(child_bookings.id, child_bookings.state, "child")
    #             # else:
    #             #     record.state_ = 'not_confirmed'
    #             #     # _logger.debug(child_booking.id, child_booking.state, "not child")
    #         else:
    #             if len(record.booking_id.room_line_ids) == 1:
    #                 if record.booking_id.state == 'block':
    #                     record.state_ = 'block'
                    
    #Haji bhai code    
    @api.depends('booking_id.state', 'room_id', 'counter')
    def _compute_state(self):
        # Pre‐fetch all child‐booking lines once
        parent_ids = self.mapped('booking_id.id')
        child_lines = self.env['room.booking.line'].search([
            ('booking_id.parent_booking_id', 'in', parent_ids)
        ])
        # Build map: parent_booking_id → { counter: line }
        child_map = {}
        for cl in child_lines:
            pb = cl.booking_id.parent_booking_id.id
            child_map.setdefault(pb, {})[cl.counter] = cl

        for line in self:
            bstate = line.booking_id.state
            # 1) Not yet confirmed?
            if bstate == 'not_confirmed':
                line.state_ = 'not_confirmed'
                continue
            # 2) No room assigned yet
            if not line.room_id:
                line.state_ = 'confirmed'
                continue
            # 3) Parent is blocked
            if bstate == 'block':
                line.state_ = 'block'
                continue
            # 4) Match child booking line by counter
            match = child_map.get(line.booking_id.id, {}).get(line.counter)
            if match:
                line.state_ = match.booking_id.state
                continue
            # 5) Fallback: single‐line parent inherits block
            if len(line.booking_id.room_line_ids) == 1 and bstate == 'block':
                line.state_ = 'block'
            else:
                # Otherwise treat as confirmed/in‐progress
                line.state_ = 'check_in' if bstate == 'check_in' else 'confirmed'

    
    hide_room_id = fields.Boolean(
        string='Hide Room Field', compute='_compute_hide_room_id',tracking=True)

    @api.depends('booking_id.state')
    def _compute_hide_room_id(self):
        for record in self:
            record.hide_room_id = record.booking_id.state == 'block'

    room_availability_result_id = fields.Many2one(
        'room.availability.result', string="Room Availability Result",
        readonly=True
    ,tracking=True)

    checkin_date = fields.Datetime(string="Check In",
                                   help="You can choose the date,"
                                        " Otherwise sets to current Date",
                                   required=True,tracking=True,index=True)
    checkout_date = fields.Datetime(string="Check Out",
                                    help="You can choose the date,"
                                         " Otherwise sets to current Date",
                                    required=True,tracking=True,index=True)

    related_hotel_room_type = fields.Many2one(
        related='booking_id.hotel_room_type',
        string="Related Room Type",
        store=True
    ,tracking=True,index=True)



    room_id = fields.Many2one(
        'hotel.room',
        string="Room",
        domain="[('room_type_name', '=', hotel_room_type), "
        "('id', 'not in', booked_room_ids), ('company_id', '=', current_company_id)]",
        help="Indicates the Room",tracking=True,index=True)

    

    @api.model
    def default_get(self, fields_list):
        defaults = super(RoomBookingLine, self).default_get(fields_list)
        defaults['current_company_id'] = self.env.company.id
        return defaults

    current_company_id = fields.Many2one('res.company', default=lambda self: self.env.company,tracking=True)

    @api.onchange('hotel_room_type', 'adult_count')
    def _onchange_room_type_or_pax(self):
        for line in self:
            _logger.debug("102", line.hotel_room_type, line.adult_count)

    booked_room_ids = fields.Many2many(
        'hotel.room',
        compute='_compute_booked_room_ids',
        string='Booked Rooms',
        store=False
    ,tracking=True)

    # @api.depends('checkin_date', 'checkout_date')
    # def _compute_booked_room_ids(self):
    #     BookingLine = self.env['room.booking.line']
    #     # 1) Split into “to compute” vs “to clear” sets
    #     to_compute = self.filtered(lambda r: isinstance(r.id, int) and r.checkin_date and r.checkout_date)
    #     to_clear = self - to_compute

    #     # 2) Clear the rest in one go
    #     for rec in to_clear:
    #         rec.booked_room_ids = []

    #     if not to_compute:
    #         return

    #     # 3) Build a loose domain covering all of them
    #     min_checkin  = min(to_compute.mapped('checkin_date'))
    #     max_checkout = max(to_compute.mapped('checkout_date'))
    #     domain = [
    #         ('booking_id.state', 'in', ['confirmed', 'block', 'check_in']),
    #         ('room_id', '!=', False),
    #         ('booking_id.checkin_date', '<', max_checkout),
    #         ('booking_id.checkout_date', '>', min_checkin),
    #     ]
    #     all_lines = BookingLine.search(domain)

    #     # 4) For each record, filter those lines by its specific window
    #     for rec in to_compute:
    #         overlapping = all_lines.filtered(
    #             lambda ln:
    #             ln.booking_id.checkin_date < rec.checkout_date
    #             and ln.booking_id.checkout_date > rec.checkin_date
    #             and not (
    #                 ln.booking_id.checkin_date <= rec.checkin_date
    #                 and ln.booking_id.checkout_date >= rec.checkout_date
    #             )
    #             and ln.id != rec.id
    #         )
    #         # overlapping = all_lines.filtered(
    #         #     lambda ln: ln.booking_id.checkin_date < rec.checkout_date
    #         #             and ln.booking_id.checkout_date > rec.checkin_date
    #         #             and ln.id != rec.id
    #         # )
    #         rec.booked_room_ids = overlapping.mapped('room_id.id')

    # @api.depends('checkin_date', 'checkout_date')
    # def _compute_booked_room_ids(self):
    #     BookingLine = self.env['room.booking.line']

    #     # 1) Split into “to compute” vs “to clear” sets
    #     to_compute = self.filtered(lambda r: isinstance(r.id, int) and r.checkin_date and r.checkout_date)
    #     to_clear   = self - to_compute

    #     _logger.debug("Compute triggered for %d records", len(self))
    #     _logger.debug(" to_compute IDs: %s", to_compute.ids)
    #     _logger.debug(" to_clear IDs: %s", to_clear.ids)

    #     # 2) Clear the rest in one go
    #     for rec in to_clear:
    #         _logger.debug(" Clearing booked_room_ids for record %s", rec.id)
    #         rec.booked_room_ids = []

    #     if not to_compute:
    #         _logger.debug(" Nothing to compute, exiting.")
    #         return

    #     # 3) Build a loose domain covering all of them
    #     min_ci  = min(to_compute.mapped('checkin_date'))
    #     max_co  = max(to_compute.mapped('checkout_date'))
    #     domain  = [
    #         ('booking_id.state', 'in', ['confirmed', 'block', 'check_in']),
    #         ('room_id', '!=', False),
    #         ('booking_id.checkin_date', '<', max_co),
    #         ('booking_id.checkout_date', '>', min_ci),
    #     ]
    #     _logger.debug(" Overall date window: %s to %s", min_ci, max_co)
    #     _logger.debug(" Search domain: %s", domain)

    #     all_lines = BookingLine.search(domain)
    #     _logger.debug(" Found %d lines matching domain", len(all_lines))

    #     # 4) For each record, filter those lines by its specific window
    #     for rec in to_compute:
    #         _logger.debug(" -- Computing for record %s (checkin=%s, checkout=%s)",
    #                      rec.id, rec.checkin_date, rec.checkout_date)
    #         overlapping = all_lines.filtered(
    #             lambda ln:
    #                 ln.booking_id.checkin_date < rec.checkout_date
    #                 and ln.booking_id.checkout_date > rec.checkin_date
    #                 and not (
    #                     ln.booking_id.checkin_date <= rec.checkin_date
    #                     and ln.booking_id.checkout_date >= rec.checkout_date
    #                 )
    #                 and ln.id != rec.id
    #         )
    #         _logger.debug("    Overlapping lines for rec %s: %s", rec.id, overlapping.ids)

    #         room_ids = overlapping.mapped('room_id.id')
    #         _logger.debug("    Mapped overlapping room_ids: %s", room_ids)

    #         rec.booked_room_ids = room_ids
    #         _logger.debug("    Set booked_room_ids for rec %s to %s", rec.id, rec.booked_room_ids.ids)    

    @api.depends('booking_id.checkin_date', 'booking_id.checkout_date', 'booking_id.state', 'hotel_room_type','related_hotel_room_type')
    def _compute_booked_room_ids(self):
        _logger.info("_compute_booked_room_ids started")
        
        # Skip expensive computation during onchange operations
        if (self.env.context.get('from_onchange') or 
            self.env.context.get('skip_forecast_computation') or
            self.env.context.get('skip_tax_computation')):
            _logger.info("SKIPPING booked_room_ids computation - context flag set")
            return
        
        BookingLine = self.env['room.booking.line']
        to_compute = self.filtered(lambda r: r.booking_id.checkin_date and r.booking_id.checkout_date)
        to_clear = self - to_compute

        if to_clear:
            to_clear.write({'booked_room_ids': [(5, 0, 0)]})

        if not to_compute:
            _logger.info("_compute_booked_room_ids completed - no records to compute")
            return

        # Pre-cache date conversions to avoid repeated processing
        min_ci = min(to_compute.mapped('booking_id.checkin_date'))
        max_co = max(to_compute.mapped('booking_id.checkout_date'))
        
        # Get all overlapping booking lines in one query
        domain = [
            ('booking_id.state', 'in', ['confirmed', 'block', 'check_in']),
            ('room_id', '!=', False),
            ('booking_id.checkin_date', '<', max_co),
            ('booking_id.checkout_date', '>', min_ci),
        ]
        all_lines = BookingLine.search(domain)
        
        # Group overlapping lines by room type and company for efficient filtering
        overlapping_by_context = {}
        for line in all_lines:
            if line.room_id and line.room_id.room_type_name and line.room_id.company_id:
                key = (line.room_id.room_type_name.id, line.room_id.company_id.id)
                if key not in overlapping_by_context:
                    overlapping_by_context[key] = []
                overlapping_by_context[key].append(line)

        for rec in to_compute:
            # Only consider rooms matching this booking line's context
            # room_type_id = rec.related_hotel_room_type.id if rec.related_hotel_room_type else None
            room_type_id = (rec.hotel_room_type.id
                            or (rec.related_hotel_room_type.id if rec.related_hotel_room_type else None))
            company_id = rec.current_company_id.id if rec.current_company_id else None
            
            if not room_type_id or not company_id:
                rec.booked_room_ids = []
                continue
                
            # Get overlapping lines for this specific room type and company
            context_key = (room_type_id, company_id)
            relevant_lines = overlapping_by_context.get(context_key, [])
            
            if not relevant_lines:
                rec.booked_room_ids = []
                continue
                
            # Pre-convert dates for this record
            ci_date = fields.Date.to_date(rec.booking_id.checkin_date)
            co_date = fields.Date.to_date(rec.booking_id.checkout_date)

            # Filter overlapping lines for this specific booking
            conflicting_room_ids = []
            for line in relevant_lines:
                if (line.id != rec.id and
                    fields.Date.to_date(line.booking_id.checkout_date) != ci_date and
                    fields.Date.to_date(line.booking_id.checkin_date) < co_date and
                    fields.Date.to_date(line.booking_id.checkout_date) > ci_date):
                    conflicting_room_ids.append(line.room_id.id)
            
            # Remove duplicates and set the result
            rec.booked_room_ids = list(set(conflicting_room_ids))
            
        _logger.info("_compute_booked_room_ids completed")

    # def _compute_booked_room_ids(self):
    #     BookingLine = self.env['room.booking.line']
    #     to_compute = self.filtered(lambda r: r.booking_id.checkin_date and r.booking_id.checkout_date)
    #     to_clear   = self - to_compute
    #
    #     _logger.debug("Compute triggered for %d lines; to_clear=%s, to_compute=%s",
    #                 len(self), to_clear.ids, to_compute.ids)
    #
    #     # only clear if there *are* records to clear
    #     if to_clear:
    #         to_clear.write({'booked_room_ids': [(5, 0, 0)]})
    #
    #     if not to_compute:
    #         return
    #
    #     min_ci  = min(to_compute.mapped('booking_id.checkin_date'))
    #     max_co  = max(to_compute.mapped('booking_id.checkout_date'))
    #     domain  = [
    #         ('booking_id.state', 'in', ['confirmed', 'block', 'check_in']),
    #         ('room_id', '!=', False),
    #         ('booking_id.checkin_date', '<', max_co),
    #         ('booking_id.checkout_date', '>', min_ci),
    #     ]
    #     all_lines = BookingLine.search(domain)
    #     _logger.debug("Found %d candidate lines in %s–%s", len(all_lines), min_ci, max_co)
    #
    #     for rec in to_compute:
    #         ci, co = rec.booking_id.checkin_date, rec.booking_id.checkout_date
    #         overlapping = all_lines.filtered(lambda ln:
    #                                                          ln.id != rec.id
    #                                            # skip lines that check out exactly when this one checks in
    #                                           and not (ln.booking_id.checkout_date == ci)
    #                                                      # true overlap otherwise
    #                                                     and ln.booking_id.checkin_date < co
    #                                           and ln.booking_id.checkout_date > ci
    #                                          )
    #         rec.booked_room_ids = overlapping.mapped('room_id.id')
    #         _logger.debug("Line %s => booked_room_ids=%s", rec.id, rec.booked_room_ids.ids)



    # @api.depends('checkin_date', 'checkout_date')
    # def _compute_booked_room_ids(self):
    #     _logger.debug("Computing booked room IDs for room booking lines.")
    #     for record in self:
    #         if isinstance(record.id, NewId):
    #             # Skip unsaved records, as they do not have a valid database ID
    #             record.booked_room_ids = []
    #             continue

    #         if record.checkin_date and record.checkout_date:
    #             overlapping_bookings = self.env['room.booking.line'].search([
    #                 ('booking_id.checkin_date', '<', record.checkout_date),
    #                 ('booking_id.checkout_date', '>', record.checkin_date),
    #                 ('booking_id.state', 'in', [
    #                  'confirmed', 'block', 'check_in']),
    #                 ('room_id', '!=', False),
    #                 ('id', '!=', record.id)  # Exclude current record
    #             ])
    #             # Collect room IDs that are already booked
    #             record.booked_room_ids = overlapping_bookings.mapped('room_id.id')
    #         else:
    #             record.booked_room_ids = []

    # hotel_room_type = fields.Many2one(
    #     'room.type',
    #     string="Room Type",
    #     help="Select a room type to filter available rooms."
    # ,tracking=True,index=True)

    hotel_room_type = fields.Many2one(
        'room.type', string="Room Type",
        domain=lambda self: [
        ('obsolete', '=', False),
        ('id', 'in', self.env['hotel.inventory'].search([
            ('company_id', '=', self.env.company.id),
        ]).mapped('room_type.id'))
        ],tracking=True)


    @api.onchange('hotel_room_type')
    def _onchange_hotel_room_type(self):
        _logger.debug("hotel room type change called")
        """Automatically filter room_id based on hotel_room_type."""
        parent_booking_id = self.booking_id.id
        # _logger.debug(parent_booking_id, type(parent_booking_id))
        # numeric_parent_id = parent_booking_id.split('=')[-1].strip('>')
        if isinstance(parent_booking_id, NewId):
            parent_booking_id_str = str(parent_booking_id)
            if '_' in parent_booking_id_str:
                numeric_parent_id = int(parent_booking_id_str.split('_')[-1])
                parent_booking_ids = self.env['room.booking'].search(
                    [('parent_booking_id', '=', numeric_parent_id)]).mapped('id')
                room_booking_line_ids = self.env['room.booking.line'].search(
                    [('booking_id', 'in', parent_booking_ids),
                     ('counter', '=', self.counter)],
                    order='id asc'  # Sort in ascending order
                ).ids
                room_ids_count = len(room_booking_line_ids)
                _logger.debug(f"Room Booking Line IDs for room type: {room_booking_line_ids}")
        # Find the affected room booking line
        affected_line = self.booking_id.room_line_ids.filtered(
            lambda line: line.id == self.id)

        if affected_line:
            affected_line_str = str(affected_line.id)

            # Extract only the numeric part
            numeric_id = affected_line_str.split('=')[-1].strip('>')
            numeric_id = int(numeric_id.split('_')[-1])
            if len(room_booking_line_ids) > 0:
                recordset = self.env['room.booking.line'].search([
                    ('id', 'in', [numeric_id, room_booking_line_ids[0]])
                ])
            else:
                recordset = self.env['room.booking.line'].search([
                    ('id', 'in', [numeric_id])
                ])

            # Check if records exist
            if recordset:
                # Update all records with the new room_id
                recordset.write({
                    'hotel_room_type': self.hotel_room_type.id,
                    'related_hotel_room_type': self.hotel_room_type.id,
                })
                # Force computation of booked_room_ids during onchange by removing skip flags
                self.with_context(
                    from_onchange=False,
                    skip_forecast_computation=False,
                    skip_tax_computation=False
                )._compute_booked_room_ids()

                self.invalidate_recordset(['booked_room_ids'])
                self.modified(['booked_room_ids'])
        _logger.debug(f"{self.hotel_room_type.id} in the onchange called")   
        return {
            'domain': {
                'room_id': [
                    # ('status', '=', 'available'),
                    ('company_id', '=',self.env.company.id),
                    ('room_type_name', '=', self.hotel_room_type.id),
                    ('id', 'not in', self.booked_room_ids.ids if self.booked_room_ids else []),
                ] if self.hotel_room_type else [('company_id', '=',self.env.company.id)]
            }
        }

    def _get_dynamic_room_domain(self):
        """Get dynamic domain for room_id based on hotel_room_type."""
        domain = [('status', '=', 'available')]
        if self.hotel_room_type:
            domain.append(('room_type_name', '=', self.hotel_room_type.id))
        return domain

    room_type = fields.Many2one('hotel.room', string="Room Type",tracking=True)

    room_type_name = fields.Many2one(
        'room.type', string="Room Type", related="room_id.room_type_name", readonly=True,tracking=True,index=True)

    adult_count = fields.Integer(string="Adults", readonly=True,tracking=True,index=True)
    child_count = fields.Integer(string="Children", related="booking_id.child_count", readonly=True,tracking=True,index=True)
    infant_count = fields.Integer(string="Infant", related="booking_id.infant_count", readonly=True,tracking=True,index=True)

    uom_qty = fields.Float(string="Duration",
                           compute='_compute_uom_qty',
                           inverse='_inverse_uom_qty',
                           help="The quantity converted into the UoM used by "
                                "the product",tracking=True,index=True)

    @api.depends('checkin_date', 'checkout_date')
    def _compute_uom_qty(self):
        for record in self:
            if record.checkin_date and record.checkout_date:
                duration = (record.checkout_date - record.checkin_date).days + \
                    ((record.checkout_date - record.checkin_date).seconds / 86400)
                record.uom_qty = duration

    @api.onchange('uom_qty')
    def _inverse_uom_qty(self):
        for record in self:
            if record.checkin_date and record.uom_qty:
                record.checkout_date = record.checkin_date + \
                    timedelta(days=record.uom_qty)

    uom_id = fields.Many2one('uom.uom',
                             default=_set_default_uom_id,
                             string="Unit of Measure",
                             help="This will set the unit of measure used",
                             readonly=True,tracking=True)
    price_unit = fields.Float(related='room_id.list_price', string='Rent',
                              digits='Product Price',
                              help="The rent price of the selected room.",tracking=True)
    tax_ids = fields.Many2many('account.tax',
                               'hotel_room_order_line_taxes_rel',
                               'room_id', 'tax_id',
                               related='room_id.taxes_ids',
                               string='Taxes',
                               help="Default taxes used when selling the room.", domain=[('type_tax_use', '=', 'sale')],tracking=True)
    currency_id = fields.Many2one(string='Currency',
                                  related='booking_id.pricelist_id.currency_id', help='The currency used',tracking=True)
    price_subtotal = fields.Float(string="Subtotal",
                                  compute='_compute_price_subtotal',
                                  help="Total Price excluding Tax",
                                  store=True,tracking=True)
    price_tax = fields.Float(string="Total Tax",
                             compute='_compute_price_subtotal',
                             help="Tax Amount",
                             store=True,tracking=True)
    price_total = fields.Float(string="Total",
                               compute='_compute_price_subtotal',
                               help="Total Price including Tax",
                               store=True,tracking=True)
    state = fields.Selection(related='booking_id.state',
                             string="Order Status",
                             help=" Status of the Order",
                             copy=False,tracking=True)
    booking_line_visible = fields.Boolean(default=False,
                                          string="Booking Line Visible",
                                          help="If True, then Booking Line "
                                               "will be visible",tracking=True)

    @api.onchange("checkin_date", "checkout_date")
    def _onchange_checkin_date(self):
        """When you change checkin_date or checkout_date it will check
        and update the qty of hotel service line
        -----------------------------------------------------------------
        @param self: object pointer"""
        if self.checkout_date < self.checkin_date:
            raise ValidationError(
                _("Checkout must be greater or equal checkin date"))
        if self.checkin_date and self.checkout_date:
            diffdate = self.checkout_date - self.checkin_date
            qty = diffdate.days
            if diffdate.total_seconds() > 0:
                qty = qty + 1
            self.uom_qty = qty

    @api.depends('uom_qty', 'price_unit', 'tax_ids')
    def _compute_price_subtotal(self):
        """Compute the amounts of the room booking line."""
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes(
                [line._convert_to_tax_base_line_dict()])
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']
            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })
            if self.env.context.get('import_file',
                                    False) and not self.env.user. \
                    user_has_groups('account.group_account_manager'):
                line.tax_id.invalidate_recordset(
                    ['invoice_repartition_line_ids'])

    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the
        generic taxes computation method
        defined on account.tax.
        :return: A python dictionary."""
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.booking_id.partner_id,
            currency=self.currency_id,
            taxes=self.tax_ids,
            price_unit=self.price_unit,
            quantity=self.uom_qty,
            price_subtotal=self.price_subtotal,
        )

    is_unassigned = fields.Boolean(string="Is Unassigned", default=True,
                                   help="Indicates if the room line is unassigned.",tracking=True)

    # @api.onchange('room_id')
    # def _onchange_room_id(self):
    #     if self.booking_id.state != 'confirmed':
    #         raise UserError("Please confirm booking first.")

    @api.model
    def _update_inventory(self, room_type_id, company_id, increment=True):
        """Update available rooms in hotel.inventory."""
        inventory = self.env['hotel.inventory'].search([
            ('room_type', '=', room_type_id),
            ('company_id', '=', company_id)
        ], limit=1)

        if inventory:
            if increment:
                inventory.available_rooms += 1
            else:
                inventory.available_rooms -= 1

    @api.model
    def assign_room(self, parent_booking, room_vals):
        """Assign a room from a parent booking, creating a child booking."""
        new_booking_vals = {
            'parent_booking_id': parent_booking.id,  # Link parent booking
            'room_line_ids': [(0, 0, room_vals)],
            'state': 'block',  # New state for child booking
        }

        # Create child booking with reference to parent
        return self.env['room.booking'].create(new_booking_vals)

    # @api.onchange('room_id')
    # def _onchange_room_id(self):
    #     """When the room_id changes, set the state to confirmed."""
    #     if self.room_id:
    #         self.state = 'confirmed'

    def unlink(self):
        """Override unlink to handle cascading deletion of related child records."""
        for record in self:
            if record.booking_id:
                # Find the corresponding child bookings based on sequence or counter
                child_bookings = self.env['room.booking'].search([
                    ('parent_booking_id', '=', record.booking_id.id),
                    # Assuming counter identifies related lines
                    ('room_line_ids.counter', '=', record.counter)
                ])

                # Log details for debugging
                child_bookings.unlink()

        # Call the original unlink method to delete the current record
        return super(RoomBookingLine, self).unlink()

    def assign_room_manual(self, room_id):
        """Method to handle manual room assignments with proper context"""
        return self.with_context(skip_code_validation=True).write({
            'room_id': room_id,
        })

    @api.constrains('room_id')
    def _check_duplicate_room(self):
        for rec in self:
            if rec.booking_id:
                existing_room_ids = rec.booking_id.room_line_ids.filtered(
                    lambda line: line.id != rec.id).mapped('room_id.id')
                if rec.room_id.id in existing_room_ids:
                    raise ValidationError(_("This room is already assigned to the current booking. Please select a different room."))

    @api.onchange('room_id')
    def _onchange_room_id(self):
        _logger.debug(f"Onchange room_id called for booking line")
        """Update booking state based on room_id value and log changes."""
        # if not self.id:
        #     return
        self = self.with_context(
            skip_total_forecast_computation=True,
            skip_tax_computation=True
        )
        if self.booking_id:
            existing_room_ids = self.booking_id.room_line_ids.filtered(lambda line: line.id != self.id).mapped('room_id.id')
            if self.room_id.id in existing_room_ids:
                raise ValidationError(_("This room is already assigned to the current booking. Please select a different room."))
        if isinstance(self.id, NewId):
            id_str_room = str(self.id)
            if '_' in id_str_room:
                current_id = int(id_str_room.split('_')[-1])

            # # current_id = None  # Exclude current record from the search
            # current_id = int(self.id.split('_')[-1])
        else:
            current_id = self.id
        if not self.id or not self.room_id:
            return
        if current_id is not None:
            # checkin_date = self.checkin_date
            checkin_date = self.booking_id.checkin_date
            checkout_date = self.booking_id.checkout_date

            # Convert to datetime if they are strings
            if isinstance(checkin_date, str):
                checkin_date = datetime.strptime(checkin_date, "%Y-%m-%d %H:%M:%S")
            if isinstance(checkout_date, str):
                checkout_date = datetime.strptime(checkout_date, "%Y-%m-%d %H:%M:%S")

            conflicting_bookings = self.env['room.booking.line'].search([
                ('room_id', '=', self.room_id.id),
                ('booking_id.state', 'in', ['block', 'check_in']),
                # ('checkin_date', '<=', checkout_date),
                # ('checkout_date', '>=', checkin_date),
                '|', '|',
                '&', ('checkin_date', '<', checkout_date), ('checkout_date', '>', checkin_date),
                '&', ('checkin_date', '<=', checkin_date), ('checkout_date', '>=', checkout_date),
                '&', ('checkin_date', '>=', checkin_date), ('checkout_date', '<=', checkout_date),
                ('id', '!=', current_id)
            ])
            _logger.debug(f"Conflicting Bookings {len(conflicting_bookings)} {conflicting_bookings}")

            if conflicting_bookings:
                raise ValidationError("This room is already assigned to another booking. Please select a different room.")
                return
        if self.booking_id:
            existing_room_ids = self.booking_id.room_line_ids.filtered(lambda line: line.id != self.id).mapped('room_id.id')
            _logger.debug(f"EXISTING ROOM IDS {existing_room_ids}")
            if self.room_id.id in existing_room_ids:
                raise ValidationError(_("This room is already assigned to the current booking. Please select a different room."))

            if self.room_id is None:
                self.booking_id.state = 'confirmed'
                _logger.debug(f"Room ID cleared. Booking state updated to 'not_confirmed' for booking ID {self.booking_id.id}.")
            else:
                # _logger.debug("395", self.room_id, self.booking_id.room_line_ids,self.booking_id.id, self.counter, self.sequence)
                parent_booking_id = self.booking_id.id
                # _logger.debug(parent_booking_id, type(parent_booking_id))
                # numeric_parent_id = parent_booking_id.split('=')[-1].strip('>')
                if isinstance(parent_booking_id, NewId):
                    parent_booking_id_str = str(parent_booking_id)
                    if '_' in parent_booking_id_str:
                        numeric_parent_id = int(parent_booking_id_str.split('_')[-1])
                        parent_booking_ids = self.env['room.booking'].search([('parent_booking_id', '=', numeric_parent_id)]).mapped('id')
                        room_booking_line_ids = self.env['room.booking.line'].search(
                            [('booking_id', 'in', parent_booking_ids),
                             ('counter', '=', self.counter)
                             ],
                            order='id asc'  # Sort in ascending order
                        ).ids
                        room_ids_count = len(room_booking_line_ids)
                        _logger.debug(room_ids_count)
                        _logger.debug(f"Room Booking Line IDs: {room_booking_line_ids}")
                # Find the affected room booking line
                affected_line = self.booking_id.room_line_ids.filtered(
                    lambda line: line.id == self.id)
                # _logger.debug('459', affected_line)

                if affected_line:
                    affected_line_str = str(affected_line.id)

                    # Extract only the numeric part
                    numeric_id = affected_line_str.split('=')[-1].strip('>')
                    numeric_id = int(numeric_id.split('_')[-1])
                    _logger.debug(
                        f"Updating room ID for room_line_id {numeric_id}. New Room ID: {self.room_id.id}")
                    if len(room_booking_line_ids) > 0:
                        recordset = self.env['room.booking.line'].search([
                            ('id', 'in', [numeric_id,
                             room_booking_line_ids[0]])
                        ])
                    else:
                        recordset = self.env['room.booking.line'].search([
                            ('id', 'in', [numeric_id])
                        ])

                    # Check if records exist
                    if recordset:
                        _logger.debug(f"Updating Room Booking Lines with IDs: {recordset.ids}, {self.sequence} ,{self.counter}")

                        # Update all records with the new room_id

                        recordset.write({
                            'room_id': self.room_id.id,
                            'sequence': self.sequence
                        })
                    # Step 2: Update records with a condition on 'room_id'
                    _logger.debug("611",parent_booking_ids, self.room_id.id)
                    bookings = self.env['room.booking'].browse(parent_booking_ids)
                    # bookings = self.env['room.booking'].search([
                    #     ('parent_booking_id', 'in', parent_booking_ids),
                    #     # ('counter', '=', self.counter)
                    # ])
                    matching_line = self.env['room.booking.line'].search([
                        ('booking_id', 'in', parent_booking_ids),
                        ('counter', '=', self.counter)
                    ], limit=1)
                    # _logger.debug('matching_',matching_line,matching_line.booking_id)

                    bookings = self.env['room.booking'].search([
                        ('id', '=', matching_line.booking_id.id)
                    ], limit=1)

                    # Step 2: Update the 'state' based on the condition
                    for booking in bookings:
                        if not self.room_id.id:
                            booking.write({'state': 'not_confirmed'})
                else:
                    _logger.debug(
                        f"New room_line created with Room ID {self.room_id.id}.")

            # self.booking_id.state = 'confirmed'
            _logger.debug(f"Room ID assigned. Booking state updated to 'confirmed' for booking ID {self.booking_id.id}.")
        

    @api.onchange('room_line_ids')
    def _onchange_room_lines(self):
        _logger.debug("Room lines changed")
        """Triggered when room lines are changed to adjust booking state."""
        for line in self.room_line_ids:
            if line.room_id is None:
                self.state = 'not_confirmed'
            else:
                child_booking = self.env['room.booking'].search([
                    ('parent_booking_id', '=', line.booking_id.id),
                    ('sequence', '=', line.sequence)
                ], limit=1)
                # Assign the state of the child booking if found, else use the parent's state
                if child_booking:
                    line.state_ = child_booking.state
                else:
                    line.state_ = 'not_confirmed'
                self.state_ = 'confirmed'
                # self.state = 'confirmed'
                # break

    
    
    def update_adult_record(self, parent_booking, counter):
        [self.env[model].search([('reservation_id', '=', parent_booking)]).write({
            'room_id': self.room_id.id,
            'room_sequence': counter
        }) for model in ['reservation.adult', 'reservation.child', 'reservation.infant']]


    def create_adult_record(self, parent_booking, new_booking, counter):
        _logger.debug("Creating adult record for parent booking: %s", parent_booking.id)
        ModelMap = {
            'reservation.adult': parent_booking.adult_count,
            'reservation.child': parent_booking.child_count,
            'reservation.infant': parent_booking.infant_count,
        }

        # Update room_id for matching sequence records under the parent booking
        for model in ModelMap:
            self.env[model].search([
                ('reservation_id', '=', parent_booking.id),
                ('room_sequence', '=', counter)
            ]).write({'room_id': self.room_id.id})

        # Create new records in new_booking based on parent_booking
        for model_name, count in ModelMap.items():
            parent_records = self.env[model_name].search([
                ('reservation_id', '=', parent_booking.id),
                ('room_sequence', '=', counter)
            ])
            for record in parent_records:
                existing = self.env[model_name].search([
                    ('reservation_id', '=', new_booking.id),
                    ('room_sequence', '=', counter),
                    ('first_name', '=', record.first_name),
                    ('last_name', '=', record.last_name)
                ])
                if not existing:
                    for _ in range(count):
                        self.env[model_name].sudo().create({
                            'reservation_id': new_booking.id,
                            'room_sequence': counter,
                            'first_name': record.first_name,
                            'last_name': record.last_name,
                            'profile': record.profile,
                            'nationality': record.nationality.id if record.nationality else False,
                            'birth_date': record.birth_date,
                            'passport_number': record.passport_number,
                            'id_number': record.id_number,
                            'visa_number': record.visa_number,
                            'id_type': record.id_type,
                            'phone_number': record.phone_number,
                            'relation': record.relation,
                            'room_type_id': self.hotel_room_type.id,
                            'room_id': self.room_id.id,
                        })
                else:
                    existing.write({'room_id': self.room_id.id})


    def _sql_get_booking_totals(self, booking_id):
        """
        Return totals from DB for a single room.booking id using SQL.
        Assumes these fields are stored in the DB.
        """
        self.env.cr.execute("""
            SELECT
                total_rate_after_discount,
                total_meal_after_discount,
                total_fixed_post_after_discount,
                total_total_forecast
            FROM room_booking
            WHERE id = %s
            """, (booking_id,))
        row = self.env.cr.fetchone()
        if not row:
            return (0.0, 0.0, 0.0, 0.0)
        return row  # tuple in the same order as SELECT

    
    #Working
    def write(self, vals):
        
        _logger.debug("Write method called with vals: %s", vals)
        
        if 'state' in vals and 'state_' not in vals:
            vals['state_'] = vals.pop('state')
        python_fields = {'state_', 'room_id'}

        # If we're not touching those, do one SQL UPDATE and return
        if not (set(vals) & python_fields):
            if not vals:   # <-- prevent empty update
                return True

            cols = ', '.join(f"{col} = %s" for col in vals.keys())
            params = list(vals.values()) + [tuple(self.ids)]
            self.env.cr.execute(
                f"UPDATE room_booking_line SET {cols} WHERE id IN %s",
                params
            )
            return True
        record_to_delete, records_to_update, parent_bookings_to_update = [], [], []
        processed_parent_bookings = set()
        for record in self:
            if record.booking_id:
                # Fetch the booking record to get the parent_booking_id
                booking_record = self.env['room.booking'].browse(record.booking_id.id)
                parent_booking_id = booking_record.parent_booking_id
                counter_write = 0
                if parent_booking_id:
                    # _logger.debug("parent_booking_id line 910",parent_booking_id)
                    # Fetch the room_id from the updated vals or fallback to the current record
                    room_id = vals.get('room_id') or record.room_id.id
                    if room_id:
                        # Ensure parent_booking_id is an integer and not a recordset
                        parent_booking_id_int = parent_booking_id.id
                        # Search for matching room.booking.line records
                        booking_line_records = self.env['room.booking.line'].search([
                            ('booking_id', '=', parent_booking_id_int),
                            ('room_id', '=', room_id)
                        ])
                        # _logger.debug("booking_line_records line 923",booking_line_records)

                        # Process the counter values if matching lines are found
                        if booking_line_records:
                            # _logger.debug(f"Found {len(booking_line_records)} records matching the criteria.")
                            for line in booking_line_records:
                                counter_write = line.counter
                                # _logger.debug("counter_write line 930",counter_write)
                                # _logger.debug(f"Room Booking Line ID: {line.id}, Counter: {line.counter}")
            parent_booking = record.booking_id
            # Retrieve room bookings associated with the parent_booking_id
            room_bookings = self.env['room.booking'].search([('parent_booking_id', '=', parent_booking.id)])
            # _logger.debug("room_bookings line 935",room_bookings)
            # _logger.debug(f"Room bookings for parent_booking_id {parent_booking.id}: {room_bookings}")
            if 'room_id' in vals and 'id' in vals:
                room_id = vals.get("room_id")
                record_id = vals.get("id")

                # Ensure the record has a valid database ID
                if isinstance(record_id, list):
                    child_booking = self.env['room.booking.line'].search([
                        # Search for records with IDs in the list
                        ('id', 'in', record_id),
                        # ('counter', '=', counter)  # Include the counter in the search criteria
                    ])
                    if child_booking.exists():
                        [super(RoomBookingLine, child).write({'room_id': room_id}) for child in child_booking]
                        return
                    else:
                        _logger.debug(f"No Room Booking Line found with ID: {record_id}")
                else:
                    _logger.debug(f"Skipping write operation for non-integer ID: {record_id}")

            if 'hotel_room_type' in vals:
                room_type = vals.get("hotel_room_type")
                # _logger.debug('536', room_type)
                related_room_type = vals.get("related_hotel_room_type")
                super(RoomBookingLine, record).write({'hotel_room_type': room_type, 'related_hotel_room_type': room_type, 'room_id': False})

            if 'room_id' in vals and 'id' not in vals:
                room_id = vals.get('room_id')
                new_room_id = vals['room_id']
                counter = vals.get('counter')
                old_room_id = record.room_id
                # _logger.debug("477",old_room_id.id)
                if room_id:
                    super(RoomBookingLine, record).write({'room_id': new_room_id, 'state': 'block'})
                    _logger.debug(f"Updating room_id for record {record.id} to {room_id}")

                if new_room_id:
                    counter = vals.get('counter')
                    super(RoomBookingLine, record).write({'room_id': new_room_id, 'state': 'block'})
                    _logger.debug(f"Updating room_id for record {record.id} to {new_room_id}")
    
                    # Check and update child bookings
                    for child_booking in room_bookings:
                        if not child_booking.room_line_ids:
                            child_booking.sudo().write({
                                'state': 'block',  # Update state to block for reassigned room
                                'room_line_ids': [(0, 0, {
                                    # 'sequence': record.sequence,
                                    'sequence': counter,
                                    'room_id': new_room_id,
                                    'checkin_date': parent_booking.checkin_date,
                                    'checkout_date': parent_booking.checkout_date,
                                    'uom_qty': 1,
                                    'adult_count': record.adult_count,
                                    'child_count': record.child_count,
                                    'infant_count': record.infant_count,
                                    'hotel_room_type': record.hotel_room_type.id,
                                    'counter': counter
                                })]
                            })
                            _logger.debug(f"Updating room_id for record {child_booking.id} to {new_room_id}")
                            

                # If room_id is not provided, move to 'not_confirmed' state
                if not room_id:
                    new_booking_vals = {
                        'parent_booking_id': parent_booking.id,
                        'parent_booking_name': parent_booking.name,
                        'partner_id': parent_booking.partner_id.id,
                        'reference_contact_': parent_booking.reference_contact_,
                        'hotel_room_type': parent_booking.hotel_room_type.id,
                        'group_booking': parent_booking.group_booking.id,
                        'room_line_ids': [],  # No room_line_ids since room_id is unlinked
                        # 'checkin_date': record.checkin_date,
                        'checkin_date': parent_booking.checkin_date,
                        # 'checkout_date': record.checkout_date,
                        'checkout_date': parent_booking.checkout_date,
                        'state': 'not_confirmed',  # Ensure state is set to 'not_confirmed'
                        'is_room_line_readonly': False,
                        'is_offline_search': False
                    }
                    _logger.debug(f"Updating room_id for record {record.id} to {new_room_id}")

                    parent_bookings_to_update.append((parent_booking, {'state': 'confirmed'}))
                    _logger.debug(f"Updating state for record {parent_booking.id} to 'confirmed'")
                    # record.write({'state_': 'confirmed'})
                    continue

                # Ensure the booking is confirmed before assigning a room
                if parent_booking.state == 'not_confirmed' and len(parent_booking.room_line_ids) >= 1:
                    raise UserError(_(
                        "Please confirm the booking before assigning a room."))

                # Move to 'block' state if only one entry exists
                if len(parent_booking.room_line_ids) == 1:
                    parent_bookings_to_update.append((parent_booking, {
                        'state': 'block',
                        'hotel_room_type': record.hotel_room_type.id,
                    }))
                    # _logger.debug(f"Booking {parent_booking.id} moved to 'block' state as it has only one room line.")
                else:
                    counter = vals.get('counter')
                    booking_record = self.env['room.booking'].browse(record.booking_id.id)
                    parent_booking_id = booking_record.parent_booking_id

                    if parent_booking_id:
                        # Fetch the room_id from the updated vals or fallback to the current record
                        room_id = vals.get('room_id') or record.room_id.id
                        if room_id:
                            # Ensure parent_booking_id is an integer and not a recordset
                            parent_booking_id_int = parent_booking_id.id
                            # Search for matching room.booking.line records
                            booking_line_records = self.env['room.booking.line'].search([
                                ('booking_id', '=', parent_booking_id_int),
                                ('room_id', '=', room_id)
                            ])

                            # Process the counter values if matching lines are found
                            if booking_line_records:
                                _logger.debug(f"Found {len(booking_line_records)} records matching the criteria.")
                                for line in booking_line_records:
                                    counter = line.counter
                                    # _logger.debug(f"Room Booking Line ID: {line.id}, Counter: {line.counter}")
                    # Handle unassigned lines and create a new child booking if needed
                    if record.is_unassigned and parent_booking.state == 'confirmed':
                        if parent_booking.id in processed_parent_bookings:
                            continue  # Skip if this parent booking is already processed

                        unassigned_lines = parent_booking.room_line_ids.filtered(lambda line: line.is_unassigned)
                        if len(unassigned_lines) == 1:
                            # Only one room left to assign, update the existing record
                            last_unassigned_line = unassigned_lines[0]
                            room_id = vals.get('room_id') or last_unassigned_line.room_id.id

                            # Update the last unassigned line with the room_id and mark as assigned
                            records_to_update.append((last_unassigned_line, {
                                'is_unassigned': False,
                                'room_id': room_id
                            }))

                            # Update the parent booking state to 'block'
                            parent_bookings_to_update.append((parent_booking, {
                                'state': 'block',
                                'parent_booking_id': parent_booking.id,
                                'parent_booking_name': parent_booking.name,
                            }))

                            
                            _logger.debug(f"Updated parent booking {parent_booking.id}, {self.counter} with the last pending room assignment.")
                            self.update_adult_record(parent_booking.id,self.counter)
                        else:
                            
                            # _logger.debug("this creates the final booking here", len(booking_line_records), record.is_unassigned)
                            room_rate = parent_booking.rate_code.id
                            meal_rate = parent_booking.meal_pattern.id
                            parent_booking_ids = parent_booking.id
                            new_booking_vals = {
                                'parent_booking_id': parent_booking_ids,
                                'parent_booking_name': parent_booking.name,
                                'partner_id': parent_booking.partner_id.id,
                                'nationality': parent_booking.nationality.id,
                                'source_of_business': parent_booking.source_of_business.id,
                                'meal_pattern': meal_rate,
                                'market_segment': parent_booking.market_segment.id,
                                'rate_code': room_rate,
                                'reference_contact_': parent_booking.reference_contact_,
                                # 'hotel_room_type': parent_booking.hotel_room_type.id,
                                'hotel_room_type': record.hotel_room_type.id,
                                'group_booking': parent_booking.group_booking.id,
                                'house_use': parent_booking.house_use,
                                'complementary': parent_booking.complementary,
                                'vip': parent_booking.vip,
                                'room_count':1,
                                'adult_count':parent_booking.adult_count,
                                'child_count': parent_booking.child_count,
                                'infant_count': parent_booking.infant_count,
                                'complementary_codes': parent_booking.complementary_codes.id,
                                'house_use_codes': parent_booking.house_use_codes.id,
                                'vip_code': parent_booking.vip_code.id,
                                'notes': parent_booking.notes,
                                # 'show_in_tree':True,
                                'room_line_ids': [(0, 0, {
                                    # 'sequence': record.sequence,
                                    'sequence': counter,
                                    'room_id': room_id,
                                    'checkin_date': parent_booking.checkin_date,
                                    'checkout_date': parent_booking.checkout_date,
                                    'uom_qty': 1,
                                    'adult_count': record.adult_count,
                                    'child_count': record.child_count,
                                    'infant_count': record.infant_count,
                                    'is_unassigned': False,
                                    'hotel_room_type': record.hotel_room_type.id,
                                    'counter': counter,
                                })],
                                'posting_item_ids': [(0, 0, {
                                    'posting_item_id': posting_item.posting_item_id.id,
                                    'item_code': posting_item.item_code,
                                    'description': posting_item.description,
                                    'posting_item_selection': posting_item.posting_item_selection,
                                    'from_date': posting_item.from_date,
                                    'to_date': posting_item.to_date,
                                    'default_value': posting_item.default_value,
                                }) for posting_item in parent_booking.posting_item_ids],
                                # 'posting_item_ids': [(6, 0, parent_booking.posting_item_ids.ids)],
                                'checkin_date': parent_booking.checkin_date,
                                'checkout_date': parent_booking.checkout_date,
                                'state': 'block',
                                'group_booking': parent_booking.group_booking.id,
                                'is_offline_search': False,
                                # 'is_grp_company': parent_booking.is_grp_company,
                                'is_agent': parent_booking.is_agent,
                                'no_of_nights': parent_booking.no_of_nights,
                                'room_price': parent_booking.room_price,
                                'use_price': parent_booking.use_price,
                                'room_discount':parent_booking.room_discount,
                                'room_is_amount':parent_booking.room_is_amount,
                                'room_amount_selection':parent_booking.room_amount_selection,
                                'room_is_percentage':parent_booking.room_is_percentage,
                                'use_meal_price': parent_booking.use_meal_price,
                                'meal_price': parent_booking.meal_price,
                                'meal_child_price': parent_booking.meal_child_price,
                                'meal_discount':parent_booking.meal_discount,
                                'meal_amount_selection': parent_booking.meal_amount_selection,
                                'meal_is_amount':parent_booking.meal_is_amount,
                                'meal_is_percentage':parent_booking.meal_is_percentage,
                                'payment_type': parent_booking.payment_type,
                                # 'is_room_line_readonly': True,
                                
                            }

                            
                            # Create the new child booking
                            new_id_booking =self.env['room.booking'].create(new_booking_vals)
                            _logger.debug(f"New child booking created with ID: {new_id_booking.id}")
                            

                            # Fetch the required fields
                            total_forecast_ = new_id_booking.total_total_forecast
                            # print('total_forecast_', total_forecast_)
                            no_of_nights_ = new_id_booking.no_of_nights

                            # Optionally, log the values or store them in variables
                            rate_forecast_total = total_forecast_ / no_of_nights_ if no_of_nights_ else 0
                            # print('rate_forecast_total',rate_forecast_total)
                            # Fetch the related rate_forecast_ids
                            rate_forecast_lines = new_id_booking.rate_forecast_ids

                            # Loop through each related rate_forecast record and update the total field
                            for rate_forecast in rate_forecast_lines:
                                rate_forecast.write({
                                    'total': rate_forecast_total,
                                })
                                _logger.debug(f"Updated rate_forecast ID {rate_forecast.id} with total: {rate_forecast_total}")

                            parent = new_id_booking.parent_booking_id
                            if parent and parent.room_count <= 2:
                                # 1) Turn on your override flag so the compute method skips
                                parent.manual_override = True

                                # 2) Sample one line to get the original components
                                sample_line = parent.rate_forecast_ids[:1]
                                # print(f"Sample line: {sample_line}")
                                if not sample_line:
                                    _logger.warning("No forecast lines on parent %s", parent.id)
                                    return

                                orig = sample_line[0]
                                # print(f"Original line: {orig}")
                                rate   = float(orig.rate or 0)
                                meals  = float(orig.meals or 0)
                                packs  = float(orig.packages or 0)
                                fp     = float(orig.fixed_post or 0)
                                bdisc  = float(orig.before_discount or 0)
                                # print(f"Original values: rate={rate}, meals={meals}, packs={packs}, fp={fp}, bdisc={bdisc}")

                                # 3) Distribute your target total (308.5) in proportion
                                target = rate_forecast_total  # e.g. 308.5
                                # print(f"Target total: {target}")
                                subtotal = rate + meals + packs + fp
                                # print(f"Subtotal: {subtotal}")
                                if subtotal:
                                    factor = target / subtotal
                                    rate_new  = round(rate   / 2, 2)
                                    meals_new = round(meals  / 2, 2)
                                    packs_new = round(packs  / 2, 2)
                                    fp_new    = round(fp     / 2, 2)
                                else:
                                    # fallback: split equally
                                    per = round(target / 4, 2)
                                    rate_new = meals_new = packs_new = fp_new = per

                                total_new       = rate_new + meals_new + packs_new + fp_new
                                _logger.debug(f"New values: rate_new={rate_new}, meals_new={meals_new}, packs_new={packs_new}, fp_new={fp_new}, total_new={total_new}")
                                bdisc_new       = round(bdisc / 2, 2)  # or whatever logic you need
                                _logger.debug(f"New before discount: {bdisc_new}")

                                # 4) **Bulk-update via ORM** (this will stick)
                                parent.rate_forecast_ids.write({
                                    'rate':            rate_new,
                                    'meals':           meals_new,
                                    'packages':        packs_new,
                                    'fixed_post':      fp_new,
                                    'before_discount': bdisc_new,
                                    'total':           rate_forecast_total,
                                })

                                # 5) Log success
                                _logger.debug(
                                    "Forecast for booking %s overridden: rate=%s, meals=%s, packages=%s, "
                                    "fixed_post=%s, total=%s, before_discount=%s",
                                    parent.id, rate_new, meals_new, packs_new, fp_new, total_new, bdisc_new
                                )
                            else:
                                _logger.debug(
                                    "Skipping override: parent %s room_count=%s",
                                    getattr(parent, 'id', None),
                                    getattr(parent, 'room_count', None)
                                )

                            # Search for room.booking.line records with the same counter
                            lines_to_delete = self.env['room.booking.line'].search([('counter', '=', self.counter),  ('booking_id', '=', parent_booking.id)])
                            _logger.debug(f"Lines to delete: {lines_to_delete}")
                            record_to_delete.append(lines_to_delete)
                            # Delete the records
                            
                            self.create_adult_record(parent_booking,new_id_booking, self.counter)
                            _logger.debug(f"Adult record created for counter {self.counter}")

                        # Mark the unassigned line as processed
                        records_to_update.append((record, {'is_unassigned': False, 'room_id': room_id}))
                        _logger.debug(f"Marking record {record.id} as processed")
                        processed_parent_bookings.add(parent_booking.id)
                        _logger.debug(f"Marking parent booking {parent_booking.id} as processed")
            else:
                if 'checkout_date' in vals and counter_write != 0:
                    super(RoomBookingLine, record).write(
                        {'counter': counter_write})

                # No room_id provided; leave the line unchanged
                # _logger.debug(f"No room_id provided for line {record.id}. Keeping it unchanged.")

        # Perform all pending updates
        for record, record_vals in records_to_update:
            # _logger.debug(f"Updating record: {record}, values: {record_vals}")
            super(RoomBookingLine, record).write(record_vals)

        for booking, booking_vals in parent_bookings_to_update:
            # _logger.debug(f"Updating parent booking: {booking}, values: {booking_vals}")
            booking.write(booking_vals)
            _logger.debug(f"Updating parent booking: {booking}, values: {booking_vals}")
        
        
        # Call super to finalize other updates
        result = super(RoomBookingLine, self).write(vals)
        _logger.debug(f"Call super to finalize other updates: {result}")
        
                    
        lines_to_update = None
        counter_line = 0
        booking_id_check = 0
        if 'room_id' in vals:
            for line in self:
                counter_line = line.counter
                booking_id_check = line.booking_id.id

                # Ensure we have a booking and a sequence
                if line.booking_id and line.counter and line.room_id:
                    # Update Adults
                    adults_to_update = self.env['reservation.adult'].search([
                        ('reservation_id', '=', line.booking_id.id),
                        ('room_sequence', '=', line.counter)
                    ])
                    _logger.debug(f"Adults to update: {adults_to_update}")
                    if adults_to_update:
                        adults_to_update.write({'room_id': line.room_id.id})
                        _logger.debug(f"Adults updated for line {line.id}")

                    # Update Children
                    children_to_update = self.env['reservation.child'].search([
                        ('reservation_id', '=', line.booking_id.id),
                        ('room_sequence', '=', line.counter)
                    ])
                    if children_to_update:
                        children_to_update.write({'room_id': line.room_id.id})

                    # Update Children
                    infants_to_update = self.env['reservation.infant'].search([
                            ('reservation_id', '=', line.booking_id.id),
                            ('room_sequence', '=', line.counter)
                    ])
                    if infants_to_update:
                        infants_to_update.write({'room_id': line.room_id.id})


        # _logger.debug("1203 ",counter_line,len(self.ids))
        if counter_line != 0 and booking_id_check !=0:
            lines_to_check = self.env['room.booking.line'].search([
                ('booking_id', '=', booking_id_check),

            ])
            _logger.debug(f"Lines to check: {lines_to_check}")
            if counter_line < len(lines_to_check):
                _logger.debug(f"Counter line is less than len(lines_to_check)")
                # update child records using room_id-
                child_booking_ids = self.env['room.booking'].search([('parent_booking_id', '=', booking_id_check)]).ids
                _logger.debug(f"Child booking ids: {child_booking_ids}")
                lines_to_update = self.env['room.booking.line'].search([
                    ('booking_id', 'in', child_booking_ids),
                    ('counter', '=', counter_line)
                ])
                _logger.debug(f"Lines to update: {lines_to_update}")
                # super(RoomBookingLine, self).write(vals)
                result = lines_to_update.write({'room_id': line.room_id.id})
                _logger.debug(f"Result: {result}")

        for line in record_to_delete:
            # Get ID of record (only primary key ID)
            line_id = line.id

        # 🧹 STEP 1: Clear ORM cache — VERY IMPORTANT
        # This prevents Odoo from trying to flush invalid in-memory records
        self.env.invalidate_all()

        # 🧹 STEP 2: Collect only IDs, avoid ORM objects
        record_ids = [rec.id for rec in record_to_delete]

        # 🧹 STEP 3: Now pure SQL loop, no ORM involved
        for line_id in record_ids:
            # Get booking_id and counter directly from DB
            self.env.cr.execute("""
                SELECT booking_id, counter 
                FROM room_booking_line
                WHERE id = %s
            """, (line_id,))
            result = self.env.cr.fetchone()

            # If record not found (already deleted), skip safely
            if not result:
                continue

            booking_id, seq = result

            # 1️⃣ Delete M2M relation first (important to avoid FK errors)
            self.env.cr.execute("""
                DELETE FROM room_forecast_booking_line_rel
                WHERE booking_line_id = %s
            """, (line_id,))

            # 2️⃣ Delete the booking line itself
            self.env.cr.execute("""
                DELETE FROM room_booking_line 
                WHERE id = %s
            """, (line_id,))

            # 3️⃣ Delete matching reservation records
            for model_table in ('reservation_adult', 'reservation_child', 'reservation_infant'):
                self.env.cr.execute(f"""
                    DELETE FROM {model_table}
                    WHERE reservation_id = %s AND room_sequence = %s
                """, (booking_id, seq))

            # 4️⃣ Update room_count in room_booking table
            self.env.cr.execute("""
                UPDATE room_booking
                SET room_count = room_count - 1
                WHERE id = %s
            """, (booking_id,))

        # 🧹 STEP 4: Commit transaction after all deletions
        self.env.cr.commit()
        
        return result

    def _delete_child_booking_records(self, counter, parent_booking):
        """Helper function to delete child booking records."""
        # Find all child bookings related to this parent booking
        child_bookings = self.env['room.booking'].search([
            ('parent_booking_id', '=', parent_booking.id)
        ])

        for child_booking in child_bookings:
            # Find matching room lines in child booking based on counter
            matching_lines = child_booking.room_line_ids.filtered(
                lambda line: line.counter == counter
            )

            if matching_lines:
                # Set state to cancel before deletion
                matching_lines.sudo().write({'state': 'cancel'})
                # Delete matching lines
                matching_lines.sudo().unlink()

                # If no room lines left, set booking to cancel and delete
                if not child_booking.room_line_ids:
                    child_booking.sudo().write({
                        'show_in_tree': False,
                        'state': 'cancel'
                    })
                    child_booking.sudo().unlink()

    # def unlink(self):
    #     """Handle deletion of room booking lines."""
    #     for record in self:
    #         if record.booking_id and not record.booking_id.parent_booking_id:
    #             # Set state to cancel before deletion
    #             record.write({'state': 'cancel'})
    #             self._delete_child_booking_records(
    #                 record.counter, record.booking_id)

    #             # Update parent booking state if needed
    #             remaining_lines = record.booking_id.room_line_ids - record
    #             if not remaining_lines:
    #                 record.booking_id.write({
    #                     'state': 'cancel'
    #                 })

    #     return super(RoomBookingLine, self).unlink()

    def unlink(self):
        # 1) Only consider “root” lines (no parent_booking_id)
        roots = self.filtered(lambda r: r.booking_id and not r.booking_id.parent_booking_id)
        root_ids = roots.ids
        if root_ids:
            # 2) Batch-cancel all of them in one SQL UPDATE
            self.env.cr.execute(
                "UPDATE room_booking_line SET state_ = %s WHERE id IN %s",
                ('cancel', tuple(root_ids))
            )

            # 3) Call your child-booking cleanup exactly once per (booking, counter)
            pairs = {(r.booking_id.id, r.counter) for r in roots}
            LineModel = self.env['room.booking.line']
            for booking_id, counter in pairs:
                booking = self.env['room.booking'].browse(booking_id)
                LineModel._delete_child_booking_records(counter, booking)

            # 4) Find which parent bookings have *only* these lines
            booking_ids = {r.booking_id.id for r in roots}
            to_cancel = []
            for bid in booking_ids:
                booking = self.env['room.booking'].browse(bid)
                # if all its current line-ids are in root_ids, they’ll be gone
                if set(booking.room_line_ids.ids) <= set(root_ids):
                    to_cancel.append(bid)
            if to_cancel:
                # batch-cancel those parent bookings
                self.env['room.booking'].browse(to_cancel).write({'state': 'cancel'})

        # 5) Finally remove *all* the lines (roots + any children)
        return super(RoomBookingLine, self).unlink()

    room_forecast_ids = fields.Many2many(
        'room.rate.forecast',
        'room_forecast_booking_line_rel',  # Relational table name
        'booking_line_id',  # Column for room.booking.line ID
        'forecast_id',  # Column for room.rate.forecast ID
        string="Forecasts",
        help="Forecast records associated with this room line."
    )