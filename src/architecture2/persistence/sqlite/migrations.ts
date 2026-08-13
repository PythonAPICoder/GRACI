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

const migration002: Migration = {
  version: 2,
  name: 'architecture_2_phase_1c_failure_classification',
  up(database) {
    database.exec(`
      ALTER TABLE failures ADD COLUMN classification TEXT NOT NULL DEFAULT 'permanent'
        CHECK (classification IN ('transient','permanent','verification_failed','approval_required','external_outcome_indeterminate'));
      UPDATE failures SET classification = CASE
        WHEN category = 'transient_infrastructure' AND retryable = 1 THEN 'transient'
        WHEN category = 'verification_failure' THEN 'verification_failed'
        WHEN category = 'external_outcome_indeterminate' THEN 'external_outcome_indeterminate'
        ELSE 'permanent' END;
    `);
  },
};

const migration003: Migration = {
  version: 3,
  name: 'architecture_2_phase_1e_legacy_history',
  up(database) {
    database.exec(`
      CREATE TABLE legacy_import_operations (
        id TEXT PRIMARY KEY,
        source_digest TEXT NOT NULL UNIQUE CHECK (length(source_digest) = 64),
        source_reference TEXT NOT NULL CHECK (length(trim(source_reference)) > 0),
        assessment_version INTEGER NOT NULL CHECK (assessment_version >= 1),
        imported_record_count INTEGER NOT NULL CHECK (imported_record_count >= 0),
        imported_at TEXT NOT NULL
      ) STRICT;

      CREATE TABLE legacy_history_records (
        import_operation_id TEXT NOT NULL REFERENCES legacy_import_operations(id) ON DELETE RESTRICT,
        source_digest TEXT NOT NULL,
        source_reference TEXT NOT NULL CHECK (length(trim(source_reference)) > 0),
        source_section TEXT NOT NULL CHECK (length(trim(source_section)) > 0),
        source_key TEXT NOT NULL CHECK (length(trim(source_key)) > 0),
        legacy_status TEXT NOT NULL CHECK (length(trim(legacy_status)) > 0),
        payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
        assessment_version INTEGER NOT NULL CHECK (assessment_version >= 1),
        imported_at TEXT NOT NULL,
        PRIMARY KEY (source_digest, source_section, source_key),
        FOREIGN KEY (source_digest) REFERENCES legacy_import_operations(source_digest) ON DELETE RESTRICT
      ) STRICT, WITHOUT ROWID;

      CREATE INDEX idx_legacy_history_operation ON legacy_history_records(import_operation_id, source_section, source_key);

      CREATE TRIGGER legacy_import_operations_no_update BEFORE UPDATE ON legacy_import_operations
      BEGIN SELECT RAISE(ABORT, 'legacy import operations are immutable'); END;
      CREATE TRIGGER legacy_import_operations_no_delete BEFORE DELETE ON legacy_import_operations
      BEGIN SELECT RAISE(ABORT, 'legacy import operations are immutable'); END;
      CREATE TRIGGER legacy_history_no_update BEFORE UPDATE ON legacy_history_records
      BEGIN SELECT RAISE(ABORT, 'legacy history records are immutable'); END;
      CREATE TRIGGER legacy_history_no_delete BEFORE DELETE ON legacy_history_records
      BEGIN SELECT RAISE(ABORT, 'legacy history records are immutable'); END;
    `);
  },
};

const migration004: Migration = {
  version: 4,
  name: 'architecture_2_phase_1f_provider_registry',
  up(database) {
    database.exec(`
      CREATE TABLE providers (
        id TEXT PRIMARY KEY, adapter_type TEXT NOT NULL, adapter_version TEXT NOT NULL,
        configuration_reference TEXT NOT NULL, created_at TEXT NOT NULL
      ) STRICT;
      CREATE TABLE capabilities (
        id TEXT PRIMARY KEY, contract_version INTEGER NOT NULL CHECK (contract_version >= 1),
        description TEXT NOT NULL, input_schema_reference TEXT NOT NULL,
        output_schema_reference TEXT NOT NULL, created_at TEXT NOT NULL
      ) STRICT;
      CREATE TABLE provider_offerings (
        id TEXT PRIMARY KEY, provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE RESTRICT,
        capability_id TEXT NOT NULL REFERENCES capabilities(id) ON DELETE RESTRICT,
        contract_version INTEGER NOT NULL CHECK (contract_version >= 1), model_identity TEXT,
        privacy_destinations_json TEXT NOT NULL CHECK (json_valid(privacy_destinations_json)),
        permissions_json TEXT NOT NULL CHECK (json_valid(permissions_json)),
        features_json TEXT NOT NULL CHECK (json_valid(features_json)),
        supported_formats_json TEXT NOT NULL CHECK (json_valid(supported_formats_json)),
        input_schema_reference TEXT NOT NULL, output_schema_reference TEXT NOT NULL,
        qualification_fingerprint TEXT NOT NULL,
        quality_level INTEGER NOT NULL CHECK (quality_level >= 0),
        expected_latency_ms INTEGER NOT NULL CHECK (expected_latency_ms >= 0),
        maximum_cost REAL NOT NULL CHECK (maximum_cost >= 0),
        side_effect_class TEXT NOT NULL CHECK (side_effect_class IN ('none','local','external_reversible','external_consequential')),
        created_at TEXT NOT NULL, UNIQUE(provider_id, capability_id, contract_version, model_identity)
      ) STRICT;
      CREATE TABLE qualifications (
        id TEXT PRIMARY KEY, offering_id TEXT NOT NULL REFERENCES provider_offerings(id) ON DELETE RESTRICT,
        status TEXT NOT NULL CHECK (status IN ('qualified','rejected')), level INTEGER NOT NULL CHECK (level >= 0),
        evidence_json TEXT NOT NULL CHECK (json_valid(evidence_json)), qualified_at TEXT NOT NULL,
        expires_at TEXT, trigger_fingerprint TEXT NOT NULL
      ) STRICT;
      CREATE TABLE provider_health_observations (
        id TEXT PRIMARY KEY, offering_id TEXT NOT NULL REFERENCES provider_offerings(id) ON DELETE RESTRICT,
        status TEXT NOT NULL CHECK (status IN ('healthy','degraded','unhealthy','unknown')),
        evidence_json TEXT NOT NULL CHECK (json_valid(evidence_json)), observed_at TEXT NOT NULL
      ) STRICT;
      CREATE TABLE provider_resolution_decisions (
        id TEXT PRIMARY KEY, capability_id TEXT NOT NULL REFERENCES capabilities(id) ON DELETE RESTRICT,
        request_json TEXT NOT NULL CHECK (json_valid(request_json)), candidates_json TEXT NOT NULL CHECK (json_valid(candidates_json)),
        selected_offering_id TEXT REFERENCES provider_offerings(id) ON DELETE RESTRICT,
        explanation TEXT NOT NULL, decided_at TEXT NOT NULL
      ) STRICT;
      CREATE INDEX idx_offerings_capability ON provider_offerings(capability_id, id);
      CREATE INDEX idx_qualifications_offering ON qualifications(offering_id, qualified_at, id);
      CREATE INDEX idx_provider_health_offering ON provider_health_observations(offering_id, observed_at, id);
      CREATE TRIGGER providers_no_update BEFORE UPDATE ON providers BEGIN SELECT RAISE(ABORT, 'providers are versioned records'); END;
      CREATE TRIGGER capabilities_no_update BEFORE UPDATE ON capabilities BEGIN SELECT RAISE(ABORT, 'capabilities are versioned records'); END;
      CREATE TRIGGER offerings_no_update BEFORE UPDATE ON provider_offerings BEGIN SELECT RAISE(ABORT, 'provider offerings are versioned records'); END;
      CREATE TRIGGER qualifications_no_update BEFORE UPDATE ON qualifications BEGIN SELECT RAISE(ABORT, 'qualifications are append-only'); END;
      CREATE TRIGGER health_no_update BEFORE UPDATE ON provider_health_observations BEGIN SELECT RAISE(ABORT, 'health observations are append-only'); END;
      CREATE TRIGGER resolutions_no_update BEFORE UPDATE ON provider_resolution_decisions BEGIN SELECT RAISE(ABORT, 'resolution decisions are append-only'); END;
      CREATE TRIGGER providers_no_delete BEFORE DELETE ON providers BEGIN SELECT RAISE(ABORT, 'providers are versioned records'); END;
      CREATE TRIGGER capabilities_no_delete BEFORE DELETE ON capabilities BEGIN SELECT RAISE(ABORT, 'capabilities are versioned records'); END;
      CREATE TRIGGER offerings_no_delete BEFORE DELETE ON provider_offerings BEGIN SELECT RAISE(ABORT, 'provider offerings are versioned records'); END;
      CREATE TRIGGER qualifications_no_delete BEFORE DELETE ON qualifications BEGIN SELECT RAISE(ABORT, 'qualifications are append-only'); END;
      CREATE TRIGGER health_no_delete BEFORE DELETE ON provider_health_observations BEGIN SELECT RAISE(ABORT, 'health observations are append-only'); END;
      CREATE TRIGGER resolutions_no_delete BEFORE DELETE ON provider_resolution_decisions BEGIN SELECT RAISE(ABORT, 'resolution decisions are append-only'); END;
    `);
  },
};

const migration005: Migration = {
  version: 5,
  name: 'architecture_2_phase_1g_node_leases',
  up(database) {
    database.exec(`
      CREATE TABLE nodes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL CHECK (length(trim(name)) > 0),
        administrative_state TEXT NOT NULL CHECK (administrative_state IN ('active','draining','disabled')),
        configuration_reference TEXT NOT NULL CHECK (length(trim(configuration_reference)) > 0),
        created_at TEXT NOT NULL
      ) STRICT;
      CREATE TABLE offering_locations (
        id TEXT PRIMARY KEY,
        node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
        offering_id TEXT NOT NULL REFERENCES provider_offerings(id) ON DELETE RESTRICT,
        enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
        capacity INTEGER NOT NULL CHECK (capacity > 0),
        privacy_classes_json TEXT NOT NULL CHECK (json_valid(privacy_classes_json) AND json_type(privacy_classes_json) = 'array'),
        created_at TEXT NOT NULL,
        UNIQUE (node_id, offering_id)
      ) STRICT;
      CREATE TABLE node_health_observations (
        id TEXT PRIMARY KEY,
        node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
        status TEXT NOT NULL CHECK (status IN ('healthy','degraded','unhealthy','unknown')),
        observed_at TEXT NOT NULL
      ) STRICT;
      CREATE TABLE resource_scheduling_decisions (
        id TEXT PRIMARY KEY,
        offering_id TEXT NOT NULL REFERENCES provider_offerings(id) ON DELETE RESTRICT,
        request_json TEXT NOT NULL CHECK (json_valid(request_json) AND json_type(request_json) = 'object'),
        candidates_json TEXT NOT NULL CHECK (json_valid(candidates_json) AND json_type(candidates_json) = 'array'),
        selected_location_id TEXT REFERENCES offering_locations(id) ON DELETE RESTRICT,
        selected_node_id TEXT REFERENCES nodes(id) ON DELETE RESTRICT,
        explanation TEXT NOT NULL CHECK (length(trim(explanation)) > 0),
        decided_at TEXT NOT NULL,
        CHECK ((selected_location_id IS NULL) = (selected_node_id IS NULL))
      ) STRICT;
      CREATE TABLE resource_leases (
        id TEXT PRIMARY KEY,
        decision_id TEXT NOT NULL UNIQUE REFERENCES resource_scheduling_decisions(id) ON DELETE RESTRICT,
        offering_id TEXT NOT NULL REFERENCES provider_offerings(id) ON DELETE RESTRICT,
        location_id TEXT NOT NULL REFERENCES offering_locations(id) ON DELETE RESTRICT,
        node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
        capacity INTEGER NOT NULL CHECK (capacity > 0),
        status TEXT NOT NULL CHECK (status IN ('active','released','expired')),
        acquired_at TEXT NOT NULL,
        expires_at TEXT NOT NULL CHECK (expires_at > acquired_at),
        released_at TEXT,
        CHECK ((status = 'active') = (released_at IS NULL)),
        CHECK (status <> 'released' OR released_at >= acquired_at)
      ) STRICT;
      CREATE INDEX idx_locations_offering ON offering_locations(offering_id, node_id, id);
      CREATE INDEX idx_node_health_node ON node_health_observations(node_id, observed_at, id);
      CREATE INDEX idx_scheduling_offering ON resource_scheduling_decisions(offering_id, decided_at, id);
      CREATE INDEX idx_leases_location_active ON resource_leases(location_id, status, expires_at, id);
      CREATE INDEX idx_leases_node_active ON resource_leases(node_id, status, expires_at, id);
      CREATE TRIGGER nodes_no_update BEFORE UPDATE ON nodes BEGIN SELECT RAISE(ABORT, 'nodes are versioned records'); END;
      CREATE TRIGGER nodes_no_delete BEFORE DELETE ON nodes BEGIN SELECT RAISE(ABORT, 'nodes are versioned records'); END;
      CREATE TRIGGER locations_no_update BEFORE UPDATE ON offering_locations BEGIN SELECT RAISE(ABORT, 'offering locations are versioned records'); END;
      CREATE TRIGGER locations_no_delete BEFORE DELETE ON offering_locations BEGIN SELECT RAISE(ABORT, 'offering locations are versioned records'); END;
      CREATE TRIGGER node_health_no_update BEFORE UPDATE ON node_health_observations BEGIN SELECT RAISE(ABORT, 'node health observations are append-only'); END;
      CREATE TRIGGER node_health_no_delete BEFORE DELETE ON node_health_observations BEGIN SELECT RAISE(ABORT, 'node health observations are append-only'); END;
      CREATE TRIGGER scheduling_no_update BEFORE UPDATE ON resource_scheduling_decisions BEGIN SELECT RAISE(ABORT, 'resource scheduling decisions are append-only'); END;
      CREATE TRIGGER scheduling_no_delete BEFORE DELETE ON resource_scheduling_decisions BEGIN SELECT RAISE(ABORT, 'resource scheduling decisions are append-only'); END;
      CREATE TRIGGER leases_guard_update BEFORE UPDATE ON resource_leases
      WHEN OLD.status <> 'active' OR NEW.id <> OLD.id OR NEW.decision_id <> OLD.decision_id
        OR NEW.offering_id <> OLD.offering_id OR NEW.location_id <> OLD.location_id OR NEW.node_id <> OLD.node_id
        OR NEW.capacity <> OLD.capacity OR NEW.acquired_at <> OLD.acquired_at OR NEW.expires_at <> OLD.expires_at
        OR NEW.status = 'active'
      BEGIN SELECT RAISE(ABORT, 'resource lease history is immutable'); END;
      CREATE TRIGGER leases_no_delete BEFORE DELETE ON resource_leases BEGIN SELECT RAISE(ABORT, 'resource leases are historical records'); END;
    `);
  },
};

const migration006: Migration = {
  version: 6,
  name: 'architecture_2_phase_1h_node_inspection_administration',
  up(database) {
    database.exec(`
      DROP TRIGGER nodes_no_update;
      ALTER TABLE nodes ADD COLUMN version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1);

      CREATE TABLE node_inspection_observations (
        id TEXT PRIMARY KEY,
        node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
        adapter_id TEXT NOT NULL CHECK (length(trim(adapter_id)) > 0),
        adapter_version INTEGER NOT NULL CHECK (adapter_version >= 1),
        health_json TEXT NOT NULL CHECK (json_valid(health_json) AND json_type(health_json) = 'object'),
        inventory_json TEXT NOT NULL CHECK (json_valid(inventory_json) AND json_type(inventory_json) = 'object'),
        inspected_at TEXT NOT NULL
      ) STRICT;
      CREATE TABLE node_administrative_transitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
        from_state TEXT NOT NULL CHECK (from_state IN ('active','draining','disabled')),
        to_state TEXT NOT NULL CHECK (to_state IN ('active','draining','disabled')),
        actor TEXT NOT NULL CHECK (length(trim(actor)) > 0),
        reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
        occurred_at TEXT NOT NULL,
        node_version INTEGER NOT NULL CHECK (node_version >= 2),
        event_id TEXT NOT NULL UNIQUE REFERENCES events(id) ON DELETE RESTRICT,
        CHECK (from_state <> to_state),
        UNIQUE (node_id, node_version)
      ) STRICT;
      CREATE INDEX idx_node_inspections_node ON node_inspection_observations(node_id, inspected_at, id);
      CREATE INDEX idx_node_transitions_node ON node_administrative_transitions(node_id, node_version);

      CREATE TRIGGER nodes_guard_update BEFORE UPDATE ON nodes
      WHEN NEW.id <> OLD.id OR NEW.name <> OLD.name OR NEW.configuration_reference <> OLD.configuration_reference
        OR NEW.created_at <> OLD.created_at OR NEW.version <> OLD.version + 1
        OR NEW.administrative_state = OLD.administrative_state
      BEGIN SELECT RAISE(ABORT, 'only versioned node administrative transitions are permitted'); END;
      CREATE TRIGGER node_inspections_no_update BEFORE UPDATE ON node_inspection_observations
      BEGIN SELECT RAISE(ABORT, 'node inspection observations are append-only'); END;
      CREATE TRIGGER node_inspections_no_delete BEFORE DELETE ON node_inspection_observations
      BEGIN SELECT RAISE(ABORT, 'node inspection observations are append-only'); END;
      CREATE TRIGGER node_transitions_no_update BEFORE UPDATE ON node_administrative_transitions
      BEGIN SELECT RAISE(ABORT, 'node administrative transitions are immutable'); END;
      CREATE TRIGGER node_transitions_no_delete BEFORE DELETE ON node_administrative_transitions
      BEGIN SELECT RAISE(ABORT, 'node administrative transitions are immutable'); END;
    `);
  },
};

const migration007: Migration = {
  version: 7,
  name: 'architecture_2_phase_1i_workstation_availability_evaluations',
  up(database) {
    database.exec(`
      CREATE TABLE workstation_availability_evaluations (
        id TEXT PRIMARY KEY,
        node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
        rule_fingerprint TEXT NOT NULL CHECK (length(trim(rule_fingerprint)) > 0),
        process_basenames_json TEXT NOT NULL
          CHECK (json_valid(process_basenames_json) AND json_type(process_basenames_json) = 'array'),
        matched_rule_ids_json TEXT NOT NULL
          CHECK (json_valid(matched_rule_ids_json) AND json_type(matched_rule_ids_json) = 'array'),
        recommendation TEXT NOT NULL
          CHECK (recommendation IN ('recommend_draining','recommend_active','inconclusive')),
        evaluated_at TEXT NOT NULL
      ) STRICT;
      CREATE INDEX idx_workstation_availability_node
        ON workstation_availability_evaluations(node_id, evaluated_at, id);
      CREATE TRIGGER workstation_availability_no_update
        BEFORE UPDATE ON workstation_availability_evaluations
        BEGIN SELECT RAISE(ABORT, 'workstation availability evaluations are append-only'); END;
      CREATE TRIGGER workstation_availability_no_delete
        BEFORE DELETE ON workstation_availability_evaluations
        BEGIN SELECT RAISE(ABORT, 'workstation availability evaluations are append-only'); END;
    `);
  },
};

export const migrations: readonly Migration[] = [migration001, migration002, migration003, migration004, migration005,
  migration006, migration007];

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
