-- supabase_functions.sql
--
-- PostgreSQL functions required by the Supabase RPC calls in db.py.
-- Run this entire file in the Supabase SQL Editor (Dashboard → SQL Editor → New query).
--
-- These functions replace the raw SQL queries that were previously executed
-- via psycopg2. Each function is called from Python via supabase.rpc("fn_name", {...}).


-- Returns team stats for a given match, joined with team name.
CREATE OR REPLACE FUNCTION fn_get_team_stats(p_match_id text)
RETURNS TABLE(team_id text, team_name text, stats jsonb)
LANGUAGE sql STABLE AS $$
    SELECT ts.team_id, t.team_name, ts.stats
    FROM team_stats ts
    JOIN teams t USING(team_id)
    WHERE ts.match_id = p_match_id;
$$;


-- Returns top players for a match, ranked by goals + assists.
CREATE OR REPLACE FUNCTION fn_get_top_players_by_match(p_match_id text, p_limit int DEFAULT 5)
RETURNS TABLE(name text, team_name text, logo text, goals int, assists int, ga int)
LANGUAGE sql STABLE AS $$
    SELECT
        p.full_name AS name,
        t.team_name,
        t.logo,
        ps.goals,
        ps.assists,
        (ps.goals + ps.assists) AS ga
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.player_id
    JOIN teams t ON p.team_id = t.team_id
    WHERE ps.match_id = p_match_id
    ORDER BY ga DESC
    LIMIT p_limit;
$$;


-- Returns top players aggregated across all matches, ranked by total goals + assists.
CREATE OR REPLACE FUNCTION fn_get_top_players_all_matches(p_limit int DEFAULT 5)
RETURNS TABLE(name text, team_name text, logo text, goals bigint, assists bigint, ga bigint)
LANGUAGE sql STABLE AS $$
    SELECT
        p.full_name AS name,
        t.team_name,
        t.logo,
        SUM(ps.goals) AS goals,
        SUM(ps.assists) AS assists,
        SUM(ps.goals + ps.assists) AS ga
    FROM player_stats ps
    JOIN players p ON ps.player_id = p.player_id
    JOIN teams t ON p.team_id = t.team_id
    GROUP BY p.player_id, p.full_name, t.team_name, t.logo
    ORDER BY ga DESC
    LIMIT p_limit;
$$;


-- Returns top goalkeepers ranked by save percentage across all matches.
CREATE OR REPLACE FUNCTION fn_get_top_goalkeepers_all_matches(p_limit int DEFAULT 5)
RETURNS TABLE(
    name text, team_name text, logo text,
    matches bigint, saves float, goals_conceded float, save_pct numeric
)
LANGUAGE sql STABLE AS $$
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
    LIMIT p_limit;
$$;


-- Returns the most aggressive teams based on a weighted score per match.
CREATE OR REPLACE FUNCTION fn_get_most_aggressive_teams(p_limit int DEFAULT 5)
RETURNS TABLE(
    team_id text, team_name text, logo text,
    matches_played bigint, total_tackles bigint, fouls bigint,
    yellow_cards bigint, red_cards bigint,
    total_aggression_score bigint, aggression_score_per_match numeric
)
LANGUAGE sql STABLE AS $$
    SELECT
        ts.team_id,
        t.team_name,
        t.logo,
        COUNT(DISTINCT ts.match_id) AS matches_played,
        SUM(ts.total_tackles) AS total_tackles,
        SUM(ts.fouls) AS fouls,
        SUM(ts.yellow_cards) AS yellow_cards,
        SUM(ts.red_cards) AS red_cards,
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
    LIMIT p_limit;
$$;


-- Returns the best defensive teams based on a weighted defensive score.
CREATE OR REPLACE FUNCTION fn_get_best_defensive_teams(p_limit int DEFAULT 5)
RETURNS TABLE(
    team_id text, team_name text, logo text,
    total_yellow_cards bigint, total_blocked_shots bigint,
    total_tackles bigint, total_effective_tackles bigint,
    total_interceptions bigint, total_clearance bigint,
    total_effective_clearance bigint, offsides_against bigint,
    goals_conceded bigint, raw_score float, defensive_score float
)
LANGUAGE sql STABLE AS $$
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
        SUM(
            CASE
                WHEN ts.team_id = m.home_team_id THEN m.away_score
                WHEN ts.team_id = m.away_team_id THEN m.home_score
                ELSE 0
            END
        ) AS goals_conceded,
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
    LIMIT p_limit;
$$;


-- Returns the best attacking teams based on a weighted score per match.
CREATE OR REPLACE FUNCTION fn_get_best_attacking_teams(p_limit int DEFAULT 5)
RETURNS TABLE(
    team_id text, team_name text, logo text,
    matches_played bigint, total_shots bigint, shots_on_target bigint,
    total_crosses bigint, accurate_crosses bigint,
    total_long_balls bigint, accurate_long_balls bigint,
    avg_possession float, avg_pass_pct float,
    won_corners bigint, goals_scored bigint, match_wins bigint,
    attacking_score_per_match float
)
LANGUAGE sql STABLE AS $$
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
        SUM(
            CASE
                WHEN ts.team_id = m.home_team_id THEN m.home_score
                WHEN ts.team_id = m.away_team_id THEN m.away_score
                ELSE 0
            END
        ) AS goals_scored,
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
    LIMIT p_limit;
$$;


-- Returns aggregated overview stats for a specific team.
CREATE OR REPLACE FUNCTION fn_get_team_overview_stats(p_team_id text)
RETURNS TABLE(
    matches bigint, wins bigint, goals_scored bigint,
    goals_conceded bigint, avg_possession float, avg_pass_pct float,
    avg_shots float, corners bigint
)
LANGUAGE sql STABLE AS $$
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
    WHERE ts.team_id = p_team_id;
$$;


-- Returns goals scored per match for a team, ordered chronologically.
CREATE OR REPLACE FUNCTION fn_get_team_goals_by_match(p_team_id text)
RETURNS TABLE(match_number bigint, goals_scored int)
LANGUAGE sql STABLE AS $$
    SELECT
        ROW_NUMBER() OVER (ORDER BY m.date) AS match_number,
        CASE
            WHEN ts.team_id = m.home_team_id THEN m.home_score
            ELSE m.away_score
        END AS goals_scored
    FROM team_stats ts
    JOIN matches m ON ts.match_id = m.id
    WHERE ts.team_id = p_team_id
    ORDER BY m.date;
$$;