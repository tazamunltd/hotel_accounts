from odoo import api, models, fields,_
from odoo.exceptions import ValidationError

class DepartmentCategory(models.Model):
    _name = 'department.category'
    _description = 'Department Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    _rec_name = 'category'
    category = fields.Char(string=_("Category"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    user_sort = fields.Char(string=_("User Sort"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)

class DepartmentCode(models.Model):
    _name = 'department.code'
    _description = 'Department Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'department'
    department = fields.Char(string=_("Department"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    unit_price = fields.Float(string="Unit Price", default=0.0,tracking=True)
    category = fields.Selection([
        ('room_charge', 'Room Charge'),
        ('food_charge', 'Food Charge'),
        ('beverage_charge', 'Beverage Charge'),
        ('telephone_charge', 'Telephone Charge'),
        ('other', 'Other Payments')
    ], string="Category",tracking=True)
    dept_category = fields.Many2one('department.category', string="Category",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)

    # Functionality selection fields
    allow_change_sign = fields.Boolean(string="Allow Change Sign",tracking=True)
    require_authorization = fields.Boolean(string="Require Authorization",tracking=True)
    allow_as_posting_item = fields.Boolean(string="Allow Using As Posting Item",tracking=True)
    allow_pre_approval_postings = fields.Boolean(string="Allow Pre-Approval Postings",tracking=True)
    entry_require_authorization = fields.Boolean(string="Entry Requires Authorization",tracking=True)

    # Charge Type
    function_type = fields.Selection([
        ('unspecified', 'Unspecified Charges'),
        ('adjustment', 'Adjustment Payments'),
        ('transfer', 'Transfer')
    ], string="Function Type", default='unspecified',tracking=True)

    # Various functional charges, payments, and taxes

    charge_room = fields.Boolean(string="Room Charge",tracking=True)
    charge_food = fields.Boolean(string="Food Charge",tracking=True)
    charge_beverage = fields.Boolean(string="Beverage Charge",tracking=True)
    charge_telephone = fields.Boolean(string="Telephone Charge",tracking=True)
    charge_other = fields.Boolean(string="Other Charge",tracking=True)

    

    payment_cash = fields.Boolean(string="Cash Payment",tracking=True)
    payment_credit_card = fields.Boolean(string="Credit Card",tracking=True)
    payment_other = fields.Boolean(string="Other Payment",tracking=True)

    tax_service_charge = fields.Boolean(string="Service Charge",tracking=True)
    tax_vat = fields.Boolean(string="Value Added Tax",tracking=True)
    tax_other = fields.Boolean(string="Other Tax",tracking=True)
    tax_municipality = fields.Boolean(string="Municipality Tax",tracking=True)

    charge_group = fields.Selection([
        ('room_charge', 'Room Charge'),
        ('food_charge', 'Food Charge'),
        ('beverage_charge', 'Beverage Charge'),
        ('telephone_charge', 'Telephone Charge'),
        ('other_charge', 'Other Charge')
    ], string="Charges")

    payment_group = fields.Selection([
        ('payment_cash', 'Cash Payment'),
        ('payment_credit_card', 'Credit Card Payment'),
        ('payment_other', 'Other Payment')
    ], string="Payments")

    tax_group = fields.Selection([
        ('tax_service_charge', 'Service Charge'),
        ('tax_vat', 'Value Added Tax'),
        ('tax_municipality', 'Municipality Tax'),
        ('tax_other', 'Other Tax')
    ], string="Taxes")
    adjustment = fields.Selection([
        ('transfer_charge', 'Transfer charge'),
    ], string="Adjustment")

    @api.onchange('charge_group')
    def _onchange_charge_group(self):
        if self.charge_group:
            self.payment_group = False
            self.tax_group = False
            self.adjustment = False

    @api.onchange('payment_group')
    def _onchange_payment_group(self):
        if self.payment_group:
            self.charge_group = False
            self.tax_group = False
            self.adjustment = False

    @api.onchange('tax_group')
    def _onchange_tax_group(self):
        if self.tax_group:
            self.charge_group = False
            self.payment_group = False
            self.adjustment = False
    
    @api.onchange('adjustment')
    def _onchange_adjustment(self):
        if self.adjustment:
            self.payment_group = False
            self.tax_group = False
            self.charge_group = False

    @api.constrains('charge_group', 'payment_group', 'tax_group', 'adjustment')
    def _check_only_one_selected(self):
        for record in self:
            selected_fields = [
                bool(record.charge_group),
                bool(record.payment_group),
                bool(record.tax_group),
                bool(record.adjustment),
            ]
            if sum(selected_fields) > 1:
                raise ValidationError(
                    "You can only select one option from Charges, Payments, adjustment or Taxes."
                )



    charge_type = fields.Selection(
        selection=[
            ('room_charge', 'Room Charge'),
            ('food_charge', 'Food Charge'),
            ('beverage_charge', 'Beverage Charge'),
            ('telephone_charge', 'Telephone Charge'),
            ('other_charge', 'Other Charge'),
            ('cash_payment','Cash Payment'),
            ('credit_card_payment','Credit Card'),
            ('other_payment','Other Payment'),
            ('service_charge_tax','Service Charge'),
            ('vat_tax','Value Added Tax'),
            ('other_tax','Other Tax'),
            ('municipality_tax','Municipality Tax'),
        ],
        string="Charge Type",
        tracking=True,
        help="Select the type of charge.",
    )

    sort_order = fields.Integer(string="Sort Order", default=0,tracking=True)

    # New Field for GI Accounts
    # default_account_id = fields.Many2one('account.account', string="Default Account")

class PostingItem(models.Model):
    _name = 'posting.item'
    _description = 'Posting Item'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'item_code'
    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True)
    item_code = fields.Char(string=_("Item"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"),tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Desc."),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbr."),tracking=True, translate=True)
    main_department = fields.Many2one('department.code', string="Main Department",tracking=True)
    default_currency = fields.Char(string=_("Default Currency"),tracking=True, translate=True)
    default_currency_ = fields.Many2one('res.currency', string=_("Default Currency"),tracking=True)
    default_value = fields.Float(string="Default Value", default=1,tracking=True)
    
    @api.onchange('default_value')
    def _onchange_default_value(self):
        if self.default_value < 1:
            raise ValidationError(_("The Default Value cannot be less than 1."))
    entry_value_type = fields.Selection([
        ('gross', 'Gross'),
        ('net', 'Net'),
        ('total', 'Total')
    ], string="Entry Value",tracking=True)
    fixed_value = fields.Boolean(string="Fixed Value", default=False,tracking=True)
    dummy_room_discount = fields.Boolean(string="Dummy Rooms Discount",tracking=True)
    allow_change_sign = fields.Boolean(string="Allow Change Sign",tracking=True)
    require_authorization = fields.Boolean(string="Require Authorization",tracking=True)
    default_sign = fields.Selection([
        ('main', 'As Main Department'),
        ('debit', 'Debit'),
        ('credit', 'Credit')
    ], string="Default Sign",tracking=True)
    entry_require_authorization = fields.Boolean(string="Entry Requires Authorization",tracking=True)
    
    # Additions Fields
    addition_line = fields.One2many('posting.item.addition', 'posting_item_id', string="Additions") #Dont add tracking
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    show_in_website = fields.Boolean(string="Show in Website",tracking=True)
    website_desc = fields.Char(string='Website Description',tracking=True, translate=True)

    posting_item_selection = fields.Selection(
        [
            ('first_night', 'First Night'),
            ('every_night', 'Every Night'),
        ],
        string="Posting Item Option",
        help="Select whether the posting applies to the first night or every night."
    ,tracking=True)

    taxes = fields.Many2many('account.tax', string="Taxes",tracking=True)

class PostingItemAddition(models.Model):
    _name = 'posting.item.addition'
    _description = 'Posting Item Addition'
    # _inherit = ['mail.thread', 'mail.activity.mixin']

    posting_item_id = fields.Many2one('posting.item', string="Posting Item", ondelete='cascade',tracking=True)
    # department = fields.Char(string=_("Department",tracking=True)
    department = fields.Many2one('department.code', string="Main Department",tracking=True)
    line = fields.Integer(string="Line",tracking=True)
    name = fields.Char(string=_("Name"),tracking=True, translate=True)
    value = fields.Float(string="Value", default=0.0,tracking=True)
    is_entry_value = fields.Boolean(string="Entry Value", default=False,tracking=True)
    added_value = fields.Float(string="Added Value", default=0.0,tracking=True)
    value_per_pax_child = fields.Float(string="Value/Child", default=0.0,tracking=True)
    value_per_room = fields.Float(string="Value/Room", default=0.0,tracking=True)
    percentage_of_additions = fields.Float(string="Percent of Additions", default=0.0,tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)

class DummyRoomCode(models.Model):
    _name = 'dummy.room.code'
    _description = 'Dummy Room Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    room_number = fields.Char(string=_("Room Number"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"),tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_desc = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbr = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    item_discount = fields.Float(string="Item Discount",tracking=True)
    company_id = fields.Many2one('res.company', string="Hotel",tracking=True)
    is_obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)
    auto_reopen_room_account = fields.Boolean(string="Automatically Open for Room Account", default=False,tracking=True)
    auto_payment_posting = fields.Boolean(string="Cash Room (Auto Payment Charge Posting)", default=False,tracking=True)

    # Applicable Taxes
    service_charge = fields.Boolean(string="Service Charge", default=False,tracking=True)
    value_added_tax = fields.Boolean(string="Value Added Tax", default=False,tracking=True)
    municipality_tax = fields.Boolean(string="Municipality Tax", default=False,tracking=True)
    head_tax = fields.Boolean(string="Head Tax", default=False,tracking=True)
    entertainment_tax = fields.Boolean(string="Entertainment Tax", default=False,tracking=True)

class CurrencyCode(models.Model):
    _name = 'currency.code'
    _description = 'Currency Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    currency = fields.Char(string=_("Currency Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"),tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_desc = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbr = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    exchange_rate = fields.Float(string="Exchange Rate", digits=(12, 4),tracking=True)
    fo_rate = fields.Float(string="F/O Rate", digits=(12, 4),tracking=True)
    rate_code_rate = fields.Float(string="Rate Code Rate", digits=(12, 4),tracking=True)
    cash_rate = fields.Float(string="Cash Rate", digits=(12, 4),tracking=True)

    # Booleans for Use Default
    use_fo_default = fields.Boolean(string="Use Default for F/O Rate", default=True,tracking=True)
    use_rate_code_default = fields.Boolean(string="Use Default for Rate Code Rate", default=True,tracking=True)
    use_cash_default = fields.Boolean(string="Use Default for Cash Rate", default=True,tracking=True)

class BudgetEntry(models.Model):
    _name = 'budget.entry'
    _description = 'Budget Entry'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    month = fields.Date(string="Month", required=True,tracking=True)
    rooms = fields.Integer(string="Rooms", default=0,tracking=True)
    pax = fields.Integer(string="Pax", default=0,tracking=True)
    child = fields.Integer(string="Child", default=0,tracking=True)
    infant = fields.Integer(string="Infant", default=0,tracking=True)
    revenue = fields.Float(string="Revenue", digits=(12, 2), default=0.0,tracking=True)

    # Buttons for Companies and Departments
    def action_view_companies(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Companies',
            'res_model': 'res.company',
            'view_mode': 'tree,form',
            'target': 'new'
        }

    def action_view_departments(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Departments',
            'res_model': 'hr.department',
            'view_mode': 'tree,form',
            'target': 'new'
        }
    
class CashBoxCode(models.Model):
    _name = 'cash.box.code'
    _description = 'Cash Box Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string=_("Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"),tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_desc = fields.Char(string=_("Arabic Desc"),tracking=True, translate=True)
    arabic_abbr = fields.Char(string=_("Arabic Abbr"),tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    max_per_day = fields.Integer(string="Max Per Day",tracking=True)
    exclusive = fields.Boolean(string="Exclusive", default=False,tracking=True)
    reset_upon_opening = fields.Boolean(string="Reset Upon Opening", default=False,tracking=True)
    status = fields.Selection([
        ('not_used', 'Not Used'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('suspended', 'Suspended'),
        ('obsolete', 'Obsolete')
    ], string="Status", default='not_used',tracking=True)

    reset_value_ids = fields.One2many('cash.box.reset.value', 'cash_box_id', string="Reset Values",tracking=True)


class CashBoxResetValue(models.Model):
    _name = 'cash.box.reset.value'
    _description = 'Cash Box Reset Value'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    currency = fields.Char(string=_("Currency"),tracking=True, translate=True)
    department = fields.Char(string=_("Department"),tracking=True, translate=True)
    value = fields.Float(string="Value",tracking=True)
    cash_box_id = fields.Many2one('cash.box.code', string="Cash Box",tracking=True)

