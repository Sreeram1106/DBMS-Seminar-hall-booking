"""University Seminar Hall Booking System - Streamlit front end.

Run:  streamlit run app.py
"""
import re
import socket
from datetime import date, datetime, timedelta
from pathlib import Path

import altair as alt
import mysql.connector
import mysqlx
import pandas as pd
import streamlit as st

import db
import nosql

st.set_page_config(page_title="Seminar Hall Booking", page_icon=":material/meeting_room:",
                   layout="wide")
ASSETS = Path(__file__).parent / "assets"

# Extra styling on top of the theme in .streamlit/config.toml
st.markdown("""
<style>
:root {
    --accent: #0F6E56; --accent-soft: #E1F5EE; --accent-line: #9FE1CB; --accent-ink: #085041;
    --ink: #1C2430; --muted: #5F6B7A; --line: #E4E7EB; --card: #FFFFFF; --soft: #F4F6F8;
    --ok-bg: #EAF3DE; --ok-ink: #27500A; --warn-bg: #FAEEDA; --warn-ink: #633806;
    --bad-bg: #FCEBEB; --bad-ink: #791F1F; --gray-bg: #F1EFE8; --gray-ink: #5F5E5A;
}
header[data-testid="stHeader"] {border-bottom: 1px solid var(--line);}
.block-container {padding-top: 4.6rem; padding-bottom: 3rem; max-width: 1180px;}
h1, h2, h3, h4 {color: var(--ink);}
[data-testid="stMetric"] {background: var(--card); border: 1px solid var(--line); border-radius: 14px;
    padding: 14px 16px; box-shadow: 0 1px 2px rgba(16, 24, 40, .05);}
[data-testid="stMetricLabel"] p {color: var(--muted); font-weight: 500; font-size: .82rem;
    white-space: normal; line-height: 1.25;}
[data-testid="stMetricValue"] {color: var(--ink); font-weight: 700; font-size: 1.7rem;}
[data-testid="stMetricValue"] div {overflow: visible; text-overflow: clip;}
[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden; border: 1px solid var(--line);}
.page-head {padding: 4px 0 16px; margin: 4px 0 20px; border-bottom: 1px solid var(--line);}
.page-head .eyebrow {display: inline-block; font-size: .72rem; font-weight: 700; letter-spacing: .06em;
    text-transform: uppercase; color: var(--accent-ink); background: var(--accent-soft);
    padding: 3px 10px; border-radius: 999px;}
.page-head h1 {font-size: 2rem; margin: 10px 0 4px; padding: 0; color: var(--ink);}
.page-head p {color: var(--muted); margin: 0; font-size: 1rem; max-width: 780px;}
.acct {display: flex; align-items: center; gap: 12px;}
.avatar {flex: 0 0 42px; height: 42px; border-radius: 50%; background: var(--accent-soft);
    color: var(--accent-ink); display: flex; align-items: center; justify-content: center; font-weight: 700;}
.acct b {display: block; color: var(--ink); font-size: .98rem; line-height: 1.25;}
.acct .who {color: var(--muted); font-size: .8rem;}
.role {display: inline-block; margin-left: 8px; background: var(--accent-soft); color: var(--accent-ink);
    border-radius: 999px; padding: 1px 9px; font-size: .66rem; font-weight: 700; letter-spacing: .05em;
    vertical-align: 2px;}
.live {display: flex; align-items: center; gap: 10px; background: var(--card); border: 1px solid var(--line);
    border-radius: 999px; padding: 5px 14px 5px 5px; width: fit-content;}
.live .num {min-width: 30px; height: 30px; border-radius: 999px; background: var(--warn-bg);
    color: var(--warn-ink); display: flex; align-items: center; justify-content: center;
    font-weight: 700; padding: 0 8px;}
.live.calm .num {background: var(--ok-bg); color: var(--ok-ink);}
.live .txt {color: var(--ink); font-size: .84rem; line-height: 1.2;}
.live-meta {color: var(--muted); font-size: .7rem; margin: 4px 0 0 8px;}
.hero {background: var(--accent-soft); border-radius: 22px; padding: 40px 38px; min-height: 470px;}
.hero h1 {color: var(--accent-ink); font-size: 2.35rem; line-height: 1.15; margin: 16px 0 10px;}
.hero h1 em {font-style: normal; color: var(--accent);}
.hero p.lead {color: var(--accent); font-size: 1.04rem; margin-bottom: 24px;}
.hero .tag {display: inline-block; background: var(--card); color: var(--accent-ink); border-radius: 999px;
    padding: 5px 14px; font-size: .72rem; font-weight: 700; letter-spacing: .06em;}
.feature {display: flex; gap: 14px; align-items: flex-start; margin: 18px 0;}
.feature .dot {flex: 0 0 38px; height: 38px; border-radius: 12px; background: var(--card); color: var(--accent);
    border: 1px solid var(--accent-line); display: flex; align-items: center; justify-content: center;
    font-weight: 800;}
.feature b {display: block; color: var(--accent-ink); font-size: 1rem;}
.feature span {color: var(--accent); font-size: .9rem;}
.badge {display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: .74rem;
    font-weight: 600; margin: 0 6px 6px 0;}
.badge.ok {background: var(--ok-bg); color: var(--ok-ink);}
.badge.ac {background: var(--accent-soft); color: var(--accent-ink);}
.badge.no {background: var(--gray-bg); color: var(--gray-ink);}
.badge.warn {background: var(--warn-bg); color: var(--warn-ink);}
.badge.bad {background: var(--bad-bg); color: var(--bad-ink);}
.hall-band {height: 62px; border-radius: 10px; background: var(--accent-soft); margin-bottom: 12px;
    display: flex; align-items: center; justify-content: space-between; padding: 0 12px;}
.hall-band .badge {background: var(--card); margin: 0; border: 1px solid var(--accent-line);}
.hall-cap {font-size: 1.9rem; font-weight: 700; color: var(--ink); line-height: 1;}
.hall-cap small {font-size: .82rem; font-weight: 500; color: var(--muted);}
.pick-name {font-weight: 700; font-size: 1.02rem; color: var(--ink); margin-bottom: 4px;}
.pick-meta {color: var(--muted); font-size: .8rem; margin: 3px 0 8px;}
.track {background: var(--card); border: 1px solid var(--line); border-radius: 14px;
    padding: 14px 18px; margin-bottom: 10px;}
.track .title {font-weight: 700; color: var(--ink); margin-bottom: 10px;}
.track .title span {color: var(--muted); font-weight: 500; font-size: .85rem;}
.steps {display: flex; align-items: center; gap: 8px; flex-wrap: wrap;}
.step {display: flex; align-items: center; gap: 8px; font-size: .86rem; color: var(--muted);}
.step .b {width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-weight: 800; font-size: .8rem; background: var(--gray-bg); color: var(--gray-ink);}
.step.done .b {background: var(--accent); color: #FFFFFF;}
.step.done {color: var(--accent-ink); font-weight: 600;}
.step.now .b {background: var(--warn-bg); color: var(--warn-ink); border: 1px solid #FAC775;}
.step.now {color: var(--warn-ink); font-weight: 700;}
.step.bad .b {background: var(--bad-ink); color: #FFFFFF;}
.step.bad {color: var(--bad-ink); font-weight: 700;}
.bar {flex: 0 0 34px; height: 3px; border-radius: 2px; background: var(--line);}
.bar.done {background: var(--accent);}
.bk-step {display: flex; align-items: center; gap: 12px; margin: 24px 0 10px;
    font-family: 'Plus Jakarta Sans', Inter, sans-serif; font-weight: 700; font-size: 1.1rem; color: var(--ink);}
.bk-step .n {width: 28px; height: 28px; border-radius: 50%; background: var(--accent); color: #FFFFFF;
    display: flex; align-items: center; justify-content: center; font-size: .85rem; font-weight: 700;}
.bk-step .hint {font-family: Inter, sans-serif; font-weight: 500; font-size: .85rem; color: var(--muted);}
.summary {background: var(--accent-soft); border: 1px solid var(--accent-line); border-radius: 12px;
    padding: 12px 16px; margin: 4px 0 12px; color: var(--accent-ink);}
.summary b {color: var(--accent-ink);}
.deptcard {background: var(--soft); border: 1px solid var(--line); border-radius: 12px;
    padding: 12px 16px; margin: 0 0 6px; color: var(--ink);}
.deptcard .sub {color: var(--muted); font-size: .9rem;}
</style>
""", unsafe_allow_html=True)


def page_header(title, subtitle, eyebrow="Seminar Hall Booking"):
    st.markdown(f'<div class="page-head"><div class="eyebrow">{eyebrow}</div>'
                f'<h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)

EVENT_TYPES = ["Seminar", "Workshop", "Guest Lecture", "Club Event", "Hackathon", "Cultural", "Other"]
TABLES = ["departments", "chairpersons", "students", "faculty", "seminar_halls",
          "time_slots", "booking_requests", "allocations", "freed_slots"]
REPORTS_FILE = Path(__file__).parent / "sql" / "04_reports.sql"


# ---------------------------------------------------------------- lookups
def faculty_options(dept_id):
    """Faculty who can be named as event head: only the student's own department
    (request_booking refuses any other department as well)."""
    df = db.fetch_df("""
        SELECT faculty_id, name, designation
        FROM faculty
        WHERE dept_id = %s
        ORDER BY name""", (dept_id,))
    return dict(zip(df.faculty_id.tolist(), (df.name + "  ·  " + df.designation).tolist()))


def slot_options():
    df = db.fetch_df("SELECT slot_id, slot_label FROM time_slots ORDER BY slot_id")
    return dict(zip(df.slot_id.tolist(), df.slot_label.tolist()))


def department_options():
    df = db.fetch_df("SELECT dept_id, dept_code FROM departments ORDER BY dept_id")
    return dict(zip(df.dept_id.tolist(), df.dept_code.tolist()))


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
        return "background-color: #EAF3DE; color: #27500A"
    if value == "TIME OVER":
        return "background-color: #F1EFE8; color: #888780"
    if value.startswith("FREED"):
        return "background-color: #E1F5EE; color: #085041; font-weight: bold"
    if value.endswith("(awaiting approval)"):
        return "background-color: #FAEEDA; color: #633806"
    if value == "UNDER MAINTENANCE":
        return "background-color: #F1EFE8; color: #5F5E5A"
    return "background-color: #FCEBEB; color: #791F1F"


def status_colour(value):
    """Colours for both the status column and the stage words."""
    return {"ALLOCATED": "background-color: #EAF3DE; color: #27500A",
            "Booked": "background-color: #EAF3DE; color: #27500A; font-weight: bold",
            "PENDING": "background-color: #FAEEDA; color: #633806",
            "Waiting for event head": "background-color: #FAEEDA; color: #633806",
            "Waiting for chairperson": "background-color: #E1F5EE; color: #085041",
            "Approved by event head": "background-color: #EAF3DE; color: #27500A; font-weight: bold",
            "REJECTED": "background-color: #FCEBEB; color: #791F1F",
            "Rejected": "background-color: #FCEBEB; color: #791F1F",
            "CANCELLED": "background-color: #F1EFE8; color: #5F5E5A",
            "Cancelled": "background-color: #F1EFE8; color: #5F5E5A"}.get(value, "")


def step_tracker(row):
    """Requested -> Event head -> Chairperson, drawn as three steps."""
    def step(label, state):
        mark = {"done": "&#10003;", "bad": "&#10005;"}.get(state, "&bull;")
        return f'<div class="step {state}"><div class="b">{mark}</div>{label}</div>'

    fac = row.faculty_status
    if row.status == "ALLOCATED":
        head, chair = ("done" if fac == "APPROVED" else ""), "done"
    elif row.status == "REJECTED":
        head = "bad" if fac == "REJECTED" else ("done" if fac == "APPROVED" else "")
        chair = "" if fac == "REJECTED" else "bad"
    else:
        head = "done" if fac == "APPROVED" else "now"
        chair = "now" if fac == "APPROVED" else ""
    bar1 = '<div class="bar done"></div>'
    bar2 = f'<div class="bar {"done" if head == "done" else ""}"></div>'
    return (f'<div class="track"><div class="title">#{row.request_id} {row.event_name} '
            f'<span>· {row.hall_name} · {row.booking_date:%d %b} · {row.slot_label}</span></div>'
            f'<div class="steps">{step("Requested", "done")}{bar1}'
            f'{step("Event head: " + row.event_head, head)}{bar2}'
            f'{step("Chairperson", chair)}</div></div>')


def show_grid(day):
    st.dataframe(schedule_grid(day).style.map(colour_cell))


def free_halls(day, slot_id, min_capacity=1):
    """Halls still free for this date and slot (empty if the slot has already started)."""
    return db.fetch_df("""
        SELECT h.hall_name, h.block, h.capacity, IF(h.has_ac, 'AC', 'Non-AC') AS ac
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
    chart = alt.Chart(df).mark_bar(color="#0F6E56", cornerRadiusTopLeft=4,
                                   cornerRadiusTopRight=4).encode(
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
SRN_PATTERN = re.compile(r"PES1UG24(?:CS|AM)(\d{3})")  # students: PES1UG24CS001-100 (CSE), PES1UG24AM001-100 (AIML)
FACULTY_PATTERN = re.compile(r"PES1UG24FAC(\d{3})")  # faculty:  PES1UG24FAC001 .. PES1UG24FAC012
CHAIR_PATTERN = re.compile(r"PES1UG24CHR(\d{3})")    # chairpersons: PES1UG24CHR001 .. PES1UG24CHR006
ID_RANGES = {"student": (SRN_PATTERN, 1, 100), "faculty": (FACULTY_PATTERN, 1, 12),
             "chair": (CHAIR_PATTERN, 1, 6)}
LOGIN_QUERIES = {
    # the number in the ID is the faculty_id / chair_id; students are looked up by SRN
    "student": "SELECT s.name, s.dept_id, d.dept_code, d.dept_name FROM students s "
               "JOIN departments d ON d.dept_id = s.dept_id WHERE s.srn = %s",
    "faculty": "SELECT f.name, f.dept_id, d.dept_code, d.dept_name FROM faculty f "
               "JOIN departments d ON d.dept_id = f.dept_id WHERE f.faculty_id = %s",
    "chair": "SELECT c.name, c.dept_id, d.dept_code, d.dept_name FROM chairpersons c "
             "JOIN departments d ON d.dept_id = c.dept_id WHERE c.chair_id = %s",
}


def check_login(user_id, password):
    """Return the login details if valid, else None. For now the password is the ID.
      student:     PES1UG24CS001 .. PES1UG24CS100 (CSE) and PES1UG24AM001 .. PES1UG24AM100 (AIML)
      faculty:     PES1UG24FAC001 .. PES1UG24FAC012 (faculty_id 1..12)
      chairperson: PES1UG24CHR001 .. PES1UG24CHR006 (chair_id 1..6, one per department)"""
    if password.strip().upper() != user_id:
        return None
    for role, (pattern, first, last) in ID_RANGES.items():
        match = pattern.fullmatch(user_id)
        if match and first <= int(match.group(1)) <= last:
            key = user_id if role == "student" else int(match.group(1))
            df = db.fetch_df(LOGIN_QUERIES[role], (key,))
            if df.empty:
                return None
            return {"role": role, "ref": key, "name": df.name[0],
                    "dept_id": int(df.dept_id[0]), "dept_code": df.dept_code[0],
                    "dept_name": df.dept_name[0]}
    return None


def logged_in_student():
    return st.session_state["user"]


def page_login():
    st.write("")
    left, gap, right = st.columns([1.15, 0.08, 1])
    with left:
        st.markdown("""
        <div class="hero">
          <span class="tag">PES UNIVERSITY &middot; SEMINAR HALLS</span>
          <h1>Book a seminar hall<br>in <em>a few clicks.</em></h1>
          <p class="lead">Pick a date, a time and a hall. Your event head and chairperson approve it,
          and you follow every step live.</p>
          <div class="feature"><div class="dot">1</div><div><b>See what is free</b>
            <span>Every hall and time slot, updated live as people book.</span></div></div>
          <div class="feature"><div class="dot">2</div><div><b>Two quick approvals</b>
            <span>The faculty heading your event, then your department chairperson.</span></div></div>
          <div class="feature"><div class="dot">3</div><div><b>No hall goes unused</b>
            <span>Cancelled slots are shown to everyone straight away.</span></div></div>
        </div>""", unsafe_allow_html=True)
    with right:
        st.write("")
        st.write("")
        st.image(str(ASSETS / "logo.svg"), width=230)
        with st.container(border=True):
            st.markdown("### Welcome back")
            st.caption("Students, faculty and chairpersons sign in here.")
            with st.form("login_form", border=False):
                user_id = st.text_input("SRN / Faculty ID / Chairperson ID", placeholder="PES1UG24AM001",
                                        icon=":material/badge:")
                password = st.text_input("Password", type="password", icon=":material/lock:")
                submitted = st.form_submit_button("Log in", type="primary", width="stretch",
                                                  icon=":material/login:")
            if submitted:
                user_id = user_id.strip().upper()
                result = check_login(user_id, password)
                if result:
                    st.session_state["user"] = user_id
                    st.session_state.update(result)
                    st.rerun()
                else:
                    st.error("Invalid ID or password.", icon=":material/error:")


def logout():
    for key in ("user", "role", "name", "ref", "dept_id", "dept_code", "dept_name",
                "seen_pending", "seen_stages", "seen_faculty", "bk_day", "bk_pill", "bk_days"):
        st.session_state.pop(key, None)


# ---------------------------------------------------------------- pages
def page_dashboard():
    page_header("Dashboard", "Today at a glance: requests, approvals, freed slots and the live schedule.",
                f"Chairperson · {st.session_state['dept_code']}")
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
    mine = db.fetch_df("""
        SELECT COUNT(CASE WHEN faculty_status = 'APPROVED' THEN 1 END) AS ready,
               COUNT(CASE WHEN faculty_status = 'PENDING' THEN 1 END)  AS at_faculty
        FROM v_booking_details
        WHERE status = 'PENDING' AND dept_id = %s""", (st.session_state["dept_id"],)).iloc[0]
    if mine.ready:
        st.warning(f"**{int(mine.ready)} request(s) from {st.session_state['dept_code']} are approved by their "
                   f"event head and waiting for you.** Open the Approvals page.", icon=":material/task_alt:")
    if mine.at_faculty:
        st.info(f"{int(mine.at_faculty)} more request(s) from {st.session_state['dept_code']} are still "
                "waiting for their event head.", icon=":material/hourglass_top:")

    st.subheader("Freed slots (visible to everyone)")
    show_freed_board()

    st.subheader(f"Today's schedule ({date.today():%d %b %Y})")
    show_grid(date.today())

    st.subheader("Latest requests")
    st.dataframe(db.fetch_df("""
        SELECT request_id, booking_date, slot_label, hall_name, event_name,
               student_name, event_head, stage
        FROM v_booking_details
        ORDER BY requested_at DESC
        LIMIT 10""").style.map(status_colour, subset=["stage"]), hide_index=True)


HALL_ICON = ('<svg width="30" height="30" viewBox="0 0 40 40" aria-hidden="true"><g fill="#0F6E56">'
             '<path d="M8 15 L20 7 L32 15 Z"/><rect x="9" y="16" width="22" height="3" rx="1"/>'
             '<rect x="11" y="21" width="3.5" height="11" rx="1"/><rect x="18.25" y="21" width="3.5" height="11" rx="1"/>'
             '<rect x="25.5" y="21" width="3.5" height="11" rx="1"/><rect x="8" y="33" width="24" height="3" rx="1"/>'
             '</g></svg>')


def pick_day_pill():
    if st.session_state.get("bk_pill"):
        st.session_state["bk_day"] = st.session_state["bk_pill"]


def pick_day_calendar():
    chosen = st.session_state["bk_cal"]
    st.session_state["bk_day"] = chosen
    st.session_state["bk_pill"] = chosen if chosen in st.session_state.get("bk_days", []) else None


def step_title(number, text, hint=""):
    hint = f'<span class="hint">{hint}</span>' if hint else ""
    st.markdown(f'<div class="bk-step"><span class="n">{number}</span>{text}{hint}</div>',
                unsafe_allow_html=True)


def page_book():
    page_header("Book a seminar hall", "Pick a date, a time and a hall, then tell us about your event. "
                "Your event head and chairperson approve it.", f"Student · {st.session_state['dept_code']}")
    srn = logged_in_student()
    chair = db.fetch_df("SELECT name FROM chairpersons WHERE dept_id = %s", (st.session_state["dept_id"],))
    st.markdown(f'<div class="deptcard"><b>{st.session_state["name"]}</b> ({srn}) · Department: '
                f'<b>{st.session_state["dept_name"]} ({st.session_state["dept_code"]})</b><br>'
                f'<span class="sub">Your event head must be from the {st.session_state["dept_code"]} faculty, '
                f'and your request is approved by the {st.session_state["dept_code"]} chairperson, '
                f'{chair.name[0] if not chair.empty else "-"}.</span></div>', unsafe_allow_html=True)

    result = st.session_state.pop("last_result", None)
    if result:
        show_booking_result(result)

    freed = open_freed_slots()
    if not freed.empty:
        with st.expander(f"{len(freed)} freed slot(s) available again: cancelled bookings anyone can take",
                         icon=":material/campaign:"):
            st.dataframe(freed, hide_index=True)

    # 1. date: the next 7 days as a strip, any later date from "Other date"
    step_title(1, "Pick a date")
    first_day = date.today() if not open_slots(date.today()).empty else date.today() + timedelta(days=1)
    days = [first_day + timedelta(days=n) for n in range(7)]
    st.session_state["bk_days"] = days
    if st.session_state.get("bk_day") is None or st.session_state["bk_day"] < date.today():
        st.session_state["bk_day"] = first_day
        st.session_state["bk_pill"] = first_day
    c1, c2 = st.columns([5, 1.25], vertical_alignment="center")
    c1.pills("Date", days, format_func=lambda d: f"{d:%a %d %b}", key="bk_pill", on_change=pick_day_pill,
             label_visibility="collapsed")
    with c2.popover("Other date", icon=":material/calendar_month:", width="stretch"):
        st.date_input("Any date in the next 3 months", value=st.session_state["bk_day"], min_value=date.today(),
                      max_value=date.today() + timedelta(days=90), format="DD/MM/YYYY", key="bk_cal",
                      on_change=pick_day_calendar)
    booking_date = st.session_state["bk_day"]
    if booking_date not in days:
        st.caption(f"Selected: {booking_date:%A, %d %B %Y}")

    # 2. time
    step_title(2, "Pick a time", "  2-hour slots between 9:00 and 16:00")
    slots_df = open_slots(booking_date)
    if slots_df.empty:
        st.info("All of this day's slots are over. Please pick another date.", icon=":material/schedule:")
        return
    slots = dict(zip(slots_df.slot_id.tolist(), slots_df.slot_label.tolist()))
    slot_id = st.segmented_control("Time", list(slots), format_func=slots.get, key=f"slot_{booking_date}",
                                   label_visibility="collapsed")
    if booking_date == date.today() and len(slots) < len(slot_options()):
        st.caption("Slots that have already started today are not shown.")
    if slot_id is None:
        st.caption("Choose a time to see the halls.")
        return

    # 3. AC or non-AC
    step_title(3, "AC or non-AC")
    ac_choice = st.segmented_control("AC", ["Any", "AC", "Non-AC"], default="Any", key="ac_choice",
                                     label_visibility="collapsed") or "Any"

    # 4. hall
    halls = db.fetch_df("""
        SELECT h.hall_id, h.hall_name, h.block, h.capacity, h.has_ac, h.is_active,
               EXISTS (SELECT 1 FROM allocations a
                       WHERE a.hall_id = h.hall_id
                         AND a.booking_date = %s
                         AND a.slot_id = %s) AS is_booked
        FROM seminar_halls h
        ORDER BY h.is_active DESC, is_booked, h.capacity DESC""", (booking_date, slot_id))
    if ac_choice == "AC":
        halls = halls[halls.has_ac == 1]
    elif ac_choice == "Non-AC":
        halls = halls[halls.has_ac == 0]
    free_ids = {int(h.hall_id) for h in halls.itertuples() if h.is_active and not h.is_booked}
    step_title(4, "Choose a hall", f"  {len(free_ids)} of {len(halls)} free on {booking_date:%d %b}, {slots[slot_id]}")
    if halls.empty:
        st.info("No hall matches. Try 'Any'.")
        return
    pick_key = f"hall_{booking_date}_{slot_id}"
    selected = st.session_state.get(pick_key)
    cols = st.columns(3)
    for i, h in enumerate(halls.itertuples()):
        hall_id = int(h.hall_id)
        with cols[i % 3].container(border=True):
            ac = '<span class="badge ac">AC</span>' if h.has_ac else '<span class="badge no">Non-AC</span>'
            if not h.is_active:
                state = '<span class="badge bad">Under maintenance</span>'
            elif h.is_booked:
                state = '<span class="badge bad">Booked</span>'
            else:
                state = '<span class="badge ok">Free</span>'
            st.markdown(f'<div class="hall-band">{HALL_ICON}{ac}</div>'
                        f'<div class="pick-name">{h.hall_name}</div>'
                        f'<div class="hall-cap">{int(h.capacity)} <small>seats</small></div>'
                        f'<div class="pick-meta">{h.block}</div>{state}', unsafe_allow_html=True)
            if hall_id in free_ids:
                chosen = selected == hall_id
                if st.button("Selected" if chosen else "Select", key=f"pick_{hall_id}",
                             type="primary" if chosen else "secondary", width="stretch",
                             icon=":material/check_circle:" if chosen else None):
                    st.session_state[pick_key] = hall_id
                    st.rerun()
            else:
                st.button("Not available", key=f"pick_{hall_id}", disabled=True, width="stretch")
    if selected not in free_ids:
        st.caption("Select a free hall to continue.")
        return

    # 5. event details
    hall = halls[halls.hall_id == selected].iloc[0]
    step_title(5, "Tell us about your event")
    st.markdown(f'<div class="summary"><b>{hall.hall_name}</b> · {booking_date:%a, %d %b %Y} · '
                f'{slots[slot_id]} · {"AC" if hall.has_ac else "Non-AC"} · {int(hall.capacity)} seats</div>',
                unsafe_allow_html=True)
    faculty = faculty_options(st.session_state["dept_id"])
    with st.form("booking_form"):
        event_name = st.text_input("Event name", placeholder="e.g. Intro to Git Workshop")
        c1, c2 = st.columns(2)
        event_type = c1.selectbox("Event type", EVENT_TYPES)
        attendees = c2.number_input("Expected attendees", min_value=1, value=min(50, int(hall.capacity)), step=5)
        faculty_id = st.selectbox(f"Event head ({st.session_state['dept_code']} faculty in charge of the event)",
                                  list(faculty), format_func=faculty.get,
                                  help="Only faculty of your department are listed. This faculty member approves "
                                       "your event first, then your department chairperson gives the final approval.")
        with st.expander("More details (optional)"):
            c1, c2 = st.columns(2)
            speaker = c1.text_input("Speaker / chief guest")
            organisation = c2.text_input("Speaker's organisation")
            notes = st.text_area("Notes for the hall staff", height=80)
        submitted = st.form_submit_button("Request booking", type="primary", width="stretch",
                                          icon=":material/send:")

    if submitted:
        if not event_name.strip():
            st.warning("Please enter the event name.")
            return
        hall_id = int(selected)
        try:
            request_id, status, message = db.request_booking(
                srn, hall_id, slot_id, booking_date, event_name.strip(), event_type,
                int(attendees), faculty_id)
        except mysql.connector.Error as e:
            st.error(f"Database error: {e}")
            return

        # NoSQL: only the fields the student filled in go into the document
        details = {"request_id": request_id, "event_type": event_type, "submitted_by": srn,
                   "created_at": now_iso()}
        if speaker.strip():
            details["speaker"] = {"name": speaker.strip()}
            if organisation.strip():
                details["speaker"]["organisation"] = organisation.strip()
        if notes.strip():
            details["notes"] = notes.strip()
        log = {"action": "REQUEST", "logged_at": now_iso(), "srn": srn,
               "request": {"hall_id": hall_id, "hall_name": hall.hall_name, "slot_id": slot_id,
                           "booking_date": str(booking_date), "attendees": int(attendees)},
               "result": {"request_id": request_id, "status": status, "message": message}}
        if status == "REJECTED" and booking_date >= date.today():
            log["alternatives_suggested"] = free_halls(booking_date, slot_id, int(attendees)).hall_name.tolist()
        try:
            nosql.save_event_details(details)
            nosql.log_action(log)
        except mysqlx.Error:
            pass

        st.session_state.pop(pick_key, None)
        st.session_state["last_result"] = {
            "request_id": request_id, "status": status, "message": message,
            "date": booking_date, "slot_id": slot_id, "hall_id": hall_id,
            "attendees": int(attendees),
            "call": (f"CALL request_booking('{srn}', {hall_id}, {slot_id}, '{booking_date}', "
                     f"'{event_name.strip()}', '{event_type}', {int(attendees)}, {faculty_id}, "
                     f"@id, @status, @msg);"),
        }
        st.rerun()


def show_booking_result(r):
    if r["status"] == "PENDING":
        st.success(f"Request #{r['request_id']}: hall HELD. {r['message']}. Nobody else can book it while "
                   "your event head and chairperson approve it. Track it on My bookings.")
    elif r["status"] == "ALLOCATED":
        st.success(f"Request #{r['request_id']}: BOOKED. {r['message']}.")
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


def page_availability():
    page_header("Hall availability", "Every hall and time slot for a day, coloured by status.", "Schedule")
    earliest = None if st.session_state["role"] == "chair" else date.today()
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
        result = result[result.ac == "AC"]
    if result.empty:
        st.info("No hall is free for that slot and size.")
    else:
        st.dataframe(result, hide_index=True)


def page_hall_details():
    page_header("Hall details", "Compare seats and AC and check free slots before you book.", "Halls")
    halls = db.fetch_df("""
        SELECT h.hall_id, h.hall_name, h.block, h.floor_no, h.capacity, h.has_ac, h.is_active
        FROM seminar_halls h
        ORDER BY h.capacity DESC""")

    first_day = date.today() if not open_slots(date.today()).empty else date.today() + timedelta(days=1)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])
    min_seats = c1.number_input("Seats needed", min_value=1, value=1, step=10)
    ac_choice = c2.selectbox("AC", ["Any", "AC only", "Non-AC only"])
    check_day = c3.date_input("Show free slots on", value=first_day, min_value=date.today())
    c4.write("")
    hide_closed = c4.checkbox("Hide halls under maintenance", value=True)

    shown = halls[halls.capacity >= min_seats]
    if ac_choice == "AC only":
        shown = shown[shown.has_ac == 1]
    elif ac_choice == "Non-AC only":
        shown = shown[shown.has_ac == 0]
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
            free = [s.slot_label for s in slots_df.itertuples() if (h.hall_id, s.slot_id) not in taken]
            ac = '<span class="badge ac">AC</span>' if h.has_ac else '<span class="badge no">Non-AC</span>'
            if not h.is_active:
                state = '<span class="badge bad">Under maintenance</span>'
            elif free:
                state = f'<span class="badge ok">{len(free)} slot(s) free</span>'
            elif slots_df.empty:
                state = '<span class="badge no">No slots left this day</span>'
            else:
                state = '<span class="badge warn">Fully booked</span>'
            st.markdown(f"#### {h.hall_name}")
            st.markdown(f'<div class="hall-cap">{int(h.capacity)} <small>seats</small></div>'
                        f'<p style="color:#64748b;margin:6px 0 10px">{h.block} · floor {h.floor_no}</p>'
                        f'{ac}{state}', unsafe_allow_html=True)
            if h.is_active:
                if free:
                    st.success(f"Free on {check_day:%d %b}: " + ", ".join(free), icon=":material/event_available:")
                else:
                    st.warning(f"No free slots on {check_day:%d %b}", icon=":material/event_busy:")

    with st.expander("Compare all halls in one table"):
        table = halls.assign(ac=halls.has_ac.map({1: "AC", 0: "Non-AC"}),
                             status=halls.is_active.map({1: "Available", 0: "Under maintenance"}))
        st.dataframe(table[["hall_name", "block", "floor_no", "capacity", "ac", "status"]], hide_index=True)


def event_facts(doc):
    """One event document as plain label: value pairs. Events have different
    fields, so a label appears only when the document has that field."""
    facts = {}
    speaker = doc.get("speaker") or {}
    if speaker.get("name"):
        facts["Speaker"] = speaker["name"]
    if speaker.get("organisation"):
        facts["Organisation"] = speaker["organisation"]
    if doc.get("club"):
        facts["Club"] = doc["club"]
    if doc.get("tools"):
        facts["Tools"] = ", ".join(doc["tools"])
    if doc.get("laptops_required"):
        facts["Laptops"] = "Participants bring laptops"
    if doc.get("teams_expected"):
        facts["Teams expected"] = str(doc["teams_expected"])
    if doc.get("prizes"):
        facts["Prizes"] = ", ".join(f"Position {p['position']}: Rs {p['amount']:,}" for p in doc["prizes"])
    if doc.get("performers"):
        facts["Performers"] = str(doc["performers"])
    if doc.get("stage_setup"):
        facts["Stage setup"] = "Needed"
    if doc.get("tags"):
        facts["Tags"] = ", ".join(doc["tags"])
    if doc.get("notes"):
        facts["Notes"] = doc["notes"]
    return facts


def page_my_bookings():
    page_header("My bookings", "Follow each request through its two approvals: your event head, then your "
                "chairperson. Updates appear here by themselves.", f"Student · {st.session_state['dept_code']}")
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
    booking_history(srn)
    history = db.fetch_df("""
        SELECT request_id, booking_date, event_name
        FROM v_booking_details
        WHERE srn = %s
        ORDER BY booking_date DESC""", (srn,))
    if history.empty:
        return

    st.subheader("Event details")
    events = {int(r.request_id): f"#{r.request_id}  {r.booking_date}  {r.event_name}"
              for r in history.itertuples()}
    chosen = st.selectbox("Request", list(events), format_func=events.get, key="details_request")
    try:
        doc = nosql.event_details_for(chosen)
        facts = event_facts(doc) if doc else {}
        if facts:
            st.markdown("  \n".join(f"**{label}:** {value}" for label, value in facts.items()))
        else:
            st.caption("No extra details were added for this event.")
    except mysqlx.Error:
        st.caption("Event details are not available right now.")

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
    if st.button("Cancel booking", key=f"cancel_{request_id}"):
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


@st.fragment(run_every="5s")
def live_updates():
    """Sidebar box that re-reads MySQL every 5 seconds on EVERY page, so all the
    screens stay in sync and show a pop-up when something new happens:
      faculty     - a student named them as event head
      chairperson - a new request from their department, or an event head approved one
      student     - their event head or chairperson decided"""
    role = st.session_state["role"]
    if role == "faculty":
        rows = db.fetch_df("""
            SELECT request_id, event_name, student_name, hall_name, booking_date, slot_label
            FROM v_booking_details
            WHERE status = 'PENDING' AND faculty_status = 'PENDING' AND faculty_id = %s""",
                           (st.session_state["ref"],))
        ids = set(rows.request_id.astype(int))
        seen = st.session_state.get("seen_faculty")
        if seen is not None:
            for r in rows[rows.request_id.isin(ids - seen)].itertuples():
                st.toast(f"New event request #{r.request_id}: {r.event_name} by {r.student_name} "
                         f"({r.hall_name}, {r.booking_date:%d %b} {r.slot_label}). See Event requests.",
                         icon=":material/notifications_active:")
        st.session_state["seen_faculty"] = ids
        count, text = len(ids), "event request(s) waiting for you"
    elif role == "chair":
        rows = db.fetch_df("""
            SELECT request_id, event_name, student_name, event_head, stage
            FROM v_booking_details
            WHERE status = 'PENDING' AND dept_id = %s""", (st.session_state["dept_id"],))
        stages = dict(zip(rows.request_id.astype(int), rows.stage))
        before = st.session_state.get("seen_pending")
        if before is not None:
            for r in rows.itertuples():
                rid = int(r.request_id)
                if rid not in before:
                    st.toast(f"New request #{rid} from {st.session_state['dept_code']}: {r.event_name} "
                             f"by {r.student_name}, event head {r.event_head}.", icon=":material/inbox:")
                elif before[rid] != r.stage and r.stage == "Waiting for chairperson":
                    st.toast(f"{r.event_head} approved #{rid} ({r.event_name}). Ready for your approval.",
                             icon=":material/task_alt:")
        st.session_state["seen_pending"] = stages
        count = sum(1 for v in stages.values() if v == "Waiting for chairperson")
        text = f"ready for your approval · {len(stages) - count} with event heads"
    else:
        rows = db.fetch_df("""
            SELECT request_id, event_name, event_head, stage, remarks
            FROM v_booking_details
            WHERE srn = %s""", (st.session_state["user"],))
        stages = dict(zip(rows.request_id.astype(int), rows.stage))
        before = st.session_state.get("seen_stages")
        if before is not None:
            for r in rows.itertuples():
                rid = int(r.request_id)
                if before.get(rid) in (None, r.stage):
                    continue
                if r.stage == "Waiting for chairperson":
                    msg = f"{r.event_head} approved #{rid} ({r.event_name}). Now waiting for the chairperson."
                elif r.stage == "Booked":
                    msg = f"#{rid} ({r.event_name}) is BOOKED. The chairperson approved it."
                elif r.stage == "Rejected":
                    msg = f"#{rid} ({r.event_name}) was rejected. {r.remarks}"
                else:
                    msg = f"#{rid} ({r.event_name}): {r.remarks}"
                st.toast(msg, icon=":material/notifications_active:")
        st.session_state["seen_stages"] = stages
        count = sum(1 for v in stages.values() if v.startswith("Waiting"))
        text = "of your requests waiting for approval"
    st.markdown(f'<div class="live{"" if count else " calm"}"><div class="num">{count}</div>'
                f'<div class="txt">{text}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="live-meta">Live · checked {datetime.now():%H:%M:%S} · server '
                f'{socket.gethostname()}</div>', unsafe_allow_html=True)


@st.fragment(run_every="5s")
def booking_history(srn):
    """The student's requests, re-read every 5 seconds: when the event head or the
    chairperson decides on another screen, the steps change here by themselves."""
    history = db.fetch_df("""
        SELECT request_id, booking_date, slot_label, hall_name, event_name, event_head,
               faculty_status, status, stage, remarks
        FROM v_booking_details
        WHERE srn = %s
        ORDER BY requested_at DESC""", (srn,))
    counts = history.status.value_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Requests", len(history))
    c2.metric("Booked", int(counts.get("ALLOCATED", 0)))
    c3.metric("Waiting for approval", int(counts.get("PENDING", 0)))
    c4.metric("Rejected / cancelled", int(counts.get("REJECTED", 0) + counts.get("CANCELLED", 0)))
    if history.empty:
        st.info("You have not requested a hall yet. Use Book a hall to make your first request.")
        return
    st.caption(f"Live: checked {datetime.now():%H:%M:%S}, refreshes every 5 seconds")
    recent = history[(history.status == "PENDING") | (history.booking_date >= date.today())].head(4)
    for row in recent.itertuples():
        if row.status != "CANCELLED":
            st.markdown(step_tracker(row), unsafe_allow_html=True)
    st.dataframe(history.drop(columns=["faculty_status", "status"])
                 .style.map(status_colour, subset=["stage"]), hide_index=True)


def page_faculty_requests():
    page_header("Event requests", "Students named you as the event head (faculty in charge). Approve the events you "
                "are really handling, or reject with a reason; the chairperson gives the final approval.",
                f"Faculty · {st.session_state['dept_code']}")
    message = st.session_state.pop("faculty_message", None)
    if message:
        st.success(message)
    faculty_queue(st.session_state["ref"])

    st.subheader("Your answers")
    st.dataframe(db.fetch_df("""
        SELECT request_id, event_name, student_name, srn, hall_name, booking_date, slot_label,
               faculty_status AS your_answer, faculty_decided_at, stage
        FROM v_booking_details
        WHERE faculty_id = %s AND faculty_status IN ('APPROVED', 'REJECTED')
        ORDER BY faculty_decided_at DESC
        LIMIT 15""", (st.session_state["ref"],)).style.map(status_colour, subset=["stage"]),
                 hide_index=True)


@st.fragment(run_every="5s")
def faculty_queue(faculty_id):
    """Requests waiting for this event head, re-read every 5 seconds."""
    pending = db.fetch_df("""
        SELECT request_id, event_name, event_type, student_name, srn, dept_code,
               hall_name, booking_date, slot_label, expected_attendees, requested_at
        FROM v_booking_details
        WHERE status = 'PENDING' AND faculty_status = 'PENDING' AND faculty_id = %s
        ORDER BY requested_at DESC""", (faculty_id,))
    st.subheader(f"Waiting for you ({len(pending)})")
    st.caption(f"Live: checked {datetime.now():%H:%M:%S}, refreshes every 5 seconds")
    if pending.empty:
        st.caption("No event requests waiting for you.")
        return
    st.dataframe(pending, hide_index=True)
    labels = {int(r.request_id): f"#{r.request_id}  {r.event_name}  ·  {r.student_name} ({r.srn})  ·  "
                                 f"{r.hall_name}, {r.booking_date:%d %b} {r.slot_label}"
              for r in pending.itertuples()}
    request_id = st.selectbox("Request", list(labels), format_func=labels.get)
    reason = st.text_input("Reason (needed when rejecting)")
    c1, c2 = st.columns(2)
    # keyed by request: a click only ever acts on the request it was made for
    approve = c1.button("Approve - I am the event head", type="primary", icon=":material/check:",
                        key=f"fac_ok_{request_id}")
    reject = c2.button("Reject", icon=":material/close:", key=f"fac_no_{request_id}")
    if reject and not reason.strip():
        st.warning("Please type a reason before rejecting.")
    elif approve or reject:
        status, msg = db.faculty_review(request_id, faculty_id, approve, reason.strip())
        log = {"action": "FACULTY_REVIEW", "logged_at": now_iso(), "faculty_id": faculty_id,
               "request_id": request_id, "decision": "APPROVED" if approve else "REJECTED"}
        if reject:
            log["reason"] = reason.strip()
        try:
            nosql.log_action(log)
        except mysqlx.Error:
            pass
        extra = (" It now goes to the chairperson." if approve else
                 " The request stops here; the trigger freed the hall and published the slot.")
        st.session_state["faculty_message"] = f"Request #{request_id}: {msg}.{extra}"
        st.rerun()


def page_chair_approvals():
    page_header("Approvals", "Final approval for requests from your department. Each one shows the student, the "
                "faculty they named as event head, and whether the event head has approved it.",
                f"Chairperson · {st.session_state['dept_code']}")
    message = st.session_state.pop("review_message", None)
    if message:
        st.success(message)
    chair_queue(st.session_state["ref"], st.session_state["dept_id"])

    st.subheader("Your recent decisions")
    st.dataframe(db.fetch_df("""
        SELECT request_id, event_name, student_name, event_head, hall_name, booking_date,
               stage, remarks, reviewed_at
        FROM v_booking_details
        WHERE reviewed_by = %s
        ORDER BY reviewed_at DESC
        LIMIT 10""", (st.session_state["name"],)).style.map(status_colour, subset=["stage"]),
                 hide_index=True)


@st.fragment(run_every="5s")
def chair_queue(chair_id, dept_id):
    """Pending requests of this chairperson's department, re-read every 5 seconds.
    Requests already approved by their event head come first."""
    pending = db.fetch_df("""
        SELECT request_id, event_name, event_type,
               CONCAT(student_name, ' (', srn, ')') AS student,
               event_head,
               CASE WHEN faculty_status = 'APPROVED' THEN 'Approved by event head'
                    ELSE 'Waiting for event head' END AS event_head_answer,
               hall_name, booking_date, slot_label, expected_attendees, capacity, requested_at
        FROM v_booking_details
        WHERE status = 'PENDING' AND dept_id = %s
        ORDER BY (faculty_status = 'APPROVED') DESC, requested_at DESC""", (dept_id,))
    ready = int((pending.event_head_answer == "Approved by event head").sum()) if not pending.empty else 0
    st.subheader(f"Waiting for your decision ({len(pending)})")
    st.caption(f"{ready} approved by their event head · {len(pending) - ready} still with the event head · "
               f"live: checked {datetime.now():%H:%M:%S}")
    if pending.empty:
        st.caption("Nothing to decide right now.")
        return
    st.dataframe(pending.style.map(status_colour, subset=["event_head_answer"]), hide_index=True)
    labels = {int(r.request_id): f"#{r.request_id}  {r.event_name}  ·  {r.student}  ·  event head "
                                 f"{r.event_head} ({'approved' if r.event_head_answer.startswith('Approved') else 'not yet'})"
              for r in pending.itertuples()}
    request_id = st.selectbox("Request", list(labels), format_func=labels.get)
    row = pending[pending.request_id == request_id].iloc[0]
    if row.event_head_answer.startswith("Approved"):
        st.success(f"**{row.event_head}** (event head) has approved this event.", icon=":material/verified:")
    else:
        st.warning(f"**{row.event_head}** (event head) has not answered yet. As chairperson you can still decide.",
                   icon=":material/hourglass_top:")
    reason = st.text_input("Reason (needed when rejecting)")
    c1, c2 = st.columns(2)
    # keyed by request: a click only ever acts on the request it was made for
    approve = c1.button("Approve - book the hall", type="primary", icon=":material/check:",
                        key=f"chair_ok_{request_id}")
    reject = c2.button("Reject", icon=":material/close:", key=f"chair_no_{request_id}")
    if reject and not reason.strip():
        st.warning("Please type a reason before rejecting.")
    elif approve or reject:
        status, msg = db.review_booking(request_id, chair_id, approve, reason.strip())
        log = {"action": "CHAIR_REVIEW", "logged_at": now_iso(), "chair_id": chair_id,
               "request_id": request_id, "decision": "APPROVED" if approve else "REJECTED"}
        if reject:
            log["reason"] = reason.strip()
        try:
            nosql.log_action(log)
        except mysqlx.Error:
            pass
        extra = ("" if approve else " The trigger freed the hall and published the slot to everyone.")
        st.session_state["review_message"] = f"Request #{request_id}: {status}. {msg}.{extra}"
        st.rerun()


def page_all_bookings():
    page_header("All bookings", "Search, filter and export every booking, or cancel one from your department "
                "with a reason.", f"Chairperson · {st.session_state['dept_code']}")
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
    c5, c6 = st.columns([1, 3])
    mine = f"My department ({st.session_state['dept_code']})"
    scope = c5.selectbox("Department", [mine, "All departments"])
    search = c6.text_input("Search by event, student name, SRN or event head")

    sql = """
        SELECT request_id, booking_date, slot_label, hall_name, event_name, event_type,
               expected_attendees, srn, student_name, dept_code, event_head, stage, status, remarks
        FROM v_booking_details
        WHERE booking_date BETWEEN %s AND %s"""
    params = [start, end]
    if scope == mine:
        sql += " AND dept_id = %s"
        params.append(st.session_state["dept_id"])
    if hall != "All halls":
        sql += " AND hall_name = %s"
        params.append(hall)
    if statuses:
        sql += " AND status IN (" + ", ".join(["%s"] * len(statuses)) + ")"
        params += statuses
    if search.strip():
        sql += " AND (event_name LIKE %s OR student_name LIKE %s OR srn LIKE %s OR event_head LIKE %s)"
        params += [f"%{search.strip()}%"] * 4
    df = db.fetch_df(sql + " ORDER BY booking_date, slot_label, hall_name", tuple(params))

    counts = df.status.value_counts()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Bookings found", len(df))
    m2.metric("Booked", int(counts.get("ALLOCATED", 0)))
    m3.metric("Waiting for approval", int(counts.get("PENDING", 0)))
    m4.metric("Expected attendees", int(df.expected_attendees.sum()) if not df.empty else 0)
    st.dataframe(df.drop(columns="status").style.map(status_colour, subset=["stage"]), hide_index=True)
    st.download_button("Download as CSV", df.to_csv(index=False), "bookings.csv", "text/csv")

    active = df[df.status.isin(["PENDING", "ALLOCATED"]) & (df.booking_date >= date.today())
                & (df.dept_code == st.session_state["dept_code"])]
    if active.empty:
        return
    st.subheader(f"Cancel a booking ({st.session_state['dept_code']} only)")
    labels = {int(r.request_id): f"#{r.request_id}  {r.booking_date}  {r.slot_label}  {r.hall_name}  "
                                 f"({r.event_name}, {r.srn})" for r in active.itertuples()}
    request_id = st.selectbox("Booking", list(labels), format_func=labels.get)
    reason = st.text_input("Reason (shown to the student)")
    if st.button("Cancel this booking", key=f"admin_cancel_{request_id}"):
        if not reason.strip():
            st.warning("Please type a reason.")
            return
        db.execute("""
            UPDATE booking_requests
            SET status = 'CANCELLED', remarks = %s
            WHERE request_id = %s AND status IN ('PENDING', 'ALLOCATED')""",
                   (f"Cancelled by the chairperson: {reason.strip()}", request_id))
        try:
            nosql.log_action({"action": "CANCEL", "logged_at": now_iso(), "by": st.session_state["user"],
                              "request_id": request_id, "reason": reason.strip()})
        except mysqlx.Error:
            pass
        st.session_state["admin_message"] = (
            f"Booking #{request_id} cancelled. The trigger freed the hall and published the slot.")
        st.rerun()


def page_reports():
    page_header("Reports", "13 SQL reports with charts. Each one runs the same query as in MySQL Workbench.", "Insights")
    reports = load_reports()
    titles = [r["title"] for r in reports]
    months = db.fetch_df("""
        SELECT DISTINCT DATE_FORMAT(booking_date, '%Y-%m') AS month
        FROM booking_requests ORDER BY month""").month.tolist()
    names = {m: datetime.strptime(m, "%Y-%m").strftime("%B") for m in months}
    names["All"] = "All"
    choice = st.segmented_control("Month", ["All"] + months, default="All", format_func=names.get,
                                  key="report_month")
    month = None if choice in (None, "All") else choice
    report = reports[titles.index(st.selectbox("Choose a report", titles))]

    period = f"{names[month]} {month[:4]}" if month else "All months"
    st.subheader(report["title"])
    st.caption(f"**{period}.** {report['about']}")
    df = db.fetch_report(report["sql"], month)
    if df.empty:
        st.info(f"No data for this report in {period}.")
        return
    if report["chart"]:
        bar_chart(df, *report["chart"])
    st.dataframe(df, hide_index=True)
    st.download_button("Download as CSV", df.to_csv(index=False),
                       report["title"].split(".")[0] + (f"_{month}" if month else "") + ".csv", "text/csv")
    with st.expander("SQL query"):
        st.code(("SET @month = " + (f"'{month}'" if month else "NULL") + ";\n") + report["sql"] + ";", language="sql")


ACTION_WORDS = {"REQUEST": "Booking requested", "FACULTY_REVIEW": "Event head answered",
                "CHAIR_REVIEW": "Chairperson decided", "CANCEL": "Booking cancelled"}


def query_used(text):
    with st.expander("Query used"):
        st.code(text, language="javascript")


def log_row(log, faculty, chairs):
    """One log document as one plain table row. Each action stores different fields."""
    action = log.get("action", "")
    result = log.get("result", {})
    if action == "REQUEST":
        who = log.get("srn", "")
        request_id = result.get("request_id")
        wanted = log.get("request", {})
        outcome = f"{wanted.get('hall_name')}, {wanted.get('booking_date')}: {result.get('status')}"
    elif action in ("FACULTY_REVIEW", "CHAIR_REVIEW"):
        who = faculty.get(log.get("faculty_id")) if action == "FACULTY_REVIEW" else chairs.get(log.get("chair_id"))
        request_id = log.get("request_id")
        outcome = log.get("decision", "") + (f": {log['reason']}" if log.get("reason") else "")
    else:
        who = log.get("srn") or log.get("by", "")
        request_id = log.get("request_id")
        outcome = log.get("reason", "Slot published to everyone")
    return {"Time": log.get("logged_at", "").replace("T", " "), "Action": ACTION_WORDS.get(action, action),
            "By": who, "Request": request_id, "Details": outcome}


def page_nosql():
    page_header("NoSQL records", "Extra event details and the activity log, kept in the MySQL Document Store "
                "and shown here as plain tables. Each record points back to MySQL by request id.", "Document store")
    if not nosql.is_available():
        st.error(f"Document Store is not reachable on port {nosql.X_PORT}.")
        return
    message = st.session_state.pop("nosql_message", None)
    if message:
        st.success(message)

    counts = nosql.document_counts()
    c1, c2 = st.columns(2)
    c1.metric("Event detail records", counts["event_details"])
    c2.metric("Activity log entries", counts["booking_logs"])

    tab_events, tab_logs, tab_reports = st.tabs(["Event details", "Activity log", "NoSQL reports"])

    with tab_events:
        st.caption("Each event type keeps different details, which is why this data is in a document store "
                   "instead of a fixed table. An empty cell means that event does not have that detail.")
        c1, c2 = st.columns(2)
        event_type = c1.selectbox("Event type", ["(any)"] + EVENT_TYPES)
        tag = c2.selectbox("Tag", ["(any)"] + [t["tag"] for t in nosql.tag_counts()])
        docs, shell = nosql.search_event_details(None if event_type == "(any)" else event_type,
                                                 None if tag == "(any)" else tag)
        st.write(f"**{len(docs)} events** (latest 50)")
        if docs:
            rows = [{"Request": d["request_id"], "Event type": d["event_type"], "Student": d["submitted_by"],
                     **event_facts(d)} for d in docs]
            table = pd.DataFrame(rows).fillna("")
            first = [c for c in ["Request", "Event type", "Student", "Speaker", "Organisation", "Club", "Tools", "Tags"]
                     if c in table.columns]
            st.dataframe(table[first + [c for c in table.columns if c not in first]], hide_index=True)
        query_used(shell)

        st.subheader("Add a tag to an event")
        c1, c2 = st.columns(2)
        tag_request = c1.number_input("Request id", min_value=1, step=1, value=1)
        new_tag = c2.text_input("New tag")
        if st.button("Add tag") and new_tag.strip():
            changed = nosql.add_tag(int(tag_request), new_tag.strip())
            st.session_state["nosql_message"] = (
                f"Tag '{new_tag.strip()}' added to request {int(tag_request)}." if changed
                else f"No record found for request {int(tag_request)}.")
            st.rerun()

    with tab_logs:
        st.caption("One entry for every request, approval, rejection and cancellation.")
        words = st.selectbox("Show", ["All actions"] + list(ACTION_WORDS.values()))
        action = next((k for k, v in ACTION_WORDS.items() if v == words), None)
        logs = nosql.latest_logs(20, action)
        faculty = dict(zip(*[c.tolist() for _, c in db.fetch_df("SELECT faculty_id, name FROM faculty").items()]))
        chairs = dict(zip(*[c.tolist() for _, c in db.fetch_df("SELECT chair_id, name FROM chairpersons").items()]))
        rows = [log_row(log, faculty, chairs) for log in logs]
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        query_used('db.booking_logs.find().sort("logged_at DESC").limit(20)')
        if logs:
            with st.expander("Delete a log entry"):
                ids = {log["_id"]: f"{r['Time']}  {r['Action']}  {r['By']}" for log, r in zip(logs, rows)}
                doc_id = st.selectbox("Entry", list(ids), format_func=ids.get)
                if st.button("Delete entry", key=f"del_{doc_id}"):
                    nosql.delete_log(doc_id)
                    st.session_state["nosql_message"] = "Log entry removed."
                    st.rerun()

    with tab_reports:
        st.subheader("N1. Events per event type")
        df = pd.DataFrame(nosql.documents_per_event_type())
        bar_chart(df, "event_type", "documents")
        st.dataframe(df, hide_index=True)
        query_used('db.event_details.find().fields("event_type", "COUNT(_id) AS documents")'
                   '.groupBy("event_type")')

        st.subheader("N2. Activity summary")
        df = pd.DataFrame(nosql.log_summary())
        df["status"] = df["status"].fillna("-")
        df["action_status"] = df["action"] + " / " + df["status"]
        bar_chart(df, "action_status", "total")
        st.dataframe(df[["action", "status", "total"]], hide_index=True)
        query_used('db.booking_logs.find().fields("action", "result.status AS status", "COUNT(_id) AS total")'
                   '.groupBy("action", "result.status")')

        st.subheader("N3. Most used event tags")
        df = pd.DataFrame(nosql.tag_counts())
        bar_chart(df, "tag", "events")
        st.dataframe(df, hide_index=True)
        query_used('db.event_details.find().fields("tags")   // then counted in Python')


def page_admin():
    page_header("Manage", "View any table, add students and halls, set maintenance and try the timing rules.",
                f"Chairperson · {st.session_state['dept_code']}")
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
            has_ac = st.radio("AC", ["AC", "Non-AC"], horizontal=True) == "AC"
            if st.form_submit_button("Add hall"):
                try:
                    # every hall has a projector, so has_projector keeps its default (TRUE)
                    db.execute("""
                        INSERT INTO seminar_halls (hall_name, block, floor_no, capacity, has_ac)
                        VALUES (%s, %s, %s, %s, %s)""",
                        (hall_name.strip(), block.strip(), int(floor_no), int(capacity), has_ac))
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
        if st.button(label, key=f"maint_{hall_id}_{int(active)}"):
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
# Each login sees only its own pages (menu along the top)
STUDENT_PAGES = [
    st.Page(page_book, title="Book a hall", icon=":material/event_available:", default=True),
    st.Page(page_my_bookings, title="My bookings", icon=":material/bookmarks:"),
    st.Page(page_availability, title="Availability", icon=":material/calendar_month:"),
    st.Page(page_hall_details, title="Halls", icon=":material/meeting_room:"),
]
FACULTY_PAGES = [
    st.Page(page_faculty_requests, title="Event requests", icon=":material/how_to_reg:", default=True),
    st.Page(page_availability, title="Availability", icon=":material/calendar_month:"),
    st.Page(page_hall_details, title="Halls", icon=":material/meeting_room:"),
]
CHAIR_PAGES = [
    st.Page(page_dashboard, title="Dashboard", icon=":material/dashboard:", default=True),
    st.Page(page_chair_approvals, title="Approvals", icon=":material/task_alt:"),
    st.Page(page_all_bookings, title="All bookings", icon=":material/list_alt:"),
    st.Page(page_availability, title="Availability", icon=":material/calendar_month:"),
    st.Page(page_hall_details, title="Halls", icon=":material/meeting_room:"),
    st.Page(page_reports, title="Reports", icon=":material/bar_chart:"),
    st.Page(page_nosql, title="NoSQL", icon=":material/data_object:"),
    st.Page(page_admin, title="Manage", icon=":material/settings:"),
]
ROLE_PAGES = {"student": STUDENT_PAGES, "faculty": FACULTY_PAGES, "chair": CHAIR_PAGES}
ROLE_LABEL = {"student": "STUDENT", "faculty": "FACULTY", "chair": "CHAIRPERSON"}


def account_bar():
    """Who is logged in, the live counter and Log out, under the top menu."""
    words = [w for w in st.session_state["name"].split() if not w.endswith(".")]
    initials = "".join(w[0] for w in words[:2]).upper()
    c1, c2, c3 = st.columns([3.1, 3, 1], vertical_alignment="center")
    c1.markdown(f'<div class="acct"><div class="avatar">{initials}</div><div>'
                f'<b>{st.session_state["name"]}<span class="role">{ROLE_LABEL[st.session_state["role"]]}</span></b>'
                f'<span class="who">{st.session_state["user"]} · {st.session_state["dept_name"]}</span>'
                f'</div></div>', unsafe_allow_html=True)
    with c2:
        live_updates()
    c3.button("Log out", on_click=logout, width="stretch", icon=":material/logout:")


try:
    db.fetch_df("SELECT 1")
except mysql.connector.Error as e:
    st.error(f"Cannot connect to MySQL: {e}")
    st.info("Start the MySQL80 service, then run `python setup_db.py` once.")
    st.stop()

# Not logged in: only the login page exists (no menu, no other pages)
if "user" not in st.session_state:
    st.navigation([st.Page(page_login, title="Sign in", icon=":material/login:")], position="hidden").run()
    st.stop()

st.logo(str(ASSETS / "logo.svg"), size="large")
nav = st.navigation(ROLE_PAGES[st.session_state["role"]], position="top")
account_bar()
nav.run()
