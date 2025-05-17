# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)


class TzFakeGroup(models.Model):
    _name = 'tz.fake.group'

    name = fields.Char(
        string="Group ID",
        readonly=True,
        index=True,
    )
    description = fields.Char()
    short = fields.Char()
    obsolete = fields.Boolean()



