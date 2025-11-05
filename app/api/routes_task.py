from fastapi import APIRouter, HTTPException, status
from celery.result import AsyncResult
from app.workers.celery_app import celery_app
from app.api.schemas import TaskStatusResponse, TaskStatus

router = APIRouter()

@router.get("/task/{task_id}", response_model=TaskStatusResponse, name="get_task_status")
def get_task_status(task_id: str):
    """
    Retrieves the status, progress, and result of an asynchronous task.
    """
    task_result = AsyncResult(task_id, app=celery_app)

    # --- Map Celery state to our Pydantic TaskStatus enum ---
    
    if not task_result.state:
        current_status = TaskStatus.PENDING
        details = "Task not found or state is unknown."
    elif task_result.state == 'PENDING':
        current_status = TaskStatus.PENDING
        details = "Task is waiting in the queue."
    elif task_result.state == 'RECEIVED':
        current_status = TaskStatus.RECEIVED
        details = "Task has been received by a worker."
    elif task_result.state == 'STARTED':
        current_status = TaskStatus.STARTED
        details = "Task has been started by a worker."
    elif task_result.state == 'PROCESSING':
        current_status = TaskStatus.PROCESSING
        details = "Task is currently processing."
    elif task_result.state == 'SUCCESS':
        current_status = TaskStatus.SUCCESS
        details = "Task completed successfully."
    elif task_result.state == 'FAILURE':
        current_status = TaskStatus.FAILURE
        details = "Task failed."
    else:
        # Catch-all for other Celery states (RETRY, REVOKED)
        current_status = TaskStatus.FAILURE
        details = f"Task is in an unexpected state: {task_result.state}"

    # --- Build the response ---

    response_data = {
        "task_id": task_id,
        "status": current_status,
        "details": details,
    }

    if task_result.info and isinstance(task_result.info, dict):
        # This is where our custom metadata (progress, artifacts, errors) lives
        response_data.update(task_result.info)
        
        # Ensure the status from the task info (which is the source of truth)
        # overrides the mapped Celery state if available.
        if 'status' in task_result.info:
             response_data['status'] = task_result.info['status']

    # If the task failed, 'info' will be the exception.
    if current_status == TaskStatus.FAILURE and not response_data.get('errors'):
        response_data['errors'] = str(task_result.info)
        
    # Handle the case where a task ID doesn't exist at all
    # (task_result.state will be 'PENDING' but info is None)
    if task_result.state == 'PENDING' and task_result.info is None:
        # This could also be a brand new task that hasn't been seen.
        # But if it stays this way, it might be an unknown task.
        # For a robust system, you might check task creation time.
        # For now, this is fine.
        pass

    # A final check for unknown task IDs
    if task_result.state == 'PENDING' and not task_result.backend.get(task_result.id):
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND, 
             detail="Task not found."
         )

    return TaskStatusResponse(**response_data)