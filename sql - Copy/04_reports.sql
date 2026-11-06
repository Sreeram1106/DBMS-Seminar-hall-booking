-- =====================================================================
--  Seminar Hall Booking System - 04_reports.sql
--  Every report shown in the app's Reports page. They can also be run
--  directly in MySQL Workbench.
--
--  Format used by the app:  "-- #" starts a report (its title),
--  other "--" lines describe it, "-- chart: x, y" picks the bar chart axes.
--
--  Month filter: every report reads the variable @month. Left empty (NULL) it
--  covers all months. To see one month in Workbench run:  SET @month = '2026-08';
-- =====================================================================

USE seminar_booking;


-- #R1. Average attendance of every hall
-- Same idea as "average salary of every department": the average number of
-- attendees at booked events in each hall, and how full the hall was on average.
-- chart: hall_name, avg_attendees
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


-- #R2. Department-wise requests and success rate
-- How many requests each department made and what percentage got a hall.
-- chart: dept_code, total_requests
SELECT  d.dept_code,
        d.dept_name,
        COUNT(r.request_id)                                AS total_requests,
        COUNT(CASE WHEN r.status = 'ALLOCATED' THEN 1 END) AS allocated,
        COUNT(CASE WHEN r.status = 'PENDING'   THEN 1 END) AS pending,
        COUNT(CASE WHEN r.status = 'REJECTED'  THEN 1 END) AS rejected,
        COUNT(CASE WHEN r.status = 'CANCELLED' THEN 1 END) AS cancelled,
        ROUND(100 * COUNT(CASE WHEN r.status = 'ALLOCATED' THEN 1 END)
              / NULLIF(COUNT(r.request_id), 0), 1)         AS success_rate_pct
FROM departments d
LEFT JOIN students s         ON s.dept_id = d.dept_id
LEFT JOIN booking_requests r ON r.srn = s.srn
                             AND (@month IS NULL OR DATE_FORMAT(r.booking_date, '%Y-%m') = @month)
GROUP BY d.dept_id, d.dept_code, d.dept_name
ORDER BY total_requests DESC;


-- #R3. Demand for each time slot
-- Which slot is most in demand, and how often students clashed for it.
-- chart: slot_label, total_requests
SELECT  t.slot_label,
        COUNT(r.request_id) AS total_requests,
        COUNT(CASE WHEN r.remarks = 'Hall already booked for this date and slot' THEN 1 END) AS clashes
FROM time_slots t
LEFT JOIN booking_requests r ON r.slot_id = t.slot_id
                             AND (@month IS NULL OR DATE_FORMAT(r.booking_date, '%Y-%m') = @month)
GROUP BY t.slot_id, t.slot_label
ORDER BY t.slot_id;


-- #R4. Month-wise booking trend
-- Requests, approved bookings and cancellations per month.
-- chart: month, allocated
SELECT  DATE_FORMAT(booking_date, '%Y-%m')               AS month,
        COUNT(*)                                         AS total_requests,
        COUNT(CASE WHEN status = 'ALLOCATED' THEN 1 END) AS allocated,
        COUNT(CASE WHEN status = 'CANCELLED' THEN 1 END) AS cancelled
FROM booking_requests
WHERE (@month IS NULL OR DATE_FORMAT(booking_date, '%Y-%m') = @month)
GROUP BY month
ORDER BY month;


-- #R5. Event type analysis
-- Number of events of each type that got a hall, with average and largest audience.
-- chart: event_type, events_held
SELECT  event_type,
        COUNT(*)                          AS events_held,
        ROUND(AVG(expected_attendees), 1) AS avg_attendees,
        MAX(expected_attendees)           AS max_attendees
FROM booking_requests
WHERE status = 'ALLOCATED'
  AND (@month IS NULL OR DATE_FORMAT(booking_date, '%Y-%m') = @month)
GROUP BY event_type
ORDER BY events_held DESC;


-- #R6. Top 5 most active students
-- Students who successfully booked the most halls.
-- chart: name, halls_booked
SELECT  s.srn,
        s.name,
        d.dept_code,
        COUNT(*) AS halls_booked
FROM booking_requests r
JOIN students s    ON s.srn = r.srn
JOIN departments d ON d.dept_id = s.dept_id
WHERE r.status = 'ALLOCATED'
  AND (@month IS NULL OR DATE_FORMAT(r.booking_date, '%Y-%m') = @month)
GROUP BY s.srn, s.name, d.dept_code
ORDER BY halls_booked DESC, s.name
LIMIT 5;


-- #R7. Events headed by each faculty member
-- Booked events per faculty event head (faculty with zero still appear).
-- chart: event_head, events_headed
SELECT  f.name      AS event_head,
        d.dept_code,
        COUNT(r.request_id) AS events_headed
FROM faculty f
JOIN departments d ON d.dept_id = f.dept_id
LEFT JOIN booking_requests r ON r.faculty_id = f.faculty_id AND r.status = 'ALLOCATED'
                             AND (@month IS NULL OR DATE_FORMAT(r.booking_date, '%Y-%m') = @month)
GROUP BY f.faculty_id, f.name, d.dept_code
ORDER BY events_headed DESC, f.name;


-- #R8. Why requests were rejected
-- Count of rejected requests for each reason.
-- chart: reason, times
SELECT  remarks  AS reason,
        COUNT(*) AS times
FROM booking_requests
WHERE status = 'REJECTED'
  AND (@month IS NULL OR DATE_FORMAT(booking_date, '%Y-%m') = @month)
GROUP BY remarks
ORDER BY times DESC;


-- #R9. Halls busier than the average hall (nested subquery)
-- The inner query counts bookings per hall, the middle one averages those
-- counts, and HAVING keeps only halls above that average.
-- chart: hall_name, bookings
SELECT  h.hall_name,
        COUNT(*) AS bookings
FROM allocations a
JOIN seminar_halls h ON h.hall_id = a.hall_id
WHERE (@month IS NULL OR DATE_FORMAT(a.booking_date, '%Y-%m') = @month)
GROUP BY h.hall_id, h.hall_name
HAVING COUNT(*) > (SELECT AVG(cnt)
                   FROM (SELECT COUNT(*) AS cnt
                         FROM allocations
                         WHERE (@month IS NULL OR DATE_FORMAT(booking_date, '%Y-%m') = @month)
                         GROUP BY hall_id) AS per_hall)
ORDER BY bookings DESC;


-- #R10. Busiest days of the week
-- Confirmed bookings for each weekday.
-- chart: day_of_week, bookings
SELECT  DAYNAME(booking_date) AS day_of_week,
        COUNT(*)              AS bookings
FROM allocations
WHERE (@month IS NULL OR DATE_FORMAT(booking_date, '%Y-%m') = @month)
GROUP BY DAYNAME(booking_date), WEEKDAY(booking_date)
ORDER BY WEEKDAY(booking_date);


-- #R11. Freed slots: were they booked again?
-- Our novelty: every cancelled or rejected booking is published in
-- freed_slots. This shows, for each hall, how many slots were freed and how
-- many of them another student picked up again (re-use of freed slots).
-- The EXISTS inside COUNT(CASE ...) is a correlated subquery: it runs once per freed slot.
-- chart: hall_name, slots_freed
SELECT  h.hall_name,
        COUNT(*) AS slots_freed,
        COUNT(CASE WHEN EXISTS (SELECT 1 FROM allocations a
                                WHERE a.hall_id = r.hall_id
                                  AND a.booking_date = r.booking_date
                                  AND a.slot_id = r.slot_id) THEN 1 END)  AS booked_again,
        COUNT(CASE WHEN f.reason LIKE 'Cancelled by%' THEN 1 END)           AS by_cancellation,
        COUNT(CASE WHEN f.reason LIKE 'Rejected by%' THEN 1 END)            AS by_rejection
FROM freed_slots f
JOIN booking_requests r ON r.request_id = f.request_id
JOIN seminar_halls h    ON h.hall_id    = r.hall_id
WHERE (@month IS NULL OR DATE_FORMAT(r.booking_date, '%Y-%m') = @month)
GROUP BY h.hall_id, h.hall_name
ORDER BY slots_freed DESC;


-- #R12. Chairperson decisions and average approval time
-- For each department's chairperson: requests booked, rejected and still
-- waiting for them, and the average number of hours a student waited for the
-- final decision (another "average per group" report).
-- chart: chairperson, avg_hours_to_decide
SELECT  c.name AS chairperson,
        d.dept_code,
        COUNT(CASE WHEN r.reviewed_by = c.chair_id AND r.remarks NOT LIKE 'Rejected%' THEN 1 END) AS approved,
        COUNT(CASE WHEN r.reviewed_by = c.chair_id AND r.remarks LIKE 'Rejected%' THEN 1 END)     AS rejected,
        COUNT(CASE WHEN r.status = 'PENDING' AND r.faculty_status = 'APPROVED' THEN 1 END)        AS waiting_for_chair,
        ROUND(AVG(CASE WHEN r.reviewed_by = c.chair_id
                       THEN TIMESTAMPDIFF(MINUTE, r.requested_at, r.reviewed_at) END) / 60, 1)    AS avg_hours_to_decide
FROM chairpersons c
JOIN departments d           ON d.dept_id = c.dept_id
JOIN students s              ON s.dept_id = c.dept_id
LEFT JOIN booking_requests r ON r.srn = s.srn
                             AND (@month IS NULL OR DATE_FORMAT(r.booking_date, '%Y-%m') = @month)
GROUP BY c.chair_id, c.name, d.dept_code
ORDER BY c.chair_id;


-- #R13. Event heads: how fast each faculty member answers
-- For each faculty member named as event head: requests received, approved,
-- rejected, still waiting, and the average hours they took to answer.
-- chart: event_head, requests_received
SELECT  f.name AS event_head,
        d.dept_code,
        COUNT(r.request_id)                                         AS requests_received,
        COUNT(CASE WHEN r.faculty_status = 'APPROVED' THEN 1 END)   AS approved,
        COUNT(CASE WHEN r.faculty_status = 'REJECTED' THEN 1 END)   AS rejected,
        COUNT(CASE WHEN r.status = 'PENDING'
                    AND r.faculty_status = 'PENDING' THEN 1 END)    AS waiting_now,
        ROUND(AVG(TIMESTAMPDIFF(MINUTE, r.requested_at, r.faculty_decided_at)) / 60, 1) AS avg_hours_to_answer
FROM faculty f
JOIN departments d ON d.dept_id = f.dept_id
LEFT JOIN booking_requests r ON r.faculty_id = f.faculty_id AND r.faculty_status IS NOT NULL
                             AND (@month IS NULL OR DATE_FORMAT(r.booking_date, '%Y-%m') = @month)
GROUP BY f.faculty_id, f.name, d.dept_code
ORDER BY requests_received DESC, f.name;
