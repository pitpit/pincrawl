"""Task management functionality for tracking background tasks and workflows."""

from typing import Optional
from sqlalchemy.orm import Session
from pincrawl.database import Task, TaskStatus


class TaskManager:
    """Manager class for handling task operations and status tracking."""

    def get_latest_task_by_name(self, session: Session, task_name: str) -> Optional[Task]:
        """Get the latest task with the given name, ordered by created_at desc."""
        return session.query(Task).filter_by(name=task_name).order_by(Task.created_at.desc()).first()

    def create_task(self, session: Session, task_name: str, status: TaskStatus = TaskStatus.IN_PROGRESS) -> Task:
        """Create a new task with the given name and status."""
        task = Task(name=task_name, status=status)
        session.add(task)
        session.commit()
        return task

    def update_task_status(self, session: Session, task: Task, status: TaskStatus) -> Task:
        """Update the status of an existing task."""
        task.status = status
        session.commit()
        return task