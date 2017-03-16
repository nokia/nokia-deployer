# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import collections
import json
import logging
import threading
from multiprocessing.dummy import Pool as ThreadPool
import time

import cherrypy
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool

from ws4py.websocket import WebSocket


class ServerStopped(Exception):
	pass


class WebSocketEvent(object):

	def __init__(self, event_type, payload):
		self.event_type = event_type
		self.payload = payload

	def to_dict(self):
		return {
			'type': self.event_type,
			'payload': self.payload
		}

	@classmethod
	def from_dict(klass, data):
		return klass(data['type'], data['payload'])


class EnvMatcher(object):

	def __init__(self, environment_id):
		self.environment_id = environment_id

	def match(self, event):
		try:
			return self.environment_id == event.payload['environment_id']
		except KeyError:
			return False


class DeployerWebSocket(WebSocket):

	def __init__(self, *args, **kwargs):
		super(DeployerWebSocket, self).__init__(*args, **kwargs)
		self.sock.settimeout(3.5)
		self.envs = None
		self.repos = None
		self.matchers = []
		self.lock = threading.Lock()
		cherrypy.engine.publish('x-add-websocket', self)

	def register_observer(self, observer):
		# Observer must provide a notify(data, ws) method
		self.observer = observer

	def forward_events_matching(self, environment_id):
		"""Send events (via notify) whose payload includes {"environment_id": environment_id}"""
		with self.lock:
			if len([m for m in self.matchers if m.environment_id == environment_id]) == 0:
				self.matchers.append(EnvMatcher(environment_id))

	def stop_forwarding_events_matching(self, environment_id):
		with self.lock:
			for matcher in self.matchers:
				if matcher.environment_id == environment_id:
					self.matchers.remove(matcher)

	def received_message(self, message):
		# Can be called from any thread
		# so do as little work as possible here in order not to create concurrency issues
		try:
			# In a later version, maybe messagepack could be supported.
			# For now, do everything in JSON: easier to debug.
			if message.is_binary:
				logging.debug("Ignoring binary message.")
				return

			data = json.loads(message.data)
			self.observer.notify(data, self)
		except Exception as e:
			logging.error("Error when processing a message received from a websocket")
			logging.info("Message was: {}".format(message))
			logging.exception(e)

	def notify(self, event):
		"""Events not matched (see forward_events_matching) will be ignored"""
		with self.lock:
			if event.event_type == "websocket.pong":
				self.send(json.dumps(event.to_dict()))
				return
			for matcher in self.matchers:
				if matcher.match(event):
					self.send(json.dumps(event.to_dict()))
					return


class Listener(object):

	def __init__(self, callable, args, kwargs):
		self.callable = callable
		self.args = args
		self.kwargs = kwargs

	def wrap_callable_in_exception_logger(self):
		def func(*args, **kwargs):
			try:
				return self.callable(*args, **kwargs)
			except Exception as e:
				logging.error("Unhandled exception in an event listener callback")
				logging.exception(e)
				raise
		return func


class DeployerWebSocketPlugin(WebSocketPlugin):

		def __init__(self, bus, observer):
			WebSocketPlugin.__init__(self, bus)
			self.observer = observer

		def start(self):
			WebSocketPlugin.start(self)
			self.bus.subscribe('x-add-websocket', self.add_websocket)

		def add_websocket(self, websocket):
			websocket.register_observer(self.observer)


class WebSocketWorker(object):

	def __init__(self, port=9000):
		self._listeners = collections.defaultdict(lambda: [])
		self._running = False
		self.thread_pool = ThreadPool(10)
		self.port = port

	def start(self):
		self._running = True
		cherrypy.config.update({
			'server.socket_port': self.port,
			'server.socket_host': '0.0.0.0',
			'engine.autoreload_on': False,
		})
		self.plugin = DeployerWebSocketPlugin(cherrypy.engine, self)
		self.plugin.subscribe()
		cherrypy.tools.websocket = WebSocketTool()

		class Root(object):
			@cherrypy.expose
			def index(self):
				pass

		cherrypy.tree.mount(Root(), '/', config={'/': {
			'tools.websocket.on': True,
			'tools.websocket.handler_cls': DeployerWebSocket
		}})
		cherrypy.engine.start()
		while self._running:
			time.sleep(2)

	def stop(self):
		self._running = False
		self.thread_pool.close()
		cherrypy.engine.stop()
		for ws in self.plugin.manager:
			ws.close()
			ws.close_connection()

	@property
	def name(self):
		return "websocket-worker"

	def publish(self, event):
		if not self._running:
			raise ServerStopped()
		for ws in self.plugin.manager:
			ws.notify(event)

	def listen(self, event_type, listener, *args, **kwargs):
		""" Register a listener that will be called when an event from the given type is received.

		The listener is called in a separate thread.

		Args:
			event_type (str): event to listen to
			listener: a callable accepting at least three arguments (an event, the websocket from which
				the event came from, and this server).
			args, kwargs: will be passed to listener
		"""
		self._listeners[event_type].append(Listener(listener, args, kwargs))

	# For internal use
	# Called by WebSocket handlers when an event is received form a websocket
	def notify(self, data, ws):
		if 'type' not in data:
			logging.warning('Missing "type" key in a received event, ignoring it: {data}'.format(data=data))
			return
		event_type = data['type']
		for listener in self._listeners[event_type]:
			self.thread_pool.apply_async(func=listener.wrap_callable_in_exception_logger(), args=((data, ws, self) + listener.args), kwds=listener.kwargs)
