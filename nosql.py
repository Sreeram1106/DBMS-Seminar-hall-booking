"""NoSQL part of the project: MySQL Document Store.

Data here is stored as schemaless JSON documents inside "collections" and is
accessed with the X DevAPI (add / find / modify / remove) over port 33060.
No SQL is written in this file.

Collections:
  event_details - extra details of each event; the shape changes with the
                  event type (speaker for lectures, tools for workshops, ...)
  booking_logs  - append-only log of every booking request and cancellation
"""
import json
from collections import Counter
from pathlib import Path

import mysqlx

from config import DB_CONFIG

X_PORT = 33060
SCHEMA = "seminar_booking"
DATA_DIR = Path(__file__).parent / "nosql_data"


def _open():
    session = mysqlx.get_session(host=DB_CONFIG["host"], port=X_PORT,
                                 user=DB_CONFIG["user"], password=DB_CONFIG["password"])
    return session, session.get_schema(SCHEMA)


def _to_dicts(result):
    return [json.loads(doc.as_str()) for doc in result.fetch_all()]


def is_available():
    try:
        session, _ = _open()
        session.close()
        return True
    except mysqlx.Error:
        return False


# ---------------------------------------------------------------- CREATE
def save_event_details(doc):
    """db.event_details.add(doc)"""
    session, schema = _open()
    try:
        schema.get_collection("event_details").add(doc).execute()
    finally:
        session.close()


def log_action(doc):
    """db.booking_logs.add(doc)"""
    session, schema = _open()
    try:
        schema.get_collection("booking_logs").add(doc).execute()
    finally:
        session.close()


# ---------------------------------------------------------------- READ
def event_details_for(request_id):
    """db.event_details.find("request_id = :rid").bind("rid", request_id)"""
    session, schema = _open()
    try:
        result = (schema.get_collection("event_details")
                  .find("request_id = :rid").bind("rid", int(request_id)).execute())
        docs = _to_dicts(result)
        return docs[0] if docs else None
    finally:
        session.close()


def search_event_details(event_type=None, tag=None, limit=50):
    """Find event documents by type and/or tag.
    Returns (documents, the same query written for MySQL Shell)."""
    conditions, binds = [], {}
    if event_type:
        conditions.append("event_type = :type")
        binds["type"] = event_type
    if tag:
        conditions.append(":tag IN tags")
        binds["tag"] = tag
    condition = " AND ".join(conditions)

    session, schema = _open()
    try:
        query = (schema.get_collection("event_details").find(condition or None)
                 .sort("request_id DESC").limit(limit))
        for name, value in binds.items():
            query = query.bind(name, value)
        docs = _to_dicts(query.execute())
    finally:
        session.close()

    shell = "db.event_details.find(" + (f'"{condition}"' if condition else "") + ")"
    shell += f'.sort("request_id DESC").limit({limit})'
    shell += "".join(f'.bind("{n}", "{v}")' for n, v in binds.items())
    return docs, shell


def latest_logs(limit=20, action=None):
    """db.booking_logs.find().sort("logged_at DESC").limit(limit)
    (with find("action = :action") when one action is chosen)"""
    session, schema = _open()
    try:
        query = schema.get_collection("booking_logs").find("action = :action" if action else None)
        query = query.sort("logged_at DESC").limit(limit)
        if action:
            query = query.bind("action", action)
        return _to_dicts(query.execute())
    finally:
        session.close()


def document_counts():
    """db.event_details.count() and db.booking_logs.count()"""
    session, schema = _open()
    try:
        return {name: schema.get_collection(name).count() for name in ("event_details", "booking_logs")}
    finally:
        session.close()


# ---------------------------------------------------------------- UPDATE
def add_tag(request_id, tag):
    """db.event_details.modify("request_id = :rid").arrayAppend("tags", tag)
    (or .set("tags", [tag]) when the document has no tags yet).
    Returns how many documents changed."""
    session, schema = _open()
    try:
        coll = schema.get_collection("event_details")
        doc = _to_dicts(coll.find("request_id = :rid").bind("rid", int(request_id)).execute())
        if not doc:
            return 0
        modify = coll.modify("request_id = :rid").bind("rid", int(request_id))
        if "tags" in doc[0]:
            modify = modify.array_append("tags", tag)
        else:
            modify = modify.set("tags", [tag])
        return modify.execute().get_affected_items_count()
    finally:
        session.close()


# ---------------------------------------------------------------- DELETE
def delete_log(doc_id):
    """db.booking_logs.remove("_id = :id").bind("id", doc_id)"""
    session, schema = _open()
    try:
        return (schema.get_collection("booking_logs")
                .remove("_id = :id").bind("id", doc_id).execute().get_affected_items_count())
    finally:
        session.close()


# ---------------------------------------------------------------- REPORTS
def documents_per_event_type():
    """db.event_details.find().fields("event_type", "COUNT(_id) AS documents").groupBy("event_type")"""
    session, schema = _open()
    try:
        rows = _to_dicts(schema.get_collection("event_details").find()
                         .fields("event_type", "COUNT(_id) AS documents")
                         .group_by("event_type").execute())
    finally:
        session.close()
    return sorted(rows, key=lambda r: r["documents"], reverse=True)


def log_summary():
    """db.booking_logs.find().fields("action", "result.status AS status", "COUNT(_id) AS total")
                         .groupBy("action", "result.status")"""
    session, schema = _open()
    try:
        rows = _to_dicts(schema.get_collection("booking_logs").find()
                         .fields("action", "result.status AS status", "COUNT(_id) AS total")
                         .group_by("action", "result.status").execute())
    finally:
        session.close()
    return sorted(rows, key=lambda r: r["total"], reverse=True)


def tag_counts():
    """Read only the tags array of every document, then count in Python
    (documents stores often leave this kind of aggregation to the application)."""
    session, schema = _open()
    try:
        docs = _to_dicts(schema.get_collection("event_details").find().fields("tags").execute())
    finally:
        session.close()
    # many events have no tags (the field comes back empty), so skip them
    counts = Counter(item for d in docs for item in (d.get("tags") or []))
    return [{"tag": k, "events": v} for k, v in counts.most_common()]


# ---------------------------------------------------------------- SETUP
def load_sample_documents():
    """Drop and recreate both collections, then load nosql_data/*.json.
    Called by setup_db.py. Returns {collection: number of documents}."""
    session, schema = _open()
    try:
        loaded = {}
        for name in ["event_details", "booking_logs"]:
            if schema.get_collection(name).exists_in_database():
                schema.drop_collection(name)
            coll = schema.create_collection(name)
            docs = json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))
            coll.add(docs).execute()
            loaded[name] = coll.count()
        # index on request_id so lookups by request do not scan every document
        schema.get_collection("event_details").create_index(
            "idx_request_id", {"fields": [{"field": "$.request_id", "type": "INT"}]}).execute()
        return loaded
    finally:
        session.close()
