"""Legacy SQLAlchemy models removed.

UserPolicy and UserClaim are now represented by Supabase tables created in
supabase/migrations/002_create_user_data_tables.sql and accessed through
app.services.user_data.
"""
