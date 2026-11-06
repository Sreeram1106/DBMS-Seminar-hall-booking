-- =====================================================================
--  Seminar Hall Booking System - 02_procedures_triggers.sql
--  Procedures:  request_booking  (student asks for a hall, names an event head)
--               faculty_review   (the event head approves or rejects)
--               review_booking   (the chairperson gives the final decision)
--  Triggers:    trg_free_hall_on_cancel  (frees the hall and publishes
--                                         the freed slot to everyone)
--               trg_slot_gap_insert / trg_slot_gap_update
--                                        (30 minute gap between slots)
-- =====================================================================

USE seminar_booking;

DELIMITER $$

-- ---------------------------------------------------------------------
-- PROCEDURE request_booking
-- A student asks for a hall on a date and slot. The request is saved first,
-- then checked. If every rule passes, the hall is HELD (a row goes into
-- allocations, so nobody else can take it) and the request stays PENDING
-- while the event head (faculty) and then the chairperson approve it.
-- Otherwise it is REJECTED with the reason. The event head must be a faculty
-- member of the student's own department.
--
-- Example:
--   CALL request_booking('PES1UG24AM001', 2, 1, '2026-11-10',
--                        'Intro to Git Workshop', 'Workshop', 60, 1,
--                        @id, @status, @msg);
--   SELECT @id, @status, @msg;
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS request_booking $$
CREATE PROCEDURE request_booking(
    IN  p_srn         VARCHAR(20),
    IN  p_hall_id     INT,
    IN  p_slot_id     INT,
    IN  p_date        DATE,
    IN  p_event_name  VARCHAR(150),
    IN  p_event_type  VARCHAR(30),
    IN  p_attendees   INT,
    IN  p_faculty_id  INT,
    OUT p_request_id  INT,
    OUT p_status      VARCHAR(20),
    OUT p_message     VARCHAR(255)
)
BEGIN
    DECLARE v_capacity    INT;
    DECLARE v_active      BOOLEAN;
    DECLARE v_slot_start  TIME;
    DECLARE v_taken       INT DEFAULT 0;
    DECLARE v_clash       BOOLEAN DEFAULT FALSE;
    DECLARE v_student_dept INT;
    DECLARE v_faculty_dept INT;

    -- If someone else grabs the same hall+date+slot between our check and our
    -- insert, the UNIQUE key on allocations raises error 1062 (duplicate key).
    -- We catch it and treat it as "already booked" instead of crashing.
    DECLARE CONTINUE HANDLER FOR 1062 SET v_clash = TRUE;

    -- Any other error: undo the whole transaction and report the error.
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- Step 1: save the request as PENDING
    INSERT INTO booking_requests
        (srn, hall_id, slot_id, booking_date, event_name, event_type,
         expected_attendees, faculty_id)
    VALUES
        (p_srn, p_hall_id, p_slot_id, p_date, p_event_name, p_event_type,
         p_attendees, p_faculty_id);
    SET p_request_id = LAST_INSERT_ID();

    -- Step 2: collect what we need to decide
    SELECT capacity, is_active INTO v_capacity, v_active
    FROM seminar_halls
    WHERE hall_id = p_hall_id;

    SELECT dept_id INTO v_student_dept FROM students WHERE srn = p_srn;
    SELECT dept_id INTO v_faculty_dept FROM faculty WHERE faculty_id = p_faculty_id;

    SELECT start_time INTO v_slot_start
    FROM time_slots
    WHERE slot_id = p_slot_id;

    SELECT COUNT(*) INTO v_taken
    FROM allocations
    WHERE hall_id = p_hall_id
      AND booking_date = p_date
      AND slot_id = p_slot_id;

    -- Step 3: hold the hall if every rule passes, otherwise reject with a reason
    IF p_date < CURDATE() THEN
        SET p_status = 'REJECTED', p_message = 'Cannot book a date in the past';
    ELSEIF p_date = CURDATE() AND v_slot_start <= CURTIME() THEN
        SET p_status = 'REJECTED', p_message = 'This time slot has already started today';
    ELSEIF v_faculty_dept <> v_student_dept THEN
        SET p_status = 'REJECTED',
            p_message = 'The event head must be a faculty member of your own department';
    ELSEIF NOT v_active THEN
        SET p_status = 'REJECTED', p_message = 'Hall is under maintenance';
    ELSEIF p_attendees > v_capacity THEN
        SET p_status = 'REJECTED',
            p_message = CONCAT('Too many attendees: hall capacity is ', v_capacity);
    ELSEIF v_taken > 0 THEN
        SET p_status = 'REJECTED', p_message = 'Hall already booked for this date and slot';
    ELSE
        INSERT INTO allocations (request_id, hall_id, slot_id, booking_date)
        VALUES (p_request_id, p_hall_id, p_slot_id, p_date);

        IF v_clash THEN
            SET p_status = 'REJECTED', p_message = 'Hall already booked for this date and slot';
        ELSE
            SET p_status = 'PENDING',
                p_message = 'Hall held for you, waiting for the event head (faculty) to approve';
        END IF;
    END IF;

    -- Step 4: store the decision on the request; a held request now waits
    -- for its event head (faculty_status = PENDING)
    UPDATE booking_requests
    SET status = p_status, remarks = p_message,
        faculty_status = IF(p_status = 'PENDING', 'PENDING', NULL)
    WHERE request_id = p_request_id;

    COMMIT;
END $$


-- ---------------------------------------------------------------------
-- PROCEDURE faculty_review
-- The faculty member the student named as EVENT HEAD confirms the event.
--   approve -> faculty_status APPROVED, the request now waits for the
--              chairperson of the student's department
--   reject  -> the request is REJECTED and stops here (trigger
--              trg_free_hall_on_cancel frees the hall and publishes the slot)
-- Only the named event head may answer, and only once.
--
-- Example:
--   CALL faculty_review(190, 1, TRUE, NULL, @status, @msg);
--   CALL faculty_review(191, 6, FALSE, 'I am not handling this event', @status, @msg);
--   SELECT @status, @msg;
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS faculty_review $$
CREATE PROCEDURE faculty_review(
    IN  p_request_id  INT,
    IN  p_faculty_id  INT,
    IN  p_approve     BOOLEAN,
    IN  p_reason      VARCHAR(200),
    OUT p_status      VARCHAR(20),
    OUT p_message     VARCHAR(255)
)
BEGIN
    DECLARE v_status     VARCHAR(20);
    DECLARE v_fac_status VARCHAR(20);
    DECLARE v_event_head INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- lock the request row so two clicks cannot answer it twice
    SELECT status, faculty_status, faculty_id INTO v_status, v_fac_status, v_event_head
    FROM booking_requests
    WHERE request_id = p_request_id
    FOR UPDATE;

    IF v_status IS NULL THEN
        SET p_status = 'ERROR', p_message = 'No such request';
    ELSEIF v_event_head <> p_faculty_id THEN
        SET p_status = v_status, p_message = 'Only the event head of this request can answer it';
    ELSEIF v_status <> 'PENDING' OR v_fac_status <> 'PENDING' THEN
        SET p_status = v_status, p_message = 'This request has already been decided';
    ELSEIF p_approve THEN
        SET p_status = 'PENDING',
            p_message = 'Approved by the event head, waiting for the chairperson';
        UPDATE booking_requests
        SET faculty_status = 'APPROVED', faculty_decided_at = NOW(),
            faculty_remarks = 'Approved', remarks = p_message
        WHERE request_id = p_request_id;
    ELSE
        SET p_status = 'REJECTED',
            p_message = CONCAT('Rejected by the event head: ',
                               COALESCE(NULLIF(TRIM(p_reason), ''), 'no reason given'));
        UPDATE booking_requests
        SET faculty_status = 'REJECTED', faculty_decided_at = NOW(),
            faculty_remarks = COALESCE(NULLIF(TRIM(p_reason), ''), 'no reason given'),
            status = 'REJECTED', remarks = p_message
        WHERE request_id = p_request_id;
    END IF;

    COMMIT;
END $$


-- ---------------------------------------------------------------------
-- PROCEDURE review_booking
-- The CHAIRPERSON of the student's department gives the final decision.
-- The chairperson sees who the event head is and whether they approved,
-- and may decide at any time (even before the event head answers).
--   approve -> ALLOCATED (the hall is booked)
--   reject  -> REJECTED  (trigger trg_free_hall_on_cancel frees the hall and
--                         publishes the slot in freed_slots)
--
-- Example:
--   CALL review_booking(190, 1, TRUE, NULL, @status, @msg);
--   CALL review_booking(191, 2, FALSE, 'Hall reserved for placement drive', @status, @msg);
--   SELECT @status, @msg;
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS review_booking $$
CREATE PROCEDURE review_booking(
    IN  p_request_id  INT,
    IN  p_chair_id    INT,
    IN  p_approve     BOOLEAN,
    IN  p_reason      VARCHAR(200),
    OUT p_status      VARCHAR(20),
    OUT p_message     VARCHAR(255)
)
BEGIN
    DECLARE v_status        VARCHAR(20);
    DECLARE v_student_dept  INT;
    DECLARE v_chair_dept    INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- lock the request row so two clicks cannot decide it twice
    SELECT r.status, s.dept_id INTO v_status, v_student_dept
    FROM booking_requests r
    JOIN students s ON s.srn = r.srn
    WHERE r.request_id = p_request_id
    FOR UPDATE;

    SELECT dept_id INTO v_chair_dept FROM chairpersons WHERE chair_id = p_chair_id;

    IF v_status IS NULL THEN
        SET p_status = 'ERROR', p_message = 'No such request';
    ELSEIF v_status <> 'PENDING' THEN
        SET p_status = v_status, p_message = CONCAT('Request is already ', v_status);
    ELSEIF v_chair_dept IS NULL OR v_chair_dept <> v_student_dept THEN
        SET p_status = 'PENDING',
            p_message = 'Only the chairperson of the student''s department can decide';
    ELSE
        IF p_approve THEN
            SET p_status = 'ALLOCATED', p_message = 'Approved by the chairperson';
        ELSE
            SET p_status = 'REJECTED',
                p_message = CONCAT('Rejected by the chairperson: ',
                                   COALESCE(NULLIF(TRIM(p_reason), ''), 'no reason given'));
        END IF;
        UPDATE booking_requests
        SET status = p_status, remarks = p_message,
            reviewed_by = p_chair_id, reviewed_at = NOW()
        WHERE request_id = p_request_id;
    END IF;

    COMMIT;
END $$


-- ---------------------------------------------------------------------
-- TRIGGER trg_free_hall_on_cancel
-- When a held (PENDING) or approved (ALLOCATED) request becomes CANCELLED or
-- REJECTED, delete its row from allocations so the hall is free again, and
-- record the freed slot in freed_slots. The app shows freed_slots to every
-- student, so a cancelled slot does not silently go unused.
--
-- Example:
--   UPDATE booking_requests SET status = 'CANCELLED', remarks = 'Cancelled by student'
--   WHERE request_id = 5;
--   -- the allocation for request 5 disappears and a freed_slots row appears
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_free_hall_on_cancel $$
CREATE TRIGGER trg_free_hall_on_cancel
AFTER UPDATE ON booking_requests
FOR EACH ROW
BEGIN
    IF OLD.status IN ('PENDING', 'ALLOCATED')
       AND NEW.status IN ('CANCELLED', 'REJECTED') THEN
        DELETE FROM allocations WHERE request_id = NEW.request_id;
        -- only publish if a hall was really held (a request rejected by a
        -- rule inside request_booking never had an allocation)
        IF ROW_COUNT() > 0 THEN
            INSERT INTO freed_slots (request_id, reason)
            VALUES (NEW.request_id, COALESCE(NEW.remarks, NEW.status));
        END IF;
    END IF;
END $$


-- ---------------------------------------------------------------------
-- TRIGGERS trg_slot_gap_insert / trg_slot_gap_update
-- College rule: at least 30 minutes between any two slots, so the hall can
-- be cleared and set up. A CHECK constraint can only look at one row, so
-- comparing a new slot with the existing ones needs a trigger.
--
-- Example (fails, starts only 0 minutes after the 09:00-11:00 slot ends):
--   INSERT INTO time_slots (slot_label, start_time, end_time)
--   VALUES ('11:00 - 12:00', '11:00', '12:00');
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_slot_gap_insert $$
CREATE TRIGGER trg_slot_gap_insert
BEFORE INSERT ON time_slots
FOR EACH ROW
BEGIN
    -- times that break the CHECK rules (before 9, after 4, over 2 hours) are
    -- left for the CHECK constraints to report with their own names
    IF NEW.start_time >= '09:00:00' AND NEW.end_time <= '16:00:00'
       AND NEW.end_time > NEW.start_time
       AND TIMEDIFF(NEW.end_time, NEW.start_time) <= '02:00:00'
       AND EXISTS (SELECT 1 FROM time_slots s
               WHERE NEW.start_time < ADDTIME(s.end_time, '00:30:00')
                 AND s.start_time < ADDTIME(NEW.end_time, '00:30:00')) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Slots must not overlap and need a 30 minute gap between them';
    END IF;
END $$

DROP TRIGGER IF EXISTS trg_slot_gap_update $$
CREATE TRIGGER trg_slot_gap_update
BEFORE UPDATE ON time_slots
FOR EACH ROW
BEGIN
    IF NEW.start_time >= '09:00:00' AND NEW.end_time <= '16:00:00'
       AND NEW.end_time > NEW.start_time
       AND TIMEDIFF(NEW.end_time, NEW.start_time) <= '02:00:00'
       AND EXISTS (SELECT 1 FROM time_slots s
               WHERE s.slot_id <> NEW.slot_id
                 AND NEW.start_time < ADDTIME(s.end_time, '00:30:00')
                 AND s.start_time < ADDTIME(NEW.end_time, '00:30:00')) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Slots must not overlap and need a 30 minute gap between them';
    END IF;
END $$

DELIMITER ;
