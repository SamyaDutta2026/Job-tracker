# database.py
import sqlite3

conn = sqlite3.connect('jobs.db')
cursor = conn.cursor()

# Create users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);
""")

# Create applications table with a user_id to link to the user
cursor.execute("""
CREATE TABLE IF NOT EXISTS application (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    status TEXT NOT NULL,
    date_applied TEXT,
    FOREIGN KEY (user_id) REFERENCES user (id)
);
""")

print("Database tables for users and applications created successfully.")
conn.commit()
conn.close()