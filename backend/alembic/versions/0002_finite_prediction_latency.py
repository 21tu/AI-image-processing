"""Reject non-finite prediction latency."""

from alembic import op

revision = "0002_finite_prediction_latency"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        op.f("ck_predictions_latency_nonnegative"), "predictions", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_predictions_latency_nonnegative"),
        "predictions",
        "latency_ms >= 0 AND latency_ms <> 'NaN'::float8 "
        "AND latency_ms < 'Infinity'::float8",
    )


def downgrade():
    op.drop_constraint(
        op.f("ck_predictions_latency_nonnegative"), "predictions", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_predictions_latency_nonnegative"), "predictions", "latency_ms >= 0"
    )
