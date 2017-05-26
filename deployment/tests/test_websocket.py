# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import json
from unittest import TestCase

from deployment.websocket import DeployerWebSocket, WebSocketEvent, WebSocketWorker, ServerStopped

try:
    import unittest.mock as mock
except ImportError as e:
    import mock


class _MockWebSocketMessage(object):

    def __init__(self, data, is_binary):
        self.data = data
        self.is_binary = is_binary


class TestDeployerWebsocket(TestCase):

    def setUp(self):
        self.ws = DeployerWebSocket(mock.MagicMock())
        self.server = mock.MagicMock()
        self.ws.register_observer(self.server)

    def test_received_message(self):
        data = {"data": "data"}
        self.ws.received_message(_MockWebSocketMessage(json.dumps(data), False))
        self.server.notify.assert_called_with(data, self.ws)

    def test_notify(self):
        event = WebSocketEvent("event.type", {'key': 'value'})
        event_2 = WebSocketEvent("event.type", {'environment_id': 1})
        with mock.patch.object(self.ws, 'send') as send_method:
            self.ws.notify(event)
            self.ws.notify(event_2)
            self.assertEquals(0, send_method.call_count)
            self.ws.forward_events_matching(1)
            self.ws.notify(event_2)
            send_method.assert_called_with(json.dumps(event_2.to_dict()))

    def test_stop_forwarding_events(self):
        event = WebSocketEvent("event.type", {'environment_id': 1})
        with mock.patch.object(self.ws, 'send') as send_method:
            self.ws.forward_events_matching(1)
            self.ws.stop_forwarding_events_matching(1)
            self.ws.notify(event)
            self.assertEquals(0, send_method.call_count)
