"""
Celery worker — backward compatibility shim.
Imports from the new tasks/ module so existing Procfile and commands still work.

Usage:
  celery -A celery_worker.celery_app worker --loglevel=info --pool=solo
"""
from tasks.celery_tasks import celery_app, process_call  # noqa: F401
