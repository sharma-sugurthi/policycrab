"""Legacy SQLAlchemy database module removed.

User data is stored through app.services.user_data using Supabase/Postgres.
Do not add new SQLAlchemy dependencies here.
"""


async def get_db():
    raise RuntimeError("SQLAlchemy has been removed. Use app.services.user_data instead.")


async def init_db():
    raise RuntimeError("SQLAlchemy startup initialization has been removed. Use Supabase migrations.")
