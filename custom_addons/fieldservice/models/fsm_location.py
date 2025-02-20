# Copyright (C) 2018 - TODAY, Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FSMLocation(models.Model):
    _name = "fsm.location"
    # _inherits = {"res.partner": "partner_id"}
    _inherit = ["mail.thread", "mail.activity.mixin", "fsm.model.mixin"]
    _description = "Field Service Location"
    _stage_type = "location"
    _rec_names_search = ["complete_name"]

    # Add fields that were previously inherited from res.partner
    name = fields.Char(string='Name', required=True,tracking=True)
    street = fields.Char(tracking=True)
    street2 = fields.Char(tracking=True)
    city = fields.Char(tracking=True)
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(tracking=True)
    country_id = fields.Many2one('res.country', string='Country')
    email = fields.Char(tracking=True)
    phone = fields.Char(tracking=True)
    mobile = fields.Char(tracking=True)
    tz = fields.Char(tracking=True)

    stage_id = fields.Many2one('fsm.stage', string="Stage ID")
    active = fields.Boolean(default=True,tracking=True)  

    # direction = fields.Char()
    direction = fields.Char(string=_("Direction"), translate=True,tracking=True)
    partner_id = fields.Many2one(
        "res.partner",tracking=True,
        string="Related Partner"
        
    )
    owner_id = fields.Many2one(
        "res.partner",
        string="Related Owner",
        required=True,
        ondelete="restrict",
        auto_join=True,tracking=True,
    )
    contact_id = fields.Many2one(
        "res.partner",
        string="Primary Contact",
        domain="[('is_company', '=', False)," " ('fsm_location', '=', False)]",
        index=True,tracking=True,
    )
    # description = fields.Char()
    description = fields.Char(string=_("Description"), translate=True,tracking=True)
    territory_id = fields.Many2one("res.territory", string="Territory",tracking=True)
    branch_id = fields.Many2one("res.branch", string="Branch",tracking=True)
    district_id = fields.Many2one("res.district", string="District",tracking=True)
    region_id = fields.Many2one("res.region", string="Region",tracking=True)
    territory_manager_id = fields.Many2one(
        string="Primary Assignment", related="territory_id.person_id",tracking=True
    )
    district_manager_id = fields.Many2one(
        string="District Manager", related="district_id.partner_id",tracking=True
    )
    region_manager_id = fields.Many2one(
        string="Region Manager", related="region_id.partner_id",tracking=True
    )
    branch_manager_id = fields.Many2one(
        string="Branch Manager", related="branch_id.partner_id",tracking=True
    )

    calendar_id = fields.Many2one("resource.calendar", string="Office Hours",tracking=True)
    fsm_parent_id = fields.Many2one("fsm.location", string="Parent", index=True,tracking=True)
    notes = fields.Text(string="Location Notes",tracking=True)
    person_ids = fields.One2many("fsm.location.person", "location_id", string="Workers")
    contact_count = fields.Integer(
        string="Contacts Count", compute="_compute_contact_ids",tracking=True
    )
    equipment_count = fields.Integer(
        string="Equipment", compute="_compute_equipment_ids",tracking=True
    )
    sublocation_count = fields.Integer(
        string="Sub Locations", compute="_compute_sublocation_ids",tracking=True
    )
    complete_name = fields.Char(
        compute="_compute_complete_name", recursive=True, store=True, translate=True,tracking=True
    )

    # @api.model_create_multi
    # def create(self, vals):
    #     res = super().create(vals)
    #     res.write({"fsm_location": True})
    #     return res

    @api.model_create_multi
    def create(self, vals_list):
        # Create the FSM Location first
        locations = super(FSMLocation, self).create(vals_list)

        # Now mark the underlying partner records as inactive
        for loc in locations:
            loc.partner_id.write({'active': False})

        return locations

    # @api.depends("partner_id.name", "fsm_parent_id.complete_name", "ref")
    # def _compute_complete_name(self):
    #     for loc in self:
    #         if loc.fsm_parent_id:
    #             if loc.ref:
    #                 loc.complete_name = "{} / [{}] {}".format(
    #                     loc.fsm_parent_id.complete_name, loc.ref, loc.partner_id.name
    #                 )
    #             else:
    #                 loc.complete_name = "{} / {}".format(
    #                     loc.fsm_parent_id.complete_name, loc.partner_id.name
    #                 )
    #         else:
    #             if loc.ref:
    #                 loc.complete_name = f"[{loc.ref}] {loc.partner_id.name}"
    #             else:
    #                 loc.complete_name = loc.partner_id.name

    @api.depends("name", "fsm_parent_id.complete_name")
    def _compute_complete_name(self):
        for loc in self:
            if loc.fsm_parent_id:
                loc.complete_name = f"{loc.fsm_parent_id.complete_name} / {loc.name}"
            else:
                loc.complete_name = loc.name


    @api.onchange("fsm_parent_id")
    def _onchange_fsm_parent_id(self):
        self.owner_id = self.fsm_parent_id.owner_id or False
        self.contact_id = self.fsm_parent_id.contact_id or False
        self.direction = self.fsm_parent_id.direction or False
        self.street = self.fsm_parent_id.street or False
        self.street2 = self.fsm_parent_id.street2 or False
        self.city = self.fsm_parent_id.city or False
        self.zip = self.fsm_parent_id.zip or False
        self.state_id = self.fsm_parent_id.state_id or False
        self.country_id = self.fsm_parent_id.country_id or False
        self.tz = self.fsm_parent_id.tz or False
        self.territory_id = self.fsm_parent_id.territory_id or False

    @api.onchange("territory_id")
    def _onchange_territory_id(self):
        self.territory_manager_id = self.territory_id.person_id or False
        self.branch_id = self.territory_id.branch_id or False
        if self.env.company.auto_populate_persons_on_location:
            person_vals_list = []
            for person in self.territory_id.person_ids:
                person_vals_list.append(
                    (0, 0, {"person_id": person.id, "sequence": 10})
                )
            self.person_ids = self.territory_id and person_vals_list or False

    @api.onchange("branch_id")
    def _onchange_branch_id(self):
        self.branch_manager_id = self.territory_id.branch_id.partner_id or False
        self.district_id = self.branch_id.district_id or False

    @api.onchange("district_id")
    def _onchange_district_id(self):
        self.district_manager_id = self.branch_id.district_id.partner_id or False
        self.region_id = self.district_id.region_id or False

    @api.onchange("region_id")
    def _onchange_region_id(self):
        self.region_manager_id = self.region_id.partner_id or False

    def comp_count(self, contact, equipment, loc):
        if equipment:
            for child in loc:
                child_locs = self.env["fsm.location"].search(
                    [("fsm_parent_id", "=", child.id)]
                )
                equip = self.env["fsm.equipment"].search_count(
                    [("location_id", "=", child.id)]
                )
            if child_locs:
                for loc in child_locs:
                    equip += loc.comp_count(0, 1, loc)
            return equip
        elif contact:
            for child in loc:
                child_locs = self.env["fsm.location"].search(
                    [("fsm_parent_id", "=", child.id)]
                )
                con = self.env["res.partner"].search_count(
                    [("service_location_id", "=", child.id)]
                )
            if child_locs:
                for loc in child_locs:
                    con += loc.comp_count(1, 0, loc)
            return con
        else:
            for child in loc:
                child_locs = self.env["fsm.location"].search(
                    [("fsm_parent_id", "=", child.id)]
                )
                subloc = self.env["fsm.location"].search_count(
                    [("fsm_parent_id", "=", child.id)]
                )
            if child_locs:
                for loc in child_locs:
                    subloc += loc.comp_count(0, 0, loc)
            return subloc

    def get_action_views(self, contact, equipment, loc):
        if equipment:
            for child in loc:
                child_locs = self.env["fsm.location"].search(
                    [("fsm_parent_id", "=", child.id)]
                )
                equip = self.env["fsm.equipment"].search(
                    [("location_id", "=", child.id)]
                )
            if child_locs:
                for loc in child_locs:
                    equip += loc.get_action_views(0, 1, loc)
            return equip
        elif contact:
            for child in loc:
                child_locs = self.env["fsm.location"].search(
                    [("fsm_parent_id", "=", child.id)]
                )
                con = self.env["res.partner"].search(
                    [("service_location_id", "=", child.id)]
                )
            if child_locs:
                for loc in child_locs:
                    con += loc.get_action_views(1, 0, loc)
            return con
        else:
            for child in loc:
                child_locs = self.env["fsm.location"].search(
                    [("fsm_parent_id", "=", child.id)]
                )
                subloc = child_locs
            if child_locs:
                for loc in child_locs:
                    subloc += loc.get_action_views(0, 0, loc)
            return subloc

    def action_view_contacts(self):
        """
        This function returns an action that display existing contacts
        of given fsm location id and its child locations. It can
        either be a in a list or in a form view, if there is only one
        contact to show.
        """
        for location in self:
            action = self.env["ir.actions.act_window"]._for_xml_id(
                "contacts.action_contacts"
            )
            contacts = self.get_action_views(1, 0, location)
            action["context"] = self.env.context.copy()
            action["context"].update({"group_by": ""})
            action["context"].update({"default_service_location_id": self.id})
            if len(contacts) == 0 or len(contacts) > 1:
                action["domain"] = [("id", "in", contacts.ids)]
            else:
                action["views"] = [
                    (self.env.ref("base." + "view_partner_form").id, "form")
                ]
                action["res_id"] = contacts.id
            return action

    def _compute_contact_ids(self):
        for loc in self:
            contacts = self.comp_count(1, 0, loc)
            loc.contact_count = contacts

    def action_view_equipment(self):
        """
        This function returns an action that display existing
        equipment of given fsm location id. It can either be a in
        a list or in a form view, if there is only one equipment to show.
        """
        for location in self:
            action = self.env["ir.actions.act_window"]._for_xml_id(
                "fieldservice.action_fsm_equipment"
            )
            equipment = self.get_action_views(0, 1, location)
            action["context"] = self.env.context.copy()
            action["context"].update({"group_by": ""})
            action["context"].update({"default_location_id": self.id})
            if len(equipment) == 0 or len(equipment) > 1:
                action["domain"] = [("id", "in", equipment.ids)]
            else:
                action["views"] = [
                    (
                        self.env.ref("fieldservice." + "fsm_equipment_form_view").id,
                        "form",
                    )
                ]
                action["res_id"] = equipment.id
            return action

    def _compute_sublocation_ids(self):
        for loc in self:
            loc.sublocation_count = self.comp_count(0, 0, loc)

    def action_view_sublocation(self):
        """
        This function returns an action that display existing
        sub-locations of a given fsm location id. It can either be a in
        a list or in a form view, if there is only one sub-location to show.
        """
        for location in self:
            action = self.env["ir.actions.act_window"]._for_xml_id(
                "fieldservice.action_fsm_location"
            )
            sublocation = self.get_action_views(0, 0, location)
            action["context"] = self.env.context.copy()
            action["context"].update({"group_by": ""})
            action["context"].update({"default_fsm_parent_id": self.id})
            if len(sublocation) > 1 or len(sublocation) == 0:
                action["domain"] = [("id", "in", sublocation.ids)]
            else:
                action["views"] = [
                    (
                        self.env.ref("fieldservice." + "fsm_location_form_view").id,
                        "form",
                    )
                ]
                action["res_id"] = sublocation.id
            return action

    def geo_localize(self):
        return self.partner_id.geo_localize()

    def _compute_equipment_ids(self):
        for loc in self:
            loc.equipment_count = self.comp_count(0, 1, loc)

    @api.constrains("fsm_parent_id")
    def _check_location_recursion(self):
        if not self._check_recursion(parent="fsm_parent_id"):
            raise ValidationError(_("You cannot create recursive location."))
        return True

    @api.onchange("country_id")
    def _onchange_country_id(self):
        if self.country_id and self.country_id != self.state_id.country_id:
            self.state_id = False

    @api.onchange("state_id")
    def _onchange_state(self):
        if self.state_id.country_id:
            self.country_id = self.state_id.country_id


class FSMPerson(models.Model):
    _inherit = "fsm.person"

    location_ids = fields.One2many(
        "fsm.location.person", "person_id", string="Linked Locations"
    )