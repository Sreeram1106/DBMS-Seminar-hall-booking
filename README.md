# University Seminar Hall Booking System

A DBMS project where students request a seminar hall for a date and time slot.
If the hall is free (and big enough, and not under maintenance) the database
holds it. The **faculty heading the event** approves it first, then the
**chairperson of the student's department** gives the final approval; otherwise
the request is rejected with the reason and the app suggests other free halls.

**Novelty, from how our college works:** two-step approval (event head, then
chairperson), and **freed slots visible to everyone**. When a booking is cancelled or rejected, a trigger publishes
the slot, so other students (especially the ones refused earlier) can book it. The
college timings (9 AM–4 PM, 2 hours max, 30 minute gap) are enforced in the database.

- **RDBMS:** MySQL 8.0 (9 tables, 2 views, 3 stored procedures, 3 triggers)
- **NoSQL:** MySQL Document Store, with 2 collections of schemaless JSON documents (`event_details`, `booking_logs`) used through the X DevAPI
- **Front end:** Python + Streamlit
- **Reports:** 13 SQL reports and 3 NoSQL reports, with charts

## Project files

| File | What it is |
|---|---|
| `sql/00_create_user.sql` | Run once as root: creates the database and the app user |
| `sql/01_schema.sql` | All 9 tables with keys and constraints, plus the 2 views |
| `sql/02_procedures_triggers.sql` | `request_booking`, `faculty_review` and `review_booking` procedures; `trg_free_hall_on_cancel` and the slot-gap triggers |
| `sql/03_sample_data.sql` | Sample data: 6 departments, 234 students (incl. PES1UG24AM001-100 and PES1UG24CS001-100), 12 faculty, 6 chairpersons, 7 halls, 3 slots, 202 requests, 14 freed slots |
| `sql/04_reports.sql` | The 13 report queries (the app reads them from here) |
| `sql/05_demo_queries.sql` | Step-by-step queries to show in MySQL Workbench (structure, booking flow, rules that must fail, reports) |
| `setup_db.py` | Runs files 01–03 and loads the NoSQL collections. Run again any time to reset to the sample data |
| `app.py` | The Streamlit app (all pages) |
| `db.py` | Connects to MySQL and runs queries and the procedure (SQL) |
| `nosql.py` | All NoSQL operations: add / find / modify / remove / groupBy on the document collections |
| `nosql_data/*.json` | Sample documents: 202 event details, 540 booking log entries |
| `config.py` | Database connection settings |
| `.streamlit/config.toml` | Look of the app: white pages with one teal accent, Inter / Plus Jakarta Sans fonts, rounded corners, hides the Deploy button |
| `assets/logo.svg` | Logo shown at the top left, next to the menu |
| `docs/er_diagram.html` | ER diagram (Chen notation) and relational schema, printable |
| `docs/er_diagram.png` | ER diagram image for slides |
| `docs/final_er.pdf` | ER diagram + relational schema as a 2-page PDF |
| `docs/viva_notes.md` | Explanation of the design, a demo script and likely viva questions |
| `docs/sql_python_explained.md` | How db.py and app.py connect the SQL to the Streamlit website |
| `docs/Project_Report.pdf` | 10-page project report to show the professor (criteria, novelty, ER, schema, procedures, tests, reports, NoSQL, Python) |
| `docs/two_laptop_demo.md` | Live demo: student + faculty on laptop 1, chairperson on laptop 2, step by step |

## First-time setup

1. Make sure the MySQL service is running. It is set to start manually on this
   laptop, so after a restart open **Services**, find **MySQL80** and click **Start**.
   You can also run this in an administrator terminal: `net start MySQL80`.
2. Run `sql/00_create_user.sql` once as root (MySQL Workbench, or
   `source D:/dbms project/sql/00_create_user.sql` at the `mysql>` prompt).
3. Install the Python packages and load the database:
   ```bash
   pip install -r requirements.txt
   ```
   ```bash
   pip install --no-deps mysqlx-connector-python
   ```
   ```bash
   python setup_db.py
   ```
   The NoSQL part connects on port 33060 (the MySQL X Protocol). It is on by default in MySQL 8.

## Run the app

```bash
streamlit run app.py
```

It opens at http://localhost:8501.

**Before every demo**, run `python setup_db.py` to reset the data, so test
bookings from practice runs disappear.

## App pages

The app opens on a **login page** only. For now the password is the same as the ID.

| Role | IDs | Pages (menu at the top) |
|---|---|---|
| Student | PES1UG24AM001 - PES1UG24AM100 (AIML), PES1UG24CS001 - PES1UG24CS100 (CSE) | Book a hall, My bookings, Availability, Halls |
| Faculty (event head) | PES1UG24FAC001 - PES1UG24FAC012 | Event requests, Availability, Halls |
| Chairperson (one per department) | PES1UG24CHR001 - PES1UG24CHR006 | Dashboard, Approvals, All bookings, Availability, Halls, Reports, NoSQL, Manage |

A student can only name faculty of their own department as event head, and only that
department's chairperson can approve:

| Department | Students | Faculty (event heads) | Chairperson |
|---|---|---|---|
| AIML | PES1UG24AM001 - AM100 | FAC003 Dr. Kavitha Rao, FAC004 Prof. Arjun Menon | CHR002 Dr. Meera Krishnan |
| CSE | PES1UG24CS001 - CS100 | FAC001 Dr. Shalini Murthy, FAC002 Prof. Naveen Shetty | CHR001 Dr. Rajesh Iyer |

- **Book a hall (student):** five simple steps: pick a date → pick a time (slot buttons on one line; slots that already started are hidden) → AC or non-AC → choose a hall from cards (seats, Free / Booked) → event name, type, attendees and the **event head**. The student's department is shown at the top, and only faculty of that department can be chosen as event head (the database refuses any other). It calls the stored procedure `request_booking` (SQL), which holds the hall, and quietly saves the optional event details in the document store (NoSQL)
- **My bookings (student):** a step tracker per request (Requested → Event head → Chairperson), summary numbers, colour-coded history, an alert when a hall they were refused is free again, each event's details in plain words, and cancelling
- **Event requests (faculty):** requests where they are the event head; approve or reject with a reason (`faculty_review`). A rejection stops the request
- **Approvals (chairperson):** requests from their department with the student, the event head and the event head's answer; final approve or reject (`review_booking`)
- **Dashboard (chairperson):** key numbers, "waiting for you" alert, the freed-slots board, today's schedule, latest requests
- **All bookings (chairperson):** filter by department / date / hall / status, search, download CSV, cancel a booking from their department with a reason
- **Availability / Halls (everyone):** colour-coded hall x slot grid (free, freed, waiting, booked, time over, maintenance), "find a free hall", and hall cards with seats and AC / non-AC
- **Reports (chairperson):** the 13 SQL reports with charts, a month filter at the top (all months, or one month), the SQL behind each, and CSV download
- **NoSQL (chairperson):** event details and the activity log as plain tables (no JSON on screen), filter by event type, tag or action, add a tag, delete a log entry, plus 3 NoSQL reports
- **Manage (chairperson):** view any table, add students or halls, put a hall under maintenance, try adding a time slot (the database enforces the college timing rules)

Every page has a live counter at the top (next to your name) that re-reads MySQL every 5
seconds and pops up new requests and decisions, so the student, faculty and chairperson
screens stay in sync.
