"""
PawPal+ — backend logic layer.

Class hierarchy:
    Owner 1──* Pet 1──* Task
    Scheduler ──uses──> Owner ──produces──> DailyPlan ──contains──> Task
"""

from __future__ import annotations

import datetime
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
# Helpers
# ---------------------------------------------------------------------------

def _fmt_time(minutes: int | None) -> str:
    """Convert minutes-from-midnight to a human-readable string like '8:00 AM'."""
    if minutes is None:
        return "?"
    h, m = divmod(minutes, 60)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


# ---------------------------------------------------------------------------
# Dataclasses  (simple value objects)
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A single pet-care activity."""

    name: str
    duration_minutes: int
    priority: Priority
    pet_name: str = ""          # stamped by Pet.add_task so the plan knows which animal
    completed: bool = False
    scheduled_time: int | None = None   # minutes from midnight (e.g. 480 = 8:00 AM)
    recurrence: str | None = None       # "daily" | "weekly" | None
    due_date: datetime.date = field(default_factory=datetime.date.today)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def time_str(self) -> str | None:
        """Return the start time as a zero-padded 'HH:MM' string, or None.

        Using a zero-padded format means plain string comparison ('08:00' <
        '12:30') produces correct chronological order — no integer conversion
        needed inside the sort key lambda.
        """
        if self.scheduled_time is None:
            return None
        h, m = divmod(self.scheduled_time, 60)
        return f"{h:02d}:{m:02d}"

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def complete(self) -> Task | None:
        """Mark this task as done and, for recurring tasks, return the next occurrence.

        Uses datetime.timedelta to calculate the next due date accurately:
          - "daily"  → due_date + timedelta(days=1)
          - "weekly" → due_date + timedelta(weeks=1)

        The caller is responsible for adding the returned Task to the pet so
        the new occurrence appears in future schedules.  Returns None for
        non-recurring tasks.
        """
        self.completed = True

        if self.recurrence == "daily":
            next_due = self.due_date + datetime.timedelta(days=1)
        elif self.recurrence == "weekly":
            next_due = self.due_date + datetime.timedelta(weeks=1)
        else:
            return None   # not recurring — nothing more to do

        # Build a fresh, incomplete copy for the next occurrence
        return Task(
            name=self.name,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            scheduled_time=self.scheduled_time,
            recurrence=self.recurrence,
            due_date=next_due,
        )

    def reset(self) -> None:
        """Clear the completed flag so the task can be scheduled again."""
        self.completed = False

    def end_time(self) -> int | None:
        """Return the finish time in minutes-from-midnight, or None if unscheduled."""
        if self.scheduled_time is None:
            return None
        return self.scheduled_time + self.duration_minutes

    def time_label(self) -> str:
        """Return a human-readable start time string, e.g. '8:00 AM'."""
        return _fmt_time(self.scheduled_time)

    def is_due(self) -> bool:
        """Return True when the task has not been completed.

        Recurring tasks are kept alive by having complete() produce a brand-new
        Task for the next occurrence rather than by ignoring the completed flag.
        This keeps the logic simple: every task is due if and only if it is not
        yet marked done.
        """
        return not self.completed


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

    def complete_task(self, task_name: str) -> Task | None:
        """Mark a task done and auto-register its next occurrence if recurring.

        Returns the newly created next-occurrence Task, or None.
        """
        for task in self.tasks:
            if task.name.lower() == task_name.lower():
                next_task = task.complete()
                if next_task is not None:
                    self.add_task(next_task)
                return next_task
        return None


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
        """Return a flat list of every due task across all pets."""
        return [task for pet in self.pets for task in pet.tasks if task.is_due()]

    def get_tasks_for_pet(self, pet_name: str) -> list[Task]:
        """Return all tasks belonging to the named pet (case-insensitive)."""
        for pet in self.pets:
            if pet.name.lower() == pet_name.lower():
                return list(pet.tasks)
        return []

    def get_tasks_by_status(self, completed: bool) -> list[Task]:
        """Return all tasks across all pets matching the given completion status."""
        return [
            task
            for pet in self.pets
            for task in pet.tasks
            if task.completed == completed
        ]


@dataclass
class DailyPlan:
    """The output produced by Scheduler.generate_plan()."""

    scheduled: list[Task] = field(default_factory=list)
    skipped: list[Task] = field(default_factory=list)
    conflicts: list[tuple[Task, Task]] = field(default_factory=list)
    total_duration: int = 0
    explanation: str = ""

    def summary(self) -> str:
        """Return a human-readable summary suitable for display in the UI."""
        lines: list[str] = []

        if self.conflicts:
            lines.append("CONFLICTS DETECTED:")
            for a, b in self.conflicts:
                lines.append(
                    f"  ! [{a.pet_name}] {a.name}"
                    f" ({a.time_label()}–{_fmt_time(a.end_time())})"
                    f" overlaps [{b.pet_name}] {b.name}"
                    f" ({b.time_label()}–{_fmt_time(b.end_time())})"
                )
            lines.append("")

        if self.scheduled:
            lines.append(f"Scheduled ({self.total_duration} min total):")
            for task in self.scheduled:
                pet_label = f"[{task.pet_name}] " if task.pet_name else ""
                time_label = f" @ {task.time_label()}" if task.scheduled_time is not None else ""
                recur_label = f" ↻ {task.recurrence}" if task.recurrence else ""
                lines.append(
                    f"  • {pet_label}{task.name}{time_label}"
                    f" — {task.duration_minutes} min"
                    f" ({task.priority.value} priority){recur_label}"
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

    Fixed-time tasks (those with a scheduled_time) are placed first and checked
    for conflicts.  Floating tasks (no scheduled_time) are sorted by priority
    and greedily fitted into the remaining time budget, starting after the last
    fixed task ends.
    """

    DAY_START_MINUTES: int = 480  # 8:00 AM

    def generate_plan(self, owner: Owner) -> DailyPlan:
        """Build and return a DailyPlan that fits within owner.available_minutes."""
        all_tasks = owner.get_all_tasks()

        if not all_tasks:
            return DailyPlan(explanation="No tasks found. Add some tasks to get started.")

        # Split into fixed-time tasks and floating tasks
        fixed = [t for t in all_tasks if t.scheduled_time is not None]
        floating = [t for t in all_tasks if t.scheduled_time is None]

        # Sort fixed tasks by their explicit start time
        fixed_sorted = self._sort_by_time(fixed)

        # Detect overlapping fixed-time windows
        conflicts = self.detect_conflicts(fixed_sorted)

        # Sort floating tasks by priority (HIGH → MEDIUM → LOW)
        floating_sorted = self._sort_by_priority(floating)

        # Cursor: floating tasks are placed sequentially after all fixed tasks
        fixed_duration = sum(t.duration_minutes for t in fixed_sorted)
        if fixed_sorted:
            cursor = max(
                (t.scheduled_time + t.duration_minutes)
                for t in fixed_sorted
                if t.scheduled_time is not None
            )
        else:
            cursor = self.DAY_START_MINUTES

        # Greedily fit floating tasks into the remaining budget
        remaining_budget = max(0, owner.available_minutes - fixed_duration)
        scheduled_floating: list[Task] = []
        skipped: list[Task] = []

        for task in floating_sorted:
            if task.duration_minutes <= remaining_budget:
                task.scheduled_time = cursor
                cursor += task.duration_minutes
                remaining_budget -= task.duration_minutes
                scheduled_floating.append(task)
            else:
                skipped.append(task)

        # Merge and re-sort by time for the final ordered view
        scheduled = self._sort_by_time(fixed_sorted + scheduled_floating)
        total_duration = sum(t.duration_minutes for t in scheduled)
        explanation = self._build_explanation(
            owner, scheduled, skipped, total_duration, conflicts
        )

        return DailyPlan(
            scheduled=scheduled,
            skipped=skipped,
            conflicts=conflicts,
            total_duration=total_duration,
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def _sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Return a new list sorted HIGH → MEDIUM → LOW (stable within each tier)."""
        return sorted(tasks, key=lambda t: _PRIORITY_RANK[t.priority])

    def _sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted chronologically using a lambda on the 'HH:MM' string.

        Why strings work here:
          "07:30" < "08:00" < "14:00" — lexicographic order matches clock order
          as long as hours are zero-padded to two digits.  The lambda returns
          "99:99" for unscheduled tasks so they always sort to the end.

        Example:
            tasks added in order:  Evening walk (18:00), Breakfast (07:30), Walk (08:00)
            lambda values:          "18:00",              "07:30",           "08:00"
            sorted result:          Breakfast → Walk → Evening walk
        """
        return sorted(
            tasks,
            key=lambda t: t.time_str if t.time_str is not None else "99:99",
        )

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    @staticmethod
    def filter_tasks(
        tasks: list[Task],
        *,
        completed: bool | None = None,
        pet_name: str | None = None,
    ) -> list[Task]:
        """Return a filtered subset of tasks.

        Both criteria are optional and can be combined:
          - completed=True   → only tasks already marked done
          - completed=False  → only tasks still pending
          - pet_name="Mochi" → only tasks belonging to that pet (case-insensitive)

        Example:
            # All pending tasks for Mochi
            Scheduler.filter_tasks(all_tasks, completed=False, pet_name="Mochi")
        """
        result = tasks
        if pet_name is not None:
            result = [t for t in result if t.pet_name.lower() == pet_name.lower()]
        if completed is not None:
            result = [t for t in result if t.completed == completed]
        return result

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def detect_conflicts(self, tasks: list[Task]) -> list[tuple[Task, Task]]:
        """Return pairs of timed tasks whose scheduled windows overlap.

        Strategy — lightweight interval-overlap test (no exceptions raised):
          Two tasks A and B conflict when:
              A.start < B.end  AND  B.start < A.end
          This is the standard "do two ranges overlap?" check.  The method
          simply collects conflicting pairs and returns them; it never raises
          an exception or modifies any task, so callers can inspect warnings
          without the program crashing.

        Works across pets: any two tasks from any pets are compared.
        """
        conflicts: list[tuple[Task, Task]] = []
        timed = [t for t in tasks if t.scheduled_time is not None]

        for i, a in enumerate(timed):
            a_start: int = a.scheduled_time  # type: ignore[assignment]
            a_end = a_start + a.duration_minutes
            for b in timed[i + 1:]:
                b_start: int = b.scheduled_time  # type: ignore[assignment]
                b_end = b_start + b.duration_minutes
                if a_start < b_end and b_start < a_end:
                    conflicts.append((a, b))

        return conflicts

    # ------------------------------------------------------------------
    # Greedy fit (kept for direct use / testing)
    # ------------------------------------------------------------------

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
        conflicts: list[tuple[Task, Task]],
    ) -> str:
        """Compose a plain-English explanation of the scheduling decisions."""
        parts: list[str] = []

        parts.append(
            f"Fixed-time tasks were placed first; remaining tasks were sorted "
            f"high → medium → low priority and fitted into "
            f"{owner.available_minutes} available minutes."
        )

        if scheduled:
            parts.append(
                f"{len(scheduled)} task(s) scheduled using {total_duration} of "
                f"{owner.available_minutes} minutes "
                f"({owner.available_minutes - total_duration} min remaining)."
            )

        if conflicts:
            parts.append(
                f"{len(conflicts)} scheduling conflict(s) detected — "
                f"review the warnings above."
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
