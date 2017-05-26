# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
"""
Collection of helpers to run commands both on local and remote hosts.
"""

import datetime
import os
from logging import getLogger
import subprocess
import select
import signal

logger = getLogger(__name__)


class Host(object):
    """A Host contains the necessary information to connect to a server using SSH
    and run commands on it.

    Args:
        name (str): server hostname (or IP address)
        username (str): username to connect as
        port (int): SSH port to use
    """

    def __init__(self, name, username, port=22):
        self.name = name
        self.username = username
        self.port = port

    @classmethod
    def from_server(klass, server, username):
        """
        Args:
        server (models.Server)
        username (str)
        """
        return klass(server.name, username, server.port)


def run_cmd_by_ssh(host, cmd, timeout=600):
    """
    Args:
        host (Host)
        cmd (list of str): command to run
        timeout (int): return (with a status code 1) if the command did
                       not complete before this time

    Returns:
        tuple: see exec_cmd documentation
    """

    full_cmd = ['ssh', '{}@{}'.format(host.username, host.name), '-p', str(host.port)] + cmd
    return exec_cmd(full_cmd, timeout=timeout)


def exec_script(working_directory, script_name, params=None):
    """Run a local shell script if it exists. No error is returned if the script does not exist.

    Args:
        working_directory: use this working directory to run the script
        script_name: path to the script (absolute, or relative to the working directory)
    """
    if params is None:
        params = []
    path = os.path.join(working_directory, script_name)
    if not os.path.exists(path):
        return (0, "No script '{}'.".format(script_name), None)
    out = exec_cmd(['bash', script_name] + params, working_directory, use_shell=False)
    return out


def remote_check_file_exists(path, host):
    """Returns true if 'ssh $username@$hostname stat $path' exits with code 0"""
    stat_cmd = ['stat', path]
    exit_code, _, __ = run_cmd_by_ssh(host, stat_cmd)
    return exit_code == 0


def exec_script_remote(host, remote_working_directory, script_name, params=None):
    """Run a (remote) script on a remote host, using SSH."""
    if params is None:
        params = []
    if not remote_check_file_exists(os.path.join(remote_working_directory, script_name), host):
        return (0, "No remote script '{}'".format(script_name), None)
    cmd = ['cd', remote_working_directory, '&&', 'bash', script_name] + params
    return run_cmd_by_ssh(host, cmd)


def exec_cmd(cmd, current_working_directory=None, timeout=600, use_shell=None):
    """
    Execute a command on the local machine.

    Args:
        cmd (list): command to execute. First element is the executable name, other elements are the parameters
        current_working_directory (str): if provided, the command will be executed in a shell with the working directory set to this.
        timeout (int): timeout in seconds for the command to complete. If the timeout is reached, returns immediately and set the exit code to 1.

    Returns
        a tuple: (exit code, stdout, sterr)
    """
    try:
        if use_shell is None:
            use_shell = current_working_directory is not None
        p = subprocess.Popen(cmd, shell=use_shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=current_working_directory, bufsize=1)

        reads = [p.stdout.fileno(), p.stderr.fileno()]
        outputs = ([], [])

        # Wait for completion
        start = datetime.datetime.now()
        while p.poll() is None:
            ret = select.select(reads, [], [], 0.2)

            for fd in ret[0]:
                for i in range(0, len(reads)):
                    if fd == reads[i]:
                        data = os.read(fd, 4096)
                        outputs[i].append(data)
                        break

            # Check whether timeout is exceeded
            now = datetime.datetime.now()
            if (now - start) > datetime.timedelta(seconds=timeout):
                os.kill(p.pid, signal.SIGKILL)
                os.waitpid(p.pid, 0)
                stdout = "".join(outputs[0])
                stderr = "".join(outputs[1])
                logger.error("cmd:[%s] timeout! so far: stdout:[%s] stderr:[%s]" % (cmd, stdout, stderr))
                return (1, stdout, "Timeout (the command took more than {}s to return)\n\n{}".format(timeout, stderr))

        # Read remaining data
        performed_read = True
        while performed_read:
            performed_read = False
            ret = select.select(reads, [], [], 0)
            for fd in ret[0]:
                for i in range(0, len(reads)):
                    if fd == reads[i]:
                        data = os.read(fd, 4096)
                        if len(data) > 0:
                            performed_read = True
                            outputs[i].append(data)
                        break

        stdout = "".join(outputs[0])
        stderr = "".join(outputs[1])
        logger.debug("cmd:[%s] stdout:[%s] stderr:[%s]" % (cmd, stdout, stderr))
        return (p.returncode, stdout, stderr)
    except Exception as e:
        logger.exception("error:[%s] cmd:[%s]" % (str(e), cmd))
        return (1, "", str(e))
