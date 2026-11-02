"""University Seminar Hall Booking System - Streamlit front end.

Run:  streamlit run app.py
"""
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import altair as alt
import mysql.connector
import mysqlx
import pandas as pd
import streamlit as st

import db
import nosql

st.set_page_config(page_title="Seminar Hall Booking", layout="wide")

EVENT_TYPES = ["Seminar", "Workshop", "Guest Lecture", "Club Event", "Hackathon", "Cultural", "Other"]
EQUIPMENT = ["Projector", "Microphone", "Speakers", "Laptop", "Whiteboard", "Video recording", "Extra chairs"]
TABLES = ["departments", "students", "faculty", "hall_coordinators", "seminar_halls",
          "time_slots", "booking_requests", "allocations", "freed_slots"]
REPORTS_FILE = Path(__file__).parent / "sql" / "04_reports.sql"


# ---------------------------------------------------------------- lookups
def faculty_options():
    df = db.fetch_df("""
        SELECT f.faculty_id, f.name, d.dept_code
        FROM faculty f JOIN departments d ON d.dept_id = f.dept_id
        ORDER BY d.dept_code, f.name""")
    return dict(zip(df.faculty_id.tolist(), (df.name + " (" + df.dept_code + ")").tolist()))


def slot_options():
    df = db.fetch_df("SELECT slot_id, slot_label FROM time_slots ORDER BY slot_id")
    return dict(zip(df.slot_id.tolist(), df.slot_label.tolist()))


def department_options():
    df = db.fetch_df("SELECT dept_id, dept_code FROM departments ORDER BY dept_id")
    return dict(zip(df.dept_id.tolist(), df.dept_code.tolist()))


def coordinator_options():
    df = db.fetch_df("SELECT coordinator_id, name FROM hall_coordinators ORDER BY coordinator_id")
    return dict(zip(df.coordinator_id.tolist(), df.name.tolist()))


def hall_options():
    df = db.fetch_df("SELECT hall_id, hall_name FROM seminar_halls ORDER BY hall_id")
    return dict(zip(df.hall_id.tolist(), df.hall_name.tolist()))


# ---------------------------------------------------------------- shared pieces
def open_slots(day):
    """Slots that can still be booked on this day: none for a past date, and on
    today only the slots that have not started yet."""
    return db.fetch_df("""
        SELECT slot_id, slot_label
        FROM time_slots
        WHERE %s > CURDATE() OR (%s = CURDATE() AND start_time > CURTIME())
        ORDER BY start_time""", (day, day))


def schedule_grid(day):
    """Halls x time slots for one day: the event name if booked, TIME OVER if the
    slot has already started (or the date is past), FREE otherwise."""
    df = db.fetch_df("""
        SELECT h.hall_name,
               t.slot_label,
               CASE WHEN NOT h.is_active THEN 'UNDER MAINTENANCE'
                    WHEN r.status = 'PENDING' THEN CONCAT(r.event_name, ' (awaiting approval)')
                    WHEN r.event_name IS NOT NULL THEN r.event_name
                    WHEN %s < CURDATE() OR (%s = CURDATE() AND t.start_time <= CURTIME())
                         THEN 'TIME OVER'
                    WHEN o.release_id IS NOT NULL THEN 'FREED - book now'
                    ELSE 'FREE' END AS booking
        FROM seminar_halls h
        CROSS JOIN time_slots t
        LEFT JOIN allocations a
               ON a.hall_id = h.hall_id AND a.slot_id = t.slot_id AND a.booking_date = %s
        LEFT JOIN booking_requests r ON r.request_id = a.request_id
        LEFT JOIN v_open_freed_slots o
               ON o.hall_id = h.hall_id AND o.slot_id = t.slot_id AND o.booking_date = %s
        ORDER BY h.hall_id, t.slot_id""", (day, day, day, day))
    return df.pivot(index="hall_name", columns="slot_label", values="booking")


def colour_cell(value):
    if value == "FREE":
        return "background-color: #d4edda; color: #155724"
    if value == "TIME OVER":
        return "background-color: #ececec; color: #6c757d"
    if value.startswith("FREED"):
        return "background-color: #b7e4c7; color: #0b5d1e; font-weight: bold"
    if value.endswith("(awaiting approval)"):
        return "background-color: #fff3cd; color: #664d03"
    if value == "UNDER MAINTENANCE":
        return "background-color: #e2e3e5; color: #41464b"
    return "background-color: #f8d7da; color: #721c24"


def status_colour(value):
    return {"ALLOCATED": "background-color: #d4edda; color: #155724",
            "PENDING": "background-color: #fff3cd; color: #664d03",
            "REJECTED": "background-color: #f8d7da; color: #721c24",
            "CANCELLED": "background-color: #ececec; color: #6c757d"}.get(value, "")


def show_grid(day):
    st.dataframe(schedule_grid(day).style.map(colour_cell))


def free_halls(day, slot_id, min_capacity=1):
    """Halls still free for this date and slot (empty if the slot has already started)."""
    return db.fetch_df("""
        SELECT h.hall_name, h.block, h.capacity,
               IF(h.has_ac, 'Yes', 'No') AS ac, IF(h.has_projector, 'Yes', 'No') AS projector
        FROM seminar_halls h
        JOIN time_slots t ON t.slot_id = %s
        WHERE h.is_active = TRUE
          AND h.capacity >= %s
          AND (%s > CURDATE() OR (%s = CURDATE() AND t.start_time > CURTIME()))
          AND NOT EXISTS (SELECT 1 FROM allocations a
                          WHERE a.hall_id = h.hall_id
                            AND a.booking_date = %s
                            AND a.slot_id = %s)
        ORDER BY h.capacity""", (slot_id, min_capacity, day, day, day, slot_id))


def open_freed_slots(srn=None):
    """Freed slots anyone can book now. With an SRN: only the ones this student
    asked for earlier and was refused because the hall was already booked."""
    sql = """
        SELECT o.booking_date, o.slot_label, o.hall_name, o.capacity, o.reason, o.freed_at
        FROM v_open_freed_slots o"""
    params = ()
    if srn:
        sql += """
        WHERE EXISTS (SELECT 1 FROM booking_requests r
                      WHERE r.srn = %s
                        AND r.status = 'REJECTED'
                        AND r.remarks = 'Hall already booked for this date and slot'
                        AND r.hall_id = o.hall_id
                        AND r.slot_id = o.slot_id
                        AND r.booking_date = o.booking_date)"""
        params = (srn,)
    return db.fetch_df(sql + "\n        ORDER BY o.booking_date, o.slot_id", params)


def show_freed_board():
    """The 'visible to everyone' part: list every freed slot that is still free."""
    freed = open_freed_slots()
    if freed.empty:
        st.caption("No freed slots right now.")
        return
    st.success(f"**{len(freed)} freed slot(s) available again.** These were booked, then "
               "cancelled or rejected, so anyone can book them now.")
    st.dataframe(freed, hide_index=True)


def bar_chart(df, x, y):
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X(f"{x}:N", sort=None, title=x),
        y=alt.Y(f"{y}:Q", title=y),
        tooltip=list(df.columns))
    st.altair_chart(chart)


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def load_reports():
    """Read sql/04_reports.sql. Each report starts with a '-- #' title line."""
    reports = []
    for line in REPORTS_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("-- #"):
            reports.append({"title": line[4:].strip(), "about": [], "chart": None, "sql": []})
        elif not reports:
            continue
        elif line.startswith("-- chart:"):
            reports[-1]["chart"] = [c.strip() for c in line[len("-- chart:"):].split(",")]
        elif line.startswith("--"):
            reports[-1]["about"].append(line[2:].strip())
        elif line.strip():
            reports[-1]["sql"].append(line)
    for r in reports:
        r["about"] = " ".join(r["about"])
        r["sql"] = "\n".join(r["sql"]).rstrip().rstrip(";")
    return reports


# ---------------------------------------------------------------- login
SRN_PATTERN = re.compile(r"PES1UG24AM(\d{3})")   # students: AIML 2024 batch
FIRST_SRN, LAST_SRN = 1, 300                       # PES1UG24AM001 .. PES1UG24AM300
ADMIN_PATTERN = re.compile(r"PES1UGADM(\d{2})")    # admins: PES1UGADM01 .. PES1UGADM10
FIRST_ADMIN, LAST_ADMIN = 1, 10


def check_login(user_id, password):
    """Return (role, name) if the login is valid, else None. For now the password
    is the ID itself.
      student: PES1UG24AM001 .. PES1UG24AM300, and the SRN must exist in students
      admin:   PES1UGADM01 .. PES1UGADM10"""
    if password.strip().upper() != user_id:
        return None
    match = ADMIN_PATTERN.fullmatch(user_id)
    if match and FIRST_ADMIN <= int(match.group(1)) <= LAST_ADMIN:
        return "admin", f"Admin {match.group(1)}"
    match = SRN_PATTERN.fullmatch(user_id)
    if match and FIRST_SRN <= int(match.group(1)) <= LAST_SRN:
        df = db.fetch_df("SELECT name FROM students WHERE srn = %s", (user_id,))
        if not df.empty:
            return "student", df.name[0]
    return None


def logged_in_student():
    return st.session_state["user"]


def page_login():
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        st.title("Seminar Hall Booking")
        st.caption("PES University · book a seminar hall in a few clicks")
        with st.form("login_form"):
            user_id = st.text_input("SRN / Admin ID", placeholder="PES1UG24AM001")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary", width="stretch")
        if submitted:
            user_id = user_id.strip().upper()
            result = check_login(user_id, password)
            if result:
                st.session_state["user"] = user_id
                st.session_state["role"], st.session_state["name"] = result
                st.rerun()
            else:
                st.error("Invalid SRN / Admin ID or password.")


def logout():
    for key in ("user", "role", "name"):
        st.session_state.pop(key, None)


# ---------------------------------------------------------------- pages
def page_dashboard():
    st.header("Dashboard")
    m = db.fetch_df("""
        SELECT (SELECT COUNT(*) FROM seminar_halls WHERE is_active)          AS active_halls,
               (SELECT COUNT(*) FROM booking_requests)                       AS total_requests,
               (SELECT COUNT(*) FROM booking_requests WHERE status = 'ALLOCATED') AS allocated,
               (SELECT COUNT(*) FROM booking_requests WHERE status = 'PENDING')   AS pending,
               (SELECT COUNT(*) FROM allocations
                 WHERE booking_date BETWEEN CURDATE() AND CURDATE() + INTERVAL 7 DAY) AS next_7_days
    """).iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Active halls", int(m.active_halls))
    c2.metric("Total requests", int(m.total_requests))
    c3.metric("Success rate", f"{100 * m.allocated / max(m.total_requests, 1):.1f}%")
    c4.metric("Waiting for approval", int(m.pending))
    c5.metric("Bookings in next 7 days", int(m.next_7_days))
    if m.pending:
        st.warning(f"**{int(m.pending)} request(s) are waiting for approval.** Open the Approvals page.")

    st.subheader("Freed slots (visible to everyone)")
    show_freed_board()

    st.subheader(f"Today's schedule ({date.today():%d %b %Y})")
    show_grid(date.today())

    st.subheader("Latest requests")
    st.dataframe(db.fetch_df("""
        SELECT request_id, booking_date, slot_label, hall_name, event_name,
               student_name, status, remarks
        FROM v_booking_details
        ORDER BY requested_at DESC
        LIMIT 10"""), hide_index=True)


def page_book():
    st.header("Request a Seminar Hall")
    srn = logged_in_student()
    st.write("Pick the date and slot first. The hall list shows which halls are free. "
             "Halls are used 9:00 to 16:00 in 2-hour slots with a 30-minute gap. A request "
             "holds the hall until the seminar hall coordinator approves it.")
    with st.expander("Freed slots (cancelled bookings anyone can take)", expanded=True):
        show_freed_board()

    result = st.session_state.pop("last_result", None)
    if result:
        show_booking_result(result)

    c1, c2 = st.columns(2)
    booking_date = c1.date_input("Date", value=date.today(), min_value=date.today(),
                                 max_value=date.today() + timedelta(days=90))
    slots_df = open_slots(booking_date)
    if slots_df.empty:
        c2.selectbox("Time slot", ["No slots left today"], disabled=True)
        st.info("All of today's slots have already started. Please pick another date.")
        return
    slots = dict(zip(slots_df.slot_id.tolist(), slots_df.slot_label.tolist()))
    slot_id = c2.selectbox("Time slot", list(slots), format_func=slots.get)

    halls = db.fetch_df("""
        SELECT h.hall_id, h.hall_name, h.capacity, h.has_ac, h.is_active,
               EXISTS (SELECT 1 FROM allocations a
                       WHERE a.hall_id = h.hall_id
                         AND a.booking_date = %s
                         AND a.slot_id = %s) AS is_booked
        FROM seminar_halls h
        ORDER BY h.is_active DESC, is_booked, h.capacity""", (booking_date, slot_id))
    hall_names = dict(zip(halls.hall_id.tolist(), halls.hall_name.tolist()))
    hall_labels = {}
    for h in halls.itertuples():
        state = "under maintenance" if not h.is_active else ("BOOKED" if h.is_booked else "FREE")
        ac = "AC" if h.has_ac else "non-AC"
        hall_labels[int(h.hall_id)] = f"{state}  ·  {h.hall_name}  ·  {h.capacity} seats  ·  {ac}"
    free_count = sum(1 for h in halls.itertuples() if h.is_active and not h.is_booked)
    st.caption(f"{free_count} of {len(halls)} halls are free on {booking_date:%d %b} at {slots[slot_id]}. "
               "Not sure which hall fits? See the Hall details page.")

    faculty = faculty_options()
    with st.form("booking_form"):
        st.text_input("Student", value=f"{srn} - {st.session_state['name']}", disabled=True)
        hall_id = st.selectbox("Seminar hall", list(hall_labels), format_func=hall_labels.get)
        event_name = st.text_input("Event name")
        c1, c2 = st.columns(2)
        event_type = c1.selectbox("Event type", EVENT_TYPES)
        attendees = c2.number_input("Expected attendees", min_value=1, value=50, step=5)
        faculty_id = st.selectbox("Faculty coordinator", list(faculty), format_func=faculty.get)

        st.markdown("**Extra event details** (optional, saved as a JSON document in the NoSQL store)")
        equipment = st.multiselect("Equipment needed", EQUIPMENT)
        c1, c2 = st.columns(2)
        speaker = c1.text_input("Speaker / chief guest")
        organisation = c2.text_input("Speaker's organisation")
        tags = st.text_input("Tags (comma separated)")
        notes = st.text_area("Notes for the hall staff")
        submitted = st.form_submit_button("Request booking", type="primary")

    if submitted:
        if not event_name.strip():
            st.warning("Please enter the event name.")
            return
        try:
            request_id, status, message = db.request_booking(
                srn, hall_id, slot_id, booking_date, event_name.strip(), event_type,
                int(attendees), faculty_id)
        except mysql.connector.Error as e:
            st.error(f"Database error: {e}")
            return

        # NoSQL: only the fields the student filled in go into the document
        details = {"request_id": request_id, "event_type": event_type, "submitted_by": srn,
                   "created_at": now_iso(), "equipment": equipment}
        if speaker.strip():
            details["speaker"] = {"name": speaker.strip()}
            if organisation.strip():
                details["speaker"]["organisation"] = organisation.strip()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            details["tags"] = tag_list
        if notes.strip():
            details["notes"] = notes.strip()
        log = {"action": "REQUEST", "logged_at": now_iso(), "srn": srn,
               "request": {"hall_id": hall_id, "hall_name": hall_names[hall_id], "slot_id": slot_id,
                           "booking_date": str(booking_date), "attendees": int(attendees)},
               "result": {"request_id": request_id, "status": status, "message": message}}
        if status == "REJECTED" and booking_date >= date.today():
            log["alternatives_suggested"] = free_halls(booking_date, slot_id, int(attendees)).hall_name.tolist()
        try:
            nosql.save_event_details(details)
            nosql.log_action(log)
            nosql_error = None
        except mysqlx.Error as e:
            nosql_error = str(e)

        st.session_state["last_result"] = {
            "request_id": request_id, "status": status, "message": message,
            "date": booking_date, "slot_id": slot_id, "hall_id": hall_id,
            "attendees": int(attendees),
            "call": (f"CALL request_booking('{srn}', {hall_id}, {slot_id}, '{booking_date}', "
                     f"'{event_name.strip()}', '{event_type}', {int(attendees)}, {faculty_id}, "
                     f"@id, @status, @msg);"),
            "details": details, "nosql_error": nosql_error,
        }
        st.rerun()


def show_booking_result(r):
    if r["status"] == "PENDING":
        st.success(f"Request #{r['request_id']}: hall HELD (PENDING). {r['message']}. "
                   "Nobody else can book it while the coordinator decides.")
    elif r["status"] == "ALLOCATED":
        st.success(f"Request #{r['request_id']}: ALLOCATED. {r['message']}.")
    else:
        st.error(f"Request #{r['request_id']}: REJECTED. {r['message']}.")
        if r["date"] >= date.today():
            slots = slot_options()
            alternatives = free_halls(r["date"], r["slot_id"], r["attendees"])
            st.write(f"**Other halls free on {r['date']:%d %b} at {slots[r['slot_id']]} "
                     f"that fit {r['attendees']} people:**")
            if alternatives.empty:
                st.write("None. Try another slot.")
            else:
                st.dataframe(alternatives, hide_index=True)
            free_slots = db.fetch_df("""
                SELECT t.slot_label
                FROM time_slots t
                WHERE (%s > CURDATE() OR (%s = CURDATE() AND t.start_time > CURTIME()))
                  AND NOT EXISTS (SELECT 1 FROM allocations a
                                  WHERE a.slot_id = t.slot_id
                                    AND a.hall_id = %s
                                    AND a.booking_date = %s)
                ORDER BY t.slot_id""", (r["date"], r["date"], r["hall_id"], r["date"]))
            st.write("**Free slots in the hall you asked for, same day:** "
                     + (", ".join(free_slots.slot_label) or "none"))
    with st.expander("SQL that was executed"):
        st.code(r["call"] + "\nSELECT @id, @status, @msg;", language="sql")
    if r["nosql_error"]:
        st.warning(f"Booking saved in MySQL, but the NoSQL documents were not saved: {r['nosql_error']}")
    else:
        with st.expander("NoSQL document saved in event_details"):
            st.code("db.event_details.add(doc)", language="javascript")
            st.json(r["details"])


def page_availability():
    st.header("Hall Availability")
    earliest = None if st.session_state["role"] == "admin" else date.today()
    day = st.date_input("Show schedule for", value=date.today(), min_value=earliest)
    st.caption("Green = free · bold green = freed by a cancellation · yellow = held, awaiting "
               "approval · red = booked · grey = time over or under maintenance")
    show_grid(day)

    st.subheader("Find a free hall")
    slots_df = open_slots(day)
    if slots_df.empty:
        st.info("No bookable slots left on this date. Pick a later date.")
        return
    slots = dict(zip(slots_df.slot_id.tolist(), slots_df.slot_label.tolist()))
    c1, c2, c3 = st.columns(3)
    slot_id = c1.selectbox("Time slot", list(slots), format_func=slots.get)
    min_capacity = c2.number_input("At least this many seats", min_value=1, value=50, step=10)
    need_ac = c3.checkbox("AC only")
    result = free_halls(day, slot_id, int(min_capacity))
    if need_ac:
        result = result[result.ac == "Yes"]
    if result.empty:
        st.info("No hall is free for that slot and size.")
    else:
        st.dataframe(result, hide_index=True)


def page_hall_details():
    st.header("Hall Details")
    st.write("Compare the halls and pick the one that suits your event.")
    halls = db.fetch_df("""
        SELECT h.hall_id, h.hall_name, h.block, h.floor_no, h.capacity, h.has_ac,
               h.has_projector, h.is_active, c.name AS coordinator, c.email AS coordinator_email
        FROM seminar_halls h
        JOIN hall_coordinators c ON c.coordinator_id = h.coordinator_id
        ORDER BY h.capacity DESC""")

    c1, c2, c3, c4 = st.columns(4)
    min_seats = c1.number_input("Seats needed", min_value=1, value=1, step=10)
    need_ac = c2.checkbox("AC")
    need_projector = c3.checkbox("Projector")
    hide_closed = c4.checkbox("Hide halls under maintenance", value=True)
    check_day = st.date_input("Show free slots on", value=date.today(), min_value=date.today())

    shown = halls[halls.capacity >= min_seats]
    if need_ac:
        shown = shown[shown.has_ac == 1]
    if need_projector:
        shown = shown[shown.has_projector == 1]
    if hide_closed:
        shown = shown[shown.is_active == 1]
    st.caption(f"{len(shown)} of {len(halls)} halls match.")
    if shown.empty:
        st.info("No hall matches. Try fewer seats or remove a filter.")
        return

    slots_df = open_slots(check_day)
    taken = db.fetch_df("SELECT hall_id, slot_id FROM allocations WHERE booking_date = %s", (check_day,))
    taken = set(zip(taken.hall_id, taken.slot_id))
    cols = st.columns(3)
    for i, h in enumerate(shown.itertuples()):
        with cols[i % 3].container(border=True):
            st.subheader(h.hall_name)
            st.caption(f"{h.block} · floor {h.floor_no}")
            m1, m2 = st.columns(2)
            m1.metric("Seats", int(h.capacity))
            m2.metric("AC", "Yes" if h.has_ac else "No")
            st.write(f"**Projector:** {'Yes' if h.has_projector else 'No'}  \n"
                     f"**Coordinator:** {h.coordinator}  \n{h.coordinator_email}")
            if not h.is_active:
                st.error("Under maintenance - cannot be booked")
                continue
            free = [s.slot_label for s in slots_df.itertuples() if (h.hall_id, s.slot_id) not in taken]
            if free:
                st.success(f"Free on {check_day:%d %b}: " + ", ".join(free))
            else:
                st.warning(f"No free slots on {check_day:%d %b}")

    with st.expander("Compare all halls in one table"):
        table = halls.assign(ac=halls.has_ac.map({1: "Yes", 0: "No"}),
                             projector=halls.has_projector.map({1: "Yes", 0: "No"}),
                             status=halls.is_active.map({1: "Available", 0: "Under maintenance"}))
        st.dataframe(table[["hall_name", "block", "floor_no", "capacity", "ac", "projector", "status",
                            "coordinator"]], hide_index=True)


def page_my_bookings():
    st.header("My Bookings")
    message = st.session_state.pop("cancel_message", None)
    if message:
        st.success(message)

    srn = logged_in_student()
    st.write(f"Bookings of **{st.session_state['name']}** ({srn})")
    wanted = open_freed_slots(srn)
    if not wanted.empty:
        st.success("**Good news: a hall you were refused earlier is free again.** "
                   "Someone cancelled, so you can book it now on the Book a hall page.")
        st.dataframe(wanted, hide_index=True)
    history = db.fetch_df("""
        SELECT request_id, booking_date, slot_label, hall_name, event_name,
               expected_attendees, coordinator, status, remarks, reviewed_by
        FROM v_booking_details
        WHERE srn = %s
        ORDER BY booking_date DESC""", (srn,))
    counts = history.status.value_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Requests", len(history))
    c2.metric("Approved", int(counts.get("ALLOCATED", 0)))
    c3.metric("Waiting for approval", int(counts.get("PENDING", 0)))
    c4.metric("Rejected / cancelled", int(counts.get("REJECTED", 0) + counts.get("CANCELLED", 0)))
    if history.empty:
        st.info("You have not requested a hall yet. Use Book a hall to make your first request.")
        return
    st.dataframe(history.style.map(status_colour, subset=["status"]), hide_index=True)

    if not history.empty:
        st.subheader("Event details (from the NoSQL store)")
        events = {int(r.request_id): f"#{r.request_id}  {r.booking_date}  {r.event_name}"
                  for r in history.itertuples()}
        chosen = st.selectbox("Request", list(events), format_func=events.get, key="details_request")
        try:
            doc = nosql.event_details_for(chosen)
            if doc:
                st.json(doc)
            else:
                st.caption("No NoSQL document for this request.")
        except mysqlx.Error as e:
            st.warning(f"NoSQL store not reachable: {e}")

    upcoming = db.fetch_df("""
        SELECT request_id, booking_date, slot_label, hall_name, event_name, status
        FROM v_booking_details
        WHERE srn = %s AND status IN ('PENDING', 'ALLOCATED') AND booking_date >= CURDATE()
        ORDER BY booking_date""", (srn,))
    if upcoming.empty:
        st.caption("No upcoming bookings to cancel.")
        return
    st.subheader("Cancel an upcoming booking")
    labels = {int(r.request_id): f"#{r.request_id}  {r.booking_date}  {r.slot_label}  "
                                 f"{r.hall_name}  ({r.event_name}, {r.status})" for r in upcoming.itertuples()}
    request_id = st.selectbox("Booking", list(labels), format_func=labels.get)
    if st.button("Cancel booking"):
        db.execute("""
            UPDATE booking_requests
            SET status = 'CANCELLED', remarks = 'Cancelled by student'
            WHERE request_id = %s AND status IN ('PENDING', 'ALLOCATED')""", (request_id,))
        st.session_state["cancel_message"] = (
            f"Booking #{request_id} cancelled. Trigger trg_free_hall_on_cancel removed its "
            "row from allocations and published the slot in freed_slots, so every student "
            "can now see that the hall is free again.")
        row = upcoming[upcoming.request_id == request_id].iloc[0]
        try:
            nosql.log_action({"action": "CANCEL", "logged_at": now_iso(), "srn": srn,
                              "request_id": request_id,
                              "freed_slot": {"hall_name": row.hall_name, "booking_date": str(row.booking_date),
                                             "slot": row.slot_label}})
        except mysqlx.Error:
            pass
        st.rerun()


def page_coordinator():
    st.header("Approvals (Seminar Hall Coordinator)")
    st.write("Every request that passes the rules holds the hall as PENDING. The coordinator "
             "in charge of the hall approves or rejects it. A rejection frees the hall and "
             "publishes the slot to everyone.")
    message = st.session_state.pop("review_message", None)
    if message:
        st.success(message)

    coordinators = coordinator_options()
    coordinator_id = st.selectbox("Coordinator", list(coordinators), format_func=coordinators.get)
    st.caption("Halls in charge: " + ", ".join(db.fetch_df(
        "SELECT hall_name FROM seminar_halls WHERE coordinator_id = %s ORDER BY hall_id",
        (coordinator_id,)).hall_name))

    pending = db.fetch_df("""
        SELECT v.request_id, v.booking_date, v.slot_label, v.hall_name, v.event_name,
               v.event_type, v.expected_attendees, v.capacity, v.student_name,
               v.coordinator AS faculty, v.requested_at
        FROM v_booking_details v
        JOIN seminar_halls h ON h.hall_name = v.hall_name
        WHERE v.status = 'PENDING' AND h.coordinator_id = %s
        ORDER BY v.booking_date, v.request_id""", (coordinator_id,))
    st.subheader(f"Waiting for your approval ({len(pending)})")
    if pending.empty:
        st.caption("Nothing to review.")
    else:
        st.dataframe(pending, hide_index=True)
        labels = {int(r.request_id): f"#{r.request_id}  {r.booking_date}  {r.slot_label}  "
                                     f"{r.hall_name}  ({r.event_name})" for r in pending.itertuples()}
        request_id = st.selectbox("Request", list(labels), format_func=labels.get)
        reason = st.text_input("Reason (needed when rejecting)")
        c1, c2 = st.columns(2)
        approve = c1.button("Approve", type="primary")
        reject = c2.button("Reject")
        if reject and not reason.strip():
            st.warning("Please type a reason before rejecting.")
        elif approve or reject:
            status, msg = db.review_booking(request_id, coordinator_id, approve, reason.strip())
            log = {"action": "REVIEW", "logged_at": now_iso(), "coordinator_id": coordinator_id,
                   "request_id": request_id, "decision": "APPROVED" if approve else "REJECTED"}
            if reject:
                log["reason"] = reason.strip()
            try:
                nosql.log_action(log)
            except mysqlx.Error:
                pass
            extra = ("" if approve else " Trigger trg_free_hall_on_cancel freed the hall and "
                     "published the slot in freed_slots.")
            st.session_state["review_message"] = f"Request #{request_id}: {status}. {msg}.{extra}"
            st.rerun()

    st.subheader("Your recent decisions")
    st.dataframe(db.fetch_df("""
        SELECT r.request_id, r.booking_date, h.hall_name, r.event_name, r.status, r.remarks,
               r.reviewed_at
        FROM booking_requests r
        JOIN seminar_halls h ON h.hall_id = r.hall_id
        WHERE r.reviewed_by = %s
        ORDER BY r.reviewed_at DESC
        LIMIT 10""", (coordinator_id,)), hide_index=True)


def page_all_bookings():
    st.header("All Bookings")
    message = st.session_state.pop("admin_message", None)
    if message:
        st.success(message)

    halls = hall_options()
    c1, c2, c3, c4 = st.columns(4)
    start = c1.date_input("From", value=date.today())
    end = c2.date_input("To", value=date.today() + timedelta(days=30))
    hall = c3.selectbox("Hall", ["All halls"] + list(halls.values()))
    statuses = c4.multiselect("Status", ["PENDING", "ALLOCATED", "REJECTED", "CANCELLED"],
                              default=["PENDING", "ALLOCATED"])
    search = st.text_input("Search by event, student name or SRN")

    sql = """
        SELECT request_id, booking_date, slot_label, hall_name, event_name, event_type,
               expected_attendees, srn, student_name, dept_code, status, remarks, reviewed_by
        FROM v_booking_details
        WHERE booking_date BETWEEN %s AND %s"""
    params = [start, end]
    if hall != "All halls":
        sql += " AND hall_name = %s"
        params.append(hall)
    if statuses:
        sql += " AND status IN (" + ", ".join(["%s"] * len(statuses)) + ")"
        params += statuses
    if search.strip():
        sql += " AND (event_name LIKE %s OR student_name LIKE %s OR srn LIKE %s)"
        params += [f"%{search.strip()}%"] * 3
    df = db.fetch_df(sql + " ORDER BY booking_date, slot_label, hall_name", tuple(params))

    counts = df.status.value_counts()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Bookings found", len(df))
    m2.metric("Approved", int(counts.get("ALLOCATED", 0)))
    m3.metric("Waiting for approval", int(counts.get("PENDING", 0)))
    m4.metric("Expected attendees", int(df.expected_attendees.sum()) if not df.empty else 0)
    st.dataframe(df.style.map(status_colour, subset=["status"]), hide_index=True)
    st.download_button("Download as CSV", df.to_csv(index=False), "bookings.csv", "text/csv")

    active = df[df.status.isin(["PENDING", "ALLOCATED"]) & (df.booking_date >= date.today())]
    if active.empty:
        return
    st.subheader("Cancel a booking (admin)")
    labels = {int(r.request_id): f"#{r.request_id}  {r.booking_date}  {r.slot_label}  {r.hall_name}  "
                                 f"({r.event_name}, {r.srn})" for r in active.itertuples()}
    request_id = st.selectbox("Booking", list(labels), format_func=labels.get)
    reason = st.text_input("Reason (shown to the student)")
    if st.button("Cancel this booking"):
        if not reason.strip():
            st.warning("Please type a reason.")
            return
        db.execute("""
            UPDATE booking_requests
            SET status = 'CANCELLED', remarks = %s
            WHERE request_id = %s AND status IN ('PENDING', 'ALLOCATED')""",
                   (f"Cancelled by admin: {reason.strip()}", request_id))
        try:
            nosql.log_action({"action": "CANCEL", "logged_at": now_iso(), "by": st.session_state["user"],
                              "request_id": request_id, "reason": reason.strip()})
        except mysqlx.Error:
            pass
        st.session_state["admin_message"] = (
            f"Booking #{request_id} cancelled. The trigger freed the hall and published the slot.")
        st.rerun()


def page_reports():
    st.header("Reports")
    reports = load_reports()
    titles = [r["title"] for r in reports]
    report = reports[titles.index(st.selectbox("Choose a report", titles))]

    st.subheader(report["title"])
    st.caption(report["about"])
    df = db.fetch_df(report["sql"])
    if report["chart"] and not df.empty:
        bar_chart(df, *report["chart"])
    st.dataframe(df, hide_index=True)
    st.download_button("Download as CSV", df.to_csv(index=False),
                       report["title"].split(".")[0] + ".csv", "text/csv")
    with st.expander("SQL query"):
        st.code(report["sql"] + ";", language="sql")


def page_nosql():
    st.header("NoSQL: MySQL Document Store")
    st.write("These collections hold schemaless JSON documents, written and read with the "
             "X DevAPI (add / find / modify / remove) instead of SQL. Each document points "
             "back to MySQL through its `request_id`.")
    if not nosql.is_available():
        st.error(f"Document Store is not reachable on port {nosql.X_PORT}.")
        return
    message = st.session_state.pop("nosql_message", None)
    if message:
        st.success(message)

    tab_events, tab_logs, tab_reports = st.tabs(["event_details", "booking_logs", "NoSQL reports"])

    with tab_events:
        st.caption("Documents have different fields depending on the event type. That is why "
                   "this data lives in a document store instead of a fixed table.")
        c1, c2 = st.columns(2)
        event_type = c1.selectbox("Event type", ["(any)"] + EVENT_TYPES)
        equipment = c2.selectbox("Needs equipment", ["(any)"] + EQUIPMENT)
        docs, shell = nosql.search_event_details(None if event_type == "(any)" else event_type,
                                                 None if equipment == "(any)" else equipment)
        st.code(shell, language="javascript")
        st.write(f"**{len(docs)} documents** (up to 50). Empty cells = field not present in that document.")
        if docs:
            table = pd.json_normalize(docs).drop(columns="_id")
            first = [c for c in ["request_id", "event_type", "submitted_by"] if c in table.columns]
            st.dataframe(table[first + [c for c in table.columns if c not in first]], hide_index=True)
            with st.expander("Raw JSON of the first document"):
                st.json(docs[0])

        st.subheader("Add a tag to an event (modify)")
        c1, c2 = st.columns(2)
        tag_request = c1.number_input("Request id", min_value=1, step=1, value=1)
        tag = c2.text_input("Tag")
        if st.button("Add tag") and tag.strip():
            changed = nosql.add_tag(int(tag_request), tag.strip())
            st.session_state["nosql_message"] = (
                f"Tag '{tag.strip()}' added to request {int(tag_request)}." if changed
                else f"No document found for request {int(tag_request)}.")
            st.rerun()

    with tab_logs:
        st.caption("Append-only log. A REQUEST entry and a CANCEL entry store different fields.")
        st.code('db.booking_logs.find().sort("logged_at DESC").limit(20)', language="javascript")
        logs = nosql.latest_logs(20)
        for log in logs:
            with st.expander(f"{log['logged_at']}   {log['action']}   {log.get('srn', '')}"):
                st.json(log)
        if logs:
            st.subheader("Delete a log document (remove)")
            ids = {log["_id"]: f"{log['logged_at']}  {log['action']}  ({log['_id']})" for log in logs}
            doc_id = st.selectbox("Document", list(ids), format_func=ids.get)
            if st.button("Delete document"):
                nosql.delete_log(doc_id)
                st.session_state["nosql_message"] = f"Log document {doc_id} removed."
                st.rerun()

    with tab_reports:
        st.subheader("N1. Documents per event type (groupBy)")
        st.code('db.event_details.find().fields("event_type", "COUNT(_id) AS documents")'
                '.groupBy("event_type")', language="javascript")
        df = pd.DataFrame(nosql.documents_per_event_type())
        bar_chart(df, "event_type", "documents")
        st.dataframe(df, hide_index=True)

        st.subheader("N2. Booking log summary (groupBy on a nested field)")
        st.code('db.booking_logs.find().fields("action", "result.status AS status", "COUNT(_id) AS total")'
                '.groupBy("action", "result.status")', language="javascript")
        df = pd.DataFrame(nosql.log_summary())
        df["status"] = df["status"].fillna("-")
        df["action_status"] = df["action"] + " / " + df["status"]
        bar_chart(df, "action_status", "total")
        st.dataframe(df[["action", "status", "total"]], hide_index=True)

        st.subheader("N3. Most requested equipment (array field)")
        st.code('db.event_details.find().fields("equipment")   // then counted in Python',
                language="javascript")
        df = pd.DataFrame(nosql.equipment_demand())
        bar_chart(df, "equipment", "events")
        st.dataframe(df, hide_index=True)


def page_admin():
    st.header("Manage")
    tab_view, tab_student, tab_hall, tab_maint, tab_slots = st.tabs(
        ["View tables", "Add student", "Add hall", "Hall maintenance", "Time slots"])

    with tab_view:
        table = st.selectbox("Table", TABLES)
        st.dataframe(db.fetch_df(f"SELECT * FROM {table}"), hide_index=True)

    with tab_student:
        depts = department_options()
        with st.form("add_student", clear_on_submit=True):
            srn = st.text_input("SRN (e.g. PES1UG24AM100)")
            name = st.text_input("Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone (10 digits)")
            c1, c2 = st.columns(2)
            semester = c1.number_input("Semester", min_value=1, max_value=8, value=5)
            dept_id = c2.selectbox("Department", list(depts), format_func=depts.get)
            if st.form_submit_button("Add student"):
                try:
                    db.execute("""
                        INSERT INTO students (srn, name, email, phone, semester, dept_id)
                        VALUES (%s, %s, %s, %s, %s, %s)""",
                        (srn.strip().upper(), name.strip(), email.strip(), phone.strip() or None,
                         int(semester), dept_id))
                    st.success(f"Student {srn.strip().upper()} added.")
                except mysql.connector.Error as e:
                    st.error(f"Could not add student: {e}")

    with tab_hall:
        with st.form("add_hall", clear_on_submit=True):
            hall_name = st.text_input("Hall name")
            c1, c2, c3 = st.columns(3)
            block = c1.text_input("Block")
            floor_no = c2.number_input("Floor", min_value=0, max_value=20, value=0)
            capacity = c3.number_input("Capacity", min_value=1, value=100, step=10)
            has_projector = st.checkbox("Has projector", value=True)
            has_ac = st.checkbox("Has AC")
            coordinators = coordinator_options()
            coordinator_id = st.selectbox("Hall coordinator", list(coordinators),
                                          format_func=coordinators.get)
            if st.form_submit_button("Add hall"):
                try:
                    db.execute("""
                        INSERT INTO seminar_halls (hall_name, block, floor_no, capacity, has_projector,
                                                   has_ac, coordinator_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (hall_name.strip(), block.strip(), int(floor_no), int(capacity),
                         has_projector, has_ac, coordinator_id))
                    st.success(f"Hall '{hall_name.strip()}' added.")
                except mysql.connector.Error as e:
                    st.error(f"Could not add hall: {e}")

    with tab_maint:
        st.write("Halls under maintenance cannot be allocated.")
        halls = hall_options()
        hall_id = st.selectbox("Hall", list(halls), format_func=halls.get, key="maint_hall")
        active = db.fetch_df("SELECT is_active FROM seminar_halls WHERE hall_id = %s",
                             (hall_id,)).is_active[0]
        st.write("Current state: " + ("**available**" if active else "**under maintenance**"))
        label = "Mark under maintenance" if active else "Mark available"
        if st.button(label):
            db.execute("UPDATE seminar_halls SET is_active = NOT is_active WHERE hall_id = %s",
                       (hall_id,))
            st.rerun()

    with tab_slots:
        st.write("College rules, enforced by the database: slots lie between 09:00 and 16:00 "
                 "(CHECK), last at most 2 hours (CHECK), and need a 30-minute gap between them "
                 "(trigger trg_slot_gap_insert). Try adding a slot that breaks a rule.")
        st.dataframe(db.fetch_df("SELECT * FROM time_slots ORDER BY start_time"), hide_index=True)
        with st.form("add_slot"):
            c1, c2 = st.columns(2)
            start = c1.time_input("Start", value=datetime.strptime("15:00", "%H:%M").time())
            end = c2.time_input("End", value=datetime.strptime("17:00", "%H:%M").time())
            if st.form_submit_button("Add slot"):
                try:
                    db.execute("""
                        INSERT INTO time_slots (slot_label, start_time, end_time)
                        VALUES (%s, %s, %s)""",
                        (f"{start:%H:%M} - {end:%H:%M}", start, end))
                    st.success("Slot added.")
                except mysql.connector.Error as e:
                    st.error(f"Rejected by the database: {e.msg}")


# ---------------------------------------------------------------- main
# Students see only what they need; admins see everything
STUDENT_PAGES = {
    "Book a hall": page_book,
    "Hall availability": page_availability,
    "Hall details": page_hall_details,
    "My bookings": page_my_bookings,
}
ADMIN_PAGES = {
    "Dashboard": page_dashboard,
    "Approvals": page_coordinator,
    "All bookings": page_all_bookings,
    "Hall availability": page_availability,
    "Hall details": page_hall_details,
    "Reports": page_reports,
    "NoSQL documents": page_nosql,
    "Manage": page_admin,
}

try:
    db.fetch_df("SELECT 1")
except mysql.connector.Error as e:
    st.error(f"Cannot connect to MySQL: {e}")
    st.info("Start the MySQL80 service, then run `python setup_db.py` once.")
    st.stop()

# Not logged in: only the login page exists (no sidebar, no other pages)
if "user" not in st.session_state:
    page_login()
    st.stop()

pages = ADMIN_PAGES if st.session_state["role"] == "admin" else STUDENT_PAGES
st.sidebar.title("Seminar Hall Booking")
st.sidebar.success(f"**{st.session_state['name']}**  \n{st.session_state['user']} · "
                   f"{st.session_state['role'].title()}")
st.sidebar.button("Log out", on_click=logout, width="stretch")
choice = st.sidebar.radio("Go to", list(pages))
st.sidebar.caption("RDBMS: MySQL tables (SQL)\n\nNoSQL: MySQL Document Store (X DevAPI)")

pages[choice]()
