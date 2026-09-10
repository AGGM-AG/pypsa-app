"""Add network_folders table and networks.folder_id.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    visibility = sa.Enum("public", "private", name="visibility", create_type=False)
    op.create_table(
        "network_folders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("visibility", visibility, nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_network_folders_created_at"), "network_folders", ["created_at"]
    )
    op.create_index(
        op.f("ix_network_folders_path"), "network_folders", ["path"], unique=True
    )
    op.create_index(op.f("ix_network_folders_user_id"), "network_folders", ["user_id"])
    op.create_index(
        op.f("ix_network_folders_visibility"), "network_folders", ["visibility"]
    )
    with op.batch_alter_table("networks") as batch_op:
        batch_op.add_column(sa.Column("folder_id", sa.Uuid(), nullable=True))
        batch_op.create_index(op.f("ix_networks_folder_id"), ["folder_id"])
        batch_op.create_foreign_key(
            "fk_networks_folder_id_network_folders",
            "network_folders",
            ["folder_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("networks") as batch_op:
        batch_op.drop_constraint(
            "fk_networks_folder_id_network_folders", type_="foreignkey"
        )
        batch_op.drop_index(op.f("ix_networks_folder_id"))
        batch_op.drop_column("folder_id")
    op.drop_index(op.f("ix_network_folders_visibility"), table_name="network_folders")
    op.drop_index(op.f("ix_network_folders_user_id"), table_name="network_folders")
    op.drop_index(op.f("ix_network_folders_path"), table_name="network_folders")
    op.drop_index(op.f("ix_network_folders_created_at"), table_name="network_folders")
    op.drop_table("network_folders")
