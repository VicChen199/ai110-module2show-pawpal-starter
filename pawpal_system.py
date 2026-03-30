"""
PawPal+ — backend logic layer.

Class hierarchy:
    Owner 1──* Pet 1──* Task
    Scheduler ──uses──> Owner ──produces──> DailyPlan ──contains──> Task
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Dataclasses  (simple value objects — no behaviour beyond storage)
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A single pet-care activity."""

    name: str
    duration_minutes: int
    priority: Priority
    pet_name: str = ""          # which pet this task belongs to (set by Pet.add_task)
    completed: bool = False

    def complete(self) -> None:
        """Mark this task as completed."""
        pass

    def reset(self) -> None:
        """Clear the completed flag."""
        pass


@dataclass
class Pet:
    """A pet owned by an Owner."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet and stamp the task with the pet's name."""
        pass

    def remove_task(self, task_name: str) -> None:
        """Remove the first task whose name matches task_name."""
        pass


# ---------------------------------------------------------------------------
# Regular classes  (stateful objects with richer behaviour)
# ---------------------------------------------------------------------------

class Owner:
    """The pet owner — root of the object graph."""

    def __init__(self, name: str, available_minutes: int) -> None:
        self.name: str = name
        self.available_minutes: int = available_minutes
        self.pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to the owner's household."""
        pass

    def remove_pet(self, pet_name: str) -> None:
        """Remove the first pet whose name matches pet_name."""
        pass

    def get_all_tasks(self) -> list[Task]:
        """Return a flat list of every task across all pets."""
        pass


@dataclass
class DailyPlan:
    """The output produced by Scheduler.generate_plan()."""

    scheduled: list[Task] = field(default_factory=list)
    skipped: list[Task] = field(default_factory=list)
    total_duration: int = 0
    explanation: str = ""

    def summary(self) -> str:
        """Return a short human-readable summary of the plan."""
        pass


class Scheduler:
    """Stateless scheduling engine.

    Takes an Owner (and their pets' tasks) and produces a DailyPlan.
    Keeping this class stateless makes it easy to unit-test independently.
    """

    def generate_plan(self, owner: Owner) -> DailyPlan:
        """Build and return a DailyPlan that fits within owner.available_minutes."""
        pass

    def _sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted high → medium → low."""
        pass

    def _fit_to_time(
        self, tasks: list[Task], budget: int
    ) -> tuple[list[Task], list[Task]]:
        """
        Greedily pick tasks (already sorted by priority) that fit in budget.

        Returns:
            (scheduled, skipped)
        """
        pass
