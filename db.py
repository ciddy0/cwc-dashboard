"""
db.py

Data access layer for the Club World Cupo 2025 Soccer Stats Dashboard

Contains functions to query the Supabse Database for matches, team stats, player
and goalkeeper stats. Each function caches teh results using Streamlit's caching
feature to optimize performance and reduce redundant databse calls (the db only updates
once per day)

Functions: 
- get_matches(): Fetches the latest 50 matches with basic details.
- get_team_stats(match_id): Fetches team-level statistics for a given match.
- get_top_players_by_match(match_id, limit=5): Fetches top players by goals + assists for a specific match.
- get_top_players_all_matches(limit=5): Fetches top players aggregated across all matches.
- get_top_goalkeepers_all_matches(limit=5): Fetches top goalkeepers across all matches based on save percentage.

Dependencies:
- pandas
- json
- utils.db_connection (provides a database connection context manager)
- streamlit (for caching)
"""

import pandas as pd
import json
from utils import db_connection
import streamlit as st

@st.cache_data(ttl=3600)
def get_matches():
    """
    Retrieves the latest 50 matches from the database, ordered by data descending

    Returns:
        pd.DataFrame: DataFrame with columns:
            - id: Match ID
            - home_team: Home team name
            - away_team: Away team name
            - home_score: Home team score
            - away_score: Away team score
            - date: Match data/time
    """

    query = """
        SELECT id, home_team, away_team, home_score, away_score, date
        FROM matches
        ORDER BY date DESC
        LIMIT 50;
    """
    with db_connection() as conn:
        df = pd.read_sql(query, conn)
    return df

@st.cache_data(ttl=600)
def get_team_stats(match_id):
    """
    Retrieves team-level statistics for a specific match

    Args:
        - match_id (int): The ID of the match

    Returns:
        pd.DataFrame: DataFrame with columns
            - team_name: Name of the team
            - <expanded stats columns>: Team stats fields parsed from JSON stored in 'stats' column
    """

    query = """
        SELECT team_id, team_name, stats
        FROM team_stats
        JOIN teams USING(team_id)
        WHERE match_id = %s
    """

    with db_connection() as conn:
        df = pd.read_sql(query, conn, params=(match_id,))
    stats_expanded = df['stats'].apply(lambda x: json.loads(x) if isinstance(x, str) else x).apply(pd.Series)
    return pd.concat([df[['team_name']], stats_expanded], axis=1)

@st.cache_data(ttl=600)
def get_top_players_by_match(match_id, limit=5):
    """
    Retrieves top players for a specific match determined by goals + assists.

    Args: 
        - match_id (int): The ID of the match
        - limit (int, optional): Number of players to return. Defaults to 5
    
        Returns: 
            pd.DataFrame: DataFrame with columns
                - name: Player full name
                - team_name: Player's team name
                - logo: Team logo URL
                - goals: Number of goals in the match
                - assists: Number of assist in the match
                - G/A: Sum of goals and assists
    """
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

@st.cache_data(ttl=600)
def get_top_players_all_matches(limit=5):
    """
    Retrieves top players aggregated across all matches, ranked by total goals + assists

    Args:
        - limit (int, optional): Number of players to return. Defaults to 5

    Returns:
        pd.DataFrame: DataFrame with columns:
            - name: Player full name
            - team_name: Player's team name
            - logo: Team logo URL or path
            - goals: Total goals across all matches
            - assists: Total assists across all matches
            - G/A: Sum of goals and assists
    """

    query = """
        SELECT 
            p.full_name AS name,
            t.team_name,
            t.logo,
            SUM(ps.goals) AS goals,
            SUM(ps.assists) AS assists,
            SUM(ps.goals + ps.assists) AS "G/A"
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id
        JOIN teams t ON p.team_id = t.team_id
        GROUP BY p.player_id, p.full_name, t.team_name, t.logo
        ORDER BY "G/A" DESC
        LIMIT %s;
    """
    with db_connection() as conn:
        return pd.read_sql(query, conn, params=(limit,))

@st.cache_data(ttl=600)
def get_top_goalkeepers_all_matches(limit=5):
    """
    Retrieves top goalkeepers ranked by save percentage across all matches
    Save percentage = saves / (saves + goals conceded)

    Args:
        limit (int, optional): Number of goalkeepers to return. Defaults to 5
    Returns:
        pd.DataFrame: DataFrame with columns:
            - name: Goalkeeper full name
            - team_name: Goalkeeper's team name
            - logo: Team logo URL or path
            - matches: Number of distinct matches played
            - saves: Total saves made
            - goals_conceded: Total goals conceded
            - save_pct: Save percentage (rounded to 2 decimals)
    """

    query = """
        SELECT 
            p.full_name AS name,
            t.team_name,
            t.logo,
            COUNT(DISTINCT ps.match_id) AS matches,
            SUM((ps.stats->>'saves')::float) AS saves,
            SUM((ps.stats->>'goalsConceded')::float) AS goals_conceded,
            ROUND((
                SUM((ps.stats->>'saves')::float) 
                / NULLIF(SUM((ps.stats->>'saves')::float + (ps.stats->>'goalsConceded')::float), 0)
            )::numeric, 2) AS save_pct
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id
        JOIN teams t ON p.team_id = t.team_id
        WHERE ps.stats->>'saves' IS NOT NULL
          AND (ps.stats->>'saves')::float > 0
        GROUP BY p.player_id, p.full_name, t.team_name, t.logo
        HAVING SUM((ps.stats->>'saves')::float + (ps.stats->>'goalsConceded')::float) > 0
        ORDER BY save_pct DESC, saves DESC, matches DESC
        LIMIT %s;
    """
    with db_connection() as conn:
        return pd.read_sql(query, conn, params=(limit,))

@st.cache_data(ttl=600)
def get_most_aggressive_teams(limit=5):
    """
    Retrieves the most aggressive teams in the tournament based on a weighted aggression score

    The aggression score is calculated as a weighted sum of the following statistics aggregated
    over all matches played by each team:
        - total_tackles (weight = 1)
        - fouls (weight = 2)
        - yellow_cards (weight = 3)
        - red_cards (weight = 5)

    Higher weights are assigned to fouls and cards to reflect their greater impact on aggression

    Args:
        limit (int): Number of top teams to return. Defaults to 5

    Returns:
        pandas.DataFrame: DataFrame containing the following columns:
            - team_id (int): Unique identifier for the team
            - team_name (str): Name of the team
            - logo (str): URL or path to the team's logo
            - total_tackles (int): Sum of tackles committed by the team
            - fouls (int): Sum of fouls committed by the team
            - yellow_cards (int): Sum of yellow cards received by the team
            - red_cards (int): Sum of red cards received by the team
            - aggression_score (int): Computed weighted aggression score
    """
    
    query = """
        SELECT 
            ts.team_id,
            t.team_name,
            t.logo,
            SUM(ts.total_tackles) AS total_tackles,
            SUM(ts.fouls) AS fouls,
            SUM(ts.yellow_cards) AS yellow_cards,
            SUM(ts.red_cards) AS red_cards,
            -- Weighted aggression score formula
            (SUM(ts.total_tackles) * 1
             + SUM(ts.fouls) * 2
             + SUM(ts.yellow_cards) * 3
             + SUM(ts.red_cards) * 5) AS aggression_score
        FROM team_stats ts
        JOIN teams t ON ts.team_id = t.team_id
        GROUP BY ts.team_id, t.team_name, t.logo
        ORDER BY aggression_score DESC
        LIMIT %s;
    """
    with db_connection() as conn:
        df = pd.read_sql(query, conn, params=(limit,))
    return df