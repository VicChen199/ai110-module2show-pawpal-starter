# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

**Three core user actions:**

1. **Enter owner and pet information** — The user provides basic context: their name, the pet's name and type, and how much time they have available each day. This data drives the scheduler's constraints and personalizes the care plan.

2. **Add and manage care tasks** — The user can create, edit, and remove individual pet care tasks (such as a morning walk, feeding, medication, or grooming). Each task has at minimum a name, estimated duration, and priority level so the scheduler knows what must be done versus what is optional.

3. **Generate and review the daily schedule** — The user triggers the scheduler to produce a concrete daily plan fitted to their available time and task priorities. The app displays the ordered list of tasks and explains why that particular plan was chosen (e.g., high-priority tasks scheduled first, tasks dropped due to time constraints).

**Class diagram (Mermaid):**

```mermaid
classDiagram
    class Owner {
        +str name
        +int available_minutes
        +list~Pet~ pets
        +add_pet(pet: Pet)
        +remove_pet(pet_name: str)
        +get_all_tasks() list~Task~
    }

    class Pet {
        +str name
        +str species
        +list~Task~ tasks
        +add_task(task: Task)
        +remove_task(task_name: str)
    }

    class Task {
        +str name
        +int duration_minutes
        +str priority
        +bool completed
        +complete()
        +reset()
    }

    class Scheduler {
        +generate_plan(owner: Owner) DailyPlan
        -_sort_by_priority(tasks: list~Task~) list~Task~
        -_fit_to_time(tasks: list~Task~, budget: int) tuple
    }

    class DailyPlan {
        +list~Task~ scheduled
        +list~Task~ skipped
        +int total_duration
        +str explanation
        +summary() str
    }

    Owner "1" --> "*" Pet : owns
    Pet "1" --> "*" Task : has
    Scheduler ..> Owner : uses
    Scheduler ..> DailyPlan : creates
    DailyPlan o-- Task : contains
```

**Design notes:**
- `Owner` is the root object — it holds the time budget and aggregates all pets (and transitively all tasks) via `get_all_tasks()`.
- `Task` is intentionally simple: name, duration, priority, and completion flag cover the scheduling requirements without over-engineering.
- `Scheduler` is stateless (no stored data) — it takes an `Owner` and returns a `DailyPlan`, making it easy to test in isolation.
- `DailyPlan` separates scheduled from skipped tasks so the UI can show both the plan and what was dropped (with `explanation` providing the reasoning).

**Classes and their responsibilities (as implemented in `pawpal_system.py`):**

| Class | Type | Responsibility |
|---|---|---|
| `Priority` | Enum | Defines the three valid priority levels (LOW, MEDIUM, HIGH) with explicit ordering |
| `Task` | Dataclass | Stores a single care activity: name, duration, priority, pet name, and completion state |
| `Pet` | Dataclass | Groups tasks under a named animal; stamps each added task with the pet's name |
| `Owner` | Class | Root object; holds the daily time budget and a list of pets; provides `get_all_tasks()` to flatten all tasks |
| `DailyPlan` | Dataclass | Holds the scheduler's output — scheduled tasks, skipped tasks, total duration, and a plain-text explanation |
| `Scheduler` | Class | Stateless engine; sorts tasks by priority, fits them greedily into the owner's time budget, and returns a `DailyPlan` |

**b. Design changes**

When I reviewed the skeleton (`pawpal_system.py`) against the original UML, I caught two problems and made two changes:

**Change 1: Replaced `str` priority with a `Priority` enum**

In the UML I wrote `priority: str` on `Task`. While reviewing the skeleton I realised that `_sort_by_priority` would need to compare those strings — and alphabetical order gives `"high" < "low" < "medium"`, which is completely wrong. I changed `priority` to a `Priority(str, Enum)` with members `LOW`, `MEDIUM`, `HIGH`. Because it inherits from `str`, it still serialises cleanly to `"low"` / `"medium"` / `"high"` for the UI and JSON, but now I can define an explicit sort order and the valid values are self-documenting. Raw strings for something the scheduler branches on would have been a silent bug waiting to happen.

**Change 2: Added `pet_name: str` to `Task`**

`Owner.get_all_tasks()` flattens all tasks from all pets into a single list. Once that happens, each `Task` loses the information about which pet it came from. When `DailyPlan` builds its `explanation` string it needs to say things like "Mochi: morning walk (20 min)" — but with the original UML it would only know the task name, not the animal. I added `pet_name: str = ""` to `Task` and made `Pet.add_task()` responsible for stamping that field when a task is attached. This keeps `Task` self-contained (no back-reference to a `Pet` object) while preserving the context the scheduler and UI need. The tradeoff is a mild redundancy — the pet name lives both on `Pet.name` and on each of its `Task.pet_name` fields — but that's a reasonable price for a flat, easy-to-iterate data structure.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers three constraints:

1. **Time budget** — `Owner.available_minutes` is a hard ceiling. No plan may exceed it; tasks that don't fit are placed in `DailyPlan.skipped` with an explanation.
2. **Priority** — tasks are ranked HIGH → MEDIUM → LOW. Within each tier, insertion order is preserved (stable sort). High-priority tasks consume the time budget first, so critical care (medication, feeding) is never crowded out by optional activities (grooming, enrichment).
3. **Fixed start times** — tasks with an explicit `scheduled_time` are placed at those exact clock positions and are not moved. Floating tasks (no scheduled time) are packed in after all fixed tasks have been placed.

Priority was treated as the most important constraint because the consequence of skipping a HIGH task (missed medication) is far worse than skipping a LOW task (missed grooming). Time is a hard physical constraint, so it is enforced without exception. Fixed times exist to accommodate real-world anchors (e.g., a vet appointment at 2 PM) that cannot be rescheduled by the algorithm.

**b. Tradeoffs**

**Tradeoff: greedy priority-first scheduling is simple but suboptimal.**

The scheduler picks tasks from highest to lowest priority and takes each one as long as it fits in the remaining budget — a classic greedy algorithm.  This is fast (O(n)) and easy to read, but it can miss better plans.

*Example:* suppose the budget is 60 minutes and three tasks are available — A (HIGH, 55 min), B (MEDIUM, 30 min), C (MEDIUM, 25 min).  The greedy algorithm schedules only A (55 min), leaving 5 min unused and skipping B and C.  An optimal knapsack solver would instead schedule B + C (55 min total), completing more tasks in the same window.

This tradeoff is reasonable here because:
- Pet care priorities are genuine — medication really does outrank grooming.
- The number of daily tasks is small (typically < 20), so suboptimal outcomes are rare and minor.
- Greedy output is predictable and explainable to the owner: "high-priority tasks were scheduled first."  A knapsack result might surprise users by dropping a HIGH task to fit two MEDIUM ones.

A future improvement would be a two-pass approach: always lock in all HIGH tasks first, then run a knapsack over the remaining budget for MEDIUM and LOW tasks.

---

## 3. AI Collaboration

**a. How you used AI**

AI assistance (Claude Code / VS Code Copilot) was used at three distinct stages:

1. **Design brainstorming** — asking "What are the most important edge cases for a pet scheduler with sorting and recurring tasks?" produced a structured list of happy paths and edge cases (same-start-time conflicts, adjacent-but-not-overlapping tasks, tasks spanning midnight) that I wouldn't have enumerated as quickly alone.

2. **Algorithm implementation** — the AI drafted the interval-overlap conflict-detection logic and the `timedelta` recurring-task pattern. Both were small, self-contained functions that were easy to read and verify in isolation before integrating them.

3. **Test generation** — prompting with the module's source file and asking for test functions for each new method produced accurate stubs quickly. The generated tests still required human review to confirm the assertions matched intended behavior (not just what the code happened to do).

The most effective prompt pattern was: *"Given this method signature and docstring, write pytest functions that cover one happy path and two edge cases."* Scoping to a single method kept suggestions focused and reviewable.

**b. Judgment and verification**

One AI suggestion that was modified: the first draft of `_sort_by_time` used `scheduled_time` (an integer) directly as the sort key rather than converting it to a `"HH:MM"` string.  The integer approach works, but the assignment specifically asked for a lambda on string keys to demonstrate that zero-padded strings sort chronologically.  I kept the string-key version and added an explanatory docstring showing the comparison (`"07:30" < "08:00" < "14:00"`) so a future reader understands *why* the string approach is valid.

Verification method: I added `test_sort_by_time_returns_chronological_order` with tasks inserted in reverse time order and asserted the exact output sequence.  The test failing before the fix and passing after it gave me confidence the logic was correct, not just plausible.

---

## 4. Testing and Verification

**a. What you tested**

21 automated tests cover four algorithm areas:

- **Sorting** — tasks inserted in reverse chronological order are returned sorted earliest → latest; unscheduled tasks always appear last; an empty list is handled without error.
- **Recurrence** — `complete()` on a `"daily"` task returns a new `Task` with `due_date = today + timedelta(days=1)`; `"weekly"` uses `timedelta(weeks=1)`; non-recurring tasks return `None`; `Pet.complete_task()` automatically appends the new instance to the pet's list.
- **Conflict detection** — same-start-time tasks are flagged; overlapping windows are flagged; tasks that only share a boundary (A ends == B starts) are correctly *not* flagged; conflicts across different pets are caught; the function never raises an exception.
- **Filtering** — filtering by pet name, by completion status, and by both criteria combined (AND logic).
- **Edge cases** — owner with pets but no tasks produces an informative explanation rather than an error; `generate_plan` includes the conflict list in the returned `DailyPlan`.

These tests matter because they verify the *decisions* the scheduler makes, not just that the code runs.  A greedy algorithm that silently drops the wrong tasks, or a conflict detector that crashes instead of warning, would both pass a "does it execute?" check but fail these behavioral assertions.

**b. Confidence**

**4 / 5 stars.**  All named behaviors and edge cases pass.  Remaining gaps:

- Tasks whose duration crosses midnight (e.g., `scheduled_time=23*60`, `duration=90`) — `end_time()` would exceed 1440 minutes; the overlap check is not tested for this.
- Owner with zero pets — `get_all_tasks()` returns `[]` and `generate_plan` would return the "no tasks" plan, but this path has no dedicated test.
- `available_minutes` smaller than every single task — the budget logic should skip everything; untested.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
