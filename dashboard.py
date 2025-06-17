import streamlit as st  
from dotenv import load_dotenv
import os
import psycopg2
import pandas as pd


load_dotenv() 

DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]
DB_NAME = st.secrets["DB_NAME"]
DB_USER = st.secrets["DB_USER"]
DB_PASS = st.secrets["DB_PASS"]

@st.cache_data(ttl=3600) 
def get_top_players(limit=10):
    query = """
        SELECT 
            p.full_name as name,
            ps.goals,
            ps.assists,
            (ps.goals + ps.assists) AS "G/A"
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id
        ORDER BY "G/A" DESC
        LIMIT %s;
    """

    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df

def main():
    st.title("Top Soccer Players by Goals + Assists (G/A)")

    limit = st.slider("Number of top players to show:", 5, 50, 10)

    with st.spinner("Fetching data..."):
        df = get_top_players(limit)

    st.dataframe(df.style.format({
        'goals': '{:.0f}',
        'assists': '{:.0f}',
        'ga': '{:.0f}'
    }))

if __name__ == "__main__":
    main()