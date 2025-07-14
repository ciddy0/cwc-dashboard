# Club World Cuup 2025 Soccer Stats Dashboard

An interactive Streamlit-powered dashboard showcasing match and tournament statistics for the club World Cup 2025.

## Overview

This repository contains the front-end application for viewing soccer statistics. The data backing the dashboard is ingested via a seperate Data Pipeline from the ESPN API, transformed, and loaded into a Supabase PostgreSQL database

> **Note**: This dashboard is hosted on Streamlit Cloud and is *not* intended for local cloning or setup. To view the live app, visit [Club World Cup Dashboard](https://cwc-dashboard.streamlit.app/)

## Data Pipeline
The end-to-end ETL pipeline is maintained in its own repository:
- **Data Pipeline repo**: https://github.com/ciddy0/club-world-cup-data-lake-2025

This pipeline:
1. **Extracts** match, team, and player stats from the ESPN public API.
2. **Transforms** raw JSON into structured tables.
3. **Loads** cleaned data into Supabase database.

## Supabase Database

- **Hosting**: Supabase PostgreSQL.
- **Credentials**: managaed securely via Streamlit secrets.

The database contains tables for:
- ```matches```
- ```teams```
- ```player_stats```
- ```team_stats```

## Dashboard Structure

- **Main App**: ```dashboard.py``` - Sets up Streamlit tabs.
- **UI Layer**: ```ui.py``` - Defines rendering for:
  - Match-level stats
  - Tournament-wide stats
  - Team profiles
- **DB Layer**: ```db.py``` - Query functions (cached) to fetch data from Supabse.
- **Utilites**: ```utils.py``` - Database connection helper.

## Viewing the App

Access the live dashboard here:
> [Club World Cup 2025 Dasboard on Streamliy Cloud](https://cwc-dashboard.streamlit.app/)

*No local installation required.*

© 2025 Diego Cid
