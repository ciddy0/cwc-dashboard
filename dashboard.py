"""
Dashboard.py

Main app for my Club World Cup 2025 Soccer Stats 

This file sets up the main UI tabs while doing data-fetching from the DB module

Structure:
- Imports necessary functions from 'db.py' for data retrieval 
- Imports UI rendering functions from 'ui.py'
- Defines the main() function that:
    - Creates two tabs: "Match Stats" and "Tournament Stats"
    - Renders the appropriate content in each tab by calling UI function
- Runs the main() function if the script is executed as the main moduel

Usage: 
- streamlit run app.py

Dependencies:
- streamlit
- db.py 
- ui.py
"""

import streamlit as st
from db import (
    get_matches,
    get_team_stats,
    get_top_players_by_match,
    get_top_players_all_matches,
    get_top_goalkeepers_all_matches,
    get_most_aggressive_teams,
    get_best_defensive_teams,
    get_best_attacking_teams,
    get_all_teams,
    get_team_matchwise_stats,
    get_team_overview_stats
)
from ui import render_match_stats_tab, render_tournament_stats_tab, render_teams_tab

def main():
    """
    Main function to launch the streamlit app

    Create two tabs:
    1. Match stats: shows match specific stats and top players of that amtch
    2. Tournament stats: shows overall top players and goalkeeprs stats

    Calls rendering functions from the UI module, passing in relevant data from the DB module
    """
    tab1, tab2 = st.tabs(["Match Stats", "Tournament Stats", "Teams"])

    with tab1:
        render_match_stats_tab(get_matches, get_team_stats, get_top_players_by_match)

    with tab2:
        render_tournament_stats_tab(get_top_players_all_matches, get_top_goalkeepers_all_matches, get_most_aggressive_teams, 
                                    get_best_defensive_teams,
                                    get_best_attacking_teams)
    with tab2:
        render_teams_tab(get_all_teams, get_team_overview_stats, get_team_matchwise_stats)

if __name__ == "__main__":
    main()
