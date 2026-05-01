"""Initial schema with RLS policies.

Revision ID: 0001_initial
Revises: 
Create Date: 2025-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

# Tables that need Row-Level Security
RLS_TABLES = [
    "properties", "units", "tenants", "leases",
    "payments", "payment_flags", "ai_usage_logs", "mortgage_accounts",
]


def upgrade() -> None:
    # All CREATE TABLE statements are handled by SQLAlchemy metadata.
    # Here we only apply RLS policies post-creation.
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"""
            DROP POLICY IF EXISTS landlord_isolation ON {table};
            CREATE POLICY landlord_isolation ON {table}
                USING (
                    landlord_id = NULLIF(
                        current_setting('app.current_landlord_id', TRUE), ''
                    )::uuid
                );
        """)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")

    # Grant superuser bypass (for migrations)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'migration_user') THEN
                -- migrations run as the DB owner / superuser, so RLS is bypassed automatically
                NULL;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS landlord_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
