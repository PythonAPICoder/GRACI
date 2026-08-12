import type { DatabaseSync } from 'node:sqlite';

export interface Migration {
  version: number;
  name: string;
  up: (database: DatabaseSync) => void;
}

const migration001: Migration = {
  version: 1,
  name: 'architecture_2_phase_1a_kernel',
  up(database) {
    database.exec(`
      CREATE TABLE goals (
        id TEXT PRIMARY KEY,
        objective TEXT NOT NULL CHECK (length(trim(objective)) > 0),
        constraints_json TEXT NOT NULL CHECK (json_valid(constraints_json)),
        priority TEXT NOT NULL CHECK (priority IN ('critical','interactive','normal','background','idle')),
        privacy_class TEXT NOT NULL CHECK (privacy_class IN ('public','internal','personal','confidential','secret')),
        status TEXT NOT NULL CHECK (status IN ('draft','planning','active','waiting_for_approval','blocked','verifying','succeeded','failed','cancelled')),
        active_graph_revision_id TEXT,
        terminal_reason TEXT,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT,
        CHECK ((status IN ('succeeded','failed','cancelled')) = (completed_at IS NOT NULL)),
        FOREIGN KEY (active_graph_revision_id, id) REFERENCES task_graph_revisions(id, goal_id) ON DELETE RESTRICT
      ) STRICT;

      CREATE TABLE goal_success_criteria (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL REFERENCES goals(id) ON DELETE RESTRICT,
        description TEXT NOT NULL CHECK (length(trim(description)) > 0),
        required INTEGER NOT NULL CHECK (required IN (0,1)),
        verification_method TEXT NOT NULL CHECK (length(trim(verification_method)) > 0),
        position INTEGER NOT NULL CHECK (position >= 0),
        created_at TEXT NOT NULL,
        UNIQUE (goal_id, position)
      ) STRICT;

      CREATE TABLE task_graph_revisions (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL REFERENCES goals(id) ON DELETE RESTRICT,
        revision INTEGER NOT NULL CHECK (revision >= 1),
        rationale TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (goal_id, revision),
        UNIQUE (id, goal_id)
      ) STRICT;

      CREATE TABLE tasks (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL,
        graph_revision_id TEXT NOT NULL,
        parent_task_id TEXT,
        title TEXT NOT NULL CHECK (length(trim(title)) > 0),
        objective TEXT NOT NULL CHECK (length(trim(objective)) > 0),
        inputs_json TEXT NOT NULL CHECK (json_valid(inputs_json)),
        required_capabilities_json TEXT NOT NULL CHECK (json_valid(required_capabilities_json)),
        privacy_class TEXT NOT NULL CHECK (privacy_class IN ('public','internal','personal','confidential','secret')),
        priority TEXT NOT NULL CHECK (priority IN ('critical','interactive','normal','background','idle')),
        status TEXT NOT NULL CHECK (status IN ('planned','blocked','ready','waiting_for_approval','scheduled','running','verifying','retry_pending','succeeded','failed','cancelled','superseded')),
        required INTEGER NOT NULL CHECK (required IN (0,1)),
        retry_policy_json TEXT NOT NULL CHECK (json_valid(retry_policy_json)),
        verification_plan_json TEXT NOT NULL CHECK (json_valid(verification_plan_json)),
        terminal_reason TEXT,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT,
        UNIQUE (id, graph_revision_id),
        UNIQUE (id, goal_id),
        FOREIGN KEY (graph_revision_id, goal_id) REFERENCES task_graph_revisions(id, goal_id) ON DELETE RESTRICT,
        FOREIGN KEY (parent_task_id, graph_revision_id) REFERENCES tasks(id, graph_revision_id) ON DELETE RESTRICT,
        CHECK (parent_task_id IS NULL OR parent_task_id <> id),
        CHECK ((status IN ('succeeded','failed','cancelled','superseded')) = (completed_at IS NOT NULL))
      ) STRICT;

      CREATE TABLE task_dependencies (
        graph_revision_id TEXT NOT NULL,
        predecessor_task_id TEXT NOT NULL,
        successor_task_id TEXT NOT NULL,
        condition TEXT NOT NULL CHECK (condition IN ('success','completion','predicate')),
        predicate_json TEXT CHECK (predicate_json IS NULL OR json_valid(predicate_json)),
        created_at TEXT NOT NULL,
        PRIMARY KEY (graph_revision_id, predecessor_task_id, successor_task_id),
        FOREIGN KEY (predecessor_task_id, graph_revision_id) REFERENCES tasks(id, graph_revision_id) ON DELETE RESTRICT,
        FOREIGN KEY (successor_task_id, graph_revision_id) REFERENCES tasks(id, graph_revision_id) ON DELETE RESTRICT,
        CHECK (predecessor_task_id <> successor_task_id),
        CHECK ((condition = 'predicate') = (predicate_json IS NOT NULL))
      ) STRICT, WITHOUT ROWID;

      CREATE TABLE attempts (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
        attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
        status TEXT NOT NULL CHECK (status IN ('created','running','succeeded','failed','cancelled','indeterminate')),
        provider_offering_id TEXT,
        compute_node_id TEXT,
        input_snapshot_json TEXT NOT NULL CHECK (json_valid(input_snapshot_json)),
        result_json TEXT CHECK (result_json IS NULL OR json_valid(result_json)),
        idempotency_key TEXT,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (task_id, attempt_number),
        UNIQUE (id, task_id),
        UNIQUE (idempotency_key),
        CHECK ((status IN ('succeeded','failed','cancelled','indeterminate')) = (completed_at IS NOT NULL))
      ) STRICT;

      CREATE TABLE verifications (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
        attempt_id TEXT,
        verdict TEXT NOT NULL CHECK (verdict IN ('passed','failed','inconclusive','requires_human_acceptance')),
        plan_version INTEGER NOT NULL CHECK (plan_version >= 1),
        verifier TEXT NOT NULL CHECK (length(trim(verifier)) > 0),
        criterion_results_json TEXT NOT NULL CHECK (json_valid(criterion_results_json)),
        evidence_json TEXT NOT NULL CHECK (json_valid(evidence_json)),
        created_at TEXT NOT NULL,
        FOREIGN KEY (attempt_id, task_id) REFERENCES attempts(id, task_id) ON DELETE RESTRICT
      ) STRICT;

      CREATE TABLE failures (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
        attempt_id TEXT,
        category TEXT NOT NULL CHECK (category IN ('transient_infrastructure','resource_unavailable','provider_or_capability_mismatch','invalid_input_or_precondition','policy_or_approval','execution_defect','verification_failure','external_outcome_indeterminate','cancelled_or_preempted','unknown')),
        code TEXT NOT NULL CHECK (length(trim(code)) > 0),
        summary TEXT NOT NULL CHECK (length(trim(summary)) > 0),
        details_json TEXT NOT NULL CHECK (json_valid(details_json)),
        retryable INTEGER NOT NULL CHECK (retryable IN (0,1)),
        created_at TEXT NOT NULL,
        FOREIGN KEY (attempt_id, task_id) REFERENCES attempts(id, task_id) ON DELETE RESTRICT
      ) STRICT;

      CREATE TABLE approvals (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL REFERENCES goals(id) ON DELETE RESTRICT,
        task_id TEXT,
        attempt_id TEXT,
        action TEXT NOT NULL CHECK (length(trim(action)) > 0),
        scope_json TEXT NOT NULL CHECK (json_valid(scope_json)),
        action_digest TEXT NOT NULL CHECK (length(action_digest) = 64),
        decision TEXT NOT NULL CHECK (decision IN ('requested','approved','denied','expired','revoked')),
        decided_by TEXT,
        requested_at TEXT NOT NULL,
        decided_at TEXT,
        expires_at TEXT,
        CHECK ((decision = 'requested') = (decided_at IS NULL)),
        CHECK ((decision = 'requested') = (decided_by IS NULL)),
        CHECK (attempt_id IS NULL OR task_id IS NOT NULL),
        FOREIGN KEY (task_id, goal_id) REFERENCES tasks(id, goal_id) ON DELETE RESTRICT,
        FOREIGN KEY (attempt_id, task_id) REFERENCES attempts(id, task_id) ON DELETE RESTRICT
      ) STRICT;

      CREATE TABLE artifacts (
        id TEXT PRIMARY KEY,
        logical_name TEXT NOT NULL CHECK (length(trim(logical_name)) > 0),
        version INTEGER NOT NULL CHECK (version >= 1),
        media_type TEXT NOT NULL CHECK (length(trim(media_type)) > 0),
        storage_reference TEXT NOT NULL CHECK (length(trim(storage_reference)) > 0),
        sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
        size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
        privacy_class TEXT NOT NULL CHECK (privacy_class IN ('public','internal','personal','confidential','secret')),
        producer_attempt_id TEXT REFERENCES attempts(id) ON DELETE RESTRICT,
        provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json)),
        created_at TEXT NOT NULL,
        UNIQUE (logical_name, version)
      ) STRICT;

      CREATE TABLE events (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT NOT NULL UNIQUE,
        aggregate_type TEXT NOT NULL CHECK (length(trim(aggregate_type)) > 0),
        aggregate_id TEXT NOT NULL CHECK (length(trim(aggregate_id)) > 0),
        event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
        event_version INTEGER NOT NULL CHECK (event_version >= 1),
        actor TEXT NOT NULL CHECK (length(trim(actor)) > 0),
        correlation_id TEXT,
        causation_id TEXT REFERENCES events(id) ON DELETE RESTRICT,
        occurred_at TEXT NOT NULL,
        payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
        previous_hash TEXT CHECK (previous_hash IS NULL OR length(previous_hash) = 64),
        event_hash TEXT NOT NULL UNIQUE CHECK (length(event_hash) = 64)
      ) STRICT;

      CREATE INDEX idx_criteria_goal ON goal_success_criteria(goal_id, position);
      CREATE INDEX idx_graph_revisions_goal ON task_graph_revisions(goal_id, revision);
      CREATE INDEX idx_tasks_graph ON tasks(graph_revision_id, created_at, id);
      CREATE INDEX idx_attempts_task ON attempts(task_id, attempt_number);
      CREATE INDEX idx_events_aggregate ON events(aggregate_type, aggregate_id, sequence);

      CREATE TRIGGER graph_revisions_no_update BEFORE UPDATE ON task_graph_revisions
      BEGIN SELECT RAISE(ABORT, 'task graph revisions are immutable'); END;
      CREATE TRIGGER graph_revisions_no_delete BEFORE DELETE ON task_graph_revisions
      BEGIN SELECT RAISE(ABORT, 'task graph revisions are immutable'); END;
      CREATE TRIGGER tasks_no_delete BEFORE DELETE ON tasks
      BEGIN SELECT RAISE(ABORT, 'tasks are historical records and cannot be deleted'); END;
      CREATE TRIGGER task_dependencies_no_update BEFORE UPDATE ON task_dependencies
      BEGIN SELECT RAISE(ABORT, 'task dependencies are immutable'); END;
      CREATE TRIGGER task_dependencies_no_delete BEFORE DELETE ON task_dependencies
      BEGIN SELECT RAISE(ABORT, 'task dependencies are immutable'); END;
      CREATE TRIGGER attempts_terminal_no_update BEFORE UPDATE ON attempts
      WHEN OLD.status IN ('succeeded','failed','cancelled','indeterminate')
      BEGIN SELECT RAISE(ABORT, 'terminal attempts are immutable'); END;
      CREATE TRIGGER attempts_no_delete BEFORE DELETE ON attempts
      BEGIN SELECT RAISE(ABORT, 'attempts are append-only'); END;
      CREATE TRIGGER events_no_update BEFORE UPDATE ON events
      BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
      CREATE TRIGGER events_no_delete BEFORE DELETE ON events
      BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
    `);
  },
};

export const migrations: readonly Migration[] = [migration001];

export function migrate(database: DatabaseSync): number {
  database.exec(`
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version INTEGER PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      applied_at TEXT NOT NULL
    ) STRICT;
  `);

  const current = Number(
    (database.prepare('SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations').get() as { version: number }).version,
  );

  for (const migration of migrations) {
    if (migration.version <= current) continue;
    database.exec('BEGIN IMMEDIATE');
    try {
      migration.up(database);
      database
        .prepare('INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)')
        .run(migration.version, migration.name, new Date().toISOString());
      database.exec(`PRAGMA user_version = ${migration.version}`);
      database.exec('COMMIT');
    } catch (error) {
      database.exec('ROLLBACK');
      throw error;
    }
  }

  return Number(
    (database.prepare('SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations').get() as { version: number }).version,
  );
}
