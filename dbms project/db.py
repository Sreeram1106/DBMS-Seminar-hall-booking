"""Small helper layer between the Streamlit app and MySQL."""
from datetime import timedelta
from decimal import Decimal

import mysql.connector
import pandas as pd

from config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def _clean(value):
    # MySQL returns AVG/ROUND results as Decimal and TIME columns as timedelta
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, timedelta):
        return str(value)
    return value


def fetch_df(sql, params=None):
    """Run a SELECT and return the rows as a pandas DataFrame."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        columns = [c[0] for c in cur.description]
        rows = [[_clean(v) for v in row] for row in cur.fetchall()]
        return pd.DataFrame(rows, columns=columns)
    finally:
        conn.close()


def execute(sql, params=None):
    """Run an INSERT / UPDATE / DELETE and return how many rows changed."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def request_booking(srn, hall_id, slot_id, booking_date, event_name, event_type,
                    attendees, faculty_id):
    """Call the request_booking stored procedure.
    Returns (request_id, status, message) from its three OUT parameters."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        args = (srn, hall_id, slot_id, booking_date, event_name, event_type,
                attendees, faculty_id, 0, "", "")
        result = cur.callproc("request_booking", args)
        conn.commit()
        return result[8], result[9], result[10]
    finally:
        conn.close()


def review_booking(request_id, coordinator_id, approve, reason=""):
    """Call the review_booking stored procedure (the hall coordinator approves or
    rejects a PENDING request). Returns (status, message) from its OUT parameters."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        args = (request_id, coordinator_id, approve, reason or None, "", "")
        result = cur.callproc("review_booking", args)
        conn.commit()
        return result[4], result[5]
    finally:
        conn.close()
