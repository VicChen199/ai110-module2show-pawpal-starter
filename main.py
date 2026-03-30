"""
main.py — manual testing ground for PawPal+ logic.
Run with: python main.py
"""

from pawpal_system import Owner, Pet, Task, Priority, Scheduler


def main() -> None:
    # --- Build the owner ---
    jordan = Owner(name="Jordan", available_minutes=90)

    # --- Build pets and their tasks ---
    mochi = Pet(name="Mochi", species="dog")
    mochi.add_task(Task("Morning walk",      duration_minutes=30, priority=Priority.HIGH))
    mochi.add_task(Task("Breakfast feeding", duration_minutes=10, priority=Priority.HIGH))
    mochi.add_task(Task("Medication",        duration_minutes=5,  priority=Priority.HIGH))
    mochi.add_task(Task("Enrichment puzzle", duration_minutes=20, priority=Priority.MEDIUM))
    mochi.add_task(Task("Grooming brush",    duration_minutes=15, priority=Priority.LOW))

    luna = Pet(name="Luna", species="cat")
    luna.add_task(Task("Breakfast feeding",  duration_minutes=5,  priority=Priority.HIGH))
    luna.add_task(Task("Litter box clean",   duration_minutes=10, priority=Priority.MEDIUM))
    luna.add_task(Task("Wand toy play",      duration_minutes=15, priority=Priority.LOW))

    jordan.add_pet(mochi)
    jordan.add_pet(luna)

    # --- Run the scheduler ---
    plan = Scheduler().generate_plan(jordan)

    # --- Print results ---
    print("=" * 50)
    print(f"  PawPal+ — Today's Schedule for {jordan.name}")
    print("=" * 50)
    print(plan.summary())
    print("=" * 50)


if __name__ == "__main__":
    main()
