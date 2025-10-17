pkill -f "celery.*worker"
nohup celery -A app.celery_app worker --loglevel=info --concurrency=2 > celery_worker.log 2>&1 &
