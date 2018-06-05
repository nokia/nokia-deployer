# Python 2 only
import logging
import base64
import time
import hashlib
import hmac

class HMAC:
    def __init__(self, username, key):
        if key is None:
            raise Exception("Missing key for HMAC")
        self.username = username
        self.username_hash = hashlib.sha1(username.encode("utf-8")).hexdigest()
        self.key = key #bytes(key, "utf-8")

    def check_hmac(self, ts_username, given_token):
        parts = ts_username.split("|")
        if len(parts) == 0:
            logging.error("Malformed username:[%s]" % ts_username)
            return False

        # Check expired
        ts = int(parts[0])
        max_ts = int(time.time())
        if ts < max_ts:
            logging.error("Given timestamp:[%d] > max:[%d]" % (ts, max_ts))
            return False

        # Check username
        username = parts[1]
        if username != self.username_hash:
            logging.error("Given username:[%s] != expected:[%s]" % (username, self.username_hash))
            return False

        # Compute HMAC
        expected_token = self.generate_hmac(ts_username)
        logging.info("given:[%s] expected:[%s]" % (given_token, expected_token))
        return given_token == expected_token

    def check_authtoken(self, given_token):
        decode_token = base64.b64decode(given_token.encode('utf-8'))
        parts = decode_token.split(':')
        if len(parts) < 2:
            logging.error("Malformed auth-token:[%s]" % given_token)
            return False

        ts_username = parts[0]
        token = parts[1]

        return self.check_hmac(ts_username, token)

    def generate_hmac(self, ts_username):
        hmac_res = hmac.new(self.key, msg=ts_username, digestmod=hashlib.sha256)
        hmac_token = base64.b64encode(hmac_res.digest()).decode('utf-8')
        return hmac_token

    def generate_authtoken(self):
        ts_username = "%d|%s" % (int(time.time() + 20), hashlib.sha1(self.username).hexdigest())
        hmac_token = self.generate_hmac(ts_username)
        auth_token = base64.b64encode("%s:%s" % (ts_username, hmac_token)).decode('utf-8')
        return auth_token

