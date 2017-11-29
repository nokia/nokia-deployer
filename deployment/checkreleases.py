from logging import getLogger
from datetime import timedelta, datetime
from threading import Condition
import time

from . import database, samodels as m
from . import execution, executils

logger = getLogger(__name__)


class CheckReleasesWorker(object):
    """Check releases from every servers and update health info."""

    def __init__(self, frequency, ignore_envs, health):
        logger.info("CheckReleases worker init. It will run every {} seconds, ignoring environments: {}".format(frequency, ignore_envs))
        self._running = True
        self._health = health
        self._ignore_envs = ignore_envs
        self._min_minutes = 30
        self.wakeup_period = timedelta(seconds=frequency)
        self.condition = Condition()

    def start(self):
        get_release_status_timeout = 10
        while self._running:
            logger.info("CheckReleases worker wakeup")
            self._health.set_ok("releases")
            try:
                with database.session_scope() as session:
                    repositories = session.query(m.Repository).all()
                    for repo in repositories:
                        try:
                            for env in repo.environments:
                                if env.name in self._ignore_envs:
                                    logger.debug("Ignore environment {}".format(env.name))
                                    continue
                                releases = set()
                                for srv in env.servers:
                                    if srv.activated == 0:
                                        logger.warning("Server:[{}] deactivated, do not check releases".format(srv.name))
                                        continue
                                    release_status = execution.get_release_status(executils.Host.from_server(srv, env.remote_user), env.target_path, get_release_status_timeout)
                                    error_code = release_status.get_error_code()
                                    if release_status.get_error():
                                        if error_code == 255:
                                            logger.warning("Server:[{}] error executing ssh command (error_code:{}), ignore releases check".format(srv.name, error_code))
                                            continue
                                        # retry after 30 seconds
                                        time.sleep(30)
                                        release_status = execution.get_release_status(executils.Host.from_server(srv, env.remote_user), env.target_path, get_release_status_timeout)
                                        if release_status.get_error():
                                            error = "No release found on server:[{}] repo:[{}] env:[{}]".format(srv.name, repo.name, env.name)
                                            logger.error(error)
                                            self._health.add_degraded("releases", error)
                                            continue
                                    age = datetime.utcnow() - release_status.get_release().deployment_date
                                    if age < timedelta(minutes=self._min_minutes):
                                        logger.debug("Ignore diff, commit was deployed less than {} minutes:[{}]".format(self._min_minutes, age))
                                    else:
                                        logger.debug("Add release:[{}:{}] repository:[{}] env:[{}] diff:[{}] ssh_error_code:[{}]".format(str(srv.id), release_status.get_release().commit, repo.name, env.name, age, error_code))
                                        releases.add(release_status.get_release().commit)
                                logger.info("Repository:[{}] env:[{}] releases_count:[{}]".format(repo.name, env.name, len(releases)))
                                if len(releases) > 1:
                                    self._health.add_degraded("releases", "at least one server is out of sync for repo:[{}] env:[{}]".format(repo.name, env.name))
                        except Exception:
                            logger.exception("Unexpected error when trying to retrieve releases for repo:[{}]".format(repo.name))
            except Exception:
                logger.exception("Unexpected error when trying to retrieve releases")
            logger.info("CheckReleases worker done")
            self.condition.acquire()
            self.condition.wait(self.wakeup_period.total_seconds())

    def stop(self):
        logger.info("CheckReleases worker stop")
        if self._running:
            self.condition.acquire()
            self.condition.notifyAll()
            self.condition.release()
            self._running = False

    @property
    def name(self):
        return "checkreleases-worker"
