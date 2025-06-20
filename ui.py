
"""
ui.py

User Interface module for the Soccer Stats Dashboard built with Streamlit

Defines rendering functions for the two main dashboard tabs:

1. render_match_stats_tab: Displays detailed stats and top players for a selected match
2. render_tournament_stats_tab: Displays aggregated tournament top players and goalkeepers

Functions accept database query functions as parameters to fetch data, enabling
decoupling of UI and data access logic.

Dependencies:
- streamlit
- plotly.graph_objects

Functions:
- render_match_stats_tab(get_matches, get_team_stats, get_top_players_by_match)
- render_tournament_stats_tab(get_top_players_all_matches, get_top_goalkeepers_all_matches)
"""

import streamlit as st
import plotly.graph_objects as go

def render_match_stats_tab(get_matches, get_team_stats, get_top_players_by_match):
    """
    Render the "Match Stats" tab of the dashboard

    Displays:
    - A dropdown to select a recent match by home/away teams and score
    - Basic match information: teams, score, and date
    - A pie chart showing possession percentage between the two teams
    - Key team stats comparison (shots, fouls, cards, pass percentage)
    - Top players in the selected match ranked by combined goals + assists (G/A)

    Args:
        - get_matches (function): Function to retrieve recent matches DataFrame
        - get_team_stats (function): Function to retrieve team stats DataFrame for a match
        - get_top_players_by_match (function): Function to retrieve top players for a match
    """
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

    st.header(f"{selected_match['home_team']} {selected_match['home_score']} - {selected_match['away_score']} {selected_match['away_team']}")
    st.caption(f"{selected_match['date']}")

    team_stats = get_team_stats(selected_match['id'])

    fig = go.Figure(data=[
        go.Pie(labels=team_stats['team_name'], values=team_stats['possessionPct'].astype(float), hole=0.4)
    ])
    fig.update_layout(title="Possession %")
    st.plotly_chart(fig, use_container_width=True)

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
def render_tournament_stats_tab(get_top_players_all_matches, get_top_goalkeepers_all_matches, get_most_aggressive_teams):
    """
    Render the "Tournament Stats" tab of the dashboard

    Displays:
    - Top players across the tournament determined by combined goals + assists
    - Top goalkeepers determined by save percentage, with an explanation on how
      the ranking is computed shown inside an expander

    Args:
        get_top_players_all_matches (function): Function to retrieve top players aggregated across all matches
        get_top_goalkeepers_all_matches (function): Function to retrieve top goalkeepers aggregated across all matches
    """
    st.header("Tournament Monsters :D")

    # Top Players
    st.subheader("Top Players by G/A(Goals + Assists)")
    top_players = get_top_players_all_matches(limit=5)
    for i in range(len(top_players)):
        row = top_players.iloc[i]
        cols = st.columns([1, 4, 2, 2, 2])
        with cols[0]: st.image(row['logo'], width=50)
        with cols[1]: 
            st.markdown(f"**{row['name']}**")
            st.caption(row['team_name'])
        with cols[2]: st.metric("Goals", int(row['goals']))
        with cols[3]: st.metric("Assists", int(row['assists']))
        with cols[4]: st.metric("G/A", int(row['G/A']))
    
    # Top Goalkeepers
    st.subheader("Top Goalkeepers by Save %")
    with st.expander("How is 'Best Goalkeeper' determined?"):
        st.write("""
        The ranking is based on:
        - Save Percentage = Saves divided by total shots faced (Saves + Goals Conceded)
        - If save percentages are tied, the player with more saves ranks higher.
        - If still tied, the player with more matches played ranks higher.
        - Goalkeepers with no saves are excluded.
        """)
    top_keepers = get_top_goalkeepers_all_matches(limit=5)
    for i in range(len(top_keepers)):
        row = top_keepers.iloc[i]
        cols = st.columns([1, 4, 2, 2, 2, 3])
        
        with cols[0]: st.image(row['logo'], width=50)
        with cols[1]:
            st.markdown(f"**{row['name']}**")
            st.caption(row['team_name'])
        with cols[2]: st.metric("Saves", int(row['saves']))
        with cols[3]: st.metric("Goals Conceded", int(row['goals_conceded']))
        with cols[4]: st.metric("Matches", int(row['matches']))
        with cols[5]: st.metric("Save %", f"{row['save_pct'] * 100}%")

    st.subheader("Most Aggressive Teams")
    with st.expander("How is 'Most Aggressive Team' determined?"):
        st.write("""
        The ranking is based on a weighted aggression score calculated as:
        - Total Tackles: 1.0 
        - Fouls: 2.0
        - Yellow Cards: 3.0
        - Red Cards: 5.0

        Teams with higher scores are considered more aggressive.
        """)
    most_aggressive_teams = get_most_aggressive_teams(limit=5)

    for i in range(len(most_aggressive_teams)):
        row = most_aggressive_teams.iloc[i]
        cols = st.columns([1, 4, 2, 2, 2, 2, 3])

        with cols[0]:
            st.image(row['logo'], width=50)
        with cols[1]:
            st.markdown(f"**{row['team_name']}**")
        with cols[2]:
            st.metric("Tackles", int(row['total_tackles']))
        with cols[3]:
            st.metric("Fouls", int(row['fouls']))
        with cols[4]:
            st.metric("Yellow Cards", int(row['yellow_cards']))
        with cols[5]:
            st.metric("Red Cards", int(row['red_cards']))
        with cols[6]:
            st.metric("Aggression Score", f"{row['aggression_score']:.1f}")