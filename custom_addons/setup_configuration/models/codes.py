from odoo import api, models, fields

class AdditionalAttribute(models.Model):
    _name = 'additional.attribute'
    _description = 'Additional Attribute'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_desc = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbr = fields.Char(string="Arabic Abbreviation",tracking=True)
    length = fields.Integer(string="Length",tracking=True)

    type = fields.Selection([
        ('code', 'Code'),
        ('string', 'String'),
        ('number', 'Number'),
        ('money', 'Money'),
        ('date', 'Date'),
        ('flag', 'Flag'),
    ], string="Type", required=True,tracking=True)

    entity_target = fields.Selection([
        ('profile', 'Profile'),
        ('reservations', 'Reservations'),
    ], string="Entity Target", required=True,tracking=True)

    mandatory = fields.Boolean(string="Mandatory", default=False,tracking=True)

class Template(models.Model):
    _name = 'template'
    _description = 'Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    usage = fields.Selection([
        ('posting', 'Posting'),
        ('other', 'Other')], string="Usage", required=True,tracking=True)
    
    name = fields.Char(string="Name", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    language = fields.Selection([
        ('default', 'Interface Default'),
        ('no', 'No'),
        ('arabic', 'Arabic'),
        ('english', 'English')], string="Language", default='default',tracking=True)
    
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    host = fields.Char(string="Host",tracking=True)
    extension = fields.Char(string="Extension", default="Htm",tracking=True)
    file_size = fields.Integer(string="File Size",tracking=True)
    file_name = fields.Char(string="File Name",tracking=True)
    is_obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

    # Placeholder for storing template content
    template_content = fields.Html(string="Template Content",tracking=True)

    # Actions for importing/exporting templates
    def action_import_template(self):
        # Implement the logic for importing a template
        pass

    def action_export_template(self):
        # Implement the logic for exporting a template
        pass

    def action_create_template(self):
        # Implement the logic for creating a new template
        pass

class CommentCategory(models.Model):
    _name = 'comment.category'
    _description = 'Comment Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    arabic_desc = fields.Char(string="Arabic Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_abbr = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

    # Usage fields
    usage_profile = fields.Boolean(string="Profile",tracking=True)
    usage_reservation = fields.Boolean(string="Reservation / Inhouse",tracking=True)
    usage_room_inspection = fields.Boolean(string="Room Inspection",tracking=True)
    usage_group_profile = fields.Boolean(string="Group Profile",tracking=True)

class TracePredefinedText(models.Model):
    _name = 'trace.predefined.text'
    _description = 'Trace Predefined Text'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    number = fields.Char(string="Number", required=True,tracking=True)
    text = fields.Char(string="Text",tracking=True)
    arabic_text = fields.Char(string="Arabic Text",tracking=True)
    department = fields.Selection([
        ('user', 'User'),
        ('front_desk', 'Front Desk'),
        ('reservation', 'Reservation'),
        ('cashier', 'Cashier'),
        ('house_keeping', 'House Keeping'),
        ('concierge', 'Concierge'),
        ('fnb', 'F&B'),
        ('maintenance', 'Maintenance'),
        ('it', 'IT'),
        ('hr', 'H/R'),
        ('security', 'Security'),
        ('management', 'Management')
    ], string="Department",tracking=True)

class MessagePredefinedText(models.Model):
    _name = 'message.predefined.text'
    _description = 'Message Predefined Text'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    number = fields.Char(string="Number", required=True,tracking=True)
    text = fields.Text(string="Text", required=True,tracking=True)
    arabic_text = fields.Text(string="Arabic Text",tracking=True)

class LocatorsPredefinedText(models.Model):
    _name = 'locators.predefined.text'
    _description = 'Locators Predefined Text'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    number = fields.Char(string="Number", required=True,tracking=True)
    text = fields.Char(string="Text", required=True,tracking=True)
    arabic_text = fields.Char(string="Arabic Text",tracking=True)

