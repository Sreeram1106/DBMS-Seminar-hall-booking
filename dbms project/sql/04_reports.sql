-- =====================================================================
--  Seminar Hall Booking System - 04_reports.sql
--  Every report shown in the app's Reports page. They can also be run
--  directly in MySQL Workbench.
--
--  Format used by the app:  "-- #" starts a report (its title),
--  other "--" lines describe it, "-- chart: x, y" picks the bar chart axes.
-- =====================================================================

USE seminar_booking;


-- #R1. Hall-wise bookings and average attendance
-- Same idea as "average salary of every department": the average number of
-- attendees for every hall, and how full the hall is on average.
-- chart: hall_name, total_bookings
SELECT  h.hall_name,
        h.capacity,
        COUNT(a.allocation_id)                                  AS total_bookings,
        ROUND(AVG(r.expected_attendees), 1)                     AS avg_attendees,
        ROUND(AVG(r.expected_attendees) * 100 / h.capacity, 1)  AS avg_occupancy_pct
FROM seminar_halls h
LEFT JOIN allocations a      ON a.hall_id = h.hall_id
LEFT JOIN booking_requests r ON r.request_id = a.request_id
GROUP BY h.hall_id, h.hall_name, h.capacity
ORDER BY total_bookings DESC;


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
GROUP BY s.srn, s.name, d.dept_code
ORDER BY halls_booked DESC, s.name
LIMIT 5;


-- #R7. Events coordinated by each faculty member
-- Allocated events per faculty coordinator (faculty with zero still appear).
-- chart: coordinator, events_coordinated
SELECT  f.name      AS coordinator,
        d.dept_code,
        COUNT(r.request_id) AS events_coordinated
FROM faculty f
JOIN departments d ON d.dept_id = f.dept_id
LEFT JOIN booking_requests r ON r.faculty_id = f.faculty_id AND r.status = 'ALLOCATED'
GROUP BY f.faculty_id, f.name, d.dept_code
ORDER BY events_coordinated DESC, f.name;


-- #R8. Why requests were rejected
-- Count of rejected requests for each reason.
-- chart: reason, times
SELECT  remarks  AS reason,
        COUNT(*) AS times
FROM booking_requests
WHERE status = 'REJECTED'
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
GROUP BY h.hall_id, h.hall_name
HAVING COUNT(*) > (SELECT AVG(cnt)
                   FROM (SELECT COUNT(*) AS cnt
                         FROM allocations
                         GROUP BY hall_id) AS per_hall)
ORDER BY bookings DESC;


-- #R10. Busiest days of the week
-- Confirmed bookings for each weekday.
-- chart: day_of_week, bookings
SELECT  DAYNAME(booking_date) AS day_of_week,
        COUNT(*)              AS bookings
FROM allocations
GROUP BY DAYNAME(booking_date), WEEKDAY(booking_date)
ORDER BY WEEKDAY(booking_date);


-- #R11. Freed slots: were they booked again?
-- Our novelty: every cancelled or coordinator-rejected booking is published in
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
        COUNT(CASE WHEN f.reason LIKE 'Rejected by the hall coordinator%' THEN 1 END) AS by_coordinator
FROM freed_slots f
JOIN booking_requests r ON r.request_id = f.request_id
JOIN seminar_halls h    ON h.hall_id    = r.hall_id
GROUP BY h.hall_id, h.hall_name
ORDER BY slots_freed DESC;


-- #R12. Hall coordinator workload and average approval time
-- For each seminar hall coordinator: requests approved, rejected and still
-- waiting, and the average number of hours a student waited for a decision.
-- chart: coordinator, avg_hours_to_decide
SELECT  c.name AS coordinator,
        COUNT(CASE WHEN r.reviewed_by = c.coordinator_id
                    AND r.remarks NOT LIKE 'Rejected by the hall coordinator%' THEN 1 END) AS approved,
        COUNT(CASE WHEN r.reviewed_by = c.coordinator_id
                    AND r.remarks LIKE 'Rejected by the hall coordinator%' THEN 1 END) AS rejected,
        COUNT(CASE WHEN r.status = 'PENDING' THEN 1 END)                    AS waiting_now,
        ROUND(AVG(CASE WHEN r.reviewed_by = c.coordinator_id
                       THEN TIMESTAMPDIFF(MINUTE, r.requested_at, r.reviewed_at) END) / 60, 1)
                                                                            AS avg_hours_to_decide
FROM hall_coordinators c
JOIN seminar_halls h          ON h.coordinator_id = c.coordinator_id
LEFT JOIN booking_requests r  ON r.hall_id = h.hall_id
GROUP BY c.coordinator_id, c.name
ORDER BY c.coordinator_id;
