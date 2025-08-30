"""Create analytics tables (idempotent): search_click, partner_click"""

from alembic import op
import sqlalchemy as sa

# Alembic identifiers
revision = '7c7d3a0c8f1b'
down_revision = 'e94ba5b3824d'
branch_labels = None
depends_on = None


def upgrade():
    # --- search_click (создать, если нет) ---
    op.execute("""
    CREATE TABLE IF NOT EXISTS search_click (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ip VARCHAR(64),
        country VARCHAR(2),
        city VARCHAR(128),
        lat DOUBLE PRECISION,
        lon DOUBLE PRECISION,
        user_agent VARCHAR(512),
        lang VARCHAR(8),
        is_refugee BOOLEAN,
        countries TEXT,
        jobs TEXT,
        city_query VARCHAR(256)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_search_click_created_at ON search_click (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_search_click_ip ON search_click (ip)")

    # --- partner_click (создать, если нет) ---
    op.execute("""
    CREATE TABLE IF NOT EXISTS partner_click (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ip VARCHAR(64),
        country VARCHAR(2),
        city VARCHAR(128),
        lat DOUBLE PRECISION,
        lon DOUBLE PRECISION,
        user_agent VARCHAR(512),
        lang VARCHAR(8),
        partner VARCHAR(32),
        target_domain VARCHAR(128),
        target_url TEXT,
        job_id VARCHAR(128),
        job_title VARCHAR(256)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_partner_click_created_at ON partner_click (created_at)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_partner_click_created_at")
    op.execute("DROP TABLE IF EXISTS partner_click")
    op.execute("DROP INDEX IF EXISTS ix_search_click_ip")
    op.execute("DROP INDEX IF EXISTS ix_search_click_created_at")
    op.execute("DROP TABLE IF EXISTS search_click")
