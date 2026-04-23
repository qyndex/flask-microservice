"""Initial schema — jobs and events tables.

Revision ID: 001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Jobs table
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_name", sa.String(200), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="job_status_enum"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payload", sa.Text(), server_default="{}"),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(36), nullable=True, unique=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Events table
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("info", "warning", "error", "critical", name="event_severity_enum"),
            nullable=False,
            server_default="info",
        ),
        sa.Column("payload", sa.Text(), server_default="{}"),
        sa.Column("metadata_json", sa.Text(), server_default="{}"),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Indexes for events
    op.create_index("ix_events_source_type", "events", ["source", "event_type"])
    op.create_index("ix_events_created_at", "events", ["created_at"])
    op.create_index("ix_events_processed", "events", ["is_processed"])


def downgrade() -> None:
    op.drop_index("ix_events_processed", table_name="events")
    op.drop_index("ix_events_created_at", table_name="events")
    op.drop_index("ix_events_source_type", table_name="events")
    op.drop_table("events")
    op.drop_table("jobs")
    op.execute("DROP TYPE IF EXISTS event_severity_enum")
    op.execute("DROP TYPE IF EXISTS job_status_enum")
