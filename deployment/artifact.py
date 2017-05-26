# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import os


class ArtifactError(Exception):
    pass


class NoArtifactDetected(Exception):
    pass


class Artifact(object):

    def __init__(self):
        self.local_path = None

    def obtain(self):
        """Perform any necessary actions (e.g. download) and set the local_path attribute,
        which points to a folder to copy to the target server."""
        return  # no-op by default

    def cleanup(self):
        """Perform cleanup operations after a deployment (such as deleting temporary files)."""
        return  # no-op by default

    def should_run_predeploy_scripts(self):
        """Whether the predeploy.sh and run_local_tests.sh scripts should be run."""
        return True

    def description(self):
        """Must return a string describing the artifact type (for logging purposes)"""
        raise NotImplementedError()


class GitArtifact(Artifact):
    """The default artifact implementation."""

    def __init__(self, local_path):
        self.local_path = local_path
        if not self.local_path.endswith('/'):
            self.local_path += '/'

    def should_run_predeploy_scripts(self):
        return True

    def obtain(self):
        return self.local_path

    def description(self):
        return "Git (run the predeploy scripts, then deploy the repository contents)"
