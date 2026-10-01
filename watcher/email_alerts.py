"""Email alerts over SMTP (stdlib only). Works with Gmail via an app password."""

import smtplib
import ssl
from email.message import EmailMessage


class Email:
    def __init__(self, host, port, username, password, to):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.to = to

    def message(self, text):
        subject, _, body = text.partition("\n")
        msg = EmailMessage()
        msg["Subject"] = subject.strip()
        msg["From"] = self.username
        msg["To"] = self.to
        msg.set_content(body.strip() or subject.strip())
        return msg

    def deliver(self, text):
        """Send, raising on failure (used by setup so you see the real error)."""
        context = ssl.create_default_context()
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=30) as smtp:
                smtp.login(self.username, self.password)
                smtp.send_message(self.message(text))
        else:
            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                smtp.starttls(context=context)
                smtp.login(self.username, self.password)
                smtp.send_message(self.message(text))

    def send(self, text):
        """Send; never raises, so a mail hiccup can't stop the watcher."""
        try:
            self.deliver(text)
            return True
        except (smtplib.SMTPException, OSError) as e:
            print(f"  ! Email send failed: {e}")
            return False
