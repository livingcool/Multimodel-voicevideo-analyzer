from app.config import settings

# Define our queues
# Even in a PoC, we define the *queues* we want.
# We might only run one worker listening to 'cpu_tasks' for now,
# but the routing logic is ready for production.
GPU_QUEUE = "gpu_tasks"
CPU_QUEUE = settings.CELERY_DEFAULT_QUEUE  # e.g., "cpu_tasks"

# The main routing configuration
task_routes = {
    'app.workers.tasks.ingest_video': {'queue': GPU_QUEUE},
    'app.workers.tasks.ingest_image': {'queue': GPU_QUEUE},
    
    # All other tasks (like audio, text, or orchestration) go to the default CPU queue
    'app.workers.tasks.*': {'queue': CPU_QUEUE},
}