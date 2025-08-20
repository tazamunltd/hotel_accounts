CREATE MATERIALIZED VIEW tz_checkout AS (    
    SELECT
        id,
        name,
        booking_id,
        room_id,
        group_booking_id,
        dummy_id,
        folio_id,
        partner_id,
        checkin_date,
        checkout_date,
        adult_count,
        child_count,
        infant_count,
        rate_code,
        meal_pattern,
        state,
        company_id
    FROM (
        -- Room Booking block
        -- Room Booking block (include individual bookings and group bookings that have a master folio)
        SELECT
            (rb.id * 10 + 1) AS id,
            COALESCE(hr.name ->> 'en_US', 'Unnamed') AS name,
            rb.id AS booking_id,
            hr.id AS room_id,
            rb.group_booking_id,
            NULL::integer AS dummy_id,
            folio.id AS folio_id,
            rb.partner_id,
            rb.checkin_date,
            rb.checkout_date,
            rb.adult_count::integer,
            rb.child_count::integer,
            rb.infant_count::integer,
            rb.rate_code::varchar,
            rb.meal_pattern::varchar,
            rb.state::varchar AS state,
            rb.company_id
        FROM room_booking rb
        JOIN room_booking_line rbl ON rbl.booking_id = rb.id
        JOIN hotel_room hr ON rbl.room_id = hr.id
        LEFT JOIN tz_master_folio folio
            ON folio.room_id = rbl.room_id
        WHERE rb.state = 'check_in'
          AND (
            rb.group_booking IS NULL
            OR (rb.group_booking IS NOT NULL AND folio.id IS NOT NULL)
          )


        UNION ALL

        -- Group Booking block
        SELECT
            (gb.id * 10 + 2) AS id,
            COALESCE(gb.group_name ->> 'en_US', 'Unnamed') AS name,
            NULL::integer AS booking_id,
            NULL::integer AS room_id,
            gb.id AS group_booking_id,
            NULL::integer AS dummy_id,
            folio.id AS folio_id,
            gb.company AS partner_id,
            gb.first_visit AS checkin_date,
            gb.last_visit AS checkout_date,
            gb.total_adult_count::integer,
            gb.total_child_count::integer,
            gb.total_infant_count::integer,
            gb.rate_code::varchar,
            gb.group_meal_pattern::varchar,
            gb.status_code::varchar AS state,
            gb.company_id
        FROM group_booking gb
        LEFT JOIN tz_master_folio folio
            ON folio.group_id = gb.id
        WHERE gb.status_code = 'confirmed'
          AND gb.id IN (SELECT rb.group_booking FROM room_booking rb WHERE rb.state = 'check_in')

        UNION ALL

        -- Dummy Group block
        SELECT
            (dg.id * 10 + 3) AS id,
            dg.description::text AS name,
            NULL::integer AS booking_id,
            NULL::integer AS room_id,
            NULL::integer AS group_booking_id,
            dg.id AS dummy_id,
            folio.id AS folio_id,
            dg.partner_id,
            dg.start_date AS checkin_date,
            dg.end_date AS checkout_date,
            NULL::integer AS adult_count,
            NULL::integer AS child_count,
            NULL::integer AS infant_count,
            NULL::varchar AS rate_code,
            NULL::varchar AS meal_pattern,
            dg.state::varchar AS state,
            dg.company_id
        FROM tz_dummy_group dg
        LEFT JOIN tz_master_folio folio
            ON folio.dummy_id = dg.id
        WHERE dg.obsolete = FALSE
    ) AS unified
);