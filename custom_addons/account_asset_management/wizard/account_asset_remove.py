# Copyright 2009-2018 Noviat
# Copyright 2021 Tecnativa - João Marques
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccountAssetRemove(models.TransientModel):
    _name = "account.asset.remove"
    _description = "Remove Asset"
    _check_company_auto = True

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        readonly=True,
        required=True,
        default=lambda self: self._default_company_id(),
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency"
    )
    date_remove = fields.Date(
        string="Asset Removal Date",
        required=True,
        default=fields.Date.today,
        help="Removal date must be after the last posted entry "
        "in case of early removal",
    )
    force_date = fields.Date(string="Force accounting date")
    sale_value = fields.Monetary(
        default=lambda self: self._default_sale_value(),
    )
    account_sale_id = fields.Many2one(
        comodel_name="account.account",
        string="Asset Sale Account",
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        default=lambda self: self._default_account_sale_id(),
    )
    account_plus_value_id = fields.Many2one(
        comodel_name="account.account",
        string="Plus-Value Account",
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        default=lambda self: self._default_account_plus_value_id(),
    )
    account_min_value_id = fields.Many2one(
        comodel_name="account.account",
        string="Min-Value Account",
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        default=lambda self: self._default_account_min_value_id(),
    )
    account_residual_value_id = fields.Many2one(
        comodel_name="account.account",
        string="Residual Value Account",
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        default=lambda self: self._default_account_residual_value_id(),
    )
    posting_regime = fields.Selection(
        selection=lambda self: self._selection_posting_regime(),
        string="Removal Entry Policy",
        required=True,
        default=lambda self: self._get_posting_regime(),
        help="Removal Entry Policy \n"
        "  * Residual Value: The non-depreciated value will be "
        "posted on the 'Residual Value Account' \n"
        "  * Gain/Loss on Sale: The Gain or Loss will be posted on "
        "the 'Plus-Value Account' or 'Min-Value Account' ",
    )
    note = fields.Text("Notes")

    @api.constrains("sale_value", "company_id")
    def _check_sale_value(self):
        if self.company_id.currency_id.compare_amounts(self.sale_value, 0) < 0:
            raise ValidationError(_("The Sale Value must be positive!"))

    @api.model
    def _default_company_id(self):
        asset_id = self.env.context.get("active_id")
        asset = self.env["account.asset"].browse(asset_id)
        return asset.company_id

    @api.model
    def _default_sale_value(self):
        return self._get_sale()["sale_value"]

    @api.model
    def _default_account_sale_id(self):
        return self._get_sale()["account_sale_id"]

    def _get_sale(self):
        asset_id = self.env.context.get("active_id")
        sale_value = 0.0
        account_sale_id = False
        inv_lines = self.env["account.move.line"].search(
            [
                ("asset_id", "=", asset_id),
                ("move_id.move_type", "in", ("out_invoice", "out_refund")),
            ]
        )
        for line in inv_lines:
            inv = line.move_id
            comp_curr = inv.currency_id
            inv_curr = inv.currency_id
            if line.move_id.payment_state == "paid" or line.parent_state == "draft":
                account_sale_id = line.account_id.id
                amount_inv_cur = line.price_subtotal
                amount_comp_cur = inv_curr._convert(
                    amount_inv_cur, comp_curr, inv.company_id, inv.date
                )
                sale_value += amount_comp_cur
        return {"sale_value": sale_value, "account_sale_id": account_sale_id}

    @api.model
    def _default_account_plus_value_id(self):
        asset_id = self.env.context.get("active_id")
        asset = self.env["account.asset"].browse(asset_id)
        return asset.profile_id.account_plus_value_id

    @api.model
    def _default_account_min_value_id(self):
        asset_id = self.env.context.get("active_id")
        asset = self.env["account.asset"].browse(asset_id)
        return asset.profile_id.account_min_value_id

    @api.model
    def _default_account_residual_value_id(self):
        asset_id = self.env.context.get("active_id")
        asset = self.env["account.asset"].browse(asset_id)
        return asset.profile_id.account_residual_value_id

    @api.model
    def _selection_posting_regime(self):
        return [
            ("residual_value", _("Residual Value")),
            ("gain_loss_on_sale", _("Gain/Loss on Sale")),
        ]

    @api.model
    def _get_posting_regime(self):
        asset_obj = self.env["account.asset"]
        asset = asset_obj.browse(self.env.context.get("active_id"))
        country = asset and asset.company_id.country_id.code or False
        if country in self._residual_value_regime_countries():
            return "residual_value"
        else:
            return "gain_loss_on_sale"

    def _residual_value_regime_countries(self):
        return ["FR"]

    def remove(self):
        self.ensure_one()
        asset_line_obj = self.env["account.asset.line"]

        asset_id = self.env.context.get("active_id")
        asset = self.env["account.asset"].browse(asset_id)
        asset_ref = asset.code and f"{asset.name} (ref: {asset.code})" or asset.name

        if self.env.context.get("early_removal"):
            residual_value = self._prepare_early_removal(asset)
        else:
            residual_value = asset.value_residual

        dlines = asset_line_obj.search(
            [
                ("asset_id", "=", asset.id),
                ("type", "=", "depreciate"),
                ("move_check", "!=", False),
            ],
            order="line_date desc",
        )
        if dlines:
            last_date = dlines[0].line_date
        else:
            create_dl = asset_line_obj.search(
                [("asset_id", "=", asset.id), ("type", "=", "create")]
            )[0]
            last_date = create_dl.line_date

        if self.date_remove < last_date:
            raise UserError(
                _("The removal date must be after " "the last depreciation date.")
            )

        line_name = asset._get_depreciation_entry_name(len(dlines) + 1)
        journal_id = asset.profile_id.journal_id.id
        if not self.force_date:
            date_remove = self.date_remove
        else:
            date_remove = self.force_date

        # create move
        move_vals = {
            "date": date_remove,
            "ref": line_name,
            "journal_id": journal_id,
            "narration": self.note,
        }
        move = self.env["account.move"].create(move_vals)

        # create asset line
        asset_line_vals = {
            "amount": residual_value,
            "asset_id": asset_id,
            "name": line_name,
            "line_date": self.date_remove,
            "move_id": move.id,
            "type": "remove",
        }
        asset_line_obj.create(asset_line_vals)
        asset.write({"state": "removed", "date_remove": self.date_remove})

        # create move lines
        move_lines = self._get_removal_data(asset, residual_value)
        move.with_context(allow_asset=True).write({"line_ids": move_lines})

        return {
            "name": _("Asset '%s' Removal Journal Entry") % asset_ref,
            "view_mode": "tree,form",
            "res_model": "account.move",
            "view_id": False,
            "type": "ir.actions.act_window",
            "context": self.env.context,
            "domain": [("id", "=", move.id)],
        }

    def _prepare_early_removal(self, asset):
        """
        Generate last depreciation entry on the day before the removal date.
        """
        date_remove = self.date_remove
        asset_line_obj = self.env["account.asset.line"]

        currency = asset.company_id.currency_id

        def _dlines(asset):
            lines = asset.depreciation_line_ids
            dlines = lines.filtered(
                lambda line: line.type == "depreciate"
                and not line.init_entry
                and not line.move_check
            )
            dlines = dlines.sorted(key=lambda line: line.line_date)
            return dlines

        dlines = _dlines(asset)
        if not dlines:
            asset.compute_depreciation_board()
            dlines = _dlines(asset)
        if not dlines:
            return asset.value_residual
        first_to_depreciate_dl = dlines[0]

        first_date = first_to_depreciate_dl.line_date
        if date_remove > first_date:
            raise UserError(
                _(
                    "You can't make an early removal if all the depreciation "
                    "lines for previous periods are not posted."
                )
            )

        if first_to_depreciate_dl.previous_id:
            last_depr_date = first_to_depreciate_dl.previous_id.line_date
        else:
            create_dl = asset_line_obj.search(
                [("asset_id", "=", asset.id), ("type", "=", "create")]
            )
            last_depr_date = create_dl.line_date

        # Never create move.
        same_month = (
            last_depr_date.month == first_to_depreciate_dl.line_date.month and 1 or 0
        )

        period_number_days = (first_date - last_depr_date).days + same_month
        new_line_date = date_remove + relativedelta(days=-1)
        to_depreciate_days = (new_line_date - last_depr_date).days + same_month
        to_depreciate_amount = currency.round(
            float(to_depreciate_days)
            / float(period_number_days)
            * first_to_depreciate_dl.amount,
        )
        residual_value = asset.value_residual - to_depreciate_amount
        if to_depreciate_amount:
            update_vals = {
                "amount": to_depreciate_amount,
                "line_date": new_line_date,
                "line_days": to_depreciate_days,
            }
            first_to_depreciate_dl.write(update_vals)
            dlines[0].create_move()
            dlines -= dlines[0]
        dlines.unlink()
        return residual_value

    def _get_removal_data(self, asset, residual_value):
        move_lines = []
        partner_id = asset.partner_id and asset.partner_id.id or False
        profile = asset.profile_id
        currency = asset.company_id.currency_id

        # asset and asset depreciation account reversal
        depr_amount = asset.depreciation_base - residual_value
        depr_amount_comp = currency.compare_amounts(depr_amount, 0)
        if depr_amount:
            move_line_vals = {
                "name": asset.name,
                "account_id": profile.account_depreciation_id.id,
                "debit": depr_amount_comp > 0 and depr_amount or 0.0,
                "credit": depr_amount_comp < 0 and -depr_amount or 0.0,
                "partner_id": partner_id,
                "asset_id": asset.id,
            }
            move_lines.append((0, 0, move_line_vals))

        depreciation_base_comp = currency.compare_amounts(asset.depreciation_base, 0)
        move_line_vals = {
            "name": asset.name,
            "account_id": profile.account_asset_id.id,
            "debit": (depreciation_base_comp < 0 and -asset.depreciation_base or 0.0),
            "credit": (depreciation_base_comp > 0 and asset.depreciation_base or 0.0),
            "partner_id": partner_id,
            "asset_id": asset.id,
        }
        move_lines.append((0, 0, move_line_vals))

        if residual_value:
            if self.posting_regime == "residual_value":
                move_line_vals = {
                    "name": asset.name,
                    "account_id": self.account_residual_value_id.id,
                    "analytic_distribution": asset.analytic_distribution,
                    "debit": residual_value,
                    "credit": 0.0,
                    "partner_id": partner_id,
                    "asset_id": asset.id,
                }
                move_lines.append((0, 0, move_line_vals))
            elif self.posting_regime == "gain_loss_on_sale":
                if self.sale_value:
                    sale_value = self.sale_value
                    move_line_vals = {
                        "name": asset.name,
                        "account_id": self.account_sale_id.id,
                        "analytic_distribution": asset.analytic_distribution,
                        "debit": sale_value,
                        "credit": 0.0,
                        "partner_id": partner_id,
                        "asset_id": asset.id,
                    }
                    move_lines.append((0, 0, move_line_vals))
                balance = self.sale_value - residual_value
                balance_comp = currency.compare_amounts(balance, 0)
                account_id = (
                    self.account_plus_value_id.id
                    if balance_comp > 0
                    else self.account_min_value_id.id
                )
                move_line_vals = {
                    "name": asset.name,
                    "account_id": account_id,
                    "debit": balance_comp < 0 and -balance or 0.0,
                    "credit": balance_comp > 0 and balance or 0.0,
                    "analytic_distribution": asset.analytic_distribution,
                    "partner_id": partner_id,
                    "asset_id": asset.id,
                }
                move_lines.append((0, 0, move_line_vals))
        return move_lines
