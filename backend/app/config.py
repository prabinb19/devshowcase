from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:dev@localhost:5432/devshowcase"
    github_token: str = ""
    e2b_api_key: str = ""
    e2b_template_id: str = ""  # Custom template name/ID; empty = default desktop
    token_encryption_key: str = ""
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:3000/api/linkedin/callback"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    checkpoint_url: str = ""
    gemini_api_key: str = ""
    portfolio_repo: str = ""
    portfolio_owner: str = ""
    agent_sandbox_timeout: int = 600
    rate_limit_runs_per_hour: int = 10
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    db_pool_size: int = 5
    db_max_overflow: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
