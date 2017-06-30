from datetime import timedelta, datetime
from logging import getLogger
import os
from shutil import rmtree
from threading import Condition

from deployment.database import session_scope
from deployment.gitutils import lock_repository_write, lock_repository_fetch
import deployment.samodels as m


logger = getLogger(__name__)


class CleanerWorker():

    def __init__(self, base_repos_path, wakeup_period=timedelta(days=1), max_unused_age=timedelta(days=20)):
        self.wakeup_period = wakeup_period
        self.max_unused_age = max_unused_age
        self.running = True
        self.condition = Condition()
        self.base_repos_path = base_repos_path

    def start(self):
        while self.running:
            try:
                self._cleanup()
            except Exception:
                logger.exception("Unexpected error when trying to clean up on-disk directories")
            self.condition.acquire()
            self.condition.wait(self.wakeup_period.total_seconds())

    def _cleanup(self):
        logger.info("Cleaner worker wakeup.")
        now = datetime.utcnow()
        with session_scope() as session:
            envs = session.query(m.Environment).\
                filter(m.Environment.id == m.DeploymentView.environment_id).\
                filter(m.DeploymentView.queued_date < now - self.max_unused_age).\
                all()
            for env in envs:
                path = os.path.join(self.base_repos_path, env.local_repo_directory_name)
                if os.path.exists(path):
                    with lock_repository_fetch(path), lock_repository_write(path):
                        rmtree(path)
                    logger.info(
                        "Deleted unused directory {}".format(env.local_repo_directory_name)
                    )
        logger.info("Cleaner worker going to sleep. Next wakeup in: {}".format(self.wakeup_period))

    def stop(self):
        self.running = False
        self.condition.acquire()
        self.condition.notifyAll()
        self.condition.release()

    @property
    def name(self):
        return "cleaner-worker"
