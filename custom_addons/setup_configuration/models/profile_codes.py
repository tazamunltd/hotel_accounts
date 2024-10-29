from odoo import api, models, fields


class AddressType(models.Model):

    _name = 'address.type'
    _description = 'Address Type'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

    # Type of Address Selection
    address_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('mailing', 'Mailing Address'),
        ('billing', 'Billing Address'),
        ('visitors', 'Visitors Address'),
        ('home', 'Home Address'),
        ('work', 'Work Address')
    ], string="Type", default='unspecified')

class ContactMethodType(models.Model):
    _name = 'contact.method.type'
    _description = 'Contact Method Type'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

    # Type of Contact Method Selection
    contact_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('phone', 'Phone'),
        ('mobile', 'Mobile'),
        ('pager', 'Pager'),
        ('fax', 'Fax'),
        ('email', 'E-Mail'),
        ('website', 'Web Site')
    ], string="Type", default='unspecified')

class ProfileCategory(models.Model):
    _name = 'profile.category'
    _description = 'Profile Category'

    _rec_name = 'code'
    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

    # Profile type selection
    profile_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('individual', 'Individual'),
        ('business', 'Business'),
        ('internal', 'Internal'),
        ('party_group', 'Party Group'),
        ('guest_profile', 'Guest Profile'),
    ], string="Type", default='unspecified')

class DocumentType(models.Model):
    _name = 'document.type'
    _description = 'Document Type'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    valid_extensions = fields.Char(string="Valid Extensions")

    # Type selection
    doc_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('picture', 'Picture'),
        ('media', 'Media'),
        ('video', 'Video'),
        ('office', 'Office'),
        ('web', 'Web'),
    ], string="Type", default='unspecified')

    # Mandatory fields
    mandatory_attachment = fields.Boolean(string="Attachment")
    mandatory_doc_number = fields.Boolean(string="Doc. Number")
    mandatory_doc_country = fields.Boolean(string="Doc. Country")
    mandatory_doc_expiry = fields.Boolean(string="Doc. Expiry")

class CreditCardType(models.Model):
    _name = 'credit.card.type'
    _description = 'Credit Card Type'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    number_mask = fields.Char(string="Number Mask")
    department_id = fields.Char(string="Department")
    
    # Card Type
    card_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('visa', 'Visa'),
        ('master', 'Master'),
        ('diners', 'Diners'),
        ('amex', 'Amex')
    ], string="Type", default='unspecified')

    # Duplicate Check
    check_duplicate = fields.Selection([
        ('no', 'No'),
        ('warning', 'Warning Only'),
        ('error', 'Error')
    ], string="Check Duplicate", default='no')

    check_all_profiles = fields.Boolean(string="Check All Profiles", default=False)

    # Expiry Check
    check_expiry = fields.Selection([
        ('no', 'No'),
        ('warning', 'Warning Only'),
        ('error', 'Error')
    ], string="Check Expiry", default='no')

class MembershipCardType(models.Model):
    _name = 'membership.card.type'
    _description = 'Membership Card Type'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    
    # Card Type
    card_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('individual', 'Individual'),
        ('business', 'Business')
    ], string="Type", default='unspecified')

    # Duplicate Check
    check_duplicate = fields.Selection([
        ('no', 'No'),
        ('warning', 'Warning Only'),
        ('error', 'Error')
    ], string="Check Duplicate", default='no')

    check_all_profiles = fields.Boolean(string="Check All Profiles", default=False)

    # Expiry Check
    check_expiry = fields.Selection([
        ('no', 'No'),
        ('warning', 'Warning Only'),
        ('error', 'Error')
    ], string="Check Expiry", default='no')

    obsolete = fields.Boolean(string="Obsolete", default=False)

class NoteCategory(models.Model):
    _name = 'note.category'
    _description = 'Note Category'

    category = fields.Char(string="Category", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    restrict = fields.Boolean(string="Restrict", default=False)
    obsolete = fields.Boolean(string="Obsolete", default=False)