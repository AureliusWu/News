"""Real news sources, articles and durable synchronization watermarks."""
from alembic import op
import sqlalchemy as sa

revision = "0002_news"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table("sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("publisher", sa.String(200), nullable=False),
        sa.Column("homepage", sa.String(1024), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("feed_url", sa.String(2048), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("rsshub_path", sa.String(512)),
        sa.Column("country", sa.String(8), nullable=False),
        sa.Column("region", sa.String(32), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("miniflux_feed_id", sa.BigInteger(), unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("health_status", sa.String(32), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        *timestamps())
    op.create_table("articles",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("miniflux_entry_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("miniflux_hash", sa.String(255)),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("canonical_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("author", sa.String(255)),
        sa.Column("summary", sa.Text()),
        sa.Column("content_html", sa.Text()),
        sa.Column("image_url", sa.Text()),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("region", sa.String(32), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps())
    op.create_index("ix_articles_published_id", "articles", ["published_at", "id"])
    op.create_index("ix_articles_source_published", "articles", ["source_id", "published_at"])
    op.create_index("ix_articles_region_category", "articles", ["region", "category", "published_at"])
    op.create_index("ix_articles_canonical_url", "articles", ["canonical_url"], postgresql_using="hash")
    op.create_table("sync_state",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.String(2048)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("sync_state")
    op.drop_table("articles")
    op.drop_table("sources")