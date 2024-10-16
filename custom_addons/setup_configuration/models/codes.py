from odoo import api, models, fields

class AdditionalAttribute(models.Model):
    _name = 'additional.attribute'
    _description = 'Additional Attribute'

    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    length = fields.Integer(string="Length")

    type = fields.Selection([
        ('code', 'Code'),
        ('string', 'String'),
        ('number', 'Number'),
        ('money', 'Money'),
        ('date', 'Date'),
        ('flag', 'Flag'),
    ], string="Type", required=True)

    entity_target = fields.Selection([
        ('profile', 'Profile'),
        ('reservations', 'Reservations'),
    ], string="Entity Target", required=True)

    mandatory = fields.Boolean(string="Mandatory", default=False)

class Template(models.Model):
    _name = 'template'
    _description = 'Template'

    usage = fields.Selection([
        ('posting', 'Posting'),
        ('other', 'Other')], string="Usage", required=True)
    
    name = fields.Char(string="Name", required=True)
    description = fields.Char(string="Description")
    language = fields.Selection([
        ('default', 'Interface Default'),
        ('no', 'No'),
        ('arabic', 'Arabic'),
        ('english', 'English')], string="Language", default='default')
    
    user_sort = fields.Integer(string="User Sort", default=0)
    host = fields.Char(string="Host")
    extension = fields.Char(string="Extension", default="Htm")
    file_size = fields.Integer(string="File Size")
    file_name = fields.Char(string="File Name")
    is_obsolete = fields.Boolean(string="Obsolete", default=False)

    # Placeholder for storing template content
    template_content = fields.Html(string="Template Content")

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

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    arabic_desc = fields.Char(string="Arabic Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

    # Usage fields
    usage_profile = fields.Boolean(string="Profile")
    usage_reservation = fields.Boolean(string="Reservation / Inhouse")
    usage_room_inspection = fields.Boolean(string="Room Inspection")
    usage_group_profile = fields.Boolean(string="Group Profile")

class TracePredefinedText(models.Model):
    _name = 'trace.predefined.text'
    _description = 'Trace Predefined Text'

    number = fields.Char(string="Number", required=True)
    text = fields.Char(string="Text")
    arabic_text = fields.Char(string="Arabic Text")
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
    ], string="Department")

class MessagePredefinedText(models.Model):
    _name = 'message.predefined.text'
    _description = 'Message Predefined Text'

    number = fields.Char(string="Number", required=True)
    text = fields.Text(string="Text", required=True)
    arabic_text = fields.Text(string="Arabic Text")

class LocatorsPredefinedText(models.Model):
    _name = 'locators.predefined.text'
    _description = 'Locators Predefined Text'

    number = fields.Char(string="Number", required=True)
    text = fields.Char(string="Text", required=True)
    arabic_text = fields.Char(string="Arabic Text")

