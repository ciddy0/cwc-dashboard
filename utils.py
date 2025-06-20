"""
db.py

Database connection utility for the Soccer Stats Dashboard

Provides a function to establish a connection to a Supabase database
using credentials stored securely in Streamlit secrets and loaded environment variables.

Dependencies:
- streamlit
- dotenv
- psycopg2

Functions:
- db_connection(): Returns a psycopg2 connection object to the Supabase database.
"""

import streamlit as st  
from dotenv import load_dotenv
import psycopg2

def db_connection():
    """
    Establishes and returns a connection to the PostgreSQL database

    Reads database connection parameters (host, port, dbname, user, password)
    from Streamlit secrets. Calls load_dotenv() to load any local .env variables,
    though the primary secrets are expected from Streamlit's secrets management

    Returns:
        psycopg2.extensions.connection: An open connection to the database

    Usage:
        with db_connection() as conn:
            # Use conn to perform queries
            pass
    """
    
    load_dotenv() 
    DB_HOST = st.secrets["DB_HOST"]
    DB_PORT = st.secrets["DB_PORT"]
    DB_NAME = st.secrets["DB_NAME"]
    DB_USER = st.secrets["DB_USER"]
    DB_PASS = st.secrets["DB_PASS"] 
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    return conn