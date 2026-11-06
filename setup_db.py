"""Creates the tables, stored procedure, trigger and sample data (MySQL),
then loads the NoSQL collections (MySQL Document Store).

Run:  python setup_db.py
Running it again resets the database back to the original sample data.
(sql/00_create_user.sql must have been run once as root before this.)
"""
from pathlib import Path

import mysql.connector
import mysqlx

import nosql
from config import DB_CONFIG

SQL_DIR = Path(__file__).parent / "sql"
FILES = ["01_schema.sql", "02_procedures_triggers.sql", "03_sample_data.sql"]


def split_statements(text):
    """Split a .sql file into single statements, honouring DELIMITER lines
    the same way MySQL Workbench does (needed for the procedure and trigger)."""
    delimiter, buffer = ";", []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER"):
            delimiter = stripped.split()[1]
            continue
        if not buffer and (not stripped or stripped.startswith("--")):
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            statement = "\n".join(buffer).strip()[: -len(delimiter)].strip()
            buffer = []
            if statement:
                yield statement


def main():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        print(f"Could not connect to MySQL: {e}")
        print("Check that the MySQL80 service is running and that sql/00_create_user.sql was run as root.")
        return

    cur = conn.cursor()
    for name in FILES:
        count = 0
        for statement in split_statements((SQL_DIR / name).read_text(encoding="utf-8")):
            try:
                cur.execute(statement)
            except mysql.connector.Error as e:
                print(f"{name}: failed on statement:\n{statement[:200]}\n-> {e}")
                if e.errno == 1419:
                    print("Run sql/00_create_user.sql as root once; it allows trigger creation.")
                conn.close()
                return
            count += 1
        conn.commit()
        print(f"{name}: {count} statements OK")
    conn.close()

    try:
        loaded = nosql.load_sample_documents()
        print("NoSQL collections:", ", ".join(f"{k} = {v} documents" for k, v in loaded.items()))
    except mysqlx.Error as e:
        print(f"NoSQL part skipped: Document Store not reachable on port {nosql.X_PORT} ({e})")
    print("Database ready. Start the app with:  streamlit run app.py")


if __name__ == "__main__":
    main()
