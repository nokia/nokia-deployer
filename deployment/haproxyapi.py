# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import requests

class haproxy:
    def __init__(self, url, auth):
        self.url = url
        self.auth = auth

    def enable(self, backend, server):
        return self.post(backend, server, "enable")

    def disable(self, backend, server):
        return self.post(backend, server, "disable")

    def post(self, backend, server, action):
        payload = 's=%s&action=%s&b=%s' % (server, action, backend)
        #payload = {'s':server, 'b':backend, 'action':action}
        #print self.url, self.auth, payload
        r = requests.post(self.url, auth=self.auth, data=payload, allow_redirects=False)
        #print r.headers
        #print r.text
        if r.status_code<>303:
            return "Error (%d)" % int(r.status_code)
        if 'DONE' not in r.headers['location']:
            return "Error (%s)" % r.headers['location']
        return "OK"

    def stats(self):
        r = requests.get("%s;csv" % self.url, auth=self.auth)
        if r.status_code<>200:
            return "Error (%d)" % int(r.status_code)
        lines = r.text.split("\n")[:-1]
        header = lines.pop(0).replace('# ','').strip(",").split(",")
        rows = []
        for l in lines:
            rows.append(dict(zip(header, l.split(","))))
        return rows

    def status(self, backend, server):
        stats = self.stats()
        servers = {}
        for s in stats:
            servers[s['pxname']+':'+s['svname']] = s
        return servers[backend+':'+server] if backend+':'+server in servers else "Not found"
