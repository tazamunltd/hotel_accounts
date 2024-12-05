from odoo import api, models, fields

class DepartmentCategory(models.Model):
    _name = 'department.category'
    _description = 'Department Category'

    _rec_name = 'category'
    category = fields.Char(string="Category", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    user_sort = fields.Char(string="User Sort")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")

class DepartmentCode(models.Model):
    _name = 'department.code'
    _description = 'Department Code'

    _rec_name = 'department'
    department = fields.Char(string="Department", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    unit_price = fields.Float(string="Unit Price", default=0.0)
    category = fields.Selection([
        ('room_charge', 'Room Charge'),
        ('food_charge', 'Food Charge'),
        ('beverage_charge', 'Beverage Charge'),
        ('telephone_charge', 'Telephone Charge'),
        ('other', 'Other Payments')
    ], string="Category")
    dept_category = fields.Many2one('department.category', string="Category")
    user_sort = fields.Integer(string="User Sort", default=0)

    # Functionality selection fields
    allow_change_sign = fields.Boolean(string="Allow Change Sign")
    require_authorization = fields.Boolean(string="Require Authorization")
    allow_as_posting_item = fields.Boolean(string="Allow Using As Posting Item")
    allow_pre_approval_postings = fields.Boolean(string="Allow Pre-Approval Postings")
    entry_require_authorization = fields.Boolean(string="Entry Requires Authorization")

    # Charge Type
    function_type = fields.Selection([
        ('unspecified', 'Unspecified Charges'),
        ('adjustment', 'Adjustment Payments'),
        ('transfer', 'Transfer')
    ], string="Function Type", default='unspecified')

    # Various functional charges, payments, and taxes
    charge_room = fields.Boolean(string="Room Charge")
    charge_food = fields.Boolean(string="Food Charge")
    charge_beverage = fields.Boolean(string="Beverage Charge")
    charge_telephone = fields.Boolean(string="Telephone Charge")
    charge_other = fields.Boolean(string="Other Charge")

    payment_cash = fields.Boolean(string="Cash Payment")
    payment_credit_card = fields.Boolean(string="Credit Card")
    payment_other = fields.Boolean(string="Other Payment")

    tax_service_charge = fields.Boolean(string="Service Charge")
    tax_vat = fields.Boolean(string="Value Added Tax")
    tax_other = fields.Boolean(string="Other Tax")
    tax_municipality = fields.Boolean(string="Municipality Tax")

    sort_order = fields.Integer(string="Sort Order", default=0)

    # New Field for GI Accounts
    # default_account_id = fields.Many2one('account.account', string="Default Account")

class PostingItem(models.Model):
    _name = 'posting.item'
    _description = 'Posting Item'

    _rec_name = 'item_code'
    item_code = fields.Char(string="Item", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Desc.")
    arabic_abbreviation = fields.Char(string="Arabic Abbr.")
    main_department = fields.Many2one('department.code', string="Main Department")
    default_currency = fields.Char(string="Default Currency")
    default_value = fields.Float(string="Default Value", default=0.0)
    entry_value_type = fields.Selection([
        ('gross', 'Gross'),
        ('net', 'Net'),
        ('total', 'Total')
    ], string="Entry Value")
    fixed_value = fields.Boolean(string="Fixed Value", default=False)
    dummy_room_discount = fields.Boolean(string="Dummy Rooms Discount")
    allow_change_sign = fields.Boolean(string="Allow Change Sign")
    require_authorization = fields.Boolean(string="Require Authorization")
    default_sign = fields.Selection([
        ('main', 'As Main Department'),
        ('debit', 'Debit'),
        ('credit', 'Credit')
    ], string="Default Sign")
    entry_require_authorization = fields.Boolean(string="Entry Requires Authorization")
    
    # Additions Fields
    addition_line = fields.One2many('posting.item.addition', 'posting_item_id', string="Additions")
    user_sort = fields.Integer(string="User Sort", default=0)
    show_in_website = fields.Boolean(string="Show in Website")
    website_desc = fields.Char(string='Website Description')

    posting_item_selection = fields.Selection(
        [
            ('first_night', 'First Night'),
            ('every_night', 'Every Night'),
        ],
        string="Posting Item Option",
        help="Select whether the posting applies to the first night or every night."
    )

    taxes = fields.Many2one('account.tax', string="Taxes")

class PostingItemAddition(models.Model):
    _name = 'posting.item.addition'
    _description = 'Posting Item Addition'

    posting_item_id = fields.Many2one('posting.item', string="Posting Item", ondelete='cascade')
    department = fields.Char(string="Department")
    line = fields.Integer(string="Line")
    name = fields.Char(string="Name")
    value = fields.Float(string="Value", default=0.0)
    is_entry_value = fields.Boolean(string="Entry Value", default=False)
    added_value = fields.Float(string="Added Value", default=0.0)
    value_per_pax_child = fields.Float(string="Value/Child", default=0.0)
    value_per_room = fields.Float(string="Value/Room", default=0.0)
    percentage_of_additions = fields.Float(string="Percent of Additions", default=0.0)
    user_sort = fields.Integer(string="User Sort", default=0)

class DummyRoomCode(models.Model):
    _name = 'dummy.room.code'
    _description = 'Dummy Room Code'

    room_number = fields.Char(string="Room Number", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    item_discount = fields.Float(string="Item Discount")
    company_id = fields.Many2one('res.company', string="Company")
    is_obsolete = fields.Boolean(string="Obsolete", default=False)
    auto_reopen_room_account = fields.Boolean(string="Automatically Open for Room Account", default=False)
    auto_payment_posting = fields.Boolean(string="Cash Room (Auto Payment Charge Posting)", default=False)

    # Applicable Taxes
    service_charge = fields.Boolean(string="Service Charge", default=False)
    value_added_tax = fields.Boolean(string="Value Added Tax", default=False)
    municipality_tax = fields.Boolean(string="Municipality Tax", default=False)
    head_tax = fields.Boolean(string="Head Tax", default=False)
    entertainment_tax = fields.Boolean(string="Entertainment Tax", default=False)

class CurrencyCode(models.Model):
    _name = 'currency.code'
    _description = 'Currency Code'

    currency = fields.Char(string="Currency Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Description")
    arabic_abbr = fields.Char(string="Arabic Abbreviation")
    exchange_rate = fields.Float(string="Exchange Rate", digits=(12, 4))
    fo_rate = fields.Float(string="F/O Rate", digits=(12, 4))
    rate_code_rate = fields.Float(string="Rate Code Rate", digits=(12, 4))
    cash_rate = fields.Float(string="Cash Rate", digits=(12, 4))

    # Booleans for Use Default
    use_fo_default = fields.Boolean(string="Use Default for F/O Rate", default=True)
    use_rate_code_default = fields.Boolean(string="Use Default for Rate Code Rate", default=True)
    use_cash_default = fields.Boolean(string="Use Default for Cash Rate", default=True)

class BudgetEntry(models.Model):
    _name = 'budget.entry'
    _description = 'Budget Entry'

    month = fields.Date(string="Month", required=True)
    rooms = fields.Integer(string="Rooms", default=0)
    pax = fields.Integer(string="Pax", default=0)
    child = fields.Integer(string="Child", default=0)
    infant = fields.Integer(string="Infant", default=0)
    revenue = fields.Float(string="Revenue", digits=(12, 2), default=0.0)

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

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    arabic_desc = fields.Char(string="Arabic Desc")
    arabic_abbr = fields.Char(string="Arabic Abbr")
    user_sort = fields.Integer(string="User Sort", default=0)
    max_per_day = fields.Integer(string="Max Per Day")
    exclusive = fields.Boolean(string="Exclusive", default=False)
    reset_upon_opening = fields.Boolean(string="Reset Upon Opening", default=False)
    status = fields.Selection([
        ('not_used', 'Not Used'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('suspended', 'Suspended'),
        ('obsolete', 'Obsolete')
    ], string="Status", default='not_used')

    reset_value_ids = fields.One2many('cash.box.reset.value', 'cash_box_id', string="Reset Values")


class CashBoxResetValue(models.Model):
    _name = 'cash.box.reset.value'
    _description = 'Cash Box Reset Value'

    currency = fields.Char(string="Currency")
    department = fields.Char(string="Department")
    value = fields.Float(string="Value")
    cash_box_id = fields.Many2one('cash.box.code', string="Cash Box")

