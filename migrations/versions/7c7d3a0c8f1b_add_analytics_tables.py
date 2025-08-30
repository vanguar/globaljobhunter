"""Create analytics tables: search_click, partner_click"""

from alembic import op
import sqlalchemy as sa

revision = '7c7d3a0c8f1b'
down_revision = 'e94ba5b3824d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'search_click',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('ip', sa.String(length=64), index=True),
        sa.Column('country', sa.String(length=2)),
        sa.Column('city', sa.String(length=128)),
        sa.Column('lat', sa.Float()),
        sa.Column('lon', sa.Float()),
        sa.Column('user_agent', sa.String(length=512)),
        sa.Column('lang', sa.String(length=8)),
        sa.Column('is_refugee', sa.Boolean()),
        sa.Column('countries', sa.Text()),
        sa.Column('jobs', sa.Text()),
        sa.Column('city_query', sa.String(length=256)),
    )
    op.create_index('ix_search_click_created_at', 'search_click', ['created_at'])
    op.create_index('ix_search_click_ip', 'search_click', ['ip'])

    op.create_table(
        'partner_click',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('ip', sa.String(length=64), index=True),
        sa.Column('country', sa.String(length=2)),
        sa.Column('city', sa.String(length=128)),
        sa.Column('lat', sa.Float()),
        sa.Column('lon', sa.Float()),
        sa.Column('user_agent', sa.String(length=512)),
        sa.Column('lang', sa.String(length=8)),
        sa.Column('partner', sa.String(length=32), index=True),
        sa.Column('target_domain', sa.String(length=128)),
        sa.Column('target_url', sa.Text()),
        sa.Column('job_id', sa.String(length=128)),
        sa.Column('job_title', sa.String(length=256)),
    )
    op.create_index('ix_partner_click_created_at', 'partner_click', ['created_at'])


def downgrade():
    op.drop_index('ix_partner_click_created_at', table_name='partner_click')
    op.drop_table('partner_click')
    op.drop_index('ix_search_click_ip', table_name='search_click')
    op.drop_index('ix_search_click_created_at', table_name='search_click')
    op.drop_table('search_click')
