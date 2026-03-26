"""
utils.py

Supabase client utility for the Soccer Stats Dashboard

Provides a cached Supabase client that connects via REST API (HTTPS),
avoiding direct PostgreSQL connection issues (pooler/IPv6).

Dependencies:
- streamlit
- supabase

Functions:
- get_supabase_client(): Returns a cached Supabase client instance.
"""

import streamlit as st
from supabase import create_client, Client

SUPABASE_URL = "https://fkbzjxgughuqlwbvdtyk.supabase.co"

@st.cache_resource
def get_supabase_client() -> Client:
    """
    Creates and returns a cached Supabase client.

    Reads the API key from Streamlit secrets (SUPABASE_KEY).
    Cached with st.cache_resource so the client is reused across reruns.

    Returns:
        supabase.Client: An authenticated Supabase client instance.
    """
    return create_client(SUPABASE_URL, st.secrets["SUPABASE_KEY"])
