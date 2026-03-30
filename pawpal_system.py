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


# Explicit rank used for sorting (lower number = scheduled first)
_PRIORITY_RANK: dict[Priority, int] = {
    Priority.HIGH: 0,
    Priority.MEDIUM: 1,
    Priority.LOW: 2,
}


# ---------------------------------------------------------------------------
# Dataclasses  (simple value objects)
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A single pet-care activity."""

    name: str
    duration_minutes: int
    priority: Priority
    pet_name: str = ""      # stamped by Pet.add_task so the plan knows which animal
    completed: bool = False

    def complete(self) -> None:
        """Mark this task as done."""
        self.completed = True

    def reset(self) -> None:
        """Clear the completed flag so the task can be scheduled again."""
        self.completed = False


@dataclass
class Pet:
    """A pet owned by an Owner."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet and record which pet owns it."""
        task.pet_name = self.name
        self.tasks.append(task)

    def remove_task(self, task_name: str) -> None:
        """Remove the first task whose name matches task_name (case-insensitive)."""
        for i, task in enumerate(self.tasks):
            if task.name.lower() == task_name.lower():
                self.tasks.pop(i)
                return


# ---------------------------------------------------------------------------
# Regular classes
# ---------------------------------------------------------------------------

class Owner:
    """The pet owner — root of the object graph."""

    def __init__(self, name: str, available_minutes: int) -> None:
        """Initialise the owner with a name and daily time budget in minutes."""
        self.name: str = name
        self.available_minutes: int = available_minutes
        self.pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to the owner's household."""
        self.pets.append(pet)

    def remove_pet(self, pet_name: str) -> None:
        """Remove the first pet whose name matches pet_name (case-insensitive)."""
        for i, pet in enumerate(self.pets):
            if pet.name.lower() == pet_name.lower():
                self.pets.pop(i)
                return

    def get_all_tasks(self) -> list[Task]:
        """Return a flat list of every incomplete task across all pets."""
        return [task for pet in self.pets for task in pet.tasks if not task.completed]


@dataclass
class DailyPlan:
    """The output produced by Scheduler.generate_plan()."""

    scheduled: list[Task] = field(default_factory=list)
    skipped: list[Task] = field(default_factory=list)
    total_duration: int = 0
    explanation: str = ""

    def summary(self) -> str:
        """Return a human-readable summary suitable for display in the UI."""
        lines: list[str] = []

        if self.scheduled:
            lines.append(f"Scheduled ({self.total_duration} min total):")
            for task in self.scheduled:
                pet_label = f"[{task.pet_name}] " if task.pet_name else ""
                lines.append(
                    f"  • {pet_label}{task.name} — {task.duration_minutes} min"
                    f" ({task.priority.value} priority)"
                )
        else:
            lines.append("No tasks could be scheduled.")

        if self.skipped:
            lines.append("\nSkipped (did not fit in available time):")
            for task in self.skipped:
                pet_label = f"[{task.pet_name}] " if task.pet_name else ""
                lines.append(
                    f"  • {pet_label}{task.name} — {task.duration_minutes} min"
                    f" ({task.priority.value} priority)"
                )

        if self.explanation:
            lines.append(f"\nReasoning: {self.explanation}")

        return "\n".join(lines)


class Scheduler:
    """Stateless scheduling engine.

    Retrieves all incomplete tasks from the owner's pets, sorts them by
    priority, then greedily fits as many as possible into the owner's
    available time budget.
    """

    def generate_plan(self, owner: Owner) -> DailyPlan:
        """Build and return a DailyPlan that fits within owner.available_minutes."""
        all_tasks = owner.get_all_tasks()

        if not all_tasks:
            return DailyPlan(explanation="No tasks found. Add some tasks to get started.")

        sorted_tasks = self._sort_by_priority(all_tasks)
        scheduled, skipped = self._fit_to_time(sorted_tasks, owner.available_minutes)

        total_duration = sum(t.duration_minutes for t in scheduled)
        explanation = self._build_explanation(
            owner, scheduled, skipped, total_duration
        )

        return DailyPlan(
            scheduled=scheduled,
            skipped=skipped,
            total_duration=total_duration,
            explanation=explanation,
        )

    def _sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Return a new list sorted HIGH → MEDIUM → LOW (stable: preserves insertion order within each tier)."""
        return sorted(tasks, key=lambda t: _PRIORITY_RANK[t.priority])

    def _fit_to_time(
        self, tasks: list[Task], budget: int
    ) -> tuple[list[Task], list[Task]]:
        """Greedily include each priority-sorted task that still fits in the remaining budget; return (scheduled, skipped)."""
        scheduled: list[Task] = []
        skipped: list[Task] = []
        remaining = budget

        for task in tasks:
            if task.duration_minutes <= remaining:
                scheduled.append(task)
                remaining -= task.duration_minutes
            else:
                skipped.append(task)

        return scheduled, skipped

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_explanation(
        self,
        owner: Owner,
        scheduled: list[Task],
        skipped: list[Task],
        total_duration: int,
    ) -> str:
        """Compose a plain-English explanation of the scheduling decisions."""
        parts: list[str] = []

        parts.append(
            f"Tasks were sorted high → medium → low priority, then fitted "
            f"greedily into {owner.available_minutes} available minutes."
        )

        if scheduled:
            parts.append(
                f"{len(scheduled)} task(s) scheduled using {total_duration} of "
                f"{owner.available_minutes} minutes "
                f"({owner.available_minutes - total_duration} min remaining)."
            )

        if skipped:
            skipped_names = ", ".join(t.name for t in skipped)
            parts.append(
                f"{len(skipped)} task(s) skipped because they did not fit in the "
                f"remaining time: {skipped_names}."
            )
        else:
            parts.append("All tasks fit within the available time.")

        return " ".join(parts)
