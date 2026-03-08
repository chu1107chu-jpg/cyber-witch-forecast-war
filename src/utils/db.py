"""Клиент Supabase."""
import os
from functools import lru_cache
from supabase import create_client, Client


@lru_cache(maxsize=1)
def get_db() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, key)
