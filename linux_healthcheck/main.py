import argparse
import getpass
import json
import datetime
import os
import sqlite3
import smtplib
import stat

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SCHEMA_SQL = """
create table if not exists counters (
    counter_id integer not null,
    path text not null,
    name text,
    primary key(counter_id));

create unique index if not exists counters_path on counters(path);

create table if not exists counter_counts (
    counter_count_id integer primary key,
    counters_counter_id integer references counters(counter_id),
    count integer not null,
    access_time datetime default current_timestamp);

create index if not exists counter_counts_access_time
    on counter_counts(access_time);
"""

ADD_COUNTER_SQL = """
insert or ignore into counters (path, name)
values ('%s', '%s');
"""

QUERY_COUNTERS_SQL = """
select counter_id, path, name from counters;
"""

UPDATE_COUNTER_SQL = """
insert into counter_counts (counters_counter_id, count)
values (%d, %d);
"""

QUERY_COUNTER_SQL = """
select max(access_time), count from counter_counts
where counters_counter_id = ?
"""


def get_connection():
    sqlfile = os.path.expanduser("~/.linux-healthcheck.db")
    it_exists = os.path.exists(sqlfile)
    conn = sqlite3.connect(sqlfile)
    if not it_exists:
        os.chmod(sqlfile, stat.S_IRUSR | stat.S_IWUSR)
    return conn


def create_schema(conn: sqlite3.Connection):
    cursor = conn.cursor()
    for cmd in SCHEMA_SQL.split(";"):
        cursor.execute(cmd + ";")


def get_counters(conn: sqlite3.Connection):
    """
    Get the paths of all counters in the database
    :param conn: connection to the database
    :return: a sequence of three-tuples of counter_id, path to the counter
    and name of the counter
    """
    cursor = conn.cursor()
    cursor.execute(QUERY_COUNTERS_SQL)
    return cursor.fetchall()


def add_counter(conn: sqlite3.Connection, path:str, name:str):
    """
    Add a new counter to the database if it doesn't exist.
    :param conn: connection
    :param path: filesystem path, e.g. /sys/devices/system/edac/mc/mc0/ce_count
    :param name: The user-readable name of the counter, e.g.
    "EDAC memory bank 0"
    """
    cursor = conn.cursor()
    cursor.execute(ADD_COUNTER_SQL % (path, name))


def update_counter(conn: sqlite3.Connection, counter_id: int, count: int):
    """

    :param conn: database connection
    :param counter_id: the row ID of the counter to be updated
    :param count: the new count
    """
    cursor = conn.cursor()
    cursor.execute(UPDATE_COUNTER_SQL % (counter_id, count))


def get_counter(conn: sqlite3.Connection, counter_id: int):
    """

    :param conn: the database connection
    :param counter_id: the counter_id of the counter to be fetched
    :param now: Fetch the latest value before this time.
    :return:
    """
    cursor = conn.cursor()
    cursor.execute(QUERY_COUNTER_SQL, (counter_id,))
    result = cursor.fetchone()
    if result is None or result[1] is None:
        return 0
    return result[1]


def read_counter(path):
    """
    Read the value of a counter
    :param path: filesystem path to the counter
    :return: the current count
    """
    with open(path, "r") as fd:
        return int(fd.read())


def get_credentials_filename():
    credentials_filename = "~/.linux-healthcheck.credentials"
    return os.path.expanduser(credentials_filename)


def write_credentials_file():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smtp-server",
                        required=True,
                        help="DNS name of the SMTP server")
    parser.add_argument("--smtp-port",
                        type=int,
                        required=True,
                        help="Port for the SMTP server")
    parser.add_argument("--sender",
                        required=True,
                        help="Address of sender")
    parser.add_argument("--recipient",
                        required=True,
                        help="Address of the recipient")
    args = parser.parse_args()
    password = getpass.getpass("SMTP password: ")
    d = dict(smtp_server=args.smtp_server,
             smtp_port=args.smtp_port,
             sender=args.sender,
             recipient=args.recipient,
             password=password)
    filename = get_credentials_filename()
    with open(filename, "w") as fd:
        os.chmod(filename, stat.S_IRUSR | stat.S_IWUSR)
        json.dump(d, fd)


def send_mail(report):
    with open(get_credentials_filename()) as fd:
        d = json.load(fd)
    s = smtplib.SMTP(host=d["smtp_server"],
                     port=d["smtp_port"])
    s.starttls()
    s.login(d["sender"], d["password"])
    msg = MIMEMultipart()
    message = "\n".join(["%s: %d" % (name, count) for name, count in report])
    msg["From"] = d["sender"]
    msg["To"] = d["recipient"]
    msg["Subject"] = "Linux healthcheck report"
    msg.attach(MIMEText(message))
    s.send_message(msg)
    s.quit()


def new_counter():
    """
    Command to create a new counter
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--path",
                        required=True,
                        help="Filesystem path to counter")
    parser.add_argument("--name",
                        required=True,
                        help="User-readable name of the counter")
    args = parser.parse_args()
    conn = get_connection()
    create_schema(conn)
    add_counter(conn, args.path, args.name)
    conn.commit()


def main():
    conn = get_connection()
    report = []
    for counter_id, path, name in get_counters(conn):
        old_value = get_counter(conn, counter_id)
        new_value = read_counter(path)
        if new_value > old_value:
            report.append((name, new_value - old_value))
            update_counter(conn, counter_id, new_value)
    if len(report) > 0:
        send_mail(report)
    conn.commit()

if __name__=="__main__":
    main()

