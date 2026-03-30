"""Tests for core PawPal+ logic.

Coverage plan
-------------
Happy paths
  - Sorting three tasks added out of order → correct chronological result
  - Daily recurrence → next Task due tomorrow
  - Weekly recurrence → next Task due 7 days later
  - Non-recurring complete() → returns None, task marked done
  - Pet.complete_task() → auto-appends next occurrence to pet's list
  - filter_tasks by pet name, by status, and with both criteria combined
  - generate_plan on an owner with no tasks → explanation, no crash

Edge cases
  - Sorting: unscheduled tasks always go last ("99:99" sentinel)
  - Sorting: empty list → empty list
  - Conflict: two tasks at exact same start time
  - Conflict: overlapping windows (B starts before A ends)
  - No conflict: adjacent tasks (A ends exactly when B starts)
  - No conflict: tasks with a clear gap between them
  - Conflict: flagged across different pets
  - generate_plan: conflict surfaces in the returned DailyPlan object
  - Pet.complete_task: unknown task name returns None gracefully
"""

import datetime

from pawpal_system import Owner, Pet, Priority, Scheduler, Task


# ---------------------------------------------------------------------------
# Existing tests (kept exactly as written)
# ---------------------------------------------------------------------------

def test_task_completion_changes_status():
    """Calling complete() on a task sets completed to True."""
    task = Task(name="Morning walk", duration_minutes=30, priority=Priority.HIGH)
    assert task.completed is False

    task.complete()

    assert task.completed is True


def test_adding_task_increases_pet_task_count():
    """Adding a task to a Pet increases its task list by one."""
    pet = Pet(name="Mochi", species="dog")
    assert len(pet.tasks) == 0

    pet.add_task(Task(name="Feeding", duration_minutes=10, priority=Priority.HIGH))

    assert len(pet.tasks) == 1


# ---------------------------------------------------------------------------
# Sorting — _sort_by_time uses a lambda on zero-padded "HH:MM" strings
# ---------------------------------------------------------------------------

def test_sort_by_time_returns_chronological_order():
    """Tasks added out of order are returned sorted earliest → latest."""
    scheduler = Scheduler()
    tasks = [
        Task("Evening walk",    30, Priority.LOW,    scheduled_time=18 * 60),      # 18:00
        Task("Morning walk",    30, Priority.HIGH,   scheduled_time=8 * 60),       # 08:00
        Task("Breakfast",       10, Priority.HIGH,   scheduled_time=7 * 60 + 30),  # 07:30
    ]

    result = scheduler._sort_by_time(tasks)

    assert [t.name for t in result] == ["Breakfast", "Morning walk", "Evening walk"]


def test_sort_by_time_unscheduled_tasks_go_last():
    """Tasks without a scheduled_time appear after all timed tasks."""
    scheduler = Scheduler()
    tasks = [
        Task("Grooming",     15, Priority.LOW),                                    # Unscheduled
        Task("Medication",    5, Priority.HIGH,   scheduled_time=8 * 60),          # 08:00
        Task("Evening walk", 30, Priority.MEDIUM, scheduled_time=18 * 60),         # 18:00
    ]

    result = scheduler._sort_by_time(tasks)

    # Unscheduled task must come last regardless of its position in the input
    assert result[-1].name == "Grooming"
    assert result[0].name == "Medication"


def test_sort_by_time_empty_list():
    """Sorting an empty list returns an empty list without raising."""
    assert Scheduler()._sort_by_time([]) == []


# ---------------------------------------------------------------------------
# Recurrence — complete() returns next occurrence; timedelta drives the date
# ---------------------------------------------------------------------------

def test_daily_recurrence_returns_next_day_task():
    """Completing a daily task creates a new Task due exactly one day later."""
    today = datetime.date.today()
    task = Task("Medication", 5, Priority.HIGH, recurrence="daily", due_date=today)

    next_task = task.complete()

    assert task.completed is True
    assert next_task is not None
    assert next_task.due_date == today + datetime.timedelta(days=1)
    # The next occurrence must start fresh — not already completed
    assert next_task.completed is False
    # Core attributes are copied over
    assert next_task.name == task.name
    assert next_task.recurrence == "daily"


def test_weekly_recurrence_returns_next_week_task():
    """Completing a weekly task creates a new Task due exactly seven days later."""
    today = datetime.date.today()
    task = Task("Grooming", 15, Priority.LOW, recurrence="weekly", due_date=today)

    next_task = task.complete()

    assert next_task is not None
    assert next_task.due_date == today + datetime.timedelta(weeks=1)


def test_non_recurring_complete_returns_none():
    """Completing a non-recurring task returns None and marks the task done."""
    task = Task("One-time vet visit", 60, Priority.HIGH)

    result = task.complete()

    assert result is None
    assert task.completed is True


def test_pet_complete_task_auto_registers_next_occurrence():
    """Pet.complete_task() appends the next recurring instance to the pet's list."""
    pet = Pet(name="Mochi", species="dog")
    pet.add_task(Task("Medication", 5, Priority.HIGH, recurrence="daily"))
    assert len(pet.tasks) == 1

    pet.complete_task("Medication")

    # Original is done; new occurrence was appended
    assert len(pet.tasks) == 2
    assert pet.tasks[0].completed is True
    assert pet.tasks[1].completed is False
    assert pet.tasks[1].name == "Medication"


def test_pet_complete_task_unknown_name_returns_none_gracefully():
    """Calling complete_task with an unknown name does not crash and returns None."""
    pet = Pet(name="Luna", species="cat")
    result = pet.complete_task("This task does not exist")
    assert result is None


# ---------------------------------------------------------------------------
# Conflict detection — lightweight interval-overlap test; never raises
# ---------------------------------------------------------------------------

def test_conflict_detected_for_same_start_time():
    """Two tasks starting at the exact same minute are flagged as a conflict."""
    scheduler = Scheduler()
    tasks = [
        Task("Morning walk", 30, Priority.HIGH, scheduled_time=8 * 60, pet_name="Mochi"),
        Task("Medication",    5, Priority.HIGH, scheduled_time=8 * 60, pet_name="Mochi"),
    ]

    conflicts = scheduler.detect_conflicts(tasks)

    assert len(conflicts) == 1
    all_names = {t.name for pair in conflicts for t in pair}
    assert "Morning walk" in all_names and "Medication" in all_names


def test_conflict_detected_for_overlapping_windows():
    """A task that starts before another finishes is detected as a conflict."""
    scheduler = Scheduler()
    tasks = [
        # Walk: 08:00–08:30
        Task("Walk",    30, Priority.HIGH, scheduled_time=8 * 60,      pet_name="Mochi"),
        # Feeding starts at 08:20 — inside the walk window
        Task("Feeding", 10, Priority.HIGH, scheduled_time=8 * 60 + 20, pet_name="Mochi"),
    ]

    conflicts = scheduler.detect_conflicts(tasks)

    assert len(conflicts) == 1


def test_no_conflict_for_adjacent_tasks():
    """Tasks that share only a boundary (A ends == B starts) do NOT conflict.

    Interval-overlap condition: A.start < B.end AND B.start < A.end
    When B.start == A.end the second condition is False → no conflict.
    """
    scheduler = Scheduler()
    tasks = [
        Task("Walk",    30, Priority.HIGH, scheduled_time=8 * 60,      pet_name="Mochi"),  # 08:00–08:30
        Task("Feeding",  5, Priority.HIGH, scheduled_time=8 * 60 + 30, pet_name="Mochi"),  # 08:30–08:35
    ]

    conflicts = scheduler.detect_conflicts(tasks)

    assert conflicts == []


def test_no_conflict_for_clearly_separated_tasks():
    """Tasks with a clear time gap between them produce no conflicts."""
    scheduler = Scheduler()
    tasks = [
        Task("Morning walk", 30, Priority.HIGH,   scheduled_time=8 * 60),    # 08:00–08:30
        Task("Evening walk", 30, Priority.MEDIUM, scheduled_time=18 * 60),   # 18:00–18:30
    ]

    assert scheduler.detect_conflicts(tasks) == []


def test_conflict_detected_across_different_pets():
    """Conflicts are flagged even when the overlapping tasks belong to different pets."""
    scheduler = Scheduler()
    tasks = [
        Task("Mochi feeding", 10, Priority.HIGH, scheduled_time=7 * 60 + 30, pet_name="Mochi"),
        Task("Luna feeding",   5, Priority.HIGH, scheduled_time=7 * 60 + 30, pet_name="Luna"),
    ]

    conflicts = scheduler.detect_conflicts(tasks)

    assert len(conflicts) == 1


# ---------------------------------------------------------------------------
# Filtering — Scheduler.filter_tasks is a static method, no instance needed
# ---------------------------------------------------------------------------

def test_filter_by_pet_name_returns_only_that_pets_tasks():
    """filter_tasks with pet_name filters out every other pet's tasks."""
    tasks = [
        Task("Walk",     30, Priority.HIGH, pet_name="Mochi"),
        Task("Feeding",   5, Priority.HIGH, pet_name="Luna"),
        Task("Grooming", 15, Priority.LOW,  pet_name="Mochi"),
    ]

    result = Scheduler.filter_tasks(tasks, pet_name="Mochi")

    assert len(result) == 2
    assert all(t.pet_name == "Mochi" for t in result)


def test_filter_by_completed_true_returns_only_done_tasks():
    """filter_tasks with completed=True returns only finished tasks."""
    done    = Task("Walk",    30, Priority.HIGH)
    pending = Task("Feeding",  5, Priority.HIGH)
    done.complete()

    result = Scheduler.filter_tasks([done, pending], completed=True)

    assert result == [done]


def test_filter_by_completed_false_returns_only_pending_tasks():
    """filter_tasks with completed=False returns only tasks still to do."""
    done    = Task("Walk",    30, Priority.HIGH)
    pending = Task("Feeding",  5, Priority.HIGH)
    done.complete()

    result = Scheduler.filter_tasks([done, pending], completed=False)

    assert result == [pending]


def test_filter_combined_pet_name_and_completed():
    """Combining both criteria returns the intersection (AND logic)."""
    mochi_done    = Task("Walk",     30, Priority.HIGH, pet_name="Mochi")
    mochi_pending = Task("Grooming", 15, Priority.LOW,  pet_name="Mochi")
    luna_done     = Task("Feeding",   5, Priority.HIGH, pet_name="Luna")
    mochi_done.complete()
    luna_done.complete()

    result = Scheduler.filter_tasks(
        [mochi_done, mochi_pending, luna_done],
        completed=True,
        pet_name="Mochi",
    )

    assert result == [mochi_done]


# ---------------------------------------------------------------------------
# generate_plan — edge cases at the plan level
# ---------------------------------------------------------------------------

def test_generate_plan_with_no_tasks_returns_explanation_not_error():
    """An owner whose pets have no tasks gets a plan with an explanation, not a crash."""
    owner = Owner(name="Jordan", available_minutes=60)
    owner.add_pet(Pet(name="Mochi", species="dog"))   # pet exists but has no tasks

    plan = Scheduler().generate_plan(owner)

    assert plan.scheduled == []
    assert "No tasks found" in plan.explanation


def test_generate_plan_surfaces_conflict_in_daily_plan():
    """Conflicting fixed-time tasks appear in DailyPlan.conflicts after generate_plan."""
    owner = Owner(name="Jordan", available_minutes=120)
    mochi = Pet(name="Mochi", species="dog")
    mochi.add_task(Task("Morning walk", 30, Priority.HIGH, scheduled_time=8 * 60))
    mochi.add_task(Task("Medication",    5, Priority.HIGH, scheduled_time=8 * 60))
    owner.add_pet(mochi)

    plan = Scheduler().generate_plan(owner)

    assert len(plan.conflicts) == 1
