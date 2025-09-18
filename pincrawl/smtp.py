import smtplib
import ssl
from urllib.parse import urlparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class Smtp:
    def __init__(self, url):
        self.parsed = urlparse(url)
        self.hostname = self.parsed.hostname
        self.port = self.parsed.port or (465 if self.parsed.scheme == 'smtps' else 587)
        self.username = self.parsed.username
        self.password = self.parsed.password
        self.use_ssl = self.parsed.scheme == 'smtps'

    def send(self, from_email, to_email, subject, body, html=False):
        if html:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(body, 'html'))
        else:
            msg = MIMEText(body)

        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email

        server = None
        try:
            if self.use_ssl:
                # For SSL (port 465), create SSL context and connect directly
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.hostname, self.port, context=context)
            else:
                # For STARTTLS (port 587), connect first then upgrade
                server = smtplib.SMTP(self.hostname, self.port)
                server.starttls()

            if self.username and self.password:
                server.login(self.username, self.password)

            server.send_message(msg)

        except Exception as e:
            # If SSL fails, try fallback methods
            if server:
                try:
                    server.quit()
                except:
                    pass
                server = None

            # Try alternative approach: plain SMTP with manual STARTTLS
            try:
                server = smtplib.SMTP(self.hostname, self.port)
                server.starttls()

                if self.username and self.password:
                    server.login(self.username, self.password)

                server.send_message(msg)

            except Exception as e2:
                # If that also fails, try without SSL/TLS (not recommended for production)
                if server:
                    try:
                        server.quit()
                    except:
                        pass
                    server = None

                try:
                    server = smtplib.SMTP(self.hostname, self.port)

                    if self.username and self.password:
                        server.login(self.username, self.password)

                    server.send_message(msg)

                except Exception as e3:
                    # Re-raise the original error with more context
                    raise Exception(f"Failed to send email. Tried SSL, STARTTLS, and plain SMTP. Original error: {str(e)}")

        finally:
            if server:
                try:
                    server.quit()
                except:
                    pass
