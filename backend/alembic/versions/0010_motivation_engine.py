"""Phase 10 — motivation engine tables

Revision ID: 0010_motivation_engine
Revises: <SET_TO_YOUR_LATEST_HEAD>
Create Date: 2026-07-25
"""
from alembic import op
import sqlalchemy as sa

# TODO: set `down_revision` to whatever your current alembic head is
# (run `alembic heads` in backend/ to find it) before applying.
revision = "0010_motivation_engine"
down_revision = "af3625856fba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "motivation_practice_days",
        sa.Column("practice_date", sa.Date, primary_key=True),
        sa.Column("session_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("practice_minutes", sa.Float, nullable=False, server_default="0"),
    )

    op.create_table(
        "motivation_goals",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("target_value", sa.Float, nullable=False),
        sa.Column("starting_value", sa.Float, nullable=False, server_default="0"),
        sa.Column("deadline", sa.Date, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("achieved_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "motivation_practice_items",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source_session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("difficulty", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("easiness_factor", sa.Float, nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("repetitions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_review_date", sa.Date, nullable=False),
        sa.Column("last_score", sa.Float, nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime, nullable=True),
        sa.Column("is_mastered", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_index(
        "ix_practice_items_next_review", "motivation_practice_items", ["next_review_date"]
    )

    op.create_table(
        "motivation_practice_item_sources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.String, sa.ForeignKey("motivation_practice_items.id"), nullable=False),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("added_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "motivation_user_achievements",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("achievement_id", sa.String, nullable=False, unique=True),
        sa.Column("unlocked_at", sa.DateTime, nullable=True),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=True),
    )

    op.create_table(
        "motivation_weekly_summaries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("week_start", sa.Date, nullable=False, unique=True),
        sa.Column("sessions_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("practice_time_hours", sa.Float, nullable=False, server_default="0"),
        sa.Column("score_trend", sa.String, nullable=False, server_default="stable"),
        sa.Column("narrative", sa.Text, nullable=False, server_default=""),
        sa.Column("focus_areas", sa.Text, nullable=False, server_default="[]"),
        sa.Column("celebration", sa.Text, nullable=False, server_default="[]"),
        sa.Column("next_week_plan", sa.Text, nullable=False, server_default="[]"),
        sa.Column("generated_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "motivation_reflections",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("prompt_id", sa.String, nullable=False),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("response", sa.Text, nullable=True),
        sa.Column("self_rating", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "motivation_calibration",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=False, unique=True),
        sa.Column("self_rating", sa.Float, nullable=False),
        sa.Column("actual_score", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "motivation_interview_days",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("company_format", sa.String, nullable=False, server_default="custom"),
        sa.Column("total_rounds", sa.Integer, nullable=False, server_default="3"),
        sa.Column("break_duration_minutes", sa.Integer, nullable=False, server_default="10"),
        sa.Column("include_lunch_break", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("fatigue_tracking", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String, nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "motivation_interview_day_rounds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("day_id", sa.String, sa.ForeignKey("motivation_interview_days.id"), nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
    )

    op.create_table(
        "motivation_notification_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("streak_reminders", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("weekly_summary", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("goal_progress", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("achievements", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("quiet_hours_start", sa.String, nullable=False, server_default="21:00"),
        sa.Column("quiet_hours_end", sa.String, nullable=False, server_default="09:00"),
        sa.Column("max_per_day", sa.Integer, nullable=False, server_default="1"),
    )

    op.create_table(
        "motivation_notification_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("notification_type", sa.String, nullable=False),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("payload", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("motivation_notification_log")
    op.drop_table("motivation_notification_settings")
    op.drop_table("motivation_interview_day_rounds")
    op.drop_table("motivation_interview_days")
    op.drop_table("motivation_calibration")
    op.drop_table("motivation_reflections")
    op.drop_table("motivation_weekly_summaries")
    op.drop_table("motivation_user_achievements")
    op.drop_table("motivation_practice_item_sources")
    op.drop_index("ix_practice_items_next_review", table_name="motivation_practice_items")
    op.drop_table("motivation_practice_items")
    op.drop_table("motivation_goals")
    op.drop_table("motivation_practice_days")
