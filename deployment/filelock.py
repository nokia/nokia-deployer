# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import fcntl
import errno


class AlreadyLocked(Exception):
	pass


class FileLock:

	def __init__(self, filename, blocking=True):
		self.filename = filename
		self.handle = open(filename, 'w')
		self._locked = False
		self.blocking = blocking

	def _acquire(self, exclusive=True, blocking=True):
		flag = fcntl.LOCK_SH
		if exclusive:
			flag = fcntl.LOCK_EX
		if not blocking:
			flag |= fcntl.LOCK_NB
		try:
			fcntl.flock(self.handle, flag)
		except IOError as e:
			if e.errno == errno.EAGAIN:
				raise AlreadyLocked()
		self._locked = True
		return self

	def _release(self):
		if self._locked:
			fcntl.flock(self.handle, fcntl.LOCK_UN)
			self._locked = False
		return self

	def __del__(self):
		self._release()
		self.handle.close()

	def __enter__(self):
		return self._acquire(blocking=self.blocking)

	def __exit__(self, type, value, traceback):
		self._release()
