"""Store Home Maintenance configuration."""

import logging
from datetime import datetime

import attr
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry, storage
from homeassistant.util import dt as dt_util

from . import const
from .binary_sensor import HomeMaintenanceSensor

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{const.DOMAIN}.storage"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 2


@attr.s(slots=True)
class HomeMaintenanceTask:
    """Represents a single home maintenance task."""

    id: str = attr.ib()
    title: str = attr.ib()
    interval_value: int = attr.ib()
    interval_type: str = attr.ib()
    last_performed: str = attr.ib()
    tag_id: str | None = attr.ib(default=None)
    icon: str | None = attr.ib(default=None)
    group_id: str | None = attr.ib(default=None)


class TaskStore:
    """Class to hold home maintenance task data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the storage."""
        self.hass = hass
        self._store = storage.Store(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            minor_version=STORAGE_VERSION_MINOR,
        )
        self._tasks: dict[str, HomeMaintenanceTask] = {}
        self._groups: set[str] = set()

    @staticmethod
    def _normalize_group_id(group_id: str | None) -> str | None:
        """Normalize a group id to a canonical stored value."""
        if group_id is None:
            return None
        normalized = group_id.strip()
        return normalized or None

    async def async_load(self) -> None:
        """Load tasks from storage."""
        data = await self._store.async_load()
        if data is None:
            return

        if isinstance(data, list):
            task_items = data
            group_items: list[str] = []
        else:
            task_items = data.get("tasks", [])
            group_items = data.get("groups", [])

        self._tasks = {
            task_data["id"]: HomeMaintenanceTask(**task_data) for task_data in task_items
        }

        stored_groups = {
            group
            for group in (self._normalize_group_id(g) for g in group_items)
            if group is not None
        }
        derived_groups = {
            group
            for group in (
                self._normalize_group_id(task.group_id) for task in self._tasks.values()
            )
            if group is not None
        }
        self._groups = stored_groups | derived_groups

    def get_all(self) -> list[dict]:
        """Get all tasks."""
        return [attr.asdict(t) for t in self._tasks.values()]

    def get(self, task_id: str) -> dict:
        """Get single task."""
        return attr.asdict(self._tasks.get(task_id))

    def get_groups(self) -> list[str]:
        """Get all configured group names."""
        return sorted(self._groups)

    def create_group(self, group_id: str) -> None:
        """Create a group if it does not already exist."""
        normalized = self._normalize_group_id(group_id)
        if not normalized:
            msg = "Group name is required."
            raise RuntimeError(msg)

        self._groups.add(normalized)
        self._save()

    def rename_group(self, old_group_id: str, new_group_id: str) -> None:
        """Rename a group and reassign all member tasks."""
        old_normalized = self._normalize_group_id(old_group_id)
        new_normalized = self._normalize_group_id(new_group_id)

        if not old_normalized or not new_normalized:
            msg = "Both old and new group names are required."
            raise RuntimeError(msg)

        if old_normalized == new_normalized:
            return

        self._groups.discard(old_normalized)
        self._groups.add(new_normalized)

        for task_id, task in self._tasks.items():
            if self._normalize_group_id(task.group_id) != old_normalized:
                continue

            task.group_id = new_normalized
            entity = self.hass.data[const.DOMAIN]["entities"].get(task_id)
            if entity is not None:
                entity.task["group_id"] = new_normalized
                self.hass.async_create_task(entity.async_update_ha_state(force_refresh=True))

        self._save()

    def delete_group(self, group_id: str) -> None:
        """Delete a group and reassign member tasks to ungrouped."""
        normalized = self._normalize_group_id(group_id)
        if not normalized:
            msg = "Group name is required."
            raise RuntimeError(msg)

        self._groups.discard(normalized)

        for task_id, task in self._tasks.items():
            if self._normalize_group_id(task.group_id) != normalized:
                continue

            task.group_id = None
            entity = self.hass.data[const.DOMAIN]["entities"].get(task_id)
            if entity is not None:
                entity.task["group_id"] = None
                self.hass.async_create_task(entity.async_update_ha_state(force_refresh=True))

        self._save()

    def _get_tag_uuids(self) -> dict[str, str]:
        """Return a mapping of all task's tag friendly IDs into tag UUIDs."""
        er = entity_registry.async_get(self.hass)

        # Get each task's tag_id, if configured
        tag_ids = [t.tag_id for t in self._tasks.values() if t.tag_id]

        tag_uuids = {}
        for tag_id in tag_ids:
            # If two tasks have the same tag_id, only get the first
            if tag_id in tag_uuids:
                continue

            # Get the tag_id -> tag_uuid mapping from entity_registry
            entry = er.async_get(tag_id)
            if entry:
                tag_uuids[tag_id] = entry.unique_id

        return tag_uuids

    def get_by_tag_uuid(self, tag_uuid: str) -> list[dict]:
        """Get tasks given a tag UUID."""
        tag_uuids = self._get_tag_uuids()

        return [
            attr.asdict(t)
            for t in self._tasks.values()
            if t.tag_id and tag_uuids.get(t.tag_id) == tag_uuid
        ]

    def get_by_tag_id(self, tag_id: str) -> list[dict]:
        """Get tasks by tag id."""
        return [attr.asdict(t) for t in self._tasks.values() if t.tag_id == tag_id]

    def add(
        self, task: HomeMaintenanceTask, labels: list[str] | None = None
    ) -> str | None:
        """Add new task."""
        add_entities = self.hass.data[const.DOMAIN].get("add_entities")
        if not add_entities:
            msg = "add_entities not registered yet."
            raise RuntimeError(msg)
            return None

        device_id = self.hass.data[const.DOMAIN].get("device_id")
        if not device_id:
            msg = "Device ID not available."
            raise RuntimeError(msg)
            return None

        entity = HomeMaintenanceSensor(
            self.hass, attr.asdict(task), device_id, labels=labels
        )
        add_entities([entity])
        task.group_id = self._normalize_group_id(task.group_id)
        if task.group_id:
            self._groups.add(task.group_id)
        self._tasks[task.id] = task
        self.hass.data[const.DOMAIN]["entities"][task.id] = entity
        self._save()

        return entity.unique_id

    def delete(self, task_id: str) -> None:
        """Remove a task."""
        er = entity_registry.async_get(self.hass)

        # Search for entity by unique_id
        entity_entry = next(
            (
                entry
                for entry in er.entities.values()
                if entry.unique_id == task_id and entry.platform == const.DOMAIN
            ),
            None,
        )
        if entity_entry is None:
            msg = f"No entity found with task ID {task_id}."
            raise RuntimeError(msg)
            return

        # Remove the entity by entity_id
        er.async_remove(entity_entry.entity_id)

        # Remove from your task list and persist
        del self._tasks[task_id]
        self._save()

    def update_task(self, task_id: str, updated: dict) -> None:
        """Update an existing task with new values from a dictionary."""
        entity = self.hass.data[const.DOMAIN]["entities"].get(task_id)
        task = self._tasks.get(task_id)

        if entity is None or task is None:
            msg = "Task not found."
            raise RuntimeError(msg)

        for key, value in updated.items():
            entity.task[key] = value
            if hasattr(task, key):
                setattr(task, key, value)

        if "tag_id" in updated:
            tag_id = updated["tag_id"]
            task.tag_id = tag_id if tag_id else None
            entity.task["tag_id"] = tag_id if tag_id else None

        if "group_id" in updated:
            group_id = self._normalize_group_id(updated["group_id"])
            task.group_id = group_id
            entity.task["group_id"] = group_id
            if group_id:
                self._groups.add(group_id)

        if "labels" in updated:
            registry = entity_registry.async_get(self.hass)
            if registry.async_get(entity.entity_id):
                registry.async_update_entity(
                    entity.entity_id,
                    labels=set(updated["labels"]),
                )

        self.hass.async_create_task(entity.async_update_ha_state(force_refresh=True))
        self._save()

    def update_last_performed(
        self, task_id: str, performed_date: datetime | None = None
    ) -> None:
        """Update a task's last performed date."""
        entity = self.hass.data[const.DOMAIN]["entities"].get(task_id)
        task = self._tasks.get(task_id)

        if entity is None or task is None:
            msg = "Task not found."
            raise RuntimeError(msg)

        if performed_date is None:
            performed_date = dt_util.now()
        performed_date_str = performed_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

        entity.task["last_performed"] = performed_date_str
        task.last_performed = performed_date_str
        self.hass.async_create_task(entity.async_update_ha_state(force_refresh=True))
        self._save()

    def _save(self) -> None:
        """Save tasks in the background."""
        self.hass.async_create_task(
            self._store.async_save(
                {
                    "tasks": [attr.asdict(task) for task in self._tasks.values()],
                    "groups": sorted(self._groups),
                }
            )
        )
