"""
PostgreSQL Row-Level Security (RLS) helpers.
Every table with landlord_id has RLS policies applied so that a Postgres
role can only see rows belonging to the current landlord.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ── RLS Policy SQL (run once during migrations) ───────────────────────────────

RLS_SETUP_SQL = """
-- Create application role (non-superuser)
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user LOGIN PASSWORD 'CHANGE_ME_APP_USER_PASSWORD';
  END IF;
END $$;

GRANT CONNECT ON DATABASE nyumba_db TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;

-- Create a Postgres config parameter for the current landlord context
-- The app sets this at the start of each request via set_tenant_context()
"""

def get_rls_policy_sql(table_name: str) -> str:
    """Generate RLS enable + policy SQL for a given table."""
    return f"""
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS landlord_isolation ON {table_name};
CREATE POLICY landlord_isolation ON {table_name}
    USING (
        landlord_id = NULLIF(current_setting('app.current_landlord_id', TRUE), '')::uuid
    );

-- Bypass for superuser / migrations
ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;
"""


TABLES_WITH_RLS = [
    "properties",
    "units",
    "tenants",
    "leases",
    "payments",
    "payment_flags",
    "ai_usage_logs",
    "mortgage_accounts",
]


# ── Runtime tenant context ────────────────────────────────────────────────────

async def set_tenant_context(db: AsyncSession, landlord_id: str) -> None:
    """
    Set the PostgreSQL session variable used by RLS policies.
    Must be called once per request/session before any data query.
    """
    await db.execute(
        text("SELECT set_config('app.current_landlord_id', :lid, TRUE)"),
        {"lid": str(landlord_id)},
    )


async def clear_tenant_context(db: AsyncSession) -> None:
    await db.execute(text("SELECT set_config('app.current_landlord_id', '', TRUE)"))
