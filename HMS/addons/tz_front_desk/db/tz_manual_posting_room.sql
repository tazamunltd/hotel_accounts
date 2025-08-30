CREATE OR REPLACE VIEW tz_manual_posting_room AS
-- Original room booking query - FIXED
SELECT
    (rb.id * 10 + 1) AS id,
    COALESCE(NULLIF(hr.name ->> 'en_US', 'Unnamed'), rb.name) AS name,
    rb.id AS booking_id,
    hr.id AS room_id,
    rb.group_booking AS group_booking_id,  -- CHANGED: Use rb.group_booking instead of NULL
    NULL::integer AS dummy_id,
    mf.id AS folio_id,
    rb.partner_id,
    rb.checkin_date,
    rb.checkout_date,
    rb.adult_count::integer,
    rb.child_count::integer,
    rb.infant_count::integer,
    rb.rate_code,
    rb.meal_pattern,
    rb.company_id,
    rb.state AS state
FROM room_booking rb
LEFT JOIN room_booking_line rbl ON rbl.booking_id = rb.id
LEFT JOIN hotel_room hr ON rbl.room_id = hr.id
JOIN tz_master_folio mf ON mf.room_id = rbl.room_id 
WHERE rb.state IN ('confirmed', 'no_show', 'block', 'check_in')

UNION ALL

-- Modified group booking query to avoid duplicates
SELECT DISTINCT ON (gb.id)
    (gb.id * 10 + 2) AS id,
    COALESCE(gb.group_name ->> 'en_US', 'Unnamed') AS name,
    (SELECT id FROM room_booking rb2 WHERE rb2.group_booking = gb.id AND rb2.state != 'check_out' LIMIT 1) AS booking_id,
    NULL AS room_id,
    gb.id AS group_booking_id,
    NULL::integer AS dummy_id,
    mf.id AS folio_id,
    gb.company,
    gb.first_visit AS checkin_date,
    gb.last_visit AS checkout_date,
    gb.total_adult_count::integer,
    gb.total_child_count::integer,
    gb.total_infant_count::integer,
    gb.rate_code,
    gb.group_meal_pattern,
    gb.company_id,
    (SELECT rb3.state FROM room_booking rb3 WHERE rb3.group_booking = gb.id AND rb3.state != 'check_out' LIMIT 1) AS state
FROM group_booking gb
JOIN tz_master_folio mf ON mf.group_id = gb.id  
WHERE gb.status_code = 'confirmed'
  AND gb.id IN (
      SELECT rb.group_booking FROM room_booking rb
      WHERE rb.group_booking IS NOT NULL 
        AND rb.state IN ('confirmed', 'no_show', 'block', 'check_in')
  )

UNION ALL

-- Dummy group query
SELECT
    (dg.id * 10 + 3) AS id,
    dg.description::text AS name,
    NULL AS booking_id,
    NULL AS room_id,
    NULL AS group_booking_id,
    dg.id AS dummy_id,
    mf.id AS folio_id,
    NULL AS partner_id,
    dg.start_date AS checkin_date,
    dg.end_date AS checkout_date,
    NULL::integer AS adult_count,
    NULL::integer AS child_count,
    NULL::integer AS infant_count,
    NULL AS rate_code,
    NULL AS meal_pattern,
    dg.company_id,
    'dummy' AS state
FROM tz_dummy_group dg
JOIN (
    SELECT DISTINCT ON (dummy_id) id, dummy_id 
    FROM tz_master_folio 
    WHERE dummy_id IS NOT NULL
    ORDER BY dummy_id, id
) mf ON mf.dummy_id = dg.id
WHERE dg.obsolete = FALSE;