"""add agent trigger event subscriptions

Revision ID: 9e7a4b2c1d3f
Revises: 8d12f3a4b5c6
Create Date: 2026-05-30 16:40:00.000000

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e7a4b2c1d3f"
down_revision: Union[str, Sequence[str], None] = "8d12f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the derived routing index for webhook trigger candidate lookup."""
    # condition remains the policy source of truth. This table only denormalizes
    # event roles so webhook ingress can use a relational source/event_type index.
    duplicate_legacy_channel_talk_event = (
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT 1
                FROM agent_triggers AS legacy
                JOIN agent_triggers AS canonical
                  ON canonical.agent_spec_id = legacy.agent_spec_id
                 AND canonical.source = legacy.source
                 AND canonical.event_type = 'user_chat.new_message'
                 AND canonical.id != legacy.id
                WHERE legacy.source = 'channel_talk'
                  AND legacy.event_type = 'user_chat.message_created'
                LIMIT 1
                """
            )
        )
        .first()
    )
    if duplicate_legacy_channel_talk_event is not None:
        raise RuntimeError(
            "Cannot canonicalize legacy Channel Talk trigger event_type while "
            "duplicate user_chat.new_message trigger definitions exist"
        )

    # Older Trigger drafts used CatchUp-normalized payload helper paths. The
    # current Channel Talk contract keeps the provider payload shape unchanged,
    # so known legacy paths must be rewritten before subscription backfill.
    op.execute(
        """
        UPDATE agent_triggers
        SET condition = replace(
            condition::text,
            '"$.payload.channel_id"',
            '"$.payload.entity.channelId"'
        )::jsonb
        WHERE source = 'channel_talk'
          AND jsonb_typeof(condition) = 'object'
          AND condition::text LIKE '%"$.payload.channel_id"%'
        """
    )
    op.execute(
        """
        UPDATE agent_triggers
        SET condition = replace(
            condition::text,
            '"user_chat.message_created"',
            '"user_chat.new_message"'
        )::jsonb
        WHERE source = 'channel_talk'
          AND jsonb_typeof(condition) = 'object'
          AND condition::text LIKE '%"user_chat.message_created"%'
        """
    )
    op.execute(
        """
        UPDATE agent_triggers
        SET event_type = 'user_chat.new_message'
        WHERE source = 'channel_talk'
          AND event_type = 'user_chat.message_created'
        """
    )
    op.execute(
        """
        UPDATE agent_triggers
        SET condition = jsonb_set(
            condition,
            '{entity_key_path}',
            to_jsonb('$.payload.entity.id'::text),
            false
        )
        WHERE source = 'channel_talk'
          AND jsonb_typeof(condition) = 'object'
          AND condition->>'entity_key_path' = '$.payload.user_chat_id'
        """
    )
    op.execute(
        """
        UPDATE agent_triggers
        SET condition = jsonb_set(
            condition,
            '{reset_entity_key_path}',
            to_jsonb('$.payload.entity.chatId'::text),
            false
        )
        WHERE source = 'channel_talk'
          AND jsonb_typeof(condition) = 'object'
          AND condition->>'reset_entity_key_path' = '$.payload.user_chat_id'
        """
    )
    op.execute(
        """
        UPDATE agent_triggers
        SET condition = jsonb_set(
            condition,
            '{where}',
            replace(
                (condition->'where')::text,
                '"$.payload.user_chat_id"',
                '"$.payload.entity.id"'
            )::jsonb,
            false
        )
        WHERE source = 'channel_talk'
          AND jsonb_typeof(condition) = 'object'
          AND condition->>'kind' = 'debounce'
          AND jsonb_typeof(condition->'where') = 'object'
          AND (condition->'where')::text LIKE '%"$.payload.user_chat_id"%'
        """
    )
    op.execute(
        """
        UPDATE agent_triggers
        SET condition = jsonb_set(
            condition,
            '{reset_where}',
            replace(
                (condition->'reset_where')::text,
                '"$.payload.user_chat_id"',
                '"$.payload.entity.chatId"'
            )::jsonb,
            false
        )
        WHERE source = 'channel_talk'
          AND jsonb_typeof(condition) = 'object'
          AND condition->>'kind' = 'debounce'
          AND jsonb_typeof(condition->'reset_where') = 'object'
          AND (condition->'reset_where')::text LIKE '%"$.payload.user_chat_id"%'
        """
    )
    op.execute(
        """
        UPDATE agent_triggers
        SET condition = jsonb_set(
            condition,
            '{where}',
            replace(
                (condition->'where')::text,
                '"$.payload.user_chat_id"',
                '"$.payload.entity.chatId"'
            )::jsonb,
            false
        )
        WHERE source = 'channel_talk'
          AND event_type = 'user_chat.new_message'
          AND jsonb_typeof(condition) = 'object'
          AND condition->>'kind' = 'immediate'
          AND jsonb_typeof(condition->'where') = 'object'
          AND (condition->'where')::text LIKE '%"$.payload.user_chat_id"%'
        """
    )
    op.execute(
        """
        UPDATE agent_triggers
        SET condition = jsonb_set(
            condition,
            '{where}',
            replace(
                (condition->'where')::text,
                '"$.payload.user_chat_id"',
                '"$.payload.entity.id"'
            )::jsonb,
            false
        )
        WHERE source = 'channel_talk'
          AND event_type = 'user_chat.created'
          AND jsonb_typeof(condition) = 'object'
          AND condition->>'kind' = 'immediate'
          AND jsonb_typeof(condition->'where') = 'object'
          AND (condition->'where')::text LIKE '%"$.payload.user_chat_id"%'
        """
    )

    op.create_table(
        "agent_trigger_event_subscriptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trigger_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["trigger_id"],
            ["agent_triggers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trigger_id",
            "source",
            "event_type",
            "role",
            name="uq_agent_trigger_event_sub_role",
        ),
    )
    op.create_index(
        "idx_agent_trigger_event_sub_lookup",
        "agent_trigger_event_subscriptions",
        ["source", "event_type"],
        unique=False,
    )
    op.create_index(
        "idx_agent_trigger_event_sub_trigger_id",
        "agent_trigger_event_subscriptions",
        ["trigger_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO agent_trigger_event_subscriptions
            (trigger_id, source, event_type, role)
        SELECT id, source, event_type, 'primary'
        FROM agent_triggers
        WHERE type = 'webhook'
          AND jsonb_typeof(condition) = 'object'
          AND condition->>'kind' = 'immediate'
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_object_keys(condition) AS condition_keys(key)
              WHERE condition_keys.key NOT IN ('kind', 'where')
          )
          AND (
              NOT condition ? 'where'
              OR jsonb_typeof(condition->'where') = 'object'
          )
          AND source IS NOT NULL
          AND event_type IS NOT NULL
        ON CONFLICT ON CONSTRAINT uq_agent_trigger_event_sub_role DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO agent_trigger_event_subscriptions
            (trigger_id, source, event_type, role)
        SELECT id, source, condition->>'start_event_type', 'start'
        FROM agent_triggers
        WHERE type = 'webhook'
          AND jsonb_typeof(condition) = 'object'
          AND condition->>'kind' = 'debounce'
          AND condition ?& ARRAY[
              'start_event_type',
              'reset_event_types',
              'entity_key_path',
              'reset_entity_key_path',
              'quiet_period_seconds'
          ]
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_object_keys(condition) AS condition_keys(key)
              WHERE condition_keys.key NOT IN (
                  'kind',
                  'start_event_type',
                  'reset_event_types',
                  'entity_key_path',
                  'reset_entity_key_path',
                  'quiet_period_seconds',
                  'run_context',
                  'where',
                  'reset_where'
              )
          )
          AND jsonb_typeof(condition->'start_event_type') = 'string'
          AND jsonb_typeof(condition->'reset_event_types') = 'array'
          AND jsonb_array_length(condition->'reset_event_types') > 0
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_array_elements(condition->'reset_event_types') AS reset_items(item)
              WHERE jsonb_typeof(reset_items.item) != 'string'
          )
          AND jsonb_typeof(condition->'entity_key_path') = 'string'
          AND jsonb_typeof(condition->'reset_entity_key_path') = 'string'
          AND CASE
              WHEN jsonb_typeof(condition->'quiet_period_seconds') = 'number'
                  THEN (condition->>'quiet_period_seconds')::numeric > 0
                      AND (condition->>'quiet_period_seconds')::numeric =
                          floor((condition->>'quiet_period_seconds')::numeric)
              WHEN jsonb_typeof(condition->'quiet_period_seconds') = 'string'
                  AND condition->>'quiet_period_seconds' ~ '^[1-9][0-9]*(\\.0+)?$'
                  THEN (condition->>'quiet_period_seconds')::numeric > 0
                      AND (condition->>'quiet_period_seconds')::numeric =
                          floor((condition->>'quiet_period_seconds')::numeric)
              ELSE false
          END
          AND (
              NOT condition ? 'run_context'
              OR jsonb_typeof(condition->'run_context') = 'string'
          )
          AND (
              NOT condition ? 'where'
              OR jsonb_typeof(condition->'where') = 'object'
          )
          AND (
              NOT condition ? 'reset_where'
              OR jsonb_typeof(condition->'reset_where') = 'object'
          )
          AND source IS NOT NULL
          AND condition->>'start_event_type' IS NOT NULL
        ON CONFLICT ON CONSTRAINT uq_agent_trigger_event_sub_role DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO agent_trigger_event_subscriptions
            (trigger_id, source, event_type, role)
        SELECT t.id, t.source, reset_events.event_type, 'reset'
        FROM agent_triggers AS t
        CROSS JOIN LATERAL jsonb_array_elements_text(
            CASE
                WHEN jsonb_typeof(t.condition->'reset_event_types') = 'array'
                    THEN t.condition->'reset_event_types'
                ELSE '[]'::jsonb
            END
        ) AS reset_events(event_type)
        WHERE t.type = 'webhook'
          AND jsonb_typeof(t.condition) = 'object'
          AND t.condition->>'kind' = 'debounce'
          AND t.condition ?& ARRAY[
              'start_event_type',
              'reset_event_types',
              'entity_key_path',
              'reset_entity_key_path',
              'quiet_period_seconds'
          ]
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_object_keys(t.condition) AS condition_keys(key)
              WHERE condition_keys.key NOT IN (
                  'kind',
                  'start_event_type',
                  'reset_event_types',
                  'entity_key_path',
                  'reset_entity_key_path',
                  'quiet_period_seconds',
                  'run_context',
                  'where',
                  'reset_where'
              )
          )
          AND jsonb_typeof(t.condition->'start_event_type') = 'string'
          AND jsonb_typeof(t.condition->'reset_event_types') = 'array'
          AND jsonb_array_length(t.condition->'reset_event_types') > 0
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_array_elements(t.condition->'reset_event_types') AS reset_items(item)
              WHERE jsonb_typeof(reset_items.item) != 'string'
          )
          AND jsonb_typeof(t.condition->'entity_key_path') = 'string'
          AND jsonb_typeof(t.condition->'reset_entity_key_path') = 'string'
          AND CASE
              WHEN jsonb_typeof(t.condition->'quiet_period_seconds') = 'number'
                  THEN (t.condition->>'quiet_period_seconds')::numeric > 0
                      AND (t.condition->>'quiet_period_seconds')::numeric =
                          floor((t.condition->>'quiet_period_seconds')::numeric)
              WHEN jsonb_typeof(t.condition->'quiet_period_seconds') = 'string'
                  AND t.condition->>'quiet_period_seconds' ~ '^[1-9][0-9]*(\\.0+)?$'
                  THEN (t.condition->>'quiet_period_seconds')::numeric > 0
                      AND (t.condition->>'quiet_period_seconds')::numeric =
                          floor((t.condition->>'quiet_period_seconds')::numeric)
              ELSE false
          END
          AND (
              NOT t.condition ? 'run_context'
              OR jsonb_typeof(t.condition->'run_context') = 'string'
          )
          AND (
              NOT t.condition ? 'where'
              OR jsonb_typeof(t.condition->'where') = 'object'
          )
          AND (
              NOT t.condition ? 'reset_where'
              OR jsonb_typeof(t.condition->'reset_where') = 'object'
          )
          AND t.source IS NOT NULL
        ON CONFLICT ON CONSTRAINT uq_agent_trigger_event_sub_role DO NOTHING
        """
    )


def downgrade() -> None:
    """Remove the derived routing index table."""
    op.drop_index(
        "idx_agent_trigger_event_sub_trigger_id",
        table_name="agent_trigger_event_subscriptions",
    )
    op.drop_index(
        "idx_agent_trigger_event_sub_lookup",
        table_name="agent_trigger_event_subscriptions",
    )
    op.drop_table("agent_trigger_event_subscriptions")
