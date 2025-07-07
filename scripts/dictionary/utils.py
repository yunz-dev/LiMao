import os
from supabase import Client, create_client


def setup_supabase_client() -> Client:
    """
    Initializes and returns the Supabase client using environment variables.
    """
    print("setting up supabase client...")
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set in your environment."
        )

    return create_client(supabase_url, supabase_key)
