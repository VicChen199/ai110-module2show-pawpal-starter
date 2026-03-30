import datetime

import streamlit as st

from pawpal_system import Owner, Pet, Task, Priority, Scheduler, _fmt_time

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

# ---------------------------------------------------------------------------
# Session-state initialisation
# Guard every key so objects survive Streamlit's full-script reruns.
# ---------------------------------------------------------------------------

if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="", available_minutes=90)

owner: Owner = st.session_state.owner

# ---------------------------------------------------------------------------
# Section 1 — Owner setup
# ---------------------------------------------------------------------------

st.subheader("1. Owner")

col_name, col_time = st.columns(2)
with col_name:
    owner.name = st.text_input("Your name", value=owner.name, placeholder="e.g. Jordan")
with col_time:
    owner.available_minutes = st.number_input(
        "Available minutes today", min_value=5, max_value=480,
        value=owner.available_minutes, step=5,
    )

st.divider()

# ---------------------------------------------------------------------------
# Section 2 — Add a pet  →  calls owner.add_pet()
# ---------------------------------------------------------------------------

st.subheader("2. Add a Pet")

col_pname, col_species, col_add = st.columns([2, 2, 1])
with col_pname:
    new_pet_name = st.text_input("Pet name", placeholder="e.g. Mochi")
with col_species:
    new_pet_species = st.selectbox("Species", ["dog", "cat", "other"])
with col_add:
    st.write("")          # vertical alignment spacer
    st.write("")
    if st.button("Add pet", use_container_width=True):
        if new_pet_name.strip():
            new_pet = Pet(name=new_pet_name.strip(), species=new_pet_species)
            owner.add_pet(new_pet)          # ← Phase 2 method call
        else:
            st.warning("Please enter a pet name.")

if owner.pets:
    st.write("Your pets:")
    for p in owner.pets:
        st.markdown(f"- **{p.name}** ({p.species}) — {len(p.tasks)} task(s)")
else:
    st.info("No pets yet. Add one above.")

st.divider()

# ---------------------------------------------------------------------------
# Section 3 — Add a task  →  calls pet.add_task()
# ---------------------------------------------------------------------------

st.subheader("3. Add a Task")

if not owner.pets:
    st.info("Add a pet first before adding tasks.")
else:
    pet_names = [p.name for p in owner.pets]
    selected_pet_name = st.selectbox("Which pet?", pet_names)
    selected_pet: Pet = next(p for p in owner.pets if p.name == selected_pet_name)

    col1, col2, col3 = st.columns(3)
    with col1:
        task_title = st.text_input("Task name", placeholder="e.g. Morning walk")
    with col2:
        duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
    with col3:
        priority_str = st.selectbox("Priority", ["high", "medium", "low"])

    # -- Scheduled time (optional) --
    col_time_toggle, col_time_picker = st.columns([1, 2])
    with col_time_toggle:
        use_time = st.checkbox("Set start time")
    with col_time_picker:
        if use_time:
            picked_time = st.time_input(
                "Start time", value=datetime.time(8, 0), label_visibility="collapsed"
            )
            scheduled_time_val: int | None = picked_time.hour * 60 + picked_time.minute
        else:
            scheduled_time_val = None

    # -- Recurrence --
    recurrence_option = st.selectbox("Repeats", ["none", "daily", "weekly"])
    recurrence_val: str | None = None if recurrence_option == "none" else recurrence_option

    if st.button("Add task", use_container_width=False):
        if task_title.strip():
            selected_pet.add_task(Task(             # ← Phase 2 method call
                name=task_title.strip(),
                duration_minutes=int(duration),
                priority=Priority(priority_str),
                scheduled_time=scheduled_time_val,
                recurrence=recurrence_val,
            ))
        else:
            st.warning("Please enter a task name.")

    st.divider()

    # -- Filter panel --
    st.subheader("3b. View & Filter Tasks")

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        filter_pet = st.selectbox(
            "Filter by pet", ["All pets"] + pet_names, key="filter_pet"
        )
    with filter_col2:
        filter_status = st.radio(
            "Filter by status", ["All", "Pending", "Completed"],
            horizontal=True, key="filter_status"
        )

    # Collect tasks to display
    if filter_pet == "All pets":
        display_tasks = [t for pet in owner.pets for t in pet.tasks]
    else:
        display_tasks = owner.get_tasks_for_pet(filter_pet)

    if filter_status == "Pending":
        display_tasks = [t for t in display_tasks if not t.completed]
    elif filter_status == "Completed":
        display_tasks = [t for t in display_tasks if t.completed]

    if display_tasks:
        # Sort by scheduled_time (unscheduled tasks at the bottom)
        display_tasks = sorted(
            display_tasks,
            key=lambda t: t.scheduled_time if t.scheduled_time is not None else float("inf"),
        )
        st.table([
            {
                "Pet": t.pet_name,
                "Task": t.name,
                "Start": t.time_label(),
                "Duration (min)": t.duration_minutes,
                "Priority": t.priority.value,
                "Repeats": t.recurrence or "—",
                "Done": t.completed,
            }
            for t in display_tasks
        ])
    else:
        st.info("No tasks match the current filter.")

st.divider()

# ---------------------------------------------------------------------------
# Section 4 — Generate schedule  →  calls Scheduler.generate_plan()
# ---------------------------------------------------------------------------

st.subheader("4. Generate Today's Schedule")

if st.button("Generate schedule", type="primary"):
    if not owner.pets:
        st.warning("Add at least one pet with tasks first.")
    else:
        plan = Scheduler().generate_plan(owner)     # ← Phase 2 method call

        # Surface conflicts prominently before the plan
        if plan.conflicts:
            st.error(
                f"**{len(plan.conflicts)} conflict(s) detected** — "
                "two or more tasks overlap in time. Review below."
            )
            for a, b in plan.conflicts:
                st.warning(
                    f"**[{a.pet_name}] {a.name}** "
                    f"({a.time_label()} – {_fmt_time(a.end_time())})"
                    f" overlaps **[{b.pet_name}] {b.name}** "
                    f"({b.time_label()} – {_fmt_time(b.end_time())})"
                )

        st.markdown("#### Today's Plan")
        st.text(plan.summary())
