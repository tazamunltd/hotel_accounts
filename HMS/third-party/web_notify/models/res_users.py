# Copyright 2016 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import json
from odoo import _, api, exceptions, fields, models

from odoo.addons.bus.models.bus import channel_with_db, json_dump
from odoo.addons.web.controllers.utils import clean_action

DEFAULT_MESSAGE = "Default message"

SUCCESS = "success"
DANGER = "danger"
WARNING = "warning"
INFO = "info"
DEFAULT = "default"


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.depends("create_date")
    def _compute_channel_names(self):
        for record in self:
            record.notify_success_channel_name = json_dump(
                channel_with_db(self.env.cr.dbname, record.partner_id)
            )
            record.notify_danger_channel_name = json_dump(
                channel_with_db(self.env.cr.dbname, record.partner_id)
            )
            record.notify_warning_channel_name = json_dump(
                channel_with_db(self.env.cr.dbname, record.partner_id)
            )
            record.notify_info_channel_name = json_dump(
                channel_with_db(self.env.cr.dbname, record.partner_id)
            )
            record.notify_default_channel_name = json_dump(
                channel_with_db(self.env.cr.dbname, record.partner_id)
            )

    notify_success_channel_name = fields.Char(compute="_compute_channel_names")
    notify_danger_channel_name = fields.Char(compute="_compute_channel_names")
    notify_warning_channel_name = fields.Char(compute="_compute_channel_names")
    notify_info_channel_name = fields.Char(compute="_compute_channel_names")
    notify_default_channel_name = fields.Char(compute="_compute_channel_names")

    def notify_success(
        self,
        message="Default message",
        title=None,
        sticky=False,
        target=None,
        action=None,
        params=None,
    ):
        title = title or _("Success")
        self._notify_channel(SUCCESS, message, title, sticky, target, action, params)

    def notify_danger(
        self,
        message="Default message",
        title=None,
        sticky=False,
        target=None,
        action=None,
        params=None,
    ):
        title = title or _("Danger")
        self._notify_channel(DANGER, message, title, sticky, target, action, params)

    def notify_warning(
        self,
        message="Default message",
        title=None,
        sticky=False,
        target=None,
        action=None,
        params=None,
    ):
        title = title or _("Warning")
        self._notify_channel(WARNING, message, title, sticky, target, action, params)

    def notify_info(
        self,
        message="Default message",
        title=None,
        sticky=False,
        target=None,
        action=None,
        params=None,
    ):
        title = title or _("Information")
        self._notify_channel(INFO, message, title, sticky, target, action, params)

    def notify_default(
        self,
        message="Default message",
        title=None,
        sticky=False,
        target=None,
        action=None,
        params=None,
    ):
        title = title or _("Default")
        self._notify_channel(DEFAULT, message, title, sticky, target, action, params)

    def _notify_channel(
        self,
        type_message=DEFAULT,
        message=DEFAULT_MESSAGE,
        title=None,
        sticky=False,
        target=None,
        action=None,
        params=None,
    ):
        if not (self.env.user._is_admin() or self.env.su) and any(
            user.id != self.env.uid for user in self
        ):
            raise exceptions.UserError(
                _("Sending a notification to another user is forbidden.")
            )
        if not target:
            target = self.partner_id
        if action:
            action = clean_action(action, self.env)
        bus_message = {
            "type": type_message,
            "message": message,
            "title": title,
            "sticky": sticky,
            "action": action,
            "params": dict(params or []),
        }

        notifications = [[partner, "web.notify", [bus_message]] for partner in target]
        self.env["bus.bus"]._sendmany(notifications)


def channel_with_db(dbname, partner_id):
    return (dbname, 'res.partner', partner_id.id)

def json_dump(v):
    return json.dumps(v)


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def create(self, vals):
        company = super(ResCompany, self).create(vals)

        if vals.get('system_date'):
            self._notify_date_change(company)

        # Prepare sequence data
        sequence_data = {
            'name': f"{company.name}",
            'code': f"room.booking",
            'company_id': company.id,
            'prefix': '',
            'padding': 5,
            'number_increment': 1,
        }

        # Print the sequence data before creation
        print("Creating sequence with values:", sequence_data)

        # Create a sequence for the new company
        self.env['ir.sequence'].create(sequence_data)

        # Print confirmation after sequence creation
        print(
            f"Sequence created for company {company.name} (ID: {company.id})")

        return company

    def write(self, vals):
        res = super(ResCompany, self).write(vals)
        if 'system_date' in vals:
            self._notify_date_change(self)
        return res

    def _notify_date_change(self, companies):
        """Send notification to all users when system date changes"""
        current_user = self.env.user

        for company in companies:
            # Get target users based on permissions
            domain = []

            # If current user is CRS_Admin or system admin, they can see all notifications
            if current_user.login == 'crs_admin' or current_user._is_admin() or self.env.su:
                domain = [('company_id', '=', company.id)]
            else:
                # Regular users only see their own company's notifications
                domain = [
                    ('company_id', '=', company.id),
                    ('id', '=', current_user.id)
                ]

            target_users = self.env['res.users'].search(domain)

            # Add CRS_Admin to target users if they exist
            crs_admin = self.env['res.users'].search(
                [('login', '=', 'crs_admin')], limit=1)
            if crs_admin and crs_admin not in target_users:
                target_users |= crs_admin

            # Prepare the notification message
            notification_type = 'info'
            message = {
                'type': notification_type,
                'title': _("System Date Change"),
                'message': _(f"System date has been changed to: {company.system_date.date()}"),
                'sticky': True,
            }

            # Send notifications to authorized users
            for user in target_users:
                if user.has_group('base.group_user') or user.login == 'crs_admin':
                    self.env['bus.bus']._sendone(
                        user.partner_id,
                        'web.notify',
                        [message]
                    )

    def _check_notification_permission(self, target_user):
        """Check if current user can send notification to target user"""
        current_user = self.env.user

        # CRS_Admin, system admin, or sudo can send to anyone
        if current_user.login == 'crs_admin' or current_user._is_admin() or self.env.su:
            return True

        # Users can only send to themselves
        if current_user.id == target_user.id:
            return True

        return False
    