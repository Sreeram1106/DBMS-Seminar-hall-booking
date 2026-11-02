# University Seminar Hall Booking System

A DBMS project where students request a seminar hall for a date and time slot.
If the hall is free (and big enough, and not under maintenance) the database
holds it and the **seminar hall coordinator** approves or rejects it; otherwise
the request is rejected with the reason and the app suggests other free halls.

**Novelty, from how our college works:** coordinator approval, and **freed slots
visible to everyone**. When a booking is cancelled or rejected, a trigger publishes
the slot, so other students (especially the ones refused earlier) can book it. The
college timings (9 AM–4 PM, 2 hours max, 30 minute gap) are enforced in the database.

- **RDBMS:** MySQL 8.0 (9 tables, 2 views, 2 stored procedures, 3 triggers)
- **NoSQL:** MySQL Document Store, with 2 collections of schemaless JSON documents (`event_details`, `booking_logs`) used through the X DevAPI
- **Front end:** Python + Streamlit
- **Reports:** 12 SQL reports and 3 NoSQL reports, with charts

## Project files

| File | What it is |
|---|---|
| `sql/00_create_user.sql` | Run once as root: creates the database and the app user |
| `sql/01_schema.sql` | All 9 tables with keys and constraints, plus the 2 views |
| `sql/02_procedures_triggers.sql` | `request_booking` and `review_booking` procedures; `trg_free_hall_on_cancel` and the slot-gap triggers |
| `sql/03_sample_data.sql` | Sample data: 6 departments, 336 students (incl. PES1UG24AM001-300), 12 faculty, 3 hall coordinators, 7 halls, 3 slots, 202 requests, 14 freed slots |
| `sql/04_reports.sql` | The 12 report queries (the app reads them from here) |
| `sql/05_demo_queries.sql` | Step-by-step queries to show in MySQL Workbench (structure, booking flow, rules that must fail, reports) |
| `setup_db.py` | Runs files 01–03 and loads the NoSQL collections. Run again any time to reset to the sample data |
| `app.py` | The Streamlit app (all pages) |
| `db.py` | Connects to MySQL and runs queries and the procedure (SQL) |
| `nosql.py` | All NoSQL operations: add / find / modify / remove / groupBy on the document collections |
| `nosql_data/*.json` | Sample documents: 202 event details, 375 booking log entries |
| `config.py` | Database connection settings |
| `docs/er_diagram.html` | ER diagram (Chen notation) and relational schema, printable |
| `docs/er_diagram.png` | ER diagram image for slides |
| `docs/final_er.pdf` | ER diagram + relational schema as a 2-page PDF |
| `docs/viva_notes.md` | Explanation of the design, a demo script and likely viva questions |
| `docs/sql_python_explained.md` | How db.py and app.py connect the SQL to the Streamlit website |
| `docs/Project_Report.pdf` | 9-page project report to show the professor (criteria, novelty, ER, schema, procedures, tests, reports, NoSQL, Python) |

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

| Role | IDs | Pages |
|---|---|---|
| Student | PES1UG24AM001 - PES1UG24AM300 | Book a hall, Hall availability, Hall details, My bookings |
| Admin | PES1UGADM01 - PES1UGADM10 | Dashboard, Approvals, All bookings, Hall availability, Hall details, Reports, NoSQL documents, Manage |

- **Book a hall (student):** dates from today only, and only slots that have not started yet. Halls are listed free-first with seats and AC. It calls the stored procedure (SQL), which holds the hall as PENDING, and saves the optional event details as a JSON document (NoSQL)
- **Hall availability:** colour-coded hall x slot grid (free, freed, awaiting approval, booked, time over, maintenance) and a "find a free hall" search with an AC filter
- **Hall details:** one card per hall with seats, AC, projector, coordinator and the free slots on a chosen date; filters for seats, AC and projector
- **My bookings (student):** summary numbers, colour-coded history, an alert when a hall they were refused is free again, each event's NoSQL document, and cancelling (the trigger frees and publishes the slot)
- **Dashboard (admin):** key numbers, a pending-approvals alert, the freed-slots board, today's schedule, latest requests
- **Approvals (admin):** the seminar hall coordinator approves or rejects pending requests for their halls (`review_booking`)
- **All bookings (admin):** filter by date / hall / status, search by event, student or SRN, download CSV, cancel a booking with a reason
- **Reports (admin):** the 12 SQL reports with charts, the SQL behind each, and CSV download
- **NoSQL documents (admin):** search, modify and remove documents, plus 3 NoSQL reports
- **Manage (admin):** view any table, add students or halls, put a hall under maintenance, try adding a time slot (the database enforces the college timing rules)
