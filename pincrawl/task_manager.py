"""Task management functionality for tracking background tasks and workflows."""

from typing import Optional
from sqlalchemy.orm import Session
from pincrawl.database import Task, TaskStatus

import logging

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

    def cleanup_old_tasks(self, session: Session, keep_count: int = 300) -> int:
        """Clean up old tasks, keeping only the most recent ones.

        Args:
            session: Database session
            keep_count: Number of most recent tasks to keep (default: 100)

        Returns:
            Number of tasks deleted
        """
        # Count total tasks
        total_tasks = session.query(Task).count()

        if total_tasks <= keep_count:
            logging.debug(f"No tasks to delete, keeping latest {keep_count} tasks (total: {total_tasks})")
            return 0

        # Get the created_at timestamp of the keep_count-th most recent task
        threshold_task = session.query(Task).order_by(Task.created_at.desc()).offset(keep_count).limit(1).first()

        if not threshold_task:
            logging.debug(f"No threshold task found")
            return 0

        # Delete all tasks older than this threshold
        deleted_count = session.query(Task).filter(Task.created_at < threshold_task.created_at).delete(synchronize_session=False)

        logging.debug(f"Deleted {deleted_count} old tasks (threshold: {threshold_task.created_at})")

        session.commit()
        return deleted_count