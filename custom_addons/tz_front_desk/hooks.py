def _auto_sync_post_init(env):
    """Post-init hook to create materialized view and sync data"""
    env['tz.manual.posting.room']._create_or_replace_view()
    env['tz.manual.posting.type'].sync_with_materialized_view()
