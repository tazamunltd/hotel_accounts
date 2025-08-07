-- PROCEDURE: public.split_confirmed_booking(integer)

-- DROP PROCEDURE IF EXISTS public.split_confirmed_booking(integer);

CREATE OR REPLACE PROCEDURE public.split_confirmed_booking(
	IN p_booking_id integer)
LANGUAGE 'plpgsql'
AS $BODY$
DECLARE
    parent_rec       room_booking%ROWTYPE;
    v_parent_num     INT;
    v_company_id     INT;
    v_company_name   TEXT;
    v_booked_ids     INT[];
    v_assigned_ids   INT[] := '{}';

    v_line           RECORD;
    v_room_type_id   INT;
    v_room_id        INT;

    v_padding        INT;
    v_increment      INT;
    v_sequence_id    INT;

    v_child_num      INT;
    v_max_child_num  INT;
    v_seq_str        TEXT;

    v_new_book_id    INT;

    -- Cursors for copying adult/child/infant rows
    rec_adult        RECORD;
    rec_child        RECORD;
    rec_infant       RECORD;
BEGIN
    -------------------------------------------------------------------
    -- 1) Load & validate parent booking
    SELECT *
      INTO parent_rec
      FROM room_booking
     WHERE id    = p_booking_id
       AND state = 'confirmed';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Booking % not found or not CONFIRMED', p_booking_id;
    END IF;

    -------------------------------------------------------------------
    -- 1a) Extract numeric part of parent name
    v_parent_num := regexp_replace(parent_rec.name, '.*/', '')::INT;

    -------------------------------------------------------------------
    -- 1b) Fetch company info (ID and name)
    SELECT id, name
      INTO v_company_id, v_company_name
      FROM res_company
     WHERE id = parent_rec.company_id;

    -------------------------------------------------------------------
    -- 1c) Get sequence info from ir_sequence for generating child booking names
    SELECT id, padding, number_increment
      INTO v_sequence_id, v_padding, v_increment
      FROM ir_sequence
     WHERE code       = 'room.booking'
       AND company_id = v_company_id
     LIMIT 1;

    -- Ensure padding is at least 5 as requested
    IF v_padding < 5 THEN
        v_padding := 5;
    END IF;

    -------------------------------------------------------------------
    -- 2a) Gather rooms already booked in the same date range
    SELECT array_agg(rl.room_id)
      INTO v_booked_ids
      FROM room_booking_line rl
      JOIN room_booking b ON rl.booking_id = b.id
     WHERE rl.room_id IS NOT NULL
       AND b.checkin_date  < parent_rec.checkout_date
       AND b.checkout_date > parent_rec.checkin_date
       AND b.state IN ('confirmed','block','check_in')
       AND b.company_id = v_company_id
	   AND NOT (DATE(b.checkout_date) = DATE(parent_rec.checkin_date));

    -------------------------------------------------------------------
    -- 2b) Single‐room shortcut (no children needed)
    IF parent_rec.room_count = 1 THEN
        SELECT id
          INTO v_room_id
          FROM hotel_room
         WHERE company_id     = v_company_id
           AND room_type_name = parent_rec.hotel_room_type
           AND id <> ALL(COALESCE(v_booked_ids, ARRAY[]::INT[]))
         LIMIT 1;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'No available room for type %', parent_rec.hotel_room_type;
        END IF;

        -- Assign that single room to the parent's only line
        UPDATE room_booking_line
           SET room_id = v_room_id,
               state_  = 'block'
         WHERE booking_id = p_booking_id;

        -- Update the parent booking itself
        UPDATE room_booking
           SET state        = 'block',
               room_count   = 1,
               show_in_tree = TRUE
         WHERE id = p_booking_id;

        -------------------------------------------------------------------
        -- COPY / UPDATE parent's reservation_adult rows (only sequence 1)
        FOR rec_adult IN
          SELECT *
            FROM reservation_adult
           WHERE reservation_id = p_booking_id
             AND room_sequence = 1
        LOOP
            UPDATE reservation_adult
               SET room_id      = v_room_id
             WHERE id = rec_adult.id;
        END LOOP;

        -------------------------------------------------------------------
        -- COPY / UPDATE parent's reservation_child rows (only sequence 1)
        FOR rec_child IN
          SELECT *
            FROM reservation_child
           WHERE reservation_id = p_booking_id
             AND room_sequence = 1
        LOOP
            UPDATE reservation_child
               SET room_id      = v_room_id
             WHERE id = rec_child.id;
        END LOOP;

        -------------------------------------------------------------------
        -- COPY / UPDATE parent's reservation_infant rows (only sequence 1)
        FOR rec_infant IN
          SELECT *
            FROM reservation_infant
           WHERE reservation_id = p_booking_id
             AND room_sequence = 1
        LOOP
            UPDATE reservation_infant
               SET room_id      = v_room_id
             WHERE id = rec_infant.id;
        END LOOP;

        RETURN;
    END IF;
    -------------------------------------------------------------------

    -- init max child‐num (we'll keep track of the highest suffix used)
    v_max_child_num := v_parent_num;

    -------------------------------------------------------------------
    -- 3) Loop each room_booking_line: assign room + create child bookings
    FOR v_line IN
      SELECT id, counter, hotel_room_type
        FROM room_booking_line
       WHERE booking_id = p_booking_id
       ORDER BY counter
    LOOP
        v_room_type_id := v_line.hotel_room_type;

        ----------------------------------------------------------------
        -- 3a) Find an available room of that type, excluding already‐booked &
        --     already‐assigned for this split operation
        SELECT id
          INTO v_room_id
          FROM hotel_room
         WHERE company_id     = v_company_id
           AND room_type_name = v_room_type_id
           AND id <> ALL(COALESCE(v_booked_ids, ARRAY[]::INT[]))
           AND id <> ALL(v_assigned_ids)
         LIMIT 1;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'No available room for type %', v_room_type_id;
        END IF;
        v_assigned_ids := array_append(v_assigned_ids, v_room_id);

        ----------------------------------------------------------------
        -- 3b) If this is the first line (counter = 1), update the parent's line:
        IF array_length(v_assigned_ids, 1) = 1 THEN
            UPDATE room_booking_line
               SET room_id = v_room_id,
                   state_  = 'block'
             WHERE id = v_line.id;

            CONTINUE;  -- move to next v_line (don't create a child booking for seq 1)

        ELSE
            ----------------------------------------------------------------
            -- 3c) Check if child booking already exists for this line
            SELECT rb.id
              INTO v_new_book_id
              FROM room_booking rb
              JOIN room_booking_line rbl ON rbl.booking_id = rb.id
             WHERE rb.parent_booking_id = p_booking_id
               AND rbl.id = v_line.id
             LIMIT 1;

            -- If child booking already exists, just update the room assignment
            IF v_new_book_id IS NOT NULL THEN
                UPDATE room_booking_line
                   SET room_id = v_room_id,
                       state_  = 'block'
                 WHERE id = v_line.id;

                CONTINUE;  -- Skip creating new child booking
            END IF;

            ----------------------------------------------------------------
            -- 3d) Generate new sequence number for child booking using nextval
            -- This will automatically get the next available sequence number
            SELECT nextval('ir_sequence_' || LPAD(v_sequence_id::TEXT, 3, '0'))
              INTO v_child_num;

            -- Format with proper padding
            v_seq_str := LPAD(v_child_num::TEXT, v_padding, '0');

            ----------------------------------------------------------------
            -- 3e) For counter > 1: create a new child booking with new sequence number
            INSERT INTO room_booking (
                name,
                parent_booking_id,
                parent_booking_name,
                partner_id,
                nationality,
                source_of_business,
                meal_pattern,
                market_segment,
                rate_code,
                reference_contact_,
                hotel_room_type,
                group_booking,
                house_use,
                complementary,
                vip,
                room_count,
                adult_count,
                child_count,
                infant_count,
                complementary_codes,
                house_use_codes,
                vip_code,
                notes,
                checkin_date,
                checkout_date,
                state,
                reservation_status_count_as,
                is_offline_search,
                is_agent,
                no_of_nights,
                room_price,
                use_price,
                room_discount,
                room_is_amount,
                room_amount_selection,
                room_is_percentage,
                use_meal_price,
                meal_price,
                meal_child_price,
                meal_discount,
                meal_amount_selection,
                meal_is_amount,
                meal_is_percentage,
                payment_type,
                date_order,
                company_id,
                show_in_tree,
                active
            ) VALUES (
                v_company_name || '/' || v_seq_str,  -- Using nextval sequence number
                parent_rec.id,
                parent_rec.name,
                parent_rec.partner_id,
                parent_rec.nationality,
                parent_rec.source_of_business,
                parent_rec.meal_pattern,
                parent_rec.market_segment,
                parent_rec.rate_code,
                parent_rec.reference_contact_,
                v_room_type_id,
                parent_rec.group_booking,
                parent_rec.house_use,
                parent_rec.complementary,
                parent_rec.vip,
                1,
                parent_rec.adult_count,
                parent_rec.child_count,
                parent_rec.infant_count,
                parent_rec.complementary_codes,
                parent_rec.house_use_codes,
                parent_rec.vip_code,
                parent_rec.notes,
                parent_rec.checkin_date,
                parent_rec.checkout_date,
                'block',
                'confirmed',
                FALSE,
                parent_rec.is_agent,
                parent_rec.no_of_nights,
                parent_rec.room_price,
                parent_rec.use_price,
                parent_rec.room_discount,
                parent_rec.room_is_amount,
                parent_rec.room_amount_selection,
                parent_rec.room_is_percentage,
                parent_rec.use_meal_price,
                parent_rec.meal_price,
                parent_rec.meal_child_price,
                parent_rec.meal_discount,
                parent_rec.meal_amount_selection,
                parent_rec.meal_is_amount,
                parent_rec.meal_is_percentage,
                parent_rec.payment_type,
                parent_rec.date_order,
                parent_rec.company_id,
                TRUE,
                TRUE
            )
            RETURNING id INTO v_new_book_id;

            ----------------------------------------------------------------
            -- 3f) Reassign that line to its new child booking
            UPDATE room_booking_line
               SET booking_id = v_new_book_id,
                   room_id    = v_room_id,
                   state_     = 'block'
             WHERE id = v_line.id;

            ----------------------------------------------------------------
            -- 3g) Copy parent's posting_item_ids into this new child
            INSERT INTO room_booking_posting_item (
                booking_id,
                posting_item_id,
                item_code,
                description,
                posting_item_selection,
                from_date,
                to_date,
                default_value
            )
            SELECT
                v_new_book_id,
                posting_item_id,
                item_code,
                description,
                posting_item_selection,
                from_date,
                to_date,
                default_value
            FROM room_booking_posting_item
            WHERE booking_id = p_booking_id;

            ----------------------------------------------------------------
            -- 3h) COPY reservation_adult rows for this sequence (counter) into the child
            FOR rec_adult IN
              SELECT *
                FROM reservation_adult
               WHERE reservation_id = p_booking_id
                 AND room_sequence = v_line.counter
            LOOP
                INSERT INTO reservation_adult (
                    reservation_id,
                    room_sequence,
                    first_name,
                    last_name,
                    profile,
                    nationality,
                    birth_date,
                    passport_number,
                    id_number,
                    visa_number,
                    id_type,
                    phone_number,
                    relation,
                    room_type_id,
                    room_id
                ) VALUES (
                    v_new_book_id,
                    v_line.counter,
                    rec_adult.first_name,
                    rec_adult.last_name,
                    rec_adult.profile,
                    rec_adult.nationality,
                    rec_adult.birth_date,
                    rec_adult.passport_number,
                    rec_adult.id_number,
                    rec_adult.visa_number,
                    rec_adult.id_type,
                    rec_adult.phone_number,
                    rec_adult.relation,
                    rec_adult.room_type_id,
                    v_room_id
                );
            END LOOP;

            ----------------------------------------------------------------
            -- 3i) COPY reservation_child rows for this sequence into the child
            FOR rec_child IN
              SELECT *
                FROM reservation_child
               WHERE reservation_id = p_booking_id
                 AND room_sequence = v_line.counter
            LOOP
                INSERT INTO reservation_child (
                    reservation_id,
                    room_sequence,
                    first_name,
                    last_name,
                    profile,
                    nationality,
                    birth_date,
                    passport_number,
                    id_number,
                    visa_number,
                    id_type,
                    phone_number,
                    relation,
                    room_type_id,
                    room_id
                ) VALUES (
                    v_new_book_id,
                    v_line.counter,
                    rec_child.first_name,
                    rec_child.last_name,
                    rec_child.profile,
                    rec_child.nationality,
                    rec_child.birth_date,
                    rec_child.passport_number,
                    rec_child.id_number,
                    rec_child.visa_number,
                    rec_child.id_type,
                    rec_child.phone_number,
                    rec_child.relation,
                    rec_child.room_type_id,
                    v_room_id
                );
            END LOOP;

            ----------------------------------------------------------------
            -- 3j) COPY reservation_infant rows for this sequence into the child
            FOR rec_infant IN
              SELECT *
                FROM reservation_infant
               WHERE reservation_id = p_booking_id
                 AND room_sequence = v_line.counter
            LOOP
                INSERT INTO reservation_infant (
                    reservation_id,
                    room_sequence,
                    first_name,
                    last_name,
                    profile,
                    nationality,
                    birth_date,
                    passport_number,
                    id_number,
                    visa_number,
                    id_type,
                    phone_number,
                    relation,
                    room_type_id,
                    room_id
                ) VALUES (
                    v_new_book_id,
                    v_line.counter,
                    rec_infant.first_name,
                    rec_infant.last_name,
                    rec_infant.profile,
                    rec_infant.nationality,
                    rec_infant.birth_date,
                    rec_infant.passport_number,
                    rec_infant.id_number,
                    rec_infant.visa_number,
                    rec_infant.id_type,
                    rec_infant.phone_number,
                    rec_infant.relation,
                    rec_infant.room_type_id,
                    v_room_id
                );
            END LOOP;

        END IF;
        ----------------------------------------------------------------
    END LOOP;

    -------------------------------------------------------------------
    -- 4) After creating all children, we must clean up the parent's reservation_* rows

    -- 4a) Update parent's reservation_adult rows where room_sequence = 1
    FOR rec_adult IN
      SELECT *
        FROM reservation_adult
       WHERE reservation_id = p_booking_id
         AND room_sequence = 1
    LOOP
        -- Find the room_id that was assigned to the parent's first line:
        UPDATE reservation_adult
           SET room_id = (
               SELECT room_id
                 FROM room_booking_line rbl
                WHERE rbl.booking_id = p_booking_id
                  AND rbl.counter = 1
           )
         WHERE id = rec_adult.id;
    END LOOP;

    -- 4b) Delete any parent's reservation_adult rows with sequence > 1
    DELETE
      FROM reservation_adult
     WHERE reservation_id = p_booking_id
       AND room_sequence > 1;

    -------------------------------------------------------------------
    -- 4c) Update parent's reservation_child rows where room_sequence = 1
    FOR rec_child IN
      SELECT *
        FROM reservation_child
       WHERE reservation_id = p_booking_id
         AND room_sequence = 1
    LOOP
        UPDATE reservation_child
           SET room_id = (
               SELECT room_id
                 FROM room_booking_line rbl
                WHERE rbl.booking_id = p_booking_id
                  AND rbl.counter = 1
           )
         WHERE id = rec_child.id;
    END LOOP;

    -- 4d) Delete any parent's reservation_child rows with sequence > 1
    DELETE
      FROM reservation_child
     WHERE reservation_id = p_booking_id
       AND room_sequence > 1;

    -------------------------------------------------------------------
    -- 4e) Update parent's reservation_infant rows where room_sequence = 1
    FOR rec_infant IN
      SELECT *
        FROM reservation_infant
       WHERE reservation_id = p_booking_id
         AND room_sequence = 1
    LOOP
        UPDATE reservation_infant
           SET room_id = (
               SELECT room_id
                 FROM room_booking_line rbl
                WHERE rbl.booking_id = p_booking_id
                  AND rbl.counter = 1
           )
         WHERE id = rec_infant.id;
    END LOOP;

    -- 4f) Delete any parent's reservation_infant rows with sequence > 1
    DELETE
      FROM reservation_infant
     WHERE reservation_id = p_booking_id
       AND room_sequence > 1;

    -------------------------------------------------------------------
    -- 5) Finally, close out the parent booking
    UPDATE room_booking
       SET state        = 'block',
           room_count   = (
               SELECT COUNT(*) FROM room_booking_line WHERE booking_id = p_booking_id
           ),
           show_in_tree = TRUE
     WHERE id = p_booking_id;
END;
$BODY$;
ALTER PROCEDURE public.split_confirmed_booking(integer)
    OWNER TO odoo17;
