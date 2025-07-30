# -*- coding: utf-8 -*-

# Load basic models first
from . import tz_master_folio
from . import tz_dummy_group
from . import room_booking
from . import group_booking

# Then load models that depend on them
from . import tz_manual_posting_type
from . import tz_manual_posting
from . import tz_manual_posting_tax
from . import tz_master_folio_report
from . import tz_hotel_checkout

