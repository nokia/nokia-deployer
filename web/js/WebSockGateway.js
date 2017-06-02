//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
function WebSockGateway(url, websocket_ctor) {
    if(typeof websocket_ctor === 'undefined') {
        websocket_ctor = WebSocket;
    }

    const pending = [];
    const listeners = {};  // keys are event types (string), values are listener
    const that = this;
    this.pinger = null;


    function publish(message) {
        const event_listeners = listeners[message.type];
        if(event_listeners !== undefined) {
            for(let i = 0, len = event_listeners.length; i < len; i++) {
                event_listeners[i](message);
            }
        }
    }

    this.websocket = null;

    this.connect = function() {
        if(!this.connected()) {
            this.websocket = new websocket_ctor(url);
            this.websocket.onopen = () => {
                that.startPinging();
                while(pending.length !== 0) {
                    that.websocket.send(pending.pop());
                }
                publish({type: 'local.websocket.connected', payload: {}});
            };
            this.websocket.onmessage = event => {
                const parsed = JSON.parse(event.data);
                publish(parsed);
            };
            this.websocket.onerror = error => {
                console.log(error);
            };
            this.websocket.onclose = error => {
                setTimeout(that.connect.bind(that), 1000)
                that.stopPinging();
            }
        }
    };

    // message is an object that will be serialized to JSON
    this.send = function(message) {
        const data = JSON.stringify(message);
        if(!this.connected()) {
            if(pending.length > 500) {
                throw "Too many pending messages in the queue";
            }
            pending.push(data);
            return;
        }
        this.websocket.send(data);
    };

    this.listen = (event_type, listener) => {
        if(!listeners.hasOwnProperty(event_type)) {
            listeners[event_type] = [];
        }
        listeners[event_type].push(listener);
    };

    this.stopListening = (event_type, listener) => {
        if(!listeners.hasOwnProperty(event_type)) {
            return;
        }
        const event_listeners = listeners[event_type];
        const index = event_listeners.indexOf(listener);
        if (index > -1) {
            event_listeners.splice(index, 1);
        }
    };

    this.connected = function() {
        return (this.websocket !== null && this.websocket.readyState === websocket_ctor.OPEN);
    };

    this.startPinging = function() {
        this.stopPinging();
        const that = this;
        const ping = {'type': 'websocket.ping'};
        this.send(ping);
        this.pinger = setInterval(() => { that.send(ping); }, 15000);
    };

    this.stopPinging = function() {
        if(this.pinger) {
            clearInterval(this.pinger);
        }
        this.pinger = null;
    };
}

let prefix = "ws://";
if(location.protocol === 'https:') {
    prefix = "wss://";
}

const url = prefix + window.location.hostname + ":9000";
const webSockGateway = new WebSockGateway(url);
webSockGateway.connect();

export default webSockGateway;
