from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def _auto_sync_post_init_room_type(env):
    """Post-init hook to create materialized view and sync data"""
    env['tz.manual.posting.room'].create_or_replace_view()
    env['tz.manual.posting.type'].sync_with_materialized_view()


# def post_init_hook(cr, registry):
#     """Post-initialization hook to setup initial data"""
#
#     env = api.Environment(cr, SUPERUSER_ID, {})
#
#     try:
#         # 1. Initialize the view
#         env['tz.checkout'].init()
#
#         # 2. Refresh the materialized view
#         env.cr.execute("REFRESH MATERIALIZED VIEW tz_checkout")
#
#         # 3. Sync data to main model
#         env['tz.hotel.checkout'].sync_from_view()
#
#         _logger.info("Successfully initialized hotel checkout data")
#     except Exception as e:
#         _logger.error("Failed to initialize hotel checkout data: %s", str(e))
#         raise
