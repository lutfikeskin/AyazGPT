import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    conn = psycopg2.connect("postgresql://postgres:Ayaz1423@localhost:5432/postgres")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    # Check if mymind exists
    cur.execute("SELECT 1 FROM pg_database WHERE datname='mymind'")
    exists = cur.fetchone()
    if not exists:
        print("Creating database mymind...")
        cur.execute("CREATE DATABASE mymind")
    cur.close()
    conn.close()

    # Now connect to mymind and create extension
    conn_mymind = psycopg2.connect("postgresql://postgres:Ayaz1423@localhost:5432/mymind")
    conn_mymind.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur_mymind = conn_mymind.cursor()
    cur_mymind.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    print("TimescaleDB extension created.")
    cur_mymind.close()
    conn_mymind.close()
    print("Database setup complete.")
except Exception as e:
    print(f"Error: {e}")
