# How the SQL is connected to Python and shown on the Streamlit website

## 1. The big picture

```
 Browser (http://localhost:8501)
        ▲  shows tables, charts, forms
        │
 app.py  ── Streamlit pages: reads form input, decides which query to run,
        │   shows the result with st.dataframe / st.altair_chart
        │
        ├── db.py     ── talks SQL to MySQL tables      (mysql-connector, port 3306)
        └── nosql.py  ── talks X DevAPI to JSON documents (mysqlx, port 33060)
        │
 MySQL 8 server ── tables, views, stored procedures, triggers, CHECKs
                   + the Document Store collections
```

**The important idea:** the business rules live **inside MySQL** (procedures,
triggers, constraints). Python does not decide whether a hall is free. It only
**sends SQL** and **shows what MySQL returns**. That is why the same queries
work in MySQL Workbench (`sql/05_demo_queries.sql`) and in the website.

| File | Job |
|---|---|
| `config.py` | Host, port, user, password, database name |
| `db.py` | 4 small functions that every page uses to run SQL |
| `app.py` | The Streamlit website: one function per page |
| `setup_db.py` | Runs the `.sql` files in order to (re)create everything |
| `sql/04_reports.sql` | The report queries. The app **reads this file**, so a report is written once |

## 2. Connecting to MySQL ([config.py](../config.py), [db.py](../db.py))

```python
DB_CONFIG = {"host": "localhost", "port": 3306, "user": "seminar_app",
             "password": "...", "database": "seminar_booking"}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)
```

- `mysql.connector` is the official MySQL driver for Python (`pip install mysql-connector-python`).
- The app logs in as **`seminar_app`**, not root. It only has rights on this one
  database (least privilege, created by `sql/00_create_user.sql`).
- Each function opens a connection, runs one thing, and closes it in `finally`,
  so a connection is never left open even if the query fails.

## 3. The four functions in db.py

### 3a. `fetch_df(sql, params)`: run a SELECT and get a table back ([db.py:24](../db.py:24))

```python
cur = conn.cursor()
cur.execute(sql, params)                          # send the SQL to MySQL
columns = [c[0] for c in cur.description]         # column names
rows = [[_clean(v) for v in row] for row in cur.fetchall()]
return pd.DataFrame(rows, columns=columns)        # a pandas table
```

A pandas **DataFrame** is a table in Python. Streamlit can draw it directly with
`st.dataframe(df)` and make charts from it.
`_clean` converts MySQL types Python can't display well: `DECIMAL` (from `AVG`,
`ROUND`) → float and `TIME` → text.

### 3b. `execute(sql, params)`: INSERT / UPDATE / DELETE ([db.py:37](../db.py:37))

Same as above plus **`conn.commit()`**. Without commit, MySQL (InnoDB) throws the
change away when the connection closes. Used for: add student, add hall,
maintenance on/off, **cancel a booking** (the UPDATE that fires the trigger).

### 3c. `request_booking(...)`: call the stored procedure ([db.py:49](../db.py:49))

```python
args = (srn, hall_id, slot_id, booking_date, event_name, event_type,
        attendees, faculty_id, 0, "", "")          # last 3 are the OUT parameters
result = cur.callproc("request_booking", args)
conn.commit()
return result[8], result[9], result[10]            # request_id, status, message
```

`callproc` is the Python version of
`CALL request_booking(..., @id, @status, @msg); SELECT @id, @status, @msg;`.
The placeholders `0, "", ""` reserve the 3 OUT slots, and `callproc` returns the
argument list with the OUT values filled in by MySQL.

### 3d. `review_booking(...)`: the coordinator's procedure ([db.py:65](../db.py:65))

The same pattern with 4 IN and 2 OUT parameters → returns `(status, message)`.

## 4. Safety: parameters, never string pasting

```python
db.fetch_df("SELECT ... FROM v_booking_details WHERE srn = %s", (srn,))
```

`%s` is a **placeholder**. The driver sends the value separately from the SQL
text, so input like `' OR 1=1 --` is treated as plain text, not as SQL. This
prevents **SQL injection**. Every query that uses user input is written this way.
The one exception is Admin → View tables (`SELECT * FROM {table}`). A table name
can't be a parameter, so the name must come from a fixed list (`TABLES` in app.py).

## 5. How a Streamlit page works ([app.py](../app.py))

Streamlit **re-runs the whole `app.py` from top to bottom** every time the user
clicks or changes something. Each widget returns its current value:

```python
srn = st.selectbox("Student", list(students))     # what the user picked
history = db.fetch_df("""SELECT ... FROM v_booking_details
                         WHERE srn = %s ORDER BY booking_date DESC""", (srn,))
st.dataframe(history)                             # draw the table
```

**Pick → query → show.** Every page follows this pattern. The sidebar chooses which page
function runs (`PAGES[choice]()` at the bottom of app.py).

**Login and roles:** until `st.session_state` has a user, app.py draws only the login page
and calls `st.stop()`, so no sidebar or other page exists. `check_login` accepts students
PES1UG24AM001 to PES1UG24AM300 (the SRN must exist: `SELECT name FROM students WHERE srn = %s`)
and admins PES1UGADM01 to PES1UGADM10; for now the password equals the ID. The ID and role
go into `st.session_state`, and the sidebar shows `STUDENT_PAGES` (4 pages) or `ADMIN_PAGES`
(8 pages) depending on the role. Log out removes them again.

**Slots that already started:** `open_slots(day)` runs
`SELECT ... FROM time_slots WHERE %s > CURDATE() OR (%s = CURDATE() AND start_time > CURTIME())`,
so the booking form never offers a slot that has begun, and the grid shows it as TIME OVER.

`st.rerun()` re-runs the script straight after a change (booking, cancel,
approve), so the page immediately shows the new data from MySQL.

## 6. Walk-through: one booking on the website

| Step | What happens | Code |
|---|---|---|
| 1 | Student fills the form and clicks **Request booking** | [app.py:256](../app.py:256) `st.form_submit_button` |
| 2 | Python calls the procedure with the form values | [app.py:263](../app.py:263) `db.request_booking(...)` |
| 3 | **MySQL** checks the rules, holds the hall, sets PENDING / REJECTED | `request_booking` in `sql/02_procedures_triggers.sql` |
| 4 | The OUT parameters come back to Python | [db.py:58](../db.py:58) `callproc` |
| 5 | The optional event details go to the NoSQL store as a JSON document | `nosql.save_event_details(details)` |
| 6 | The page shows the result, the exact `CALL` statement and the JSON | `show_booking_result` [app.py:307](../app.py:307) |

**Coordinator approves:** [app.py:466](../app.py:466) → `db.review_booking` →
procedure `review_booking`.
**Student cancels:** `db.execute("UPDATE booking_requests SET status='CANCELLED' ...")`.
Python **does not** delete the allocation or publish the freed slot. Trigger
`trg_free_hall_on_cancel` does both inside MySQL. The Dashboard then simply runs
`SELECT ... FROM v_open_freed_slots` ([app.py:111](../app.py:111)).

## 7. Reports: SQL file → chart ([app.py:154](../app.py:154), [app.py:491](../app.py:491))

`sql/04_reports.sql` is written in a simple format:

```sql
-- #R1. Hall-wise bookings and average attendance     ← title
-- Same idea as "average salary of every department"  ← description
-- chart: hall_name, total_bookings                   ← x and y for the bar chart
SELECT h.hall_name, ...;                              ← the query
```

`load_reports()` reads the file line by line and splits it into reports. The
Reports page runs the chosen query with `db.fetch_df(report["sql"])`, draws a bar
chart with Altair (`bar_chart`, [app.py:142](../app.py:142)), shows the table, and
shows the SQL in an expander. **Same file, same query** in Workbench and on the website.

## 8. setup_db.py: loading the .sql files from Python

It reads `01_schema.sql`, `02_procedures_triggers.sql`, `03_sample_data.sql` and
runs each statement with `cur.execute`. Procedures and triggers contain `;` inside
them, so the files use `DELIMITER $$` like in Workbench. `split_statements`
([setup_db.py:20](../setup_db.py:20)) understands `DELIMITER` lines and cuts the file at
the right places. Then it loads the JSON documents into the NoSQL collections.

## 9. What to say to mam (short version)

1. "All the rules are in MySQL: the procedure decides, the trigger frees and
   publishes slots, and CHECK constraints plus a trigger enforce our timings. I showed
   that in Workbench."
2. "Python connects with `mysql.connector` as a limited user. `db.py` has 4
   functions: `fetch_df` for SELECT, `execute` for changes with commit, and
   `callproc` for the two procedures, which returns the OUT parameters."
3. "All user input goes through `%s` placeholders, so there is no SQL injection."
4. "Streamlit re-runs the page on every click: read the widget → run the query →
   `st.dataframe` / chart. The reports are read from the same `04_reports.sql` file I ran in Workbench."

## 10. Likely questions

**Q: Where is the SQL in your Python code?**
As strings passed to `db.fetch_df` / `db.execute`, the two `callproc` calls, and
the report queries read from `sql/04_reports.sql`.

**Q: Why use a stored procedure instead of writing the checks in Python?**
The rules run inside one transaction in the database, so they also apply from
Workbench or any other program, and two users can't double-book between a check
and an insert. Python only shows the result.

**Q: What is a cursor?**
The object that sends a statement to MySQL and then holds its result rows
(`cur.execute`, `cur.fetchall`).

**Q: Why `conn.commit()`?**
InnoDB is transactional. Changes are only saved permanently after COMMIT.
Without it they are rolled back when the connection closes.

**Q: What does `callproc` return?**
A copy of the argument list where the OUT parameters are replaced by the values
MySQL set, which is why we read `result[8]`, `result[9]`, `result[10]`.

**Q: How does the website update after a booking?**
`st.rerun()` re-runs the page, so every query runs again and shows the new rows.
