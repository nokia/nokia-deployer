from logging import getLogger
from datetime import timedelta, datetime
from threading import Condition
from itertools import repeat
import json

from .instancehealth import InstanceHealth
from . import database, samodels as m
from . import execution, executils

logger = getLogger(__name__)


class CheckReleasesWorker(object):
    """Check releases from every servers and update health info."""

    def __init__(self, frequency, health):
        logger.info("CheckReleases worker init. It will run every %d seconds" % frequency)
        self._running = True
        self._frequency = frequency
        self._health = health
        self.wakeup_period = timedelta(seconds=self._frequency)
        self.condition = Condition()

    def start(self):
        logger.info("CheckReleases worker wakeup.")
        self._health.set_ok("releases")
        while self._running:
            try:
                with database.session_scope() as session:
                    repositories = session.query(m.Repository).all()
                    for repo in repositories:
                        for env in repo.environments:
                            releases = set()
                            for srv in env.servers:
                                release = execution.get_release_status(executils.Host.from_server(srv, env.remote_user), env.target_path)
                                diff_minutes = (datetime.now() - release._release.deployment_date).seconds * 60
                                branch, commit = release._release.branch, release._release.commit
                                if diff_minutes < 30:
                                    logger.info("ignore diff, commit was deployed less than [%d] minutes" % diff_minutes)
                                else:
                                    logger.info("repository:[%s] env:[%s] release:[%s:%s/%s] diff_minutes:[%d]" % (repo.name, env.name, str(srv.id), branch, commit, diff_minutes))
                                    releases.add(branch+":"+commit)
                            logger.info("repository:[%s] env:[%s] releases_count:[%d]" % (repo.name, env.name, len(releases)))
                            if len(releases) > 1:
                                self._health.add_degraded("releases", "at least one server is out of sync for repo:[%s] env:[%s]" % (repo.name, env.name))
                            break
                        break
            except Exception:
                logger.exception("Unexpected error when trying to retrieve releases")
            self.condition.acquire()
            self.condition.wait(self.wakeup_period.total_seconds())

    def stop(self):
        logger.info("CheckReleases worker stop.")
        if self._running:
            self.condition.acquire()
            self.condition.notifyAll()
            self.condition.release()
            self._running = False

    @property
    def name(self):
        return "checkreleases-worker"
