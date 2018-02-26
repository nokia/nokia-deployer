# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import smtplib
from logging import getLogger


try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty

MAIL_QUEUE = Queue()

logger = getLogger(__name__)


def send_mail(sender, receivers, subject, message, attachments=None):
    if attachments is None:
        attachments = []
    MAIL_QUEUE.put((sender, receivers, subject, message, attachments))


class MailWorker():

    def __init__(self, mta):
        self.mta = mta
        self.running = True

    def start(self):
        try:
            smtp = smtplib.SMTP(self.mta)
            while self.running:
                try:
                    (sender, receivers, subject, message, attachments) = MAIL_QUEUE.get(block=True, timeout=2)
                    self._send_mail(smtp, sender, receivers, subject, message, attachments)
                except Empty:
                    pass
                except smtplib.SMTPServerDisconnected:
                    # Reconnect and retry once
                    try:
                        smtp.connect(self.mta)
                        self._send_mail(smtp, sender, receivers, subject, message, attachments)
                    except Exception:
                        logger.exception("Unhandled exception in mail thread")
                except Exception:
                    logger.exception("Unhandled exception in mail thread")
            smtp.quit()
        except Exception:
            logger.exception("Could not start mail worker")

    def _send_mail(self, smtp, sender, receivers, subject, message, attachments):
        if len(attachments) == 0:
            mail = MIMEText(message)
        else:
            mail = MIMEMultipart()
            mail.attach(MIMEText(message))
        for attachment in attachments:
            with open(attachment, 'rb') as f:
                img = MIMEImage(f.read())
                mail.attach(img)
        mail['Subject'] = subject
        mail['From'] = sender
        mail['To'] = ", ".join(receivers)
        smtp.sendmail(sender, receivers, mail.as_string())
        logger.debug("Sent mail '{}' to {}".format(subject, ", ".join(receivers)))

    def stop(self):
        self.running = False

    @property
    def name(self):
        return "mail-worker"
