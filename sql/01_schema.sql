-- =====================================================================
--  Seminar Hall Booking System - 01_schema.sql
--  Creates all 9 tables and 2 views. Safe to re-run: it drops and
--  recreates them.
--
--  Approval flow (how our college works):
--    student requests a hall and names a faculty member as EVENT HEAD
--    -> the event head (faculty) approves or rejects
--    -> the CHAIRPERSON of the student's department gives the final approval
-- =====================================================================

USE seminar_booking;

-- Drop child tables before parent tables (foreign key order)
DROP VIEW IF EXISTS v_open_freed_slots;
DROP VIEW IF EXISTS v_booking_details;
DROP TABLE IF EXISTS freed_slots;
DROP TABLE IF EXISTS allocations;
DROP TABLE IF EXISTS booking_requests;
DROP TABLE IF EXISTS time_slots;
DROP TABLE IF EXISTS seminar_halls;
-- (hall_coordinators is an old table from an earlier version of the project)
DROP TABLE IF EXISTS hall_coordinators;
DROP TABLE IF EXISTS chairpersons;
DROP TABLE IF EXISTS faculty;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS departments;


-- 1. DEPARTMENTS -------------------------------------------------------
CREATE TABLE departments (
    dept_id    INT AUTO_INCREMENT PRIMARY KEY,
    dept_code  VARCHAR(10)  NOT NULL UNIQUE,
    dept_name  VARCHAR(100) NOT NULL
);


-- 2. CHAIRPERSONS (one per department, gives the final approval) --------
-- dept_id is UNIQUE: a department has exactly one chairperson.
CREATE TABLE chairpersons (
    chair_id   INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(100) NOT NULL UNIQUE,
    dept_id    INT          NOT NULL UNIQUE,
    CONSTRAINT fk_chair_dept FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
);


-- 3. STUDENTS (they raise booking requests) -----------------------------
CREATE TABLE students (
    srn        VARCHAR(20)  PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(100) NOT NULL UNIQUE,
    phone      CHAR(10),
    semester   TINYINT      NOT NULL,
    dept_id    INT          NOT NULL,
    CONSTRAINT chk_semester CHECK (semester BETWEEN 1 AND 8),
    CONSTRAINT fk_student_dept FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
);


-- 4. FACULTY (every event has a faculty member as its event head) -------
CREATE TABLE faculty (
    faculty_id   INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    email        VARCHAR(100) NOT NULL UNIQUE,
    designation  VARCHAR(50),
    dept_id      INT NOT NULL,
    CONSTRAINT fk_faculty_dept FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
);


-- 5. SEMINAR HALLS (every hall has a projector, so it defaults to TRUE) --
CREATE TABLE seminar_halls (
    hall_id        INT AUTO_INCREMENT PRIMARY KEY,
    hall_name      VARCHAR(100) NOT NULL UNIQUE,
    block          VARCHAR(50)  NOT NULL,
    floor_no       TINYINT,
    capacity       INT          NOT NULL,
    has_projector  BOOLEAN      NOT NULL DEFAULT TRUE,
    has_ac         BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_capacity CHECK (capacity > 0)
);


-- 6. TIME SLOTS (a hall is booked slot-wise, not for the whole day) -----
-- College rules: halls are used only between 09:00 and 16:00, one booking
-- lasts at most 2 hours, and there is a 30 minute gap between slots (for
-- clearing and setting up the hall). The first three rules are CHECKs here;
-- the 30 minute gap compares rows, so trigger trg_slot_gap enforces it.
CREATE TABLE time_slots (
    slot_id     INT AUTO_INCREMENT PRIMARY KEY,
    slot_label  VARCHAR(30) NOT NULL UNIQUE,
    start_time  TIME        NOT NULL,
    end_time    TIME        NOT NULL,
    CONSTRAINT chk_slot_time    CHECK (end_time > start_time),
    CONSTRAINT chk_slot_hours   CHECK (start_time >= '09:00:00' AND end_time <= '16:00:00'),
    CONSTRAINT chk_slot_max_2h  CHECK (TIMEDIFF(end_time, start_time) <= '02:00:00')
);


-- 7. BOOKING REQUESTS (every request a student makes, booked or not) ----
-- status:         PENDING   = hall is held while the approvals happen
--                 ALLOCATED = final approval by the chairperson (booked)
--                 REJECTED  = failed a rule, or rejected by the event head
--                             or by the chairperson
--                 CANCELLED = cancelled by the student or the chairperson
-- faculty_status: the event head's answer (NULL = never sent, because the
--                 request failed a rule straight away)
CREATE TABLE booking_requests (
    request_id          INT AUTO_INCREMENT PRIMARY KEY,
    srn                 VARCHAR(20)  NOT NULL,
    hall_id             INT          NOT NULL,
    slot_id             INT          NOT NULL,
    booking_date        DATE         NOT NULL,
    event_name          VARCHAR(150) NOT NULL,
    event_type          ENUM('Seminar','Workshop','Guest Lecture','Club Event',
                             'Hackathon','Cultural','Other') NOT NULL,
    expected_attendees  INT          NOT NULL,
    faculty_id          INT          NOT NULL,          -- the event head
    faculty_status      ENUM('PENDING','APPROVED','REJECTED'),
    faculty_remarks     VARCHAR(255),
    faculty_decided_at  DATETIME,
    status              ENUM('PENDING','ALLOCATED','REJECTED','CANCELLED')
                        NOT NULL DEFAULT 'PENDING',
    remarks             VARCHAR(255),
    requested_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by         INT,                            -- the chairperson
    reviewed_at         DATETIME,
    CONSTRAINT chk_attendees CHECK (expected_attendees > 0),
    CONSTRAINT fk_req_student FOREIGN KEY (srn)        REFERENCES students(srn),
    CONSTRAINT fk_req_hall    FOREIGN KEY (hall_id)    REFERENCES seminar_halls(hall_id),
    CONSTRAINT fk_req_slot    FOREIGN KEY (slot_id)    REFERENCES time_slots(slot_id),
    CONSTRAINT fk_req_faculty FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id),
    CONSTRAINT fk_req_chair   FOREIGN KEY (reviewed_by) REFERENCES chairpersons(chair_id),
    INDEX idx_req_date (booking_date),
    INDEX idx_req_status (status)
);


-- 8. ALLOCATIONS (the real hall schedule: booked halls, plus PENDING
--    requests that hold the hall while the approvals happen) -------------
-- The UNIQUE key on (hall_id, booking_date, slot_id) makes it IMPOSSIBLE
-- for the database to store two bookings of the same hall in the same slot,
-- even if two students click "Book" at the same moment.
CREATE TABLE allocations (
    allocation_id  INT AUTO_INCREMENT PRIMARY KEY,
    request_id     INT      NOT NULL UNIQUE,
    hall_id        INT      NOT NULL,
    slot_id        INT      NOT NULL,
    booking_date   DATE     NOT NULL,
    allocated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_no_double_booking UNIQUE (hall_id, booking_date, slot_id),
    CONSTRAINT fk_alloc_request FOREIGN KEY (request_id) REFERENCES booking_requests(request_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_alloc_hall    FOREIGN KEY (hall_id)    REFERENCES seminar_halls(hall_id),
    CONSTRAINT fk_alloc_slot    FOREIGN KEY (slot_id)    REFERENCES time_slots(slot_id)
);


-- 9. FREED SLOTS (a booked slot that became free again) -----------------
-- Filled ONLY by trigger trg_free_hall_on_cancel: when a held or approved
-- booking is cancelled or rejected, its slot is published here so every
-- student can see it (and the students who were refused that slot earlier
-- are told it is free). Hall, date and slot come from the request.
CREATE TABLE freed_slots (
    release_id  INT AUTO_INCREMENT PRIMARY KEY,
    request_id  INT          NOT NULL UNIQUE,
    reason      VARCHAR(255) NOT NULL,
    freed_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_freed_request FOREIGN KEY (request_id) REFERENCES booking_requests(request_id)
        ON DELETE CASCADE
);


-- VIEW: one row per request with all the names joined in -----------------
-- stage turns status + faculty_status into the words people see.
CREATE VIEW v_booking_details AS
SELECT  r.request_id,
        r.booking_date,
        t.slot_label,
        h.hall_name,
        r.event_name,
        r.event_type,
        r.expected_attendees,
        h.capacity,
        s.srn,
        s.name       AS student_name,
        s.dept_id,
        d.dept_code,
        r.faculty_id,
        f.name       AS event_head,
        r.faculty_status,
        r.faculty_remarks,
        r.faculty_decided_at,
        CASE
            WHEN r.status = 'PENDING' AND r.faculty_status = 'APPROVED' THEN 'Waiting for chairperson'
            WHEN r.status = 'PENDING'   THEN 'Waiting for event head'
            WHEN r.status = 'ALLOCATED' THEN 'Booked'
            WHEN r.status = 'REJECTED'  THEN 'Rejected'
            ELSE 'Cancelled'
        END          AS stage,
        r.status,
        r.remarks,
        r.requested_at,
        c.name       AS reviewed_by,
        r.reviewed_at
FROM booking_requests r
JOIN students      s ON s.srn        = r.srn
JOIN departments   d ON d.dept_id    = s.dept_id
JOIN seminar_halls h ON h.hall_id    = r.hall_id
JOIN time_slots    t ON t.slot_id    = r.slot_id
JOIN faculty       f ON f.faculty_id = r.faculty_id
LEFT JOIN chairpersons c ON c.chair_id = r.reviewed_by;


-- VIEW: freed slots that anyone can book right now ------------------------
-- (date not passed, slot not started yet today, and nobody has re-booked it)
CREATE VIEW v_open_freed_slots AS
SELECT  f.release_id,
        f.freed_at,
        f.reason,
        r.request_id AS freed_by_request,
        r.booking_date,
        r.hall_id,
        h.hall_name,
        h.capacity,
        r.slot_id,
        t.slot_label
FROM freed_slots f
JOIN booking_requests r ON r.request_id = f.request_id
JOIN seminar_halls    h ON h.hall_id    = r.hall_id
JOIN time_slots       t ON t.slot_id    = r.slot_id
WHERE h.is_active
  AND (r.booking_date > CURDATE()
       OR (r.booking_date = CURDATE() AND t.start_time > CURTIME()))
  AND NOT EXISTS (SELECT 1 FROM allocations a
                  WHERE a.hall_id = r.hall_id
                    AND a.booking_date = r.booking_date
                    AND a.slot_id = r.slot_id)
  -- if the same slot was freed more than once, show only the latest release
  AND f.release_id = (SELECT MAX(f2.release_id)
                      FROM freed_slots f2
                      JOIN booking_requests r2 ON r2.request_id = f2.request_id
                      WHERE r2.hall_id = r.hall_id
                        AND r2.booking_date = r.booking_date
                        AND r2.slot_id = r.slot_id);
