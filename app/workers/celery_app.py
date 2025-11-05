from celery import Celery
from app.config import settings

# Define the list of modules where Celery should look for tasks
# We will create 'app.workers.tasks' next.
TASK_MODULES = [
    'app.workers.tasks'
]

# Create the Celery application instance
celery_app = Celery(
    "multimodal_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=TASK_MODULES
)

# Load the task routing configuration from our other file
celery_app.config_from_object('app.workers.task_routes')

# Optional: Set other Celery configurations from our settings object
celery_app.conf.update(
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # This ensures tasks are acknowledged only after they complete or fail
    task_acks_late=True, 
    # Use 'json' for serializer, as it's language-agnostic
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
)

if __name__ == "__main__":
    celery_app.start()