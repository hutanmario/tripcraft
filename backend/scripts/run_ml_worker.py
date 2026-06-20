from rq import Queue, SimpleWorker

from app.config import settings
from app.services.ml_queue import get_redis_connection


def main() -> None:
    connection = get_redis_connection()
    queue = Queue(settings.RQ_ML_QUEUE_NAME, connection=connection)
    worker = SimpleWorker([queue], connection=connection)
    worker.work(logging_level="INFO", with_scheduler=False)


if __name__ == "__main__":
    main()
