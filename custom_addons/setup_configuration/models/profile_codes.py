from odoo import api, models, fields


class AddressType(models.Model):

    _name = 'address.type'
    _description = 'Address Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_desc = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbr = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

    # Type of Address Selection
    address_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('mailing', 'Mailing Address'),
        ('billing', 'Billing Address'),
        ('visitors', 'Visitors Address'),
        ('home', 'Home Address'),
        ('work', 'Work Address')
    ], string="Type", default='unspecified',tracking=True)

class ContactMethodType(models.Model):
    _name = 'contact.method.type'
    _description = 'Contact Method Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_desc = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbr = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

    # Type of Contact Method Selection
    contact_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('phone', 'Phone'),
        ('mobile', 'Mobile'),
        ('pager', 'Pager'),
        ('fax', 'Fax'),
        ('email', 'E-Mail'),
        ('website', 'Web Site')
    ], string="Type", default='unspecified',tracking=True)

class ProfileCategory(models.Model):
    _name = 'profile.category'
    _description = 'Profile Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'code'
    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_desc = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbr = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

    # Profile type selection
    profile_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('individual', 'Individual'),
        ('business', 'Business'),
        ('internal', 'Internal'),
        ('party_group', 'Party Group'),
        ('guest_profile', 'Guest Profile'),
    ], string="Type", default='unspecified',tracking=True)

class DocumentType(models.Model):
    _name = 'document.type'
    _description = 'Document Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_desc = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbr = fields.Char(string="Arabic Abbreviation",tracking=True)
    valid_extensions = fields.Char(string="Valid Extensions",tracking=True)

    # Type selection
    doc_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('picture', 'Picture'),
        ('media', 'Media'),
        ('video', 'Video'),
        ('office', 'Office'),
        ('web', 'Web'),
    ], string="Type", default='unspecified',tracking=True)

    # Mandatory fields
    mandatory_attachment = fields.Boolean(string="Attachment",tracking=True)
    mandatory_doc_number = fields.Boolean(string="Doc. Number",tracking=True)
    mandatory_doc_country = fields.Boolean(string="Doc. Country",tracking=True)
    mandatory_doc_expiry = fields.Boolean(string="Doc. Expiry",tracking=True)

class CreditCardType(models.Model):
    _name = 'credit.card.type'
    _description = 'Credit Card Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_desc = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbr = fields.Char(string="Arabic Abbreviation",tracking=True)
    number_mask = fields.Char(string="Number Mask",tracking=True)
    department_id = fields.Char(string="Department",tracking=True)
    
    # Card Type
    card_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('visa', 'Visa'),
        ('master', 'Master'),
        ('diners', 'Diners'),
        ('amex', 'Amex')
    ], string="Type", default='unspecified',tracking=True)

    # Duplicate Check
    check_duplicate = fields.Selection([
        ('no', 'No'),
        ('warning', 'Warning Only'),
        ('error', 'Error')
    ], string="Check Duplicate", default='no',tracking=True)

    check_all_profiles = fields.Boolean(string="Check All Profiles", default=False,tracking=True)

    # Expiry Check
    check_expiry = fields.Selection([
        ('no', 'No'),
        ('warning', 'Warning Only'),
        ('error', 'Error')
    ], string="Check Expiry", default='no',tracking=True)

class MembershipCardType(models.Model):
    _name = 'membership.card.type'
    _description = 'Membership Card Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_desc = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbr = fields.Char(string="Arabic Abbreviation",tracking=True)
    
    # Card Type
    card_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('individual', 'Individual'),
        ('business', 'Business')
    ], string="Type", default='unspecified',tracking=True)

    # Duplicate Check
    check_duplicate = fields.Selection([
        ('no', 'No'),
        ('warning', 'Warning Only'),
        ('error', 'Error')
    ], string="Check Duplicate", default='no',tracking=True)

    check_all_profiles = fields.Boolean(string="Check All Profiles", default=False,tracking=True)

    # Expiry Check
    check_expiry = fields.Selection([
        ('no', 'No'),
        ('warning', 'Warning Only'),
        ('error', 'Error')
    ], string="Check Expiry", default='no',tracking=True)

    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

class NoteCategory(models.Model):
    _name = 'note.category'
    _description = 'Note Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    category = fields.Char(string="Category", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_desc = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbr = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    restrict = fields.Boolean(string="Restrict", default=False,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)