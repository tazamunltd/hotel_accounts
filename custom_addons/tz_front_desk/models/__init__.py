# -*- coding: utf-8 -*-

from . import group_booking
from . import room_booking
from . import tz_manual_posting
from . import tz_manual_posting_tax
from . import tz_master_folio
from . import tz_master_folio_report
from . import tz_dummy_group
from . import muk_model
from . import tz_checkout

# def pre_init_hook(cr):
#     """Clean up references before module update"""
#     cr.execute("""
#         DELETE FROM ir_model_fields
#         WHERE model IN ('mk.sale.order', 'mk.sale.order.line');
#     """)
#     cr.execute("""
#         DELETE FROM ir_model
#         WHERE model IN ('mk.sale.order', 'mk.sale.order.line');
#     """)
#     cr.execute("""
#         DELETE FROM ir_model_data
#         WHERE model IN ('mk.sale.order', 'mk.sale.order.line');
#     """)
