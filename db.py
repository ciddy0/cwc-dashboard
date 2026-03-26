"""
db.py

Data access layer for the Club World Cup 2025 Soccer Stats Dashboard

Contains functions to query the Supabase Database for matches, team stats, player
and goalkeeper stats. Each function caches the results using Streamlit's caching
feature to optimize performance and reduce redundant database calls (the db only updates
once per day).

Simple queries use the Supabase table API directly.
Complex queries (JOINs, aggregations, window functions) use supabase.rpc() to call
PostgreSQL functions defined in supabase_functions.sql.

Functions:
- get_matches(): Fetches the latest 50 matches with basic details.
- get_team_stats(match_id): Fetches team-level statistics for a given match.
- get_top_players_by_match(match_id, limit=5): Fetches top players by goals + assists for a specific match.
- get_top_players_all_matches(limit=5): Fetches top players aggregated across all matches.
- get_top_goalkeepers_all_matches(limit=5): Fetches top goalkeepers across all matches based on save percentage.
- get_most_aggressive_teams(limit=5): Fetches most aggressive teams by weighted score.
- get_best_defensive_teams(limit=5): Fetches best defensive teams by weighted score.
- get_best_attacking_teams(limit=5): Fetches best attacking teams by weighted score.
- get_all_teams(): Fetches all teams ordered by name.
- get_team_overview_stats(team_id): Fetches aggregated stats for a team.
- get_team_goals_by_match(team_id): Fetches goals scored per match for a team.

Dependencies:
- pandas
- utils (provides get_supabase_client)
- streamlit (for caching)
"""

import pandas as pd
import streamlit as st
from utils import get_supabase_client


@st.cache_data(ttl=3600)
def get_matches():
    """
    Retrieves the latest 50 matches from the database, ordered by date descending.

    Returns:
        pd.DataFrame: DataFrame with columns:
            - id, home_team, away_team, home_score, away_score, date
    """
    supabase = get_supabase_client()
    response = (
        supabase.table("matches")
        .select("id,home_team,away_team,home_score,away_score,date")
        .order("date", desc=True)
        .limit(50)
        .execute()
    )
    return pd.DataFrame(response.data)


@st.cache_data(ttl=600)
def get_team_stats(match_id):
    """
    Retrieves team-level statistics for a specific match.

    Args:
        match_id (int): The ID of the match.

    Returns:
        pd.DataFrame: DataFrame with team_name and expanded stats columns.
    """
    supabase = get_supabase_client()
    response = supabase.rpc("fn_get_team_stats", {"p_match_id": match_id}).execute()
    df = pd.DataFrame(response.data)
    stats_expanded = df["stats"].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series)
    return pd.concat([df[["team_name"]], stats_expanded], axis=1)


@st.cache_data(ttl=600)
def get_top_players_by_match(match_id, limit=5):
    """
    Retrieves top players for a specific match determined by goals + assists.

    Args:
        match_id (int): The ID of the match.
        limit (int, optional): Number of players to return. Defaults to 5.

    Returns:
        pd.DataFrame: DataFrame with columns: name, team_name, logo, goals, assists, G/A
    """
    supabase = get_supabase_client()
    response = supabase.rpc(
        "fn_get_top_players_by_match",
        {"p_match_id": match_id, "p_limit": limit}
    ).execute()
    df = pd.DataFrame(response.data)
    return df.rename(columns={"ga": "G/A"})


@st.cache_data(ttl=600)
def get_top_players_all_matches(limit=5):
    """
    Retrieves top players aggregated across all matches, ranked by total goals + assists.

    Args:
        limit (int, optional): Number of players to return. Defaults to 5.

    Returns:
        pd.DataFrame: DataFrame with columns: name, team_name, logo, goals, assists, G/A
    """
    supabase = get_supabase_client()
    response = supabase.rpc("fn_get_top_players_all_matches", {"p_limit": limit}).execute()
    df = pd.DataFrame(response.data)
    return df.rename(columns={"ga": "G/A"})


@st.cache_data(ttl=600)
def get_top_goalkeepers_all_matches(limit=5):
    """
    Retrieves top goalkeepers ranked by save percentage across all matches.

    Args:
        limit (int, optional): Number of goalkeepers to return. Defaults to 5.

    Returns:
        pd.DataFrame: DataFrame with columns: name, team_name, logo, matches, saves, goals_conceded, save_pct
    """
    supabase = get_supabase_client()
    response = supabase.rpc("fn_get_top_goalkeepers_all_matches", {"p_limit": limit}).execute()
    return pd.DataFrame(response.data)


@st.cache_data(ttl=600)
def get_most_aggressive_teams(limit=5):
    """
    Retrieves the most aggressive teams based on a weighted aggression score per match.

    Args:
        limit (int): Number of top teams to return. Defaults to 5.

    Returns:
        pd.DataFrame: DataFrame with columns: team_id, team_name, logo, matches_played,
                      total_tackles, fouls, yellow_cards, red_cards,
                      total_aggression_score, aggression_score_per_match
    """
    supabase = get_supabase_client()
    response = supabase.rpc("fn_get_most_aggressive_teams", {"p_limit": limit}).execute()
    return pd.DataFrame(response.data)


@st.cache_data(ttl=600)
def get_best_defensive_teams(limit=5):
    """
    Retrieves the best defensive teams based on a weighted defensive score.

    Args:
        limit (int): Number of top teams to return. Defaults to 5.

    Returns:
        pd.DataFrame: DataFrame with defensive stats columns and defensive_score.
    """
    supabase = get_supabase_client()
    response = supabase.rpc("fn_get_best_defensive_teams", {"p_limit": limit}).execute()
    return pd.DataFrame(response.data)


@st.cache_data(ttl=600)
def get_best_attacking_teams(limit=5):
    """
    Retrieves the best attacking teams based on a weighted attacking score per match.

    Args:
        limit (int): Number of top teams to return. Defaults to 5.

    Returns:
        pd.DataFrame: DataFrame with attacking stats columns and attacking_score_per_match.
    """
    supabase = get_supabase_client()
    response = supabase.rpc("fn_get_best_attacking_teams", {"p_limit": limit}).execute()
    return pd.DataFrame(response.data)


@st.cache_data(ttl=3600)
def get_all_teams():
    """
    Retrieves all teams ordered by name.

    Returns:
        pd.DataFrame: DataFrame with columns: team_id, team_name, logo
    """
    supabase = get_supabase_client()
    response = (
        supabase.table("teams")
        .select("team_id,team_name,logo")
        .order("team_name")
        .execute()
    )
    return pd.DataFrame(response.data)


@st.cache_data(ttl=600)
def get_team_overview_stats(team_id):
    """
    Retrieves aggregated overview stats for a specific team.

    Args:
        team_id (int): The ID of the team.

    Returns:
        dict: Keys: matches, wins, goals_scored, goals_conceded,
              avg_possession, avg_pass_pct, avg_shots, corners
    """
    supabase = get_supabase_client()
    response = supabase.rpc("fn_get_team_overview_stats", {"p_team_id": team_id}).execute()
    return response.data[0]


@st.cache_data(ttl=600)
def get_team_goals_by_match(team_id):
    """
    Retrieves goals scored by the specified team in each match, ordered chronologically.

    Args:
        team_id (int): The ID of the team.

    Returns:
        pd.DataFrame: DataFrame with columns:
            - match_number (int): Sequential match index based on date (1 = oldest).
            - goals_scored (int): Goals scored by the team in that match.
    """
    supabase = get_supabase_client()
    response = supabase.rpc("fn_get_team_goals_by_match", {"p_team_id": team_id}).execute()
    return pd.DataFrame(response.data)
