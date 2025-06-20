import streamlit as st  
import pandas as pd
from utils import db_connection
import plotly.graph_objects as go
import plotly.express as px
import json

# cached match list
@st.cache_data(ttl=3600)
def get_matches():
    query = """
        SELECT id, home_team, away_team, home_score, away_score, date
        FROM matches
        ORDER BY date DESC
        LIMIT 50;
    """
    with db_connection() as conn:
        df = pd.read_sql(query, conn)
    return df

# Load team stats
@st.cache_data(ttl=600)
def get_team_stats(match_id):
    query = f"""
        SELECT team_id, team_name, stats
        FROM team_stats
        JOIN teams USING(team_id)
        WHERE match_id = %s
    """
    with db_connection() as conn:
        df = pd.read_sql(query, conn, params=(match_id,))
    stats_expanded = df['stats'].apply(lambda x: json.loads(x) if isinstance(x, str) else x).apply(pd.Series)
    return pd.concat([df[['team_name']], stats_expanded], axis=1)

# Load top player stats by match
@st.cache_data(ttl=600)
def get_top_players_by_match(match_id, limit=5):
    query = """
        SELECT 
            p.full_name AS name,
            t.team_name,
            t.logo,
            ps.goals,
            ps.assists,
            (ps.goals + ps.assists) AS "G/A"
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id
        JOIN teams t ON p.team_id = t.team_id
        WHERE ps.match_id = %s
        ORDER BY "G/A" DESC
        LIMIT %s;
    """
    with db_connection() as conn:
        df = pd.read_sql(query, conn, params=(match_id, limit))
    return df


# Main app
st.title("Match Overview")

matches_df = get_matches()
matches_df['label'] = (
    matches_df['home_team'] + ' ' +
    matches_df['home_score'].astype(str) + ' - ' +
    matches_df['away_score'].astype(str) + ' ' +
    matches_df['away_team']
)
selected_label = st.selectbox("Select a Match", matches_df['label'])
selected_match = matches_df[matches_df['label'] == selected_label].iloc[0]

# Basic match info
st.header(f"{selected_match['home_team']} {selected_match['home_score']} - {selected_match['away_score']} {selected_match['away_team']}")
st.caption(f"{selected_match['date']}")

# Team stats
team_stats = get_team_stats(selected_match['id'])

# Possession Chart
fig = go.Figure(data=[
    go.Pie(labels=team_stats['team_name'], values=team_stats['possessionPct'].astype(float), hole=0.4)
])
fig.update_layout(title="Possession %")
st.plotly_chart(fig, use_container_width=True)

# Key stats comparison 
st.subheader("Key Team Stats")
compare_stats = ['totalShots', 'shotsOnTarget', 'foulsCommitted', 'yellowCards', 'redCards', 'passPct']
cols = st.columns(3)

for i, stat in enumerate(compare_stats):
    with cols[i % 3]:
        values = team_stats[stat].astype(float)

        if stat == 'passPct':
            display_value = f"{values.iloc[0]:.1f}% vs {values.iloc[1]:.1f}%"
        else:
            display_value = f"{int(values.iloc[0])} vs {int(values.iloc[1])}"

        label = (
            stat.replace("Pct", " %")
                .replace("total", "Total ")
                .replace("OnTarget", " on Target")
                .replace("Committed", " Committed")
                .replace("yellow", "Yellow ")
                .replace("red", "Red ")
                .replace("fouls", "Fouls ")
        ).replace("_", " ").strip().title()

        st.metric(label=label, value=display_value)

#  Top players of that match
st.subheader("Top Players by G/A (By Goals + Assists)")
top_players = get_top_players_by_match(selected_match['id'], limit=5)


for i in range(len(top_players)):
    row = top_players.iloc[i]
    cols = st.columns([1, 4, 2, 2, 2])
    
    with cols[0]:
        st.image(row['logo'], width=50)
    with cols[1]:
        st.markdown(f"**{row['name']}**")
        st.caption(row['team_name'])
    with cols[2]:
        st.metric("Goals", row['goals'])
    with cols[3]:
        st.metric("Assists", row['assists'])
    with cols[4]:
        st.metric("G/A", row['G/A'])
