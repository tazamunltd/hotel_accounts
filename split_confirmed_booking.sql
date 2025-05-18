CREATE OR REPLACE PROCEDURE split_confirmed_booking(p_booking_id INT)
LANGUAGE plpgsql AS
$$
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

    v_child_num      INT;
    v_max_child_num  INT;
    v_seq_str        TEXT;

    v_new_book_id    INT;
BEGIN
    -- 1) Load & validate parent booking
    SELECT *
      INTO parent_rec
      FROM room_booking
     WHERE id    = p_booking_id
       AND state = 'confirmed';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Booking % not found or not CONFIRMED', p_booking_id;
    END IF;

    -- 1a) Extract the numeric part of the parent name
    v_parent_num := regexp_replace(parent_rec.name, '.*/', '')::INT;

    -- 1b) Fetch company info
    SELECT id, name
      INTO v_company_id, v_company_name
      FROM res_company
     WHERE id = parent_rec.company_id;

    -- 1c) Get sequence padding & increment
    SELECT padding, number_increment
      INTO v_padding, v_increment
      FROM ir_sequence
     WHERE code       = 'room.booking'
       AND company_id = v_company_id
     LIMIT 1;

    -- 2a) Gather rooms already booked in the same date range
    SELECT array_agg(rl.room_id)
      INTO v_booked_ids
      FROM room_booking_line rl
      JOIN room_booking b ON rl.booking_id = b.id
     WHERE rl.room_id IS NOT NULL
       AND b.checkin_date  < parent_rec.checkout_date
       AND b.checkout_date > parent_rec.checkin_date
       AND b.state IN ('confirmed','block','check_in')
       AND b.company_id = v_company_id;

    -- initialize max child-num to the parent number
    v_max_child_num := v_parent_num;

    -- 3) Loop each line: assign room + create child bookings
    FOR v_line IN
      SELECT id, counter, hotel_room_type
        FROM room_booking_line
       WHERE booking_id = p_booking_id
       ORDER BY counter
    LOOP
        v_room_type_id := v_line.hotel_room_type;
        
        -- 3a) Find an available room of that type
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

        -- 3b) Compute this line's numeric suffix
        v_child_num := v_parent_num + (v_line.counter - 1);
        IF v_child_num > v_max_child_num THEN
            v_max_child_num := v_child_num;
        END IF;
        v_seq_str := LPAD(v_child_num::TEXT, v_padding, '0');

        IF v_line.counter = 1 THEN
            -- first line: assign back to parent
            UPDATE room_booking_line
               SET room_id = v_room_id,
                   state_  = 'block'
             WHERE id = v_line.id;
        ELSE
            -- subsequent lines: create child booking
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
                v_company_name || '/' || v_seq_str,
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

            -- reassign that line to its child booking
            UPDATE room_booking_line
               SET booking_id = v_new_book_id,
                   room_id    = v_room_id
             WHERE id = v_line.id;
        END IF;
    END LOOP;

    -- 4) Close out the parent booking
    UPDATE room_booking
       SET state       = 'block',
           room_count  = (
               SELECT COUNT(*) FROM room_booking_line WHERE booking_id = p_booking_id
           ),
           show_in_tree = TRUE
     WHERE id = p_booking_id;
END;
$$;