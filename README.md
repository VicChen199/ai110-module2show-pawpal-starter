# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Smarter Scheduling

The scheduler now goes beyond basic priority-first fitting with four algorithm improvements:

**Sorting by time** — tasks are sorted chronologically using a lambda that compares `"HH:MM"` strings.  Zero-padded strings sort lexicographically in clock order (`"07:30" < "08:00" < "14:00"`), so no integer conversion is needed in the key function.  Unscheduled tasks fall back to `"99:99"` and appear at the end.

**Filtering** — `Scheduler.filter_tasks(tasks, completed=..., pet_name=...)` returns any subset of tasks by completion status, pet, or both criteria combined.  `Owner.get_tasks_for_pet()` and `Owner.get_tasks_by_status()` offer the same filtering scoped to the owner's full household.

**Recurring tasks** — tasks can be marked `recurrence="daily"` or `recurrence="weekly"`.  When `Pet.complete_task()` is called, it uses `datetime.timedelta(days=1)` or `timedelta(weeks=1)` to compute the next due date and automatically registers a fresh task instance — no manual re-entry required.

**Conflict detection** — `Scheduler.detect_conflicts()` runs a lightweight O(n²) interval-overlap test (`A.start < B.end and B.start < A.end`) across all scheduled tasks, including tasks belonging to different pets.  Conflicts are returned as warning pairs — the program never raises an exception — and are surfaced prominently in the plan summary and Streamlit UI.

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.
