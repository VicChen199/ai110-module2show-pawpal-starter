"""
main.py — manual testing ground for PawPal+ logic.
Run with: python main.py

Demonstrates:
  1. Sorting tasks added out of order using a lambda on "HH:MM" strings
  2. Filtering tasks by pet name and completion status
  3. Recurring task auto-creation via timedelta
  4. Conflict detection returning warnings (no crash)
"""

import datetime

from pawpal_system import Owner, Pet, Task, Priority, Scheduler


SEP  = "=" * 55
SEP2 = "-" * 55


def main() -> None:

    # ----------------------------------------------------------------
    # Build the owner
    # ----------------------------------------------------------------
    jordan = Owner(name="Jordan", available_minutes=120)

    # ----------------------------------------------------------------
    # Build pets — tasks added INTENTIONALLY OUT OF ORDER by time
    # so sorting is visibly useful.
    # ----------------------------------------------------------------
    mochi = Pet(name="Mochi", species="dog")

    # Added last → first by clock time to prove sort works
    mochi.add_task(Task("Evening walk",    duration_minutes=30, priority=Priority.MEDIUM,
                        scheduled_time=18 * 60))            # 18:00  ← added first
    mochi.add_task(Task("Enrichment puzzle", duration_minutes=20, priority=Priority.MEDIUM,
                        scheduled_time=10 * 60))            # 10:00
    mochi.add_task(Task("Morning walk",    duration_minutes=30, priority=Priority.HIGH,
                        scheduled_time=8 * 60))             # 08:00
    # Medication starts at 08:00 — same slot as Morning walk → CONFLICT
    mochi.add_task(Task("Medication",      duration_minutes=5,  priority=Priority.HIGH,
                        scheduled_time=8 * 60,              # 08:00  ← deliberate conflict
                        recurrence="daily"))
    mochi.add_task(Task("Grooming brush",  duration_minutes=15, priority=Priority.LOW))
    # No scheduled_time → floating task, placed by scheduler

    luna = Pet(name="Luna", species="cat")
    luna.add_task(Task("Breakfast feeding", duration_minutes=5,  priority=Priority.HIGH,
                       scheduled_time=7 * 60 + 30))         # 07:30
    luna.add_task(Task("Wand toy play",     duration_minutes=15, priority=Priority.LOW,
                       recurrence="weekly"))
    luna.add_task(Task("Litter box clean",  duration_minutes=10, priority=Priority.MEDIUM))

    jordan.add_pet(mochi)
    jordan.add_pet(luna)

    # ----------------------------------------------------------------
    # Collect every task for sorting / filtering demos
    # ----------------------------------------------------------------
    all_tasks: list[Task] = [t for pet in jordan.pets for t in pet.tasks]
    scheduler = Scheduler()

    # ================================================================
    # 1. SORT BY TIME  (lambda on "HH:MM" string)
    # ================================================================
    # The lambda returns each task's time_str ("HH:MM") as the sort key.
    # Zero-padded strings sort lexicographically == chronologically.
    # Unscheduled tasks (time_str is None) fall back to "99:99" so they
    # always appear at the end of the sorted list.
    print(SEP)
    print("  1. TASKS SORTED BY TIME (lambda on 'HH:MM')")
    print(SEP)
    sorted_tasks = scheduler._sort_by_time(all_tasks)
    for t in sorted_tasks:
        label = t.time_str if t.time_str is not None else "Unscheduled"
        print(f"  {label:>11}  [{t.pet_name:<5}] {t.name}")

    # ================================================================
    # 2. FILTERING
    # ================================================================
    print(f"\n{SEP}")
    print("  2a. FILTER: Mochi's tasks only")
    print(SEP)
    mochi_tasks = Scheduler.filter_tasks(all_tasks, pet_name="Mochi")
    for t in mochi_tasks:
        print(f"  [{t.priority.value:<6}] {t.name}")

    print(f"\n{SEP2}")
    print("  2b. FILTER: Pending tasks only (completed=False)")
    print(SEP2)
    pending = Scheduler.filter_tasks(all_tasks, completed=False)
    for t in pending:
        print(f"  [{t.pet_name:<5}] {t.name}")

    print(f"\n{SEP2}")
    print("  2c. FILTER: Pending Mochi tasks (both criteria combined)")
    print(SEP2)
    mochi_pending = Scheduler.filter_tasks(all_tasks, completed=False, pet_name="Mochi")
    for t in mochi_pending:
        print(f"  {t.name}")

    # ================================================================
    # 3. RECURRING TASK — complete and inspect next occurrence
    # ================================================================
    # timedelta is how Python calculates accurate date arithmetic:
    #   today + timedelta(days=1)  → tomorrow's date regardless of
    #   month boundaries, leap years, etc.
    #   today + timedelta(weeks=1) → same weekday next week.
    #
    # Task.complete() performs this math internally and returns the
    # next Task; Pet.complete_task() calls it and registers the result.
    print(f"\n{SEP}")
    print("  3. RECURRING TASKS — completing and auto-scheduling next")
    print(SEP)

    # Daily: Medication
    today = datetime.date.today()
    next_med = mochi.complete_task("Medication")
    med_original = next(t for t in mochi.tasks if t.name == "Medication" and t.completed)
    print(f"  Completed  : [{med_original.pet_name}] {med_original.name}  (due {med_original.due_date})")
    if next_med:
        print(f"  Next due   : {next_med.due_date}   "
              f"(today {today} + timedelta(days=1))")

    # Weekly: Wand toy play
    next_play = luna.complete_task("Wand toy play")
    play_original = next(t for t in luna.tasks if t.name == "Wand toy play" and t.completed)
    print(f"  Completed  : [{play_original.pet_name}] {play_original.name}  (due {play_original.due_date})")
    if next_play:
        print(f"  Next due   : {next_play.due_date}   "
              f"(today {today} + timedelta(weeks=1))")

    # ================================================================
    # 4. CONFLICT DETECTION
    # ================================================================
    # Mochi has "Morning walk" and "Medication" both at 08:00.
    # detect_conflicts() uses an interval-overlap test and returns
    # warning pairs — it never raises an exception.
    print(f"\n{SEP}")
    print("  4. CONFLICT DETECTION")
    print(SEP)
    plan = scheduler.generate_plan(jordan)

    if plan.conflicts:
        print(f"  WARNING — {len(plan.conflicts)} conflict(s) found:")
        for a, b in plan.conflicts:
            print(
                f"    [{a.pet_name}] '{a.name}' @ {a.time_str}"
                f"–{a.end_time() // 60:02d}:{a.end_time() % 60:02d}"   # type: ignore[operator]
                f"  overlaps"
                f"  [{b.pet_name}] '{b.name}' @ {b.time_str}"
                f"–{b.end_time() // 60:02d}:{b.end_time() % 60:02d}"   # type: ignore[operator]
            )
    else:
        print("  No conflicts detected.")

    # ================================================================
    # 5. FULL PLAN SUMMARY
    # ================================================================
    print(f"\n{SEP}")
    print(f"  Today's Schedule for {jordan.name}")
    print(SEP)
    print(plan.summary())
    print(SEP)


if __name__ == "__main__":
    main()
