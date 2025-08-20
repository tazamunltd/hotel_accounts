from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Add missing child_pax_1 column to rate_detail table
    
    Migration script created on: 2025-01-08
    Purpose: Resolve database schema error in cron job processing
    """
    _logger.debug("Starting migration to add child_pax_1 column to rate_detail")
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    try:
        # Check if column already exists to prevent errors
        cr.execute("""
            DO $$
            BEGIN
                BEGIN
                    ALTER TABLE rate_detail ADD COLUMN child_pax_1 INTEGER;
                    RAISE NOTICE 'Column child_pax_1 added successfully';
                EXCEPTION
                    WHEN duplicate_column THEN 
                        RAISE NOTICE 'Column child_pax_1 already exists in rate_detail.';
                END;
            END $$;
        """)
        
        # Optional: Set a default value if needed
        cr.execute("""
            UPDATE rate_detail 
            SET child_pax_1 = 0 
            WHERE child_pax_1 IS NULL;
        """)
        
        # Commit the changes
        cr.commit()
        _logger.debug("Migration completed successfully")
    except Exception as e:
        _logger.error(f"Error during migration: {str(e)}")
        cr.rollback()
        raise
