-- =====================================================================
--  Seminar Hall Booking System - 05_demo_queries.sql
--  Queries to show in MySQL (Workbench or the mysql> prompt) that the
--  database works on its own, before showing the Streamlit app.
--
--  HOW TO RUN: in MySQL Workbench put the cursor on ONE statement and press
--  Ctrl+Enter (runs only that statement). Do not use "Execute all": Part 4
--  contains statements that are SUPPOSED to fail, and Workbench stops there.
--
--  Before the demo:  python setup_db.py   (fresh sample data)
--  After the demo:   python setup_db.py   (removes the demo bookings again)
-- =====================================================================

USE seminar_booking;


-- ---------------------------------------------------------------------
-- PART 1. The structure: 9 tables, 2 views, 3 procedures, 3 triggers
-- ---------------------------------------------------------------------

SHOW FULL TABLES;                 -- 9 BASE TABLEs + 2 VIEWs

DESCRIBE booking_requests;        -- columns, keys, defaults, ENUMs

-- Every foreign key in the database (the lines of the ER diagram)
SELECT  table_name  AS child_table,
        column_name AS fk_column,
        referenced_table_name  AS parent_table,
        referenced_column_name AS parent_column
FROM information_schema.key_column_usage
WHERE table_schema = 'seminar_booking'
  AND referenced_table_name IS NOT NULL
ORDER BY child_table;

-- Every CHECK constraint (includes our college timing rules on time_slots)
SELECT  table_name, constraint_name, check_clause
FROM information_schema.check_constraints c
JOIN information_schema.table_constraints t USING (constraint_schema, constraint_name)
WHERE constraint_schema = 'seminar_booking';

SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'seminar_booking';
SELECT trigger_name, action_timing, event_manipulation, event_object_table
FROM information_schema.triggers
WHERE trigger_schema = 'seminar_booking';

-- How many rows each table has
SELECT 'departments' AS table_name, COUNT(*) AS total_rows FROM departments
UNION ALL SELECT 'chairpersons',      COUNT(*) FROM chairpersons
UNION ALL SELECT 'students',          COUNT(*) FROM students
UNION ALL SELECT 'faculty',           COUNT(*) FROM faculty
UNION ALL SELECT 'seminar_halls',     COUNT(*) FROM seminar_halls
UNION ALL SELECT 'time_slots',        COUNT(*) FROM time_slots
UNION ALL SELECT 'booking_requests',  COUNT(*) FROM booking_requests
UNION ALL SELECT 'allocations',       COUNT(*) FROM allocations
UNION ALL SELECT 'freed_slots',       COUNT(*) FROM freed_slots;


-- ---------------------------------------------------------------------
-- PART 2. Look at the data
-- ---------------------------------------------------------------------

-- One chairperson per department (JOIN with the new chairpersons table)
SELECT  d.dept_code, d.dept_name, c.chair_id, c.name AS chairperson
FROM departments d
JOIN chairpersons c ON c.dept_id = d.dept_id;

-- The halls (every hall has a projector; seats and AC are what students compare)
SELECT hall_id, hall_name, capacity, IF(has_ac, 'AC', 'Non-AC') AS ac, is_active
FROM seminar_halls;

-- The 3 slots: 9 AM to 4 PM, 2 hours each, 30 minute gap
SELECT * FROM time_slots;

-- Schedule of 27 Nov 2026 (the view hides a 7-table join)
SELECT booking_date, slot_label, hall_name, event_name, event_head, stage, reviewed_by
FROM v_booking_details
WHERE booking_date = '2026-11-27'
ORDER BY slot_label, hall_name;

-- Requests waiting for approval: which step each one is at
SELECT request_id, event_name, student_name, dept_code, event_head, stage
FROM v_booking_details
WHERE status = 'PENDING';

-- Freed slots that EVERY student can see and book right now (novelty)
SELECT * FROM v_open_freed_slots;


-- ---------------------------------------------------------------------
-- PART 3. One booking from start to end (procedures + trigger)
-- ---------------------------------------------------------------------

-- 3a. Clash: Seminar Hall 1 (hall 2) is already booked on 27 Nov, 14:00-16:00 (slot 3)
CALL request_booking('PES1UG24AM001', 2, 3, '2026-11-27',
                     'Viva Demo', 'Seminar', 50, 4, @id, @status, @msg);
SELECT @id, @status, @msg;                       -- REJECTED: already booked

-- 3b. Too many people: Conference Room (hall 6) has 40 seats
CALL request_booking('PES1UG24AM001', 6, 3, '2026-11-27',
                     'Viva Demo', 'Seminar', 60, 4, @id, @status, @msg);
SELECT @id, @status, @msg;                       -- REJECTED: capacity is 40

-- 3b2. Event head from ANOTHER department: AIML student names faculty 1 (Dr. Shalini Murthy, CSE)
CALL request_booking('PES1UG24AM001', 4, 3, '2026-11-27',
                     'Viva Demo', 'Seminar', 50, 1, @id, @status, @msg);
SELECT @id, @status, @msg;                       -- REJECTED: event head must be from your own department

-- 3c. Free hall: AIML Seminar Hall (hall 4), same date and slot.
--     Student PES1UG24AM001 (AIML) names faculty 4, Prof. Arjun Menon (AIML), as event head.
CALL request_booking('PES1UG24AM001', 4, 3, '2026-11-27',
                     'Viva Demo', 'Seminar', 50, 4, @id, @status, @msg);
SELECT @id, @status, @msg;                       -- PENDING: hall held, waiting for the event head
SET @viva = @id;

SELECT * FROM allocations WHERE request_id = @viva;                         -- the hold: 1 row
SELECT stage, event_head FROM v_booking_details WHERE request_id = @viva;  -- Waiting for event head

-- 3d. A faculty member who is NOT the event head cannot answer
--     (faculty 3, Dr. Kavitha Rao, is also AIML, but she is not the event head of this request)
CALL faculty_review(@viva, 3, TRUE, NULL, @status, @msg);
SELECT @status, @msg;                            -- "Only the event head of this request can answer it"

-- 3e. The event head (faculty 4, Prof. Arjun Menon) approves
CALL faculty_review(@viva, 4, TRUE, NULL, @status, @msg);
SELECT @status, @msg;                            -- Approved by the event head, waiting for the chairperson
SELECT stage, faculty_status, faculty_decided_at FROM v_booking_details WHERE request_id = @viva;

-- 3f. The CSE chairperson (1, Dr. Rajesh Iyer) cannot decide an AIML student's request
CALL review_booking(@viva, 1, TRUE, NULL, @status, @msg);
SELECT @status, @msg;                            -- "Only the chairperson of the student's department..."

-- 3g. The AIML chairperson (2, Dr. Meera Krishnan) gives the final approval
CALL review_booking(@viva, 2, TRUE, NULL, @status, @msg);
SELECT @status, @msg;                            -- ALLOCATED: Approved by the chairperson
SELECT request_id, event_name, event_head, faculty_status, stage, reviewed_by, reviewed_at
FROM v_booking_details WHERE request_id = @viva;

-- 3h. The event head REJECTS: request 190 (GenAI for Beginners) names faculty 3, Dr. Kavitha Rao
CALL faculty_review(190, 3, FALSE, 'I am not handling this event', @status, @msg);
SELECT @status, @msg;                            -- REJECTED: it stops here, never reaches the chairperson

-- the trigger freed the hall AND published the slot:
SELECT * FROM allocations WHERE request_id = 190;     -- 0 rows
SELECT * FROM freed_slots WHERE request_id = 190;     -- 1 row
SELECT * FROM v_open_freed_slots;                     -- 26 Nov AIML hall is now listed

-- 3i. The student cancels the approved booking (this is all the app runs)
UPDATE booking_requests
SET status = 'CANCELLED', remarks = 'Cancelled by student'
WHERE request_id = @viva;

SELECT * FROM allocations WHERE request_id = @viva;   -- 0 rows (trigger deleted it)
SELECT * FROM freed_slots WHERE request_id = @viva;   -- 1 row  (trigger published it)

-- 3j. Students who were refused a slot that is now free (the "good news" alert)
SELECT  r.srn, s.name, o.hall_name, o.booking_date, o.slot_label, o.reason
FROM v_open_freed_slots o
JOIN booking_requests r ON r.hall_id = o.hall_id
                       AND r.slot_id = o.slot_id
                       AND r.booking_date = o.booking_date
JOIN students s ON s.srn = r.srn
WHERE r.status = 'REJECTED'
  AND r.remarks = 'Hall already booked for this date and slot';


-- ---------------------------------------------------------------------
-- PART 4. The database refuses bad data (each of these MUST fail)
--         Run them one at a time with Ctrl+Enter.
-- ---------------------------------------------------------------------

-- No double booking: hall 2, 27 Nov, slot 3 is already in allocations.
-- Request 148 asked for that slot and was rejected; try to force it in anyway:
INSERT INTO allocations (request_id, hall_id, slot_id, booking_date)
VALUES (148, 2, 3, '2026-11-27');
-- Error 1062: Duplicate entry ... for key 'uq_no_double_booking'

-- College rule: halls only between 9 AM and 4 PM
INSERT INTO time_slots (slot_label, start_time, end_time) VALUES ('15:00 - 17:00', '15:00', '17:00');
-- Error 3819: Check constraint 'chk_slot_hours' is violated

-- College rule: a booking lasts at most 2 hours
INSERT INTO time_slots (slot_label, start_time, end_time) VALUES ('09:00 - 12:00', '09:00', '12:00');
-- Error 3819: Check constraint 'chk_slot_max_2h' is violated

-- College rule: 30 minute gap between slots (checked by trigger trg_slot_gap_insert)
INSERT INTO time_slots (slot_label, start_time, end_time) VALUES ('11:00 - 11:20', '11:00', '11:20');
-- Error 1644: Slots must not overlap and need a 30 minute gap between them

-- Foreign key: no request from a student who does not exist
CALL request_booking('NOBODY', 4, 1, '2026-11-20', 'X', 'Seminar', 10, 1, @id, @status, @msg);
-- Error 1452: foreign key constraint fails (the procedure rolled back)

-- CHECK: semester must be 1 to 8
INSERT INTO students (srn, name, email, semester, dept_id)
VALUES ('PES1UG26XX001', 'Test', 'test@example.edu', 9, 1);
-- Error 3819: Check constraint 'chk_semester' is violated


-- ---------------------------------------------------------------------
-- PART 5. Reports (all 13 are in sql/04_reports.sql; these are the key ones)
-- ---------------------------------------------------------------------

-- R1. "Average salary of every department" style: average attendance of every hall
-- @month empty = all months
SET @month = NULL;
SELECT  h.hall_name,
        h.capacity,
        COUNT(*)                                                AS total_bookings,
        ROUND(AVG(r.expected_attendees), 1)                     AS avg_attendees,
        ROUND(AVG(r.expected_attendees) * 100 / h.capacity, 1)  AS avg_occupancy_pct
FROM booking_requests r
JOIN seminar_halls h ON h.hall_id = r.hall_id
WHERE r.status = 'ALLOCATED'
  AND (@month IS NULL OR DATE_FORMAT(r.booking_date, '%Y-%m') = @month)
GROUP BY h.hall_id, h.hall_name, h.capacity
ORDER BY h.hall_id;

-- The same report for August only (this is what the month filter on the website does)
SET @month = '2026-08';
SELECT  h.hall_name,
        h.capacity,
        COUNT(*)                                                AS total_bookings,
        ROUND(AVG(r.expected_attendees), 1)                     AS avg_attendees,
        ROUND(AVG(r.expected_attendees) * 100 / h.capacity, 1)  AS avg_occupancy_pct
FROM booking_requests r
JOIN seminar_halls h ON h.hall_id = r.hall_id
WHERE r.status = 'ALLOCATED'
  AND (@month IS NULL OR DATE_FORMAT(r.booking_date, '%Y-%m') = @month)
GROUP BY h.hall_id, h.hall_name, h.capacity
ORDER BY h.hall_id;
SET @month = NULL;

-- R2. Department-wise requests and success rate
SELECT  d.dept_code,
        COUNT(r.request_id)                                AS total_requests,
        COUNT(CASE WHEN r.status = 'ALLOCATED' THEN 1 END) AS allocated,
        ROUND(100 * COUNT(CASE WHEN r.status = 'ALLOCATED' THEN 1 END)
              / NULLIF(COUNT(r.request_id), 0), 1)         AS success_rate_pct
FROM departments d
LEFT JOIN students s         ON s.dept_id = d.dept_id
LEFT JOIN booking_requests r ON r.srn = s.srn
GROUP BY d.dept_id, d.dept_code
ORDER BY total_requests DESC;

-- R9. Halls busier than the average hall (nested subquery in HAVING)
SELECT  h.hall_name, COUNT(*) AS bookings
FROM allocations a
JOIN seminar_halls h ON h.hall_id = a.hall_id
GROUP BY h.hall_id, h.hall_name
HAVING COUNT(*) > (SELECT AVG(cnt)
                   FROM (SELECT COUNT(*) AS cnt FROM allocations GROUP BY hall_id) AS per_hall)
ORDER BY bookings DESC;

-- R11. Novelty: freed slots and how many were booked again
SELECT  h.hall_name,
        COUNT(*) AS slots_freed,
        COUNT(CASE WHEN EXISTS (SELECT 1 FROM allocations a
                                WHERE a.hall_id = r.hall_id
                                  AND a.booking_date = r.booking_date
                                  AND a.slot_id = r.slot_id) THEN 1 END) AS booked_again
FROM freed_slots f
JOIN booking_requests r ON r.request_id = f.request_id
JOIN seminar_halls h    ON h.hall_id    = r.hall_id
GROUP BY h.hall_id, h.hall_name
ORDER BY slots_freed DESC;

-- R12. Chairperson decisions and AVERAGE hours a student waited for the final decision
SELECT  c.name AS chairperson,
        d.dept_code,
        COUNT(CASE WHEN r.status = 'PENDING' AND r.faculty_status = 'APPROVED' THEN 1 END) AS waiting_for_chair,
        ROUND(AVG(CASE WHEN r.reviewed_by = c.chair_id
                       THEN TIMESTAMPDIFF(MINUTE, r.requested_at, r.reviewed_at) END) / 60, 1) AS avg_hours_to_decide
FROM chairpersons c
JOIN departments d           ON d.dept_id = c.dept_id
JOIN students s              ON s.dept_id = c.dept_id
LEFT JOIN booking_requests r ON r.srn = s.srn
GROUP BY c.chair_id, c.name, d.dept_code;

-- R13. Event heads: requests received, approved and average hours to answer
SELECT  f.name AS event_head,
        COUNT(r.request_id)                                       AS requests_received,
        COUNT(CASE WHEN r.faculty_status = 'APPROVED' THEN 1 END) AS approved,
        ROUND(AVG(TIMESTAMPDIFF(MINUTE, r.requested_at, r.faculty_decided_at)) / 60, 1) AS avg_hours_to_answer
FROM faculty f
LEFT JOIN booking_requests r ON r.faculty_id = f.faculty_id AND r.faculty_status IS NOT NULL
GROUP BY f.faculty_id, f.name
ORDER BY requests_received DESC;
