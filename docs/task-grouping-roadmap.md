# Task Grouping Roadmap

## Goal

Introduce task groups in a low-risk way.

1. Phase 1 adds group structure and UI grouping only.
1. Phase 2 maps groups to Home Assistant devices.
1. Ungrouped tasks remain on the existing Home Maintenance device.

## Decisions Locked In

- Group assignment is optional.
- No group means task stays on current Home Maintenance device.
- Service behavior stays entity based.
- Phase 1 must not require entity or device migration.

## Current System Baseline

- Task model has no group field.
- Task CRUD flows through websocket commands and store persistence.
- Binary sensors are attached to one integration device.
- Panel lists tasks flat without grouping.

---

## Phase 1: Pre-Device Grouping (Data + UI)

### Phase 2 Outcome

Users can create, edit, view, and move tasks between groups in the Home Maintenance panel, while backend entities still use the current single device.

### Phase 2 Scope

- Add optional group metadata to tasks.
- Add group management in panel UI.
- Add grouping, filtering, and move actions in panel UI.
- Keep Home Assistant entity/device behavior unchanged.

### Phase 2 Non-Goals

- No device registry changes.
- No device-per-group creation.
- No service signature changes.

### Data Model Changes

- Add optional field on task object: group_id: string | null.
- Keep null or empty equivalent to Ungrouped.
- Add migration-safe defaults for older stored tasks.

### Phase 2 Backend Changes

1. Store model and persistence

- Extend HomeMaintenanceTask with group_id.
- Ensure async_load tolerates older entries missing group_id.
- Ensure add, update, and save include group_id.

1. Websocket API

- Accept group_id in add and update commands.
- Return group_id in get_task and get_tasks responses.
- Validate type as string or null.

1. Internal conventions

- Reserve a frontend-only display key for Ungrouped.
- Persist null for Ungrouped.

### Frontend Changes (Panel)

1. Types and data calls

- Add group_id to Task type.
- Include group_id in save and update payloads.

1. Group management UX

- Add a Groups section in panel with create, rename, and delete actions.
- On group delete, tasks in that group become Ungrouped.

1. Task form UX

- Group selector on create and edit.
- Default selection is Ungrouped.

1. Task list UX

- Grouped display sections.
- Ungrouped first, then named groups alphabetically.
- Show per-group counts.
- Add quick Move to group action in task row menu.

1. Backward compatibility

- Existing tasks without group render as Ungrouped.

### Phase 2 Suggested Implementation Order

1. Add group_id backend model and websocket plumbing.
1. Add frontend type updates and payload wiring.
1. Add grouped rendering and selector UI.
1. Add group management create, rename, and delete.
1. Add move action shortcut in row menu.

### Phase 2 Testing Plan

1. Backend checks

- Add task with no group.
- Add task with group.
- Update task group.
- Remove group from task.
- Restart HA and verify persistence.

1. Frontend checks

- Group selector defaults to Ungrouped.
- Grouped task list renders correctly.
- Move action updates section immediately.
- Delete group reassigns tasks to Ungrouped.

1. Regression checks

- reset_last_performed service still works.
- Tag scan completion still works.
- Existing tasks migrate without errors.

### Phase 2 Exit Criteria

- Group metadata is persisted and editable.
- Panel supports practical group workflows.
- No behavior changes in entities, services, or device registry.

---

## Phase 2: Device-Backed Grouping

### Outcome

Each non-empty group maps to a Home Assistant device. Ungrouped tasks remain on the existing Home Maintenance device.

### Scope

- Device mapping based on task group.
- Move between groups updates entity device association.
- Optional panel indication of device backing status.

### Non-Goals

- No change to existing reset service contract.
- No requirement to assign every task to a named group.

### Architecture Decisions

- Keep group_id as the source of truth.
- Device key derived from group_id.
- Ungrouped maps to existing const.DEVICE_KEY device.
- Group rename should not force entity_id changes.

### Backend Changes

1. Device management layer

- Add helper that resolves group_id to device identifier.
- Create group device on first assignment if missing.
- Reuse existing device for Ungrouped or null.

1. Entity association

- Update sensor device_info to reflect group device identifier.
- On group change, trigger entity/device rebind strategy.
- Ensure rebind is safe during reload and restart.

1. Lifecycle and cleanup

- Define policy for empty groups and devices.
- Apply chosen policy consistently.

1. Migration behavior

- Existing tasks with null group remain on current device.
- Existing grouped tasks begin mapping to group devices after update.

### Service Impact

- Existing domain services continue to target entity_id.
- Optional future additive service: reset_group_last_performed by group_id or device_id.

### Frontend Changes

- Mostly unchanged from Phase 1.
- Optional badge indicating device-backed group.

### Suggested Implementation Order

1. Add device resolution helpers.
1. Update sensor device_info strategy.
1. Implement rebind on group changes.
1. Handle reload and startup consistency.
1. Add cleanup policy for unused group devices.

### Testing Plan

1. Device mapping

- Create grouped task and verify device creation.
- Move task between groups and verify device changes.
- Move back to Ungrouped and verify fallback device.

1. Service compatibility

- reset_last_performed works across grouped and ungrouped tasks.

1. Registry stability

- Entity_id and unique_id remain stable across moves.
- No orphaned entities after repeated moves and restarts.

1. Resilience

- Upgrade from pre-phase users with no groups.
- Restart HA during active grouped configuration.

### Exit Criteria

- Group-to-device mapping is stable and predictable.
- Existing service and automation flows continue to work.
- No unexpected entity churn.

---

## Risks and Mitigations

1. Entity and device rebind edge cases

- Mitigation: phased rollout and move or restart regression tests.

1. Group rename causing device churn

- Mitigation: use internal stable group_id separate from display name.

1. User confusion around Ungrouped behavior

- Mitigation: explicit Ungrouped label and helper text in UI.

1. Storage compatibility issues

- Mitigation: default missing group_id to null on load.

---

## Work Tracking Checklist

### Phase 1 Checklist

- [x] Add group_id to task model and store persistence.
- [x] Extend websocket add, update, and get schemas for group_id.
- [x] Update panel task types and websocket payload helpers.
- [x] Implement grouped task rendering in panel.
- [x] Implement group selector in task create and edit.
- [x] Implement group CRUD UI.
- [x] Implement move-to-group quick action.
- [ ] Run regression checks for services, tag scan, and restart.

### Phase 2 Checklist

- [ ] Add group_id to device resolution helpers.
- [ ] Implement group device creation and lookup.
- [ ] Update sensor device_info mapping.
- [ ] Implement rebind when group changes.
- [ ] Add or choose empty-group device cleanup policy.
- [ ] Validate restart and migration scenarios.
- [ ] Validate service and automation compatibility.

---

## Deferred Ideas

- Group-level bulk complete and reset actions.
- Group-level dashboards and cards.
- Group SLA indicators.
- Optional service APIs that accept group_id.
