"""Add email and error_message to EmailLog (idempotent)"""

from alembic import op
import sqlalchemy as sa

# Alembic identifiers
revision = 'e94ba5b3824d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Идемпотентные изменения: не падают, если колонка уже есть
    op.execute("ALTER TABLE email_log ADD COLUMN IF NOT EXISTS email VARCHAR(120)")
    op.execute("ALTER TABLE email_log ADD COLUMN IF NOT EXISTS error_message TEXT")


def downgrade():
    op.execute("ALTER TABLE email_log DROP COLUMN IF EXISTS error_message")
    op.execute("ALTER TABLE email_log DROP COLUMN IF EXISTS email")
