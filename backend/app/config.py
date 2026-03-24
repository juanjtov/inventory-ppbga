from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str
    cors_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()

# Note: We maintain two Supabase clients:
# - supabase_admin (secret key): for all DB operations (bypasses RLS)
# - supabase_auth (publishable key): for auth operations (sign_in_with_password)
# This is needed because sign_in_with_password changes the client's auth context,
# which would break subsequent DB queries if done on the admin client.
