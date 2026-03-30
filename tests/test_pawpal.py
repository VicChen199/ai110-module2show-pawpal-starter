"""Tests for core PawPal+ logic."""

from pawpal_system import Pet, Task, Priority


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
