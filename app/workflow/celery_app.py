from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "roxy",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    imports=(
        "app.workflow.tasks",
        "app.render.tasks",
        "app.agents.storyboard.tasks",
        "app.voice.tasks",
        "app.voice.align_tasks",
        "app.qc.tasks",
    ),
    task_default_queue="workflow",
    task_routes={
        "workflow.dispatch_outbox": {"queue": "workflow"},
        "workflow.reconcile_nodes": {"queue": "workflow"},
        "storyboard.generate": {"queue": "agent"},
        "voice.episode": {"queue": "media"},
        "align.episode": {"queue": "media"},
        "qc.episode": {"queue": "agent"},
        "render.episode": {"queue": "render"},
        "render.shot": {"queue": "render"},
        "render.concat": {"queue": "render"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_always_eager,
    task_annotations={
        "workflow.dispatch_outbox": {"soft_time_limit": 60, "time_limit": 120},
        "workflow.reconcile_nodes": {"soft_time_limit": 60, "time_limit": 120},
        "storyboard.generate": {"soft_time_limit": 300, "time_limit": 330},
        "voice.episode": {"soft_time_limit": 3600, "time_limit": 3900},
        "align.episode": {"soft_time_limit": 1800, "time_limit": 2100},
        "qc.episode": {"soft_time_limit": 1200, "time_limit": 1500},
        "render.episode": {"soft_time_limit": 3300, "time_limit": 3600},
        "render.shot": {"soft_time_limit": 600, "time_limit": 660},
        "render.concat": {"soft_time_limit": 600, "time_limit": 660},
    },
    beat_schedule={
        "dispatch-outbox": {
            "task": "workflow.dispatch_outbox",
            "schedule": settings.outbox_poll_interval_s,
        },
        "reconcile-nodes": {
            "task": "workflow.reconcile_nodes",
            "schedule": settings.reconciler_interval_s,
        },
    },
)

# Register tasks for eager mode and for processes that only import the app.
from app.qc import tasks as _qc_tasks  # noqa: E402,F401
from app.render import tasks as _render_tasks  # noqa: E402,F401
from app.agents.storyboard import tasks as _storyboard_tasks  # noqa: E402,F401
from app.voice import align_tasks as _align_tasks  # noqa: E402,F401
from app.voice import tasks as _voice_tasks  # noqa: E402,F401
from app.workflow import tasks as _tasks  # noqa: E402,F401
