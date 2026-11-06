# Viva Notes: University Seminar Hall Booking System

## 1. The project in one line

Students request a seminar hall for a date and a time slot and name the **faculty
member who heads the event**. The database checks the request and, if the hall is
free, **holds it** for the student. The **event head (faculty)** approves it first,
then the **chairperson of the student's department** gives the final approval.
When a booking is cancelled or rejected, the freed slot is **published to
everyone**, so the hall does not sit empty. Slots follow our college's timings:
9 AM to 4 PM, at most 2 hours, with a 30 minute gap.

**Problem it solves (from our own college):** halls are booked through the college
website. A request needs the faculty in charge of the event and then the
chairperson to approve it. When someone cancels, nobody else finds out, so the hall
stays empty even though other students wanted it. Here the database makes double
booking impossible, records both approvals, and makes every freed slot visible.

**Three logins (for now the password is the same as the ID):**

| Role | IDs | Sees (menu at the top) |
|---|---|---|
| Student | PES1UG24AM001 - PES1UG24AM100 (AIML), PES1UG24CS001 - PES1UG24CS100 (CSE) | Book a hall, My bookings, Availability, Halls |
| Faculty (event head) | PES1UG24FAC001 - PES1UG24FAC012 | Event requests (approve / reject), Availability, Halls |
| Chairperson (one per department) | PES1UG24CHR001 - PES1UG24CHR006 | Dashboard, Approvals, All bookings, Availability, Halls, Reports, NoSQL, Manage |

Who belongs together (a student can only name faculty of their own department, and only
that department's chairperson can approve):

| Department | Students | Faculty (event heads) | Chairperson |
|---|---|---|---|
| AIML | PES1UG24AM001 - AM100 | FAC003 Dr. Kavitha Rao, FAC004 Prof. Arjun Menon | CHR002 Dr. Meera Krishnan |
| CSE | PES1UG24CS001 - CS100 | FAC001 Dr. Shalini Murthy, FAC002 Prof. Naveen Shetty | CHR001 Dr. Rajesh Iyer |

**RDBMS + NoSQL:** the structured core (departments, chairpersons, students,
faculty, halls, slots, requests, allocations, freed slots) is in **MySQL tables**
and uses SQL. The flexible, varying data (extra event details and activity logs)
is in the **MySQL Document Store** as JSON documents and uses the X DevAPI, not
SQL. See section 12.

## 2. How one booking works (the flow)

1. The student fills the form: hall, date, slot, event, attendees and the **event head**. The page
   shows the student's department, and only faculty of **that department** are offered as event head.
2. The app calls the stored procedure `request_booking(...)`.
3. The procedure saves the request in `booking_requests` with status `PENDING`.
4. It checks the rules in this order:
   - Is the date in the past? → REJECTED
   - Is it today and the slot has already started? → REJECTED
   - Is the event head from a different department than the student? → REJECTED
   - Is the hall under maintenance (`is_active = FALSE`)? → REJECTED
   - Are there more attendees than the hall's capacity? → REJECTED
   - Is there already a row in `allocations` for this hall + date + slot? → REJECTED
   - Otherwise it inserts a row into `allocations` (the hall is **held**), the request
     stays **PENDING** and `faculty_status` becomes **PENDING** (waiting for the event head).
5. It writes the status and reason back on the request, then COMMITs.
6. The **event head** logs in (Event requests page) and calls `faculty_review(...)`:
   - approve → `faculty_status = APPROVED`, the request now **waits for the chairperson**;
   - reject (with a reason) → the request is **REJECTED** and stops there.
7. The **chairperson of the student's department** logs in (Approvals page). Each request
   shows the student, the event head and whether the event head approved. The
   chairperson calls `review_booking(...)`: approve → **ALLOCATED** (booked); reject
   (with a reason) → **REJECTED**. The chairperson may also decide before the event head answers.
8. If a request is rejected (by the event head or the chairperson) or cancelled, the
   **trigger** deletes the allocation row and writes a row into `freed_slots`. The app
   shows freed slots to everyone, and tells students who were refused that exact slot
   earlier that it is free again.

Status words the app shows (column `stage` of the view): **Waiting for event head →
Waiting for chairperson → Booked**, or **Rejected / Cancelled**.

## 3. Tables (9)

| # | Table | Primary key | Foreign keys | Purpose |
|---|---|---|---|---|
| 1 | `departments` | `dept_id` | none | AIML, CSE, ECE, EEE, ME, BT |
| 2 | `chairpersons` | `chair_id` | `dept_id` → departments (UNIQUE) | **New.** One chairperson per department; gives the final approval |
| 3 | `students` | `srn` | `dept_id` → departments | Students who raise requests |
| 4 | `faculty` | `faculty_id` | `dept_id` → departments | Faculty who can be named as event head |
| 5 | `seminar_halls` | `hall_id` | none | Halls with capacity, block, AC, projector, active flag |
| 6 | `time_slots` | `slot_id` | none | 3 slots: 9:00–11:00, 11:30–13:30, 14:00–16:00 (college rules enforced) |
| 7 | `booking_requests` | `request_id` | `srn`, `hall_id`, `slot_id`, `faculty_id` (event head), `reviewed_by` (chairperson) | **Every** request ever made, with the event head's answer (`faculty_status`, `faculty_remarks`, `faculty_decided_at`), the final status, reason, and who approved it |
| 8 | `allocations` | `allocation_id` | `request_id`, `hall_id`, `slot_id` | The hall schedule: booked halls and PENDING holds |
| 9 | `freed_slots` | `release_id` | `request_id` | **New.** Every booked slot that became free again (filled by the trigger) |

Plus two **views**: `v_booking_details` joins requests with student, department,
hall, slot, event head and chairperson names, and adds a `stage` column (Waiting for
event head / Waiting for chairperson / Booked / Rejected / Cancelled).
`v_open_freed_slots` lists the freed slots that are still free and in the future.

### Why are `booking_requests` and `allocations` separate tables?

- `booking_requests` is the history of all requests, including rejected and cancelled ones. The reports need this history.
- `allocations` holds the hall schedule (booked halls and PENDING holds). It has the key rule of the project:
  **`UNIQUE (hall_id, booking_date, slot_id)`**. Because of this constraint, the
  database can never store two bookings of the same hall in the same slot, even
  if the application code has a bug or two students click "Book" at the same moment.
- `hall_id`, `slot_id` and `booking_date` are copied into `allocations` on
  purpose (controlled redundancy). MySQL cannot put a UNIQUE constraint across two tables.

### Why is the chairperson a table and not just a column in departments?

The chairperson logs in, approves requests and is recorded on each request
(`reviewed_by`). That needs its own key and foreign keys. `dept_id` in
`chairpersons` is UNIQUE, so the 1 : 1 rule "one chairperson per department" is
enforced by the database.

## 4. Relationships (from the ER diagram)

| Relationship | Between | Cardinality | Participation |
|---|---|---|---|
| BELONGS_TO | Student – Department | N : 1 | every student has a department (total) |
| WORKS_IN | Faculty – Department | N : 1 | every faculty member has a department (total) |
| HEADS | Chairperson – Department | 1 : 1 | every chairperson heads one department (total) |
| RAISES | Student – Booking request | 1 : N | every request has a student (total on request side) |
| EVENT_HEAD | Faculty – Booking request | 1 : N | every request names an event head (total on request side). Relationship attributes: `faculty_status`, `faculty_remarks`, `faculty_decided_at` |
| REVIEWS | Chairperson – Booking request | 1 : N | partial: a request has no reviewer until the chairperson decides. Relationship attribute: `reviewed_at` |
| FOR_HALL | Booking request – Seminar hall | N : 1 | every request is for one hall |
| IN_SLOT | Booking request – Time slot | N : 1 | every request is for one slot |
| RESULTS_IN | Booking request – Allocation | 1 : 1 | a request may or may not get an allocation (partial); every allocation comes from a request (total) |
| RESERVES | Allocation – Seminar hall | N : 1 | |
| DURING | Allocation – Time slot | N : 1 | |
| FREES | Booking request – Freed slot | 1 : 1 | a request may free a slot (partial); every freed slot comes from a request (total) |

Double lines in the ER diagram mean total participation, single lines mean partial
participation. Ovals attached to a diamond are attributes of that relationship.

## 5. Constraints used

| Constraint | Where | Why |
|---|---|---|
| PRIMARY KEY | every table | unique row identity |
| FOREIGN KEY | chairpersons, students, faculty, booking_requests, allocations, freed_slots | no request for a student/hall/slot/faculty/chairperson that doesn't exist |
| UNIQUE | `dept_code`, `email`, `hall_name`, `slot_label`, `chairpersons.dept_id`, `allocations.request_id`, `(hall_id, booking_date, slot_id)` | no duplicates; one chairperson per department; **no double booking** |
| CHECK | `semester BETWEEN 1 AND 8`, `capacity > 0`, `expected_attendees > 0`, `end_time > start_time` | reject invalid values |
| CHECK (college rules) | `start_time >= '09:00' AND end_time <= '16:00'`, `TIMEDIFF(end_time, start_time) <= '02:00:00'` | halls only 9 AM–4 PM, at most 2 hours |
| TRIGGER (college rule) | `trg_slot_gap_insert` / `trg_slot_gap_update` on `time_slots` | 30 minute gap between slots (a CHECK can't compare two rows) |
| NOT NULL / DEFAULT | most columns; `status DEFAULT 'PENDING'`, `requested_at DEFAULT CURRENT_TIMESTAMP`, `has_projector DEFAULT TRUE` | required data, sensible defaults |
| ENUM | `event_type`, `status`, `faculty_status` | only allowed values |
| ON DELETE CASCADE | `allocations.request_id`, `freed_slots.request_id` | deleting a request deletes its allocation and freed-slot row |

## 6. Normalization

- **1NF:** every column holds one atomic value, and there are no repeating groups (one request = one slot).
- **2NF:** every primary key is a single column, so partial dependency is impossible.
- **3NF / BCNF:** every non-key column depends only on the key of its own table.
  For example, the department name is not stored in `students` (only `dept_id`), the
  chairperson's name is not stored in `departments` (it is in `chairpersons`), and the
  hall capacity is not stored in `booking_requests` (only `hall_id`).
- In `allocations`, `request_id` and `(hall_id, booking_date, slot_id)` are both
  candidate keys, so every determinant is a candidate key and the table is in BCNF.
  The repeated hall/date/slot values are redundancy across tables, chosen on purpose
  for the UNIQUE constraint (see section 3).

## 7. Stored procedure `request_booking`

```sql
CALL request_booking('PES1UG24AM001', 4, 3, '2026-11-27',
                     'Viva Demo', 'Seminar', 50, 4,
                     @id, @status, @msg);
SELECT @id, @status, @msg;   -- 203 | PENDING | Hall held for you, waiting for the event head (faculty) to approve
```

- **8 IN parameters** (the form fields, the last one is the event head's `faculty_id`) and
  **3 OUT parameters**: request id, status and message.
- The whole procedure runs inside **`START TRANSACTION … COMMIT`**, so it is atomic:
  either the request and its allocation are both saved, or nothing is saved.
- `DECLARE EXIT HANDLER FOR SQLEXCEPTION … ROLLBACK; RESIGNAL;` handles bad input,
  such as an SRN that doesn't exist (a foreign key error). The transaction is undone and the error goes back to the app.
- If every rule passes, the request is **PENDING**, `faculty_status` is **PENDING** and the
  hall is held (a row in `allocations`), so nobody else can take it while the approvals happen.
- `DECLARE CONTINUE HANDLER FOR 1062` handles the race case. If two students book
  the same slot at the same instant, both may pass the "is it free?" check. Only
  one INSERT can succeed because of the UNIQUE key. The other gets error 1062
  (duplicate key), and the handler turns that into a clean "already booked" rejection.

## 8. Procedures `faculty_review` and `review_booking`, and the triggers

```sql
CALL faculty_review(203, 4, TRUE, NULL, @status, @msg);                        -- event head (faculty 4) approves
CALL faculty_review(190, 3, FALSE, 'I am not handling this event', @status, @msg); -- event head (faculty 3) rejects
CALL review_booking(203, 2, TRUE, NULL, @status, @msg);                        -- AIML chairperson (2) approves
CALL review_booking(192, 2, FALSE, 'Hall needed for placement drive', @status, @msg); -- AIML chairperson rejects
SELECT @status, @msg;
```

**`faculty_review`** (the event head) locks the request row (`SELECT … FOR UPDATE`),
checks that **this faculty member is the event head named on the request** and that
they have not answered yet. Approve → `faculty_status = APPROVED` (now waiting for the
chairperson). Reject → `faculty_status = REJECTED` **and** `status = REJECTED`, so the
request stops there.

**`review_booking`** (the chairperson) locks the row, checks it is still PENDING and
that **this chairperson heads the student's department** (`chairpersons.dept_id =
students.dept_id`), then sets ALLOCATED or REJECTED, `reviewed_by` and `reviewed_at`.

**Trigger `trg_free_hall_on_cancel`** (AFTER UPDATE on `booking_requests`):

```sql
IF OLD.status IN ('PENDING','ALLOCATED') AND NEW.status IN ('CANCELLED','REJECTED') THEN
    DELETE FROM allocations WHERE request_id = NEW.request_id;
    IF ROW_COUNT() > 0 THEN
        INSERT INTO freed_slots (request_id, reason) VALUES (NEW.request_id, NEW.remarks);
    END IF;
END IF;
```

It fires for every way a held hall can be released: the event head rejects, the
chairperson rejects, the student cancels, or the chairperson cancels. The trigger
frees the hall **and publishes the freed slot**, so no application code can forget
either step. `ROW_COUNT() > 0` means a slot is published only if a hall was really held.

**Triggers `trg_slot_gap_insert` / `trg_slot_gap_update`** (BEFORE INSERT/UPDATE on
`time_slots`) raise `SIGNAL SQLSTATE '45000'` if a new slot starts less than 30
minutes after another ends (or overlaps it).

**Procedure vs trigger:** a procedure is called explicitly (`CALL`). A trigger
runs automatically when an INSERT, UPDATE or DELETE happens on its table.

## 9. Reports (`sql/04_reports.sql`) and the SQL concept each one shows

| Report | Shows |
|---|---|
| R1 Average attendance of every hall | `AVG`, `COUNT`, `GROUP BY`. **This is the "average salary per department" example.** Shows the 6 active halls, counting booked events only; use the month filter for one month |
| R2 Department-wise requests and success rate | `COUNT(CASE WHEN …)`, percentage, `NULLIF` to avoid divide-by-zero, joins across 3 tables |
| R3 Demand for each time slot | grouping on a lookup table, conditional count |
| R4 Month-wise trend | `DATE_FORMAT`, grouping by a computed column |
| R5 Event type analysis | `AVG`, `MAX`, `WHERE` before `GROUP BY` |
| R6 Top 5 students | `ORDER BY … DESC` with `LIMIT` |
| R7 Events headed by each faculty member | `LEFT JOIN` with the condition in `ON` (faculty with 0 events still listed) |
| R8 Rejection reasons | grouping on a text column |
| R9 Halls busier than average | **nested subquery** inside `HAVING` |
| R10 Busiest weekdays | `DAYNAME`, `WEEKDAY` for correct ordering |
| R11 Freed slots: were they booked again? | **Novelty report.** correlated `EXISTS` subquery inside `COUNT(CASE …)`, `LIKE` |
| R12 Chairperson decisions and average approval time | `AVG(TIMESTAMPDIFF(…))` = average hours a student waited for the final decision, per department chairperson |
| R13 Event heads: how fast each faculty member answers | approvals, rejections and average hours to answer per event head (`AVG`, `TIMESTAMPDIFF`, conditional counts) |

**Month filter:** the Reports page has a Month filter at the top, for all 13 reports. **All** is
selected first and shows all months; click August and every report shows only August. Each query reads the
variable `@month`: `WHERE (@month IS NULL OR DATE_FORMAT(booking_date, '%Y-%m') = @month)`. In
Workbench the same thing is `SET @month = '2026-08';`, and `SET @month = NULL;` goes back to all.

## 10. Demo script (about 8 minutes)

Run `python setup_db.py` first, then `streamlit run app.py`. The dates below use
**27 Nov 2026**. If the demo is on or after 27 Nov, open Availability, pick any
upcoming date with a red (booked) cell and use that hall, date and slot instead.

**Setup for the live part:** laptop 1 with two tabs (student + faculty), laptop 2 with the
chairperson. Follow `docs/two_laptop_demo.md`. Every screen refreshes itself every 5
seconds and pops up new requests and decisions.

1. **ER diagram:** open `docs/er_diagram.html`. Explain the 9 entities. The two **green**
   ones (CHAIRPERSON, FREED_SLOT) come from how our own college works. Point at the spine
   DEPARTMENT – HEADS – CHAIRPERSON – REVIEWS – BOOKING_REQUEST and at EVENT_HEAD with its
   relationship attributes (faculty_status, faculty_remarks, faculty_decided_at).
2. **Login page:** only the login page is visible. Show that **PES1UG24AM101** or a wrong
   password gives "Invalid ID or password".
3. **Student (tab 1, PES1UG24AM001):** only 4 pages in the menu at the top.
   - **Halls:** "Seats needed" 100 and "AC only". Each card shows seats, AC and the
     free slots on the chosen date (every hall has a projector).
   - **Availability:** today's started slots show **TIME OVER**; on **27 Nov** Seminar Hall 1
     and the Mini Auditorium are booked 14:00-16:00 and Seminar Hall 1 at 11:30-13:30 shows
     **FREED - book now**.
   - **Book a hall** works in 5 steps: date → time buttons → AC / non-AC → hall cards → event details.
     On **27 Nov, 14:00-16:00** (if it is not in the date strip: **Other date** → click the date box → click 27 in the calendar), Seminar Hall 1 shows **Booked** (its card cannot be selected), so a
     clash is impossible from the website; the database rule is shown in Workbench (section 7).
   - **Book a hall (held):** same date and slot, **AIML Seminar Hall** (Select), event "Viva Demo",
     event head **Prof. Arjun Menon** → **hall HELD, waiting for the event head**. Open "SQL that was
     executed". The event details and a log entry are saved to NoSQL in the background (no JSON on
     screen). **One action, two databases.**
   - **My bookings:** the step tracker shows Requested ✓ → Event head (current) → Chairperson.
4. **Faculty (tab 2, PES1UG24FAC004 = Prof. Arjun Menon, AIML):** within 5 seconds a pop-up says
   "New event request #…: Viva Demo by Suhas Hegde". **Approve - I am the event head.**
5. **Chairperson (laptop 2, PES1UG24CHR002 = Dr. Meera Krishnan, AIML):** a pop-up says
   "Prof. Arjun Menon approved #… Ready for your approval." On **Approvals** the request shows
   the student, the event head and a green "has approved this event". **Approve - book the hall.**
6. **Student (tab 1):** a pop-up says "#… (Viva Demo) is BOOKED", and all three steps turn green.
7. **Chairperson extras:**
   - **Dashboard:** totals, "waiting for you" alert, freed-slots board, today's schedule.
   - **All bookings:** filter by department, date, hall, status; search; **Download as CSV**;
     cancel a booking from your department with a reason (the trigger frees and publishes the slot).
   - **Manage → Time slots:** 15:00-17:00 → CHECK `chk_slot_hours`; 09:00-12:00 → CHECK
     `chk_slot_max_2h`; 11:00-11:20 → gap trigger. **The college rules live in the database.**
   - **Reports:** R1 (the professor's example; show All, then click August), R11 (freed slots), R12 (chairperson approval
     time), R13 (event heads), R9 (nested query); each has a CSV download.
   - **NoSQL:** Event details as a plain table (different details per event type, empty cell = not
     present), filter by tag, add a tag (modify); Activity log filtered by action; N1-N3 reports.
     The JSON itself is only shown in MySQL Shell, not on the website.
8. **Event head rejects (optional):** student books another free slot naming a faculty; that
   faculty clicks **Reject** with a reason → the request stops, the hall is freed and appears on
   the freed-slots board.
9. Optional, in MySQL Workbench: `sql/05_demo_queries.sql`, one query at a time.

## 11. Likely viva questions

**Q: What is new (novel) in your project?**
It comes from how our own college works. (1) **Two-step approval**: the student names the
faculty heading the event; that **event head** confirms it (`faculty_review`), then the
**chairperson of the student's department** gives the final approval (`review_booking`).
The chairperson sees the student, the event head and the event head's answer on one
screen. (2) When a booking is cancelled or rejected, a trigger **publishes the freed slot**
in `freed_slots`; everyone sees it, and students who were refused that slot are told it
is free. (3) Our college's timings (9 AM–4 PM, 2 hours max, 30 minute gap) are enforced
**by the database** (CHECK constraints plus a trigger), not just by the form.

**Q: Why two approvals?**
The event head is the faculty actually responsible for the event, so their approval
confirms the event is real. The chairperson then decides for the department, and can see
at a glance who requested it, who is heading it and that the event head agreed.

**Q: What if the event head rejects?**
`faculty_review` sets the request to REJECTED immediately; it never reaches the
chairperson. The trigger frees the hall and publishes the slot.

**Q: Can the chairperson approve before the event head answers?**
Yes. The chairperson has the final say; the screen shows "event head has not answered yet"
as a warning. Once decided, the event head can no longer answer ("already decided").

**Q: Can a student choose a faculty member from another department as event head?**
No. The booking page only lists faculty of the student's department, and `request_booking`
also compares `faculty.dept_id` with `students.dept_id` and rejects a mismatch ("The event head
must be a faculty member of your own department"), so the rule holds even from Workbench.

**Q: How does the app know which chairperson can decide a request?**
`review_booking` compares `chairpersons.dept_id` with the student's `dept_id`. A
chairperson of another department gets "Only the chairperson of the student's
department can decide".

**Q: Why not just delete the allocation on cancel? Why a freed_slots table?**
Deleting frees the hall but nobody knows. `freed_slots` keeps a record of every freed
slot, so it can be shown to everyone, matched against students who were refused,
and measured (R11: how many freed slots were booked again).

**Q: Why does a PENDING request already have a row in allocations?**
So the hall is held while the event head and chairperson decide. Otherwise two students
could both wait for approval for the same slot. The UNIQUE key still guarantees one booking per slot.

**Q: Why a trigger for the 30 minute gap and not a CHECK?**
A CHECK constraint can only look at the values in the same row. The gap compares the
new slot with the other rows in `time_slots`, so it needs a trigger.

**Q: How does the login work? Who can see what?**
Until someone logs in, the app shows only the login page (no menu, no other pages).
The ID pattern and number range decide the role: students PES1UG24AM001–100 (AIML) and
PES1UG24CS001–100 (CSE) (the SRN must exist in `students`), faculty PES1UG24FAC001–012 (the number is the `faculty_id`) and
chairpersons PES1UG24CHR001–006 (the number is the `chair_id`). Each is looked up with a
parameterised SELECT. For now the password is the ID itself. The ID and role are kept in
Streamlit's `st.session_state`, so each person only sees their own pages and acts in their
own name. In a real system we would store users with a `password_hash` (for example bcrypt).

**Q: What if a student opens the booking page at 12:00 for today?**
`open_slots` only offers slots whose start time is still in the future
(`start_time > CURTIME()` for today), the date picker starts at today, and the grid shows
already-started free slots as TIME OVER. The procedure `request_booking` also rejects them
("This time slot has already started today"), so the rule holds even outside the app.

**Q: What happens if two students book the same hall and slot at the same time?**
Only one INSERT into `allocations` can succeed because of `UNIQUE (hall_id, booking_date, slot_id)`.
The second gets error 1062, and the procedure's handler turns it into a rejection.

**Q: Why SRN as the primary key of students instead of an auto-increment id?**
The SRN is already unique for every student and never changes, so it is a good natural key.

**Q: Why a separate `time_slots` table instead of storing start and end times in each request?**
Fixed slots make the clash check a simple equality on `slot_id`, and slot timings can be changed in one place.

**Q: What is a view and why did you use one?**
A view is a saved SELECT that behaves like a table. `v_booking_details` hides a 7-table join
and works out the `stage` words, so every page and report queries it simply.

**Q: Difference between WHERE and HAVING?**
WHERE filters rows before grouping. HAVING filters groups after `GROUP BY`. R9 uses HAVING with a subquery.

**Q: Difference between INNER JOIN and LEFT JOIN? Where did you need LEFT JOIN?**
LEFT JOIN keeps rows from the left table even with no match. In R7 a faculty member with no
booked events would still be listed because of the LEFT JOIN; in the view, `reviewed_by` uses a
LEFT JOIN because most requests have no chairperson decision yet.

**Q: COUNT(*) vs COUNT(column)?**
COUNT(*) counts rows. COUNT(column) skips NULLs. In R2, `COUNT(r.request_id)` gives 0 for a department with no requests, where COUNT(*) would wrongly give 1.

**Q: Where is a transaction used, and what are the ACID properties here?**
In all three procedures. *Atomicity:* the request and allocation are saved together or not at all.
*Consistency:* the constraints always hold. *Isolation:* concurrent bookings can't double-book
(UNIQUE key) and `SELECT … FOR UPDATE` stops two clicks deciding the same request twice.
*Durability:* InnoDB keeps committed bookings after a crash.

**Q: How do you prevent SQL injection?**
Every query that takes user input uses parameter placeholders (`%s`), so the input is never pasted into the SQL text.
The one query built with a table name (Manage → View tables) only accepts names from a fixed list.

**Q: Why does the app use `seminar_app` instead of root?**
Principle of least privilege: the app user only has rights on the `seminar_booking` database.

**Q: What is `log_bin_trust_function_creators` in the setup script?**
Binary logging is on in this MySQL server. In that mode only SUPER users can create
triggers unless this flag is set. It lets the app user create the trigger.

**Q: Is any entity weak?**
No. Every entity has its own key. ALLOCATION and FREED_SLOT depend on BOOKING_REQUEST
for their existence (total participation), but each is identified by its own id.

**Q: What does ON DELETE CASCADE do here?**
If a booking request row is deleted, its allocation and freed-slot rows are deleted automatically.

## 12. NoSQL part: MySQL Document Store

### What it is

MySQL 8 can also work as a **NoSQL document database**. Data is stored as
**JSON documents** inside **collections**, not as rows in tables with fixed
columns. You work with it through the **X DevAPI** (`add`, `find`, `modify`,
`remove`) over the **X Protocol on port 33060**, not through SQL. It is the same
model as MongoDB: a collection is like a MongoDB collection, a document is like a
MongoDB document, and every document gets an automatic `_id`.

### The two collections and why they are NoSQL

| Collection | What is stored | Why a document store fits |
|---|---|---|
| `event_details` | Extra details for each booking request: speaker, tools, club, prizes, tags, notes | **Every event type has different fields.** A guest lecture has a speaker object, a workshop has a tools array, a hackathon has a prizes array. In SQL this would need many mostly-NULL columns or a separate table per event type. A document simply has the fields it needs. |
| `booking_logs` | One entry per action: REQUEST (with the result and suggested alternatives), FACULTY_REVIEW (event head's answer), CHAIR_REVIEW (chairperson's decision), CANCEL | Logs are **append-only, high-volume, and vary in shape** (each action stores different fields). There are no joins and no updates, which is a classic document-store job. |

Example documents (notice the different fields):

```json
{"request_id": 5, "event_type": "Hackathon",
 "teams_expected": 25, "prizes": [{"position": 1, "amount": 10000}, {"position": 2, "amount": 5000}],
 "tags": ["beginner-friendly", "competition"]}

{"action": "FACULTY_REVIEW", "faculty_id": 4, "request_id": 203, "decision": "APPROVED",
 "logged_at": "2026-11-02T19:08:41"}

{"action": "CHAIR_REVIEW", "chair_id": 2, "request_id": 203, "decision": "APPROVED",
 "logged_at": "2026-11-02T19:09:20"}
```

### How SQL and NoSQL are linked

Each document stores the `request_id` of its MySQL request. The app saves the
SQL row first (through the procedure), then the document. The **My bookings** page
reads the SQL history and shows the matching document's details in plain words. NoSQL has **no
foreign keys**, so the application keeps the link correct. That is the usual
trade-off: flexibility instead of enforced integrity.

### CRUD in the code (`nosql.py`)

| Operation | X DevAPI call | Used for |
|---|---|---|
| **Create** | `collection.add(doc)` | saving event details and log entries on every booking, approval and cancel |
| **Read** | `collection.find("event_type = :type AND :tag IN tags").bind(...)` | search page, My bookings |
| **Update** | `collection.modify("request_id = :rid").array_append("tags", tag)` | "Add a tag" on the NoSQL page |
| **Delete** | `collection.remove("_id = :id").bind("id", ...)` | "Delete document" on the NoSQL page |
| **Aggregate** | `find().fields("event_type", "COUNT(_id) AS documents").group_by("event_type")` | NoSQL reports N1 and N2 |
| **Index** | `create_index("idx_request_id", {"fields": [{"field": "$.request_id", "type": "INT"}]})` | fast lookup by request |

`:type`, `:tag` and `:rid` are **bound parameters**, the NoSQL version of `%s`
in SQL. They also protect against injection.

### Live demo in MySQL Shell (optional)

Open a terminal and run the command below, then type the `seminar_app` password from `config.py`:

```bash
"C:\Program Files\MySQL\MySQL Shell 8.0\bin\mysqlsh.exe" --uri seminar_app@localhost:33060/seminar_booking --js
```

Then type these one at a time. In the shell, statements run as soon as you press Enter:

```js
db.getCollections()
db.event_details.count()
db.event_details.find("event_type = 'Workshop'").fields("request_id", "tools").limit(3)
db.booking_logs.find("action = 'FACULTY_REVIEW'").limit(3)
db.event_details.find().fields("event_type", "COUNT(_id) AS n").groupBy("event_type")
db.event_details.modify("request_id = 5").arrayAppend("tags", "viva")
db.event_details.find("request_id = 5")
db.booking_logs.add({action: "TEST", note: "added in viva"})
db.booking_logs.remove("action = 'TEST'")
```

In the shell `.bind()` must come **last** (after `fields`, `sort` and `limit`).
Use `COUNT(_id)`, not `COUNT(*)`. Method names are camelCase in the shell
(`arrayAppend`, `groupBy`) and snake_case in Python (`array_append`, `group_by`).

### Likely NoSQL viva questions

**Q: Is this really NoSQL if it's MySQL?**
Yes. The Document Store is MySQL's official NoSQL interface: schemaless JSON
documents, collections, and a CRUD API over the X Protocol (port 33060) with no SQL
written. MongoDB is another document database built on the same idea.

**Q: SQL vs NoSQL, and why use both?**
SQL suits fixed-structure data that needs relationships, constraints and
transactions, such as bookings and approvals, where double booking must be impossible.
NoSQL suits data whose shape varies or grows quickly, such as event details and logs.
Using each for what it does best is called *polyglot persistence*.

**Q: What does "schemaless" mean here?**
The collection doesn't define columns. Each document can have different fields.
For example, a hackathon document has `prizes` and a lecture has `speaker`, and
both sit in the same collection.

**Q: What is `_id`?**
A unique key that MySQL generates automatically for every document, like the primary key of a row.

**Q: Why not just add a JSON column to the `booking_requests` table?**
That would still be SQL and the relational model. The point of the document store
is to treat the data as independent documents, with their own API, collection and
indexes, without changing the relational schema whenever event details change.

**Q: Which is stronger for consistency?**
The relational side. It has foreign keys, UNIQUE constraints and transactions. The
document store gives flexibility, and the application keeps the `request_id` links valid.

## 13. Novelty (from our college)

| What our college does | What we built | Where |
|---|---|---|
| Halls are booked on the college website | Booking form and live availability grid | Book a hall, Availability |
| The **faculty heading the event** must agree | The student names an event head; only that faculty member can approve or reject it; a rejection stops the request | `faculty_review`, `faculty_status` columns, Event requests page, R13 |
| The **chairperson** gives the final approval | One chairperson per department; sees student + event head + event head's answer; only the chairperson of the student's department can decide | `chairpersons`, `review_booking`, Approvals page, R12 |
| **Cancelled slots are not visible to others** (the problem) | Trigger publishes every freed slot; board for everyone; alert to students who were refused that slot | `freed_slots`, `trg_free_hall_on_cancel`, `v_open_freed_slots`, Dashboard, My bookings, R11 |
| Any department can book a free hall | No hall is tied to a department (only free, active, big enough) | `request_booking` |
| Halls 9 AM–4 PM, 2 hours max, 30 min gap | 3 slots; CHECK constraints + gap trigger | `time_slots`, `trg_slot_gap_insert`, Manage → Time slots |
