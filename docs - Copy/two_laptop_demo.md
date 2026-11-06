# Live demo: student + faculty on laptop 1, chairperson on laptop 2

**Laptop 1 (the main laptop)** runs MySQL and the app, and shows **two browser tabs**:
the student and the faculty (event head).
**Laptop 2** only needs a browser: it opens the app from laptop 1 over Wi-Fi / hotspot
and shows the **chairperson**.
All three screens use the **same database**, so every action shows up on the others.

A **live counter at the top of every page** (next to your name, under the menu) re-reads
MySQL every 5 seconds and shows a pop-up when something happens:

| Screen | Pop-up when |
|---|---|
| Faculty | a student names them as event head ("New event request #…") |
| Chairperson | a new request from their department arrives, and when its event head approves it ("… approved #…. Ready for your approval.") |
| Student | the event head approves ("… Now waiting for the chairperson."), and when the chairperson decides ("… is BOOKED" / "… was rejected") |

Each browser tab is its own login, so tab 1 (student) and tab 2 (faculty) on the same
laptop do not mix. **Do not press F5 / refresh** during the demo: a refresh logs that tab out.

## 1. Before mam arrives (5 minutes)

1. Connect **both laptops to the same Wi-Fi**. College Wi-Fi often blocks laptops from
   reaching each other, so the safest choice is a **phone hotspot** for both.
2. On **laptop 1**, start MySQL (administrator terminal) and reset the data:
   ```bash
   net start MySQL80
   ```
   ```bash
   python setup_db.py
   ```
3. On laptop 1, start the app from the `D:\dbms project` folder:
   ```bash
   python -m streamlit run app.py
   ```
   The terminal prints a **Local URL** (`http://localhost:8501`) and a **Network URL**
   (for example `http://192.168.137.106:8501`). The Network URL changes with each network.
4. If Windows asks "Allow Python to communicate on networks?", click **Allow**.
5. **Laptop 1:** open Chrome at `http://localhost:8501` **twice** (two tabs). Drag one tab out
   and snap the two windows side by side.
6. **Laptop 2:** open Chrome at laptop 1's **Network URL** (not `localhost`).
7. On every screen, if a "Help agents write better apps" box appears, click **Don't show again**.

**Check all three use the same app:** after logging in, the line under the live counter ends
with `server <name>` (for example `server Sreeram`). It must be the **same name on every screen**.

## 2. Who logs in where (password = same as the ID)

Use **one department for all three logins**: the student can only pick an event head from
their own department, and only that department's chairperson can approve.

**AIML (recommended):**

| Screen | Login | Who it is | Page |
|---|---|---|---|
| Tab 1 | **PES1UG24AM001** | Student Suhas Hegde (AIML) | Book a hall |
| Tab 2 | **PES1UG24FAC004** | Prof. Arjun Menon (AIML), event head | Event requests |
| Tab 3 / laptop 2 | **PES1UG24CHR002** | Dr. Meera Krishnan, AIML chairperson | Approvals |

**CSE (alternative):**

| Screen | Login | Who it is | Page |
|---|---|---|---|
| Tab 1 | **PES1UG24CS001** | Student Chetan Verma (CSE) | Book a hall |
| Tab 2 | **PES1UG24FAC002** | Prof. Naveen Shetty (CSE), event head | Event requests |
| Tab 3 / laptop 2 | **PES1UG24CHR001** | Dr. Rajesh Iyer, CSE chairperson | Approvals |

Students: PES1UG24AM001–100 (AIML) and PES1UG24CS001–100 (CSE).
AIML faculty: FAC003 Dr. Kavitha Rao, FAC004 Prof. Arjun Menon. AIML chairperson: CHR002 Dr. Meera Krishnan.
CSE faculty: FAC001 Dr. Shalini Murthy, FAC002 Prof. Naveen Shetty. CSE chairperson: CHR001 Dr. Rajesh Iyer.

Prof. Arjun Menon (and Prof. Naveen Shetty for CSE) start with **0** requests, so the counter
visibly goes 0 → 1. Dr. Kavitha Rao already has one waiting (#190) and Dr. Shalini Murthy has #189.

## 3. The live demo (about 3 minutes)

| Step | Student (laptop 1, tab 1) | Faculty (laptop 1, tab 2) | Chairperson (laptop 2) |
|---|---|---|---|
| 1 | **Book a hall**: date **27 Nov** (if it is not in the date strip: **Other date** → click the date box → click 27 in the calendar) → time **14:00 - 16:00** → **AC** → **AIML Seminar Hall** → **Select** → "Viva Demo", 50 people, event head **Prof. Arjun Menon** (only AIML faculty are listed) → **Request booking** → "hall HELD, waiting for the event head" | | |
| 2 | | Pop-up **"New event request #…: Viva Demo by Suhas Hegde"**, counter 0 → 1 | Pop-up "New request #… from AIML … event head Prof. Arjun Menon" |
| 3 | Open **My bookings**: tracker Requested ✓ → Event head (current) → Chairperson | Click **Approve - I am the event head** | |
| 4 | Pop-up "Prof. Arjun Menon approved #… Now waiting for the chairperson."; second step turns green | | Pop-up **"Prof. Arjun Menon approved #…. Ready for your approval."** |
| 5 | | | On **Approvals** pick the request: green box "Prof. Arjun Menon (event head) has approved this event" → **Approve - book the hall** |
| 6 | Pop-up **"#… (Viva Demo) is BOOKED"**, all three steps green | | |

**Optional, a rejection:** the student books another free slot naming **Prof. Arjun Menon**;
the faculty types a reason and clicks **Reject** → the request stops (never reaches the
chairperson), the student sees "was rejected", and the slot appears on the freed-slots board.

**What to say:** "All three screens use the same MySQL database. The student's click calls
the stored procedure `request_booking`, which holds the hall. The event head's click calls
`faculty_review`, and the chairperson's click calls `review_booking`. A rejection fires the
trigger that frees the hall and publishes the slot. Every page re-reads MySQL every 5
seconds, so all screens stay in sync."

## 4. If something does not work

- **Laptop 2 can't open the page:** both laptops must be on the same hotspot; type the
  Network URL exactly, with `http://` and `:8501`. Backup: open the chairperson in a third
  tab on laptop 1 (or an Incognito window).
- **A request does not reach the faculty / chairperson:** check it was not REJECTED (hall
  already booked, too many people, maintenance); pick a hall marked **Free**. Also check the
  student named the faculty who is logged in, and that the chairperson is from the
  student's department.
- **Different `server` names on the screens:** that screen opened its own copy of the app;
  open laptop 1's Network URL instead.

## 5. After the demo

Run `python setup_db.py` on laptop 1 to remove the demo bookings.
