from supabase import create_client
from app.config import settings

# Admin client (secret key) — bypasses RLS, used for all DB operations
supabase = create_client(settings.supabase_url, settings.supabase_secret_key)

# Auth client (publishable key) — used only for sign_in_with_password
# Keeps the admin client's auth context clean
supabase_auth_client = create_client(settings.supabase_url, settings.supabase_publishable_key)
