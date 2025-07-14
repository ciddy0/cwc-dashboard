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
            COUNT(DISTINCT ts.match_id) AS matches_played,
            SUM(ts.total_tackles) AS total_tackles,
            SUM(ts.fouls) AS fouls,
            SUM(ts.yellow_cards) AS yellow_cards,
            SUM(ts.red_cards) AS red_cards,
            -- Raw aggression score
            (SUM(ts.total_tackles) * 1 +
            SUM(ts.fouls) * 2 +
            SUM(ts.yellow_cards) * 3 +
            SUM(ts.red_cards) * 5) AS total_aggression_score,
            ROUND(
                (SUM(ts.total_tackles) * 1 +
                SUM(ts.fouls) * 2 +
                SUM(ts.yellow_cards) * 3 +
                SUM(ts.red_cards) * 5)::numeric
                / NULLIF(COUNT(DISTINCT ts.match_id), 0), 2
            ) AS aggression_score_per_match
        FROM team_stats ts
        JOIN teams t ON ts.team_id = t.team_id
        GROUP BY ts.team_id, t.team_name, t.logo
        ORDER BY aggression_score_per_match DESC
        LIMIT %s;
    """
    with db_connection() as conn:
        df = pd.read_sql(query, conn, params=(limit,))
    return df

@st.cache_data(ttl=600)
def get_best_defensive_teams(limit=5):
    query = """
        SELECT
            ts.team_id,
            t.team_name,
            t.logo,
            SUM(ts.yellow_cards) AS total_yellow_cards,
            SUM(ts.blocked_shots) AS total_blocked_shots,
            SUM(ts.total_tackles) AS total_tackles,
            SUM(ts.effective_tackles) AS total_effective_tackles,
            SUM(ts.interceptions) AS total_interceptions,
            SUM(ts.total_clearance) AS total_clearance,
            SUM(ts.effective_clearance) AS total_effective_clearance,
            SUM(opp.offsides) AS offsides_against,
            -- Calculate goals conceded based on match role
            SUM(
                CASE 
                    WHEN ts.team_id = m.home_team_id THEN m.away_score
                    WHEN ts.team_id = m.away_team_id THEN m.home_score
                    ELSE 0
                END
            ) AS goals_conceded,
            -- Raw defensive score
            (
                SUM(opp.offsides) * 2.0 +
                SUM(ts.yellow_cards) * 1.0 +
                SUM(ts.blocked_shots) * 1.5 +
                SUM(ts.total_tackles) * 1.0 +
                SUM(ts.effective_tackles) * 2.5 +
                SUM(ts.interceptions) * 1.5 +
                SUM(ts.total_clearance) * 1.0 +
                SUM(ts.effective_clearance) * 2.5
            ) AS raw_score,
            -- Final adjusted score
            (
                (
                    SUM(opp.offsides) * 2.0 +
                    SUM(ts.yellow_cards) * 1.0 +
                    SUM(ts.blocked_shots) * 1.5 +
                    SUM(ts.total_tackles) * 1.0 +
                    SUM(ts.effective_tackles) * 2.5 +
                    SUM(ts.interceptions) * 1.5 +
                    SUM(ts.total_clearance) * 1.0 +
                    SUM(ts.effective_clearance) * 2.5
                ) - 
                SUM(
                    CASE 
                        WHEN ts.team_id = m.home_team_id THEN m.away_score
                        WHEN ts.team_id = m.away_team_id THEN m.home_score
                        ELSE 0
                    END
                ) * 2.0
            ) / (1 + 
                SUM(
                    CASE 
                        WHEN ts.team_id = m.home_team_id THEN m.away_score
                        WHEN ts.team_id = m.away_team_id THEN m.home_score
                        ELSE 0
                    END
                )
            ) AS defensive_score

        FROM team_stats ts
        JOIN teams t ON ts.team_id = t.team_id
        JOIN matches m ON ts.match_id = m.id
        JOIN team_stats opp ON ts.match_id = opp.match_id AND ts.team_id != opp.team_id

        GROUP BY ts.team_id, t.team_name, t.logo
        ORDER BY defensive_score DESC
        LIMIT %s;
    """
    with db_connection() as conn:
        df = pd.read_sql(query, conn, params=(limit,))
    return df

@st.cache_data(ttl=600)
def get_best_attacking_teams(limit=5):
    query = """
        SELECT
            ts.team_id,
            t.team_name,
            t.logo,
            COUNT(*) AS matches_played,
            SUM(ts.total_shots) AS total_shots,
            SUM(ts.shots_on_target) AS shots_on_target,
            SUM(ts.total_crosses) AS total_crosses,
            SUM(ts.accurate_crosses) AS accurate_crosses,
            SUM(ts.total_long_balls) AS total_long_balls,
            SUM(ts.accurate_long_balls) AS accurate_long_balls,
            AVG(ts.possession_pct) AS avg_possession,
            AVG(ts.pass_pct) AS avg_pass_pct,
            SUM(ts.corners) AS won_corners,
            -- Goals scored
            SUM(
              CASE 
                WHEN ts.team_id = m.home_team_id THEN m.home_score
                WHEN ts.team_id = m.away_team_id THEN m.away_score
                ELSE 0
              END
            ) AS goals_scored,

            -- Match wins
            SUM(
              CASE
                WHEN ts.team_id = m.home_team_id AND m.home_score > m.away_score THEN 1
                WHEN ts.team_id = m.away_team_id AND m.away_score > m.home_score THEN 1
                ELSE 0
              END
            ) AS match_wins,
            (
              SUM(ts.total_shots) * 1.5 +
              SUM(ts.shots_on_target) * 2.0 +
              SUM(ts.total_crosses) * 1.0 +
              SUM(ts.accurate_crosses) * 2.0 +
              SUM(ts.total_long_balls) * 0.5 +
              SUM(ts.accurate_long_balls) * 1.0 +
              SUM(ts.corners) * 1.0 +
              AVG(ts.possession_pct) * 0.5 +
              AVG(ts.pass_pct) * 0.5 +
              SUM(
                CASE 
                  WHEN ts.team_id = m.home_team_id THEN m.home_score
                  WHEN ts.team_id = m.away_team_id THEN m.away_score
                  ELSE 0
                END
              ) * 4.0 +
              SUM(
                CASE
                  WHEN ts.team_id = m.home_team_id AND m.home_score > m.away_score THEN 1
                  WHEN ts.team_id = m.away_team_id AND m.away_score > m.home_score THEN 1
                  ELSE 0
                END
              ) * 3.0
            ) / COUNT(*) AS attacking_score_per_match
        FROM team_stats ts
        JOIN teams t ON ts.team_id = t.team_id
        JOIN matches m ON ts.match_id = m.id
        GROUP BY ts.team_id, t.team_name, t.logo
        ORDER BY attacking_score_per_match DESC
        LIMIT %s;
    """
    with db_connection() as conn:
        df = pd.read_sql(query, conn, params=(limit,))
    return df

@st.cache_data(ttl=3600)
def get_all_teams():
    query = """
        SELECT team_id, team_name, logo 
        FROM teams 
        ORDER BY team_name;
    """
    with db_connection() as conn:
        return pd.read_sql(query, conn)

@st.cache_data(ttl=600)
def get_team_overview_stats(team_id):
    query = """
        SELECT
          COUNT(*) AS matches,
          SUM(CASE 
              WHEN ts.team_id = m.home_team_id AND m.home_score > m.away_score THEN 1
              WHEN ts.team_id = m.away_team_id AND m.away_score > m.home_score THEN 1
              ELSE 0
          END) AS wins,
          SUM(CASE 
              WHEN ts.team_id = m.home_team_id THEN m.home_score
              WHEN ts.team_id = m.away_team_id THEN m.away_score
              ELSE 0
          END) AS goals_scored,
          SUM(CASE 
              WHEN ts.team_id = m.home_team_id THEN m.away_score
              WHEN ts.team_id = m.away_team_id THEN m.home_score
              ELSE 0
          END) AS goals_conceded,
          AVG(ts.possession_pct) AS avg_possession,
          AVG(ts.pass_pct) AS avg_pass_pct,
          AVG(ts.total_shots) AS avg_shots,
          SUM(ts.corners) AS corners
        FROM team_stats ts
        JOIN matches m ON ts.match_id = m.id
        WHERE ts.team_id = %s;
    """
    with db_connection() as conn:
        return pd.read_sql(query, conn, params=(team_id,)).iloc[0].to_dict()

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
    query = """
        SELECT
            ROW_NUMBER() OVER (ORDER BY m.date) AS match_number,
            CASE
                WHEN ts.team_id = m.home_team_id THEN m.home_score
                ELSE m.away_score
            END AS goals_scored
        FROM team_stats ts
        JOIN matches m ON ts.match_id = m.id
        WHERE ts.team_id = %s
        ORDER BY m.date;
    """
    with db_connection() as conn:
        df = pd.read_sql(query, conn, params=(team_id,))
    return df
