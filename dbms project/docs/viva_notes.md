# Viva Notes: University Seminar Hall Booking System

## 1. The project in one line

Students request a seminar hall for a date and a time slot. The database
checks the request and, if the hall is free, **holds it** for the student. The
**seminar hall coordinator** then approves or rejects it. When a booking is
cancelled (or rejected), the freed slot is **published to everyone**, so the
hall does not sit empty. Slots follow our college's timings: 9 AM to 4 PM,
at most 2 hours, with a 30 minute gap.

**Problem it solves (from our own college):** halls are booked through the
college website and approved by the seminar hall coordinator. When someone
cancels, nobody else finds out, so the hall stays empty even though other
students wanted it. Here the database makes double booking impossible and makes
every freed slot visible.

**RDBMS + NoSQL:** the structured core (students, halls, slots, requests,
allocations) is in **MySQL tables** and uses SQL. The flexible, varying data
(extra event details and activity logs) is in the **MySQL Document Store** as
JSON documents and uses the X DevAPI, not SQL. See section 12.

## 2. How one booking works (the flow)

1. The student fills the form: student, hall, date, slot, event, attendees, faculty coordinator.
2. The app calls the stored procedure `request_booking(...)`.
3. The procedure saves the request in `booking_requests` with status `PENDING`.
4. It checks the rules in this order:
   - Is the date in the past? → REJECTED
   - Is it today and the slot has already started? → REJECTED
   - Is the hall under maintenance (`is_active = FALSE`)? → REJECTED
   - Are there more attendees than the hall's capacity? → REJECTED
   - Is there already a row in `allocations` for this hall + date + slot? → REJECTED
   - Otherwise it inserts a row into `allocations` (the hall is **held**) and the request stays **PENDING**
5. It writes the status and reason back on the request, then COMMITs.
6. The **seminar hall coordinator** of that hall opens the Coordinator page and calls
   `review_booking(...)`: approve → **ALLOCATED**; reject (with a reason) → **REJECTED**.
7. If the coordinator rejects it, or the student cancels (`CANCELLED`), the **trigger**
   deletes the allocation row and writes a row into `freed_slots`. The app shows
   freed slots to every student, and tells the students who were refused that
   exact slot earlier that it is free again.

## 3. Tables (9)

| # | Table | Primary key | Foreign keys | Purpose |
|---|---|---|---|---|
| 1 | `departments` | `dept_id` | none | AIML, CSE, ECE, … |
| 2 | `students` | `srn` | `dept_id` → departments | Students who raise requests |
| 3 | `faculty` | `faculty_id` | `dept_id` → departments | Faculty coordinator for each event |
| 4 | `hall_coordinators` | `coordinator_id` | none | **New.** Staff who approve or reject hall requests |
| 5 | `seminar_halls` | `hall_id` | `coordinator_id` → hall_coordinators | Halls with capacity, block, AC, projector, active flag, and who is in charge |
| 6 | `time_slots` | `slot_id` | none | 3 slots: 9:00–11:00, 11:30–13:30, 14:00–16:00 (college rules enforced) |
| 7 | `booking_requests` | `request_id` | `srn`, `hall_id`, `slot_id`, `faculty_id`, `reviewed_by` | **Every** request ever made, with status, reason and who reviewed it |
| 8 | `allocations` | `allocation_id` | `request_id`, `hall_id`, `slot_id` | The hall schedule: approved bookings and PENDING holds |
| 9 | `freed_slots` | `release_id` | `request_id` | **New.** Every booked slot that became free again (filled by the trigger) |

Plus two **views**: `v_booking_details` joins requests with student, department,
hall, slot, faculty and coordinator names, and `v_open_freed_slots` lists the freed
slots that are still free and still in the future (what the app shows to everyone).

### Why are `booking_requests` and `allocations` separate tables?

- `booking_requests` is the history of all requests, including rejected and cancelled ones. The reports need this history.
- `allocations` holds the hall schedule (approved bookings and PENDING holds). It has the key rule of the project:
  **`UNIQUE (hall_id, booking_date, slot_id)`**. Because of this constraint, the
  database can never store two bookings of the same hall in the same slot, even
  if the application code has a bug or two students click "Book" at the same moment.
- `hall_id`, `slot_id` and `booking_date` are copied into `allocations` on
  purpose (controlled redundancy). MySQL cannot put a UNIQUE constraint across two tables.

## 4. Relationships (from the ER diagram)

| Relationship | Between | Cardinality | Participation |
|---|---|---|---|
| BELONGS_TO | Student – Department | N : 1 | every student must have a department (total) |
| WORKS_IN | Faculty – Department | N : 1 | every faculty member must have a department (total) |
| RAISES | Student – Booking request | 1 : N | every request must have a student (total on request side) |
| COORDINATES | Faculty – Booking request | 1 : N | every request must have a coordinator |
| FOR_HALL | Booking request – Seminar hall | N : 1 | every request is for one hall |
| IN_SLOT | Booking request – Time slot | N : 1 | every request is for one slot |
| RESULTS_IN | Booking request – Allocation | 1 : 1 | a request may or may not get an allocation (partial); every allocation comes from a request (total) |
| RESERVES | Allocation – Seminar hall | N : 1 | |
| DURING | Allocation – Time slot | N : 1 | |
| MANAGES | Hall coordinator – Seminar hall | 1 : N | every hall has a coordinator (total on hall side) |
| REVIEWS | Hall coordinator – Booking request | 1 : N | partial: a request has no reviewer until the coordinator decides |
| FREES | Booking request – Freed slot | 1 : 1 | a request may free a slot (partial); every freed slot comes from a request (total) |

Double lines in the ER diagram mean total participation, single lines mean partial participation.

## 5. Constraints used

| Constraint | Where | Why |
|---|---|---|
| PRIMARY KEY | every table | unique row identity |
| FOREIGN KEY | students, faculty, booking_requests, allocations | no request for a student/hall/slot that doesn't exist |
| UNIQUE | `dept_code`, `email`, `hall_name`, `slot_label`, `allocations.request_id`, `(hall_id, booking_date, slot_id)` | no duplicates; **no double booking** |
| CHECK | `semester BETWEEN 1 AND 8`, `capacity > 0`, `expected_attendees > 0`, `end_time > start_time` | reject invalid values |
| CHECK (college rules) | `start_time >= '09:00' AND end_time <= '16:00'`, `TIMEDIFF(end_time, start_time) <= '02:00:00'` | halls only 9 AM–4 PM, at most 2 hours |
| TRIGGER (college rule) | `trg_slot_gap_insert` / `trg_slot_gap_update` on `time_slots` | 30 minute gap between slots (a CHECK can't compare two rows) |
| NOT NULL / DEFAULT | most columns; `status DEFAULT 'PENDING'`, `requested_at DEFAULT CURRENT_TIMESTAMP` | required data, sensible defaults |
| ENUM | `event_type`, `status` | only allowed values |
| ON DELETE CASCADE | `allocations.request_id`, `freed_slots.request_id` | deleting a request deletes its allocation and freed-slot row |

## 6. Normalization

- **1NF:** every column holds one atomic value, and there are no repeating groups (one request = one slot).
- **2NF:** every primary key is a single column, so partial dependency is impossible.
- **3NF / BCNF:** every non-key column depends only on the key of its own table.
  For example, the department name is not stored in `students` (only `dept_id`), and
  the hall capacity is not stored in `booking_requests` (only `hall_id`).
- In `allocations`, `request_id` and `(hall_id, booking_date, slot_id)` are both
  candidate keys, so every determinant is a candidate key and the table is in BCNF.
  The repeated hall/date/slot values are redundancy across tables, chosen on purpose
  for the UNIQUE constraint (see section 3).

## 7. Stored procedure `request_booking`

```sql
CALL request_booking('PES1UG24AM005', 2, 1, '2026-11-10',
                     'Git Workshop', 'Workshop', 60, 1,
                     @id, @status, @msg);
SELECT @id, @status, @msg;
```

- **8 IN parameters** (the form fields) and **3 OUT parameters**: request id, status and message.
- The whole procedure runs inside **`START TRANSACTION … COMMIT`**, so it is atomic:
  either the request and its allocation are both saved, or nothing is saved.
- `DECLARE EXIT HANDLER FOR SQLEXCEPTION … ROLLBACK; RESIGNAL;` handles bad input,
  such as an SRN that doesn't exist (a foreign key error). The transaction is undone and the error goes back to the app.
- If every rule passes, the request is **PENDING** and the hall is held (a row in `allocations`),
  so nobody else can take it while the coordinator decides.
- `DECLARE CONTINUE HANDLER FOR 1062` handles the race case. If two students book
  the same slot at the same instant, both may pass the "is it free?" check. Only
  one INSERT can succeed because of the UNIQUE key. The other gets error 1062
  (duplicate key), and the handler turns that into a clean "already booked" rejection.

## 8. Procedure `review_booking` and the triggers

```sql
CALL review_booking(190, 3, TRUE, NULL, @status, @msg);                         -- approve
CALL review_booking(191, 1, FALSE, 'Hall needed for placement drive', @status, @msg); -- reject
SELECT @status, @msg;
```

`review_booking` locks the request row (`SELECT … FOR UPDATE`, so two clicks can't
decide it twice), checks it is still PENDING and that **this coordinator is in charge
of that hall**, then sets ALLOCATED or REJECTED, `reviewed_by` and `reviewed_at`.

**Trigger `trg_free_hall_on_cancel`** (AFTER UPDATE on `booking_requests`):

```sql
IF OLD.status IN ('PENDING','ALLOCATED') AND NEW.status IN ('CANCELLED','REJECTED') THEN
    DELETE FROM allocations WHERE request_id = NEW.request_id;
    IF ROW_COUNT() > 0 THEN
        INSERT INTO freed_slots (request_id, reason) VALUES (NEW.request_id, NEW.remarks);
    END IF;
END IF;
```

The app only runs `UPDATE … SET status = 'CANCELLED'` (or the coordinator rejects).
The trigger frees the hall **and publishes the freed slot**, so no application code
can forget either step. `ROW_COUNT() > 0` means a slot is published only if a hall
was really held (a request rejected by a rule never had one).

**Triggers `trg_slot_gap_insert` / `trg_slot_gap_update`** (BEFORE INSERT/UPDATE on
`time_slots`) raise `SIGNAL SQLSTATE '45000'` if a new slot starts less than 30
minutes after another ends (or overlaps it).

**Procedure vs trigger:** a procedure is called explicitly (`CALL`). A trigger
runs automatically when an INSERT, UPDATE or DELETE happens on its table.

## 9. Reports (`sql/04_reports.sql`) and the SQL concept each one shows

| Report | Shows |
|---|---|
| R1 Hall-wise bookings and average attendance | `AVG`, `COUNT`, `LEFT JOIN`, `GROUP BY`. **This is the "average salary per department" example.** Seminar Hall 3 has 0 bookings but still appears because of the LEFT JOIN |
| R2 Department-wise requests and success rate | `COUNT(CASE WHEN …)`, percentage, `NULLIF` to avoid divide-by-zero, joins across 3 tables |
| R3 Demand for each time slot | grouping on a lookup table, conditional count |
| R4 Month-wise trend | `DATE_FORMAT`, grouping by a computed column |
| R5 Event type analysis | `AVG`, `MAX`, `WHERE` before `GROUP BY` |
| R6 Top 5 students | `ORDER BY … DESC` with `LIMIT` |
| R7 Events per faculty | `LEFT JOIN` with the condition in `ON` (faculty with 0 events still listed) |
| R8 Rejection reasons | grouping on a text column |
| R9 Halls busier than average | **nested subquery** inside `HAVING` |
| R10 Busiest weekdays | `DAYNAME`, `WEEKDAY` for correct ordering |
| R11 Freed slots: were they booked again? | **Novelty report.** correlated `EXISTS` subquery inside `COUNT(CASE …)`, `LIKE` |
| R12 Coordinator workload and average approval time | `AVG(TIMESTAMPDIFF(…))` = average hours a student waited, per coordinator (another "average per group") |

## 10. Demo script (about 7 minutes)

Run `python setup_db.py` first, then `streamlit run app.py`. The dates below use
**6 Nov 2026**. If the demo is on or after 6 Nov, open Hall availability, pick any
upcoming date with a red (booked) cell and use that hall, date and slot instead.

**Logins (for now the password is the same as the ID):**

| Role | IDs | Sees |
|---|---|---|
| Student | PES1UG24AM001 - PES1UG24AM300 | Book a hall, Hall availability, Hall details, My bookings |
| Admin | PES1UGADM01 - PES1UGADM10 | Dashboard, Approvals, All bookings, Hall availability, Hall details, Reports, NoSQL documents, Manage |

1. **ER diagram:** open `docs/er_diagram.html`. Explain the 9 entities. The two **green**
   ones (HALL_COORDINATOR, FREED_SLOT) come from how our own college works.
2. **Login page:** the app opens on the login page only. Show that **PES1UG24AM301**, a CSE
   SRN or a wrong password gives "Invalid SRN / Admin ID or password".
3. **Student (PES1UG24AM001):** only 4 pages in the sidebar.
   - **Hall details:** filter "Seats needed" 100 and tick AC. Each card shows seats, AC,
     projector, the coordinator and the free slots on the chosen date.
   - **Hall availability:** pick today. Slots that have already started show **TIME OVER**
     (grey), never FREE. Then pick **6 Nov**: Seminar Hall 1 and the Mini Auditorium are
     booked 14:00-16:00, and Seminar Hall 1 at 11:30-13:30 shows **FREED - book now**.
   - **Book a hall (clash):** 6 Nov, 14:00-16:00, **Seminar Hall 1** (marked BOOKED), event
     "Viva Demo", 50 people -> **REJECTED: Hall already booked**, with suggested free halls.
     (The date picker does not allow past dates, and today's started slots are not offered.)
   - **Book a hall (held):** same date and slot, **AIML Seminar Hall**. Fill the optional extra
     details -> **PENDING: hall held, waiting for the coordinator**. Open "SQL that was
     executed" and "NoSQL document saved". **One action, two databases.**
   - **Book a hall (capacity):** **Conference Room (40 seats)** with 60 attendees -> **REJECTED**.
   - **My bookings:** the summary (requests, approved, waiting, rejected) and the colour-coded history.
4. **Admin (log out, then PES1UGADM01):** 8 pages.
   - **Dashboard:** totals, the yellow "requests waiting for approval" alert, the freed-slots board.
   - **Approvals:** choose **Mr. Anand Kumar** (AIML Seminar Hall). "Viva Demo" is waiting ->
     **Approve** -> ALLOCATED. Then pick "GenAI for Beginners" (5 Nov), type a reason and
     **Reject**: the trigger frees the hall and the Dashboard board now lists it.
   - **All bookings:** filter by date, hall, status or search a name / SRN; **Download as CSV**;
     cancel any booking with a reason (the trigger frees and publishes the slot).
   - **Manage -> Time slots:** try 15:00-17:00 -> rejected by the CHECK (after 4 PM).
     Try 09:00-12:00 -> rejected (more than 2 hours). Try 11:00-11:20 -> rejected by the
     trigger (no 30 minute gap). **The college rules live in the database.**
   - **Reports:** R1 (average attendance, the professor's example), R11 (freed slots, our
     novelty), R12 (average approval time per coordinator), R9 (nested query); each has a
     CSV download.
   - **NoSQL documents:** event_details (different fields per event type), add a tag (modify),
     booking_logs (REQUEST / REVIEW / CANCEL shapes), remove a log, N1-N3 reports.
   - **Manage -> View tables:** `booking_requests`, `allocations`, `freed_slots`.
5. **Student again:** log in as **PES1UG24AM001**, My bookings -> **Cancel** "Viva Demo": the slot
   is published for everyone. Log in as **PES1UG24AM005**: My bookings shows a green message,
   the hall they were refused (Seminar Hall 1, 6 Nov, 11:30-13:30) is **free again**.
6. Optional, in MySQL Workbench: `sql/05_demo_queries.sql`, one query at a time.

## 11. Likely viva questions

**Q: What is new (novel) in your project?**
It comes from how our own college works. (1) A request only **holds** the hall; the
seminar hall coordinator in charge of that hall approves or rejects it
(`review_booking`, `hall_coordinators`). (2) When a booking is cancelled or rejected,
a trigger **publishes the freed slot** in `freed_slots`. Everyone sees it, and the
students who were refused that exact slot are told it is free. Without this, a
cancelled hall just stays empty. (3) Our college's timings (9 AM–4 PM, 2 hours max,
30 minute gap) are enforced **by the database** (CHECK constraints plus a trigger),
not just by the form.

**Q: Why not just delete the allocation on cancel? Why a freed_slots table?**
Deleting frees the hall but nobody knows. `freed_slots` keeps a record of every freed
slot, so it can be shown to everyone, matched against students who were refused,
and measured (R11: how many freed slots were booked again).

**Q: Why does a PENDING request already have a row in allocations?**
So the hall is held while the coordinator decides. Otherwise two students could both
wait for approval for the same slot. The UNIQUE key still guarantees one booking per slot.

**Q: Why a trigger for the 30 minute gap and not a CHECK?**
A CHECK constraint can only look at the values in the same row. The gap compares the
new slot with the other rows in `time_slots`, so it needs a trigger.

**Q: How does the login work? Who can see what?**
Until someone logs in, the app shows only the login page (no sidebar, no other pages).
Students **PES1UG24AM001 to PES1UG24AM300** (pattern + number range, and the SRN must exist in
`students`, checked with `SELECT name FROM students WHERE srn = %s`) see only Book a hall,
Hall availability, Hall details and My bookings. Admins **PES1UGADM01 to PES1UGADM10** see
everything: dashboard, approvals, all bookings, reports, NoSQL documents and management.
For now the password is the ID itself. The ID and role are kept in Streamlit's
`st.session_state`, so bookings are always made in the logged-in student's name. In a real
system we would store users in a table with a `password_hash` (for example bcrypt), never the password.

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
A view is a saved SELECT that behaves like a table. `v_booking_details` hides a 5-table join, so the app and reports query it simply.

**Q: Difference between WHERE and HAVING?**
WHERE filters rows before grouping. HAVING filters groups after `GROUP BY`. R9 uses HAVING with a subquery.

**Q: Difference between INNER JOIN and LEFT JOIN? Where did you need LEFT JOIN?**
LEFT JOIN keeps rows from the left table even with no match. In R1 the hall with 0 bookings (Seminar Hall 3) still appears only because of the LEFT JOIN.

**Q: COUNT(*) vs COUNT(column)?**
COUNT(*) counts rows. COUNT(column) skips NULLs. In R2, `COUNT(r.request_id)` gives 0 for a department with no requests, where COUNT(*) would wrongly give 1.

**Q: Where is a transaction used, and what are the ACID properties here?**
In `request_booking`. *Atomicity:* the request and allocation are saved together or not at all.
*Consistency:* the constraints always hold. *Isolation:* concurrent bookings can't double-book (UNIQUE key).
*Durability:* InnoDB keeps committed bookings after a crash.

**Q: How do you prevent SQL injection?**
Every query that takes user input uses parameter placeholders (`%s`), so the input is never pasted into the SQL text.
The one query built with a table name (Admin → View tables) only accepts names from a fixed list.

**Q: Why does the app use `seminar_app` instead of root?**
Principle of least privilege: the app user only has rights on the `seminar_booking` database.

**Q: What is `log_bin_trust_function_creators` in the setup script?**
Binary logging is on in this MySQL server. In that mode only SUPER users can create
triggers unless this flag is set. It lets the app user create the trigger.

**Q: Is any entity weak?**
No. Every entity has its own key. ALLOCATION and FREED_SLOT depend on BOOKING_REQUEST
for their existence (total participation), but each is identified by its own id.

**Q: What does ON DELETE CASCADE do here?**
If a booking request row is deleted, its allocation row is deleted automatically.

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
| `event_details` | Extra details for each booking request: equipment list, speaker, tools, prizes, tags, notes | **Every event type has different fields.** A guest lecture has a speaker object, a workshop has a tools array, a hackathon has a prizes array. In SQL this would need many mostly-NULL columns or a separate table per event type. A document simply has the fields it needs. |
| `booking_logs` | One entry per action: every booking request (with the result and suggested alternatives) and every cancellation | Logs are **append-only, high-volume, and vary in shape** (REQUEST and CANCEL entries store different fields). There are no joins and no updates, which is a classic document-store job. |

Example documents (notice the different fields):

```json
{"request_id": 5, "event_type": "Hackathon", "equipment": ["Extra chairs", "Laptop", "Projector"],
 "teams_expected": 25, "prizes": [{"position": 1, "amount": 10000}, {"position": 2, "amount": 5000}],
 "tags": ["beginner-friendly", "competition"]}

{"request_id": 12, "event_type": "Guest Lecture", "equipment": ["Video recording", "Whiteboard"],
 "speaker": {"name": "Mr. Farhan Ali", "organisation": "CloudNest Technologies", "session_minutes": 90},
 "tags": ["industry", "first-years", "inter-college"]}
```

### How SQL and NoSQL are linked

Each document stores the `request_id` of its MySQL request. The app saves the
SQL row first (through the procedure), then the document. The **My bookings** page
reads the SQL history and the matching document side by side. NoSQL has **no
foreign keys**, so the application keeps the link correct. That is the usual
trade-off: flexibility instead of enforced integrity.

### CRUD in the code (`nosql.py`)

| Operation | X DevAPI call | Used for |
|---|---|---|
| **Create** | `collection.add(doc)` | saving event details and log entries on every booking or cancel |
| **Read** | `collection.find("event_type = :type AND :equipment IN equipment").bind(...)` | search page, My bookings |
| **Update** | `collection.modify("request_id = :rid").array_append("tags", tag)` | "Add a tag" on the NoSQL page |
| **Delete** | `collection.remove("_id = :id").bind("id", ...)` | "Delete document" on the NoSQL page |
| **Aggregate** | `find().fields("event_type", "COUNT(_id) AS documents").group_by("event_type")` | NoSQL reports N1 and N2 |
| **Index** | `create_index("idx_request_id", {"fields": [{"field": "$.request_id", "type": "INT"}]})` | fast lookup by request |

`:type`, `:equipment` and `:rid` are **bound parameters**, the NoSQL version of `%s`
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
db.event_details.find(":e IN equipment").fields("request_id", "equipment").limit(3).bind("e", "Projector")
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
transactions, such as bookings, where double booking must be impossible. NoSQL
suits data whose shape varies or grows quickly, such as event details and logs.
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
| Halls are booked on the college website | Booking form and live availability grid | Book a hall, Hall availability |
| The **seminar hall coordinator** approves | Request holds the hall as PENDING; coordinator approves/rejects; only the coordinator in charge of that hall can decide | `hall_coordinators`, `review_booking`, Coordinator page |
| **Cancelled slots are not visible to others** (the problem) | Trigger publishes every freed slot; board for everyone; alert to students who were refused that slot | `freed_slots`, `trg_free_hall_on_cancel`, `v_open_freed_slots`, Dashboard, My bookings, R11 |
| Any department can book a free hall | No department restriction (only free, active, big enough) | `request_booking` |
| Halls 9 AM–4 PM, 2 hours max, 30 min gap | 3 slots; CHECK constraints + gap trigger | `time_slots`, `trg_slot_gap_insert`, Admin → Time slots |
