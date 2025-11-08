import smtplib
import ssl
import logging
from urllib.parse import urlparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class Smtp:
    def __init__(self, url):
        self.parsed = urlparse(url)
        self.hostname = self.parsed.hostname
        self.port = self.parsed.port or (465 if self.parsed.scheme == 'smtps' else 587)
        self.username = self.parsed.username
        self.password = self.parsed.password
        self.use_ssl = self.parsed.scheme == 'smtps'
        logger.debug(f"SMTP initialized: hostname={self.hostname}, port={self.port}, use_ssl={self.use_ssl}, has_auth={bool(self.username)}")

    def send(self, from_email, to_email, subject, body, html=False, bcc: str | None = None):
        logger.debug(f"Preparing to send email: from={from_email}, to={to_email}, subject={subject}, html={html}, bcc={bcc}")

        if html:
            msg = MIMEMultipart('alternative')
            # Add plain text version
            text_body = "Please view this email in an HTML-capable email client."
            msg.attach(MIMEText(text_body, 'plain'))
            # Add HTML version with charset
            msg.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            msg = MIMEText(body)

        recipients = [to_email]
        if bcc:
            recipients.append(bcc)
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email

        server = None
        try:
            if self.use_ssl:
                logger.debug(f"Attempting SSL connection to {self.hostname}:{self.port}")
                # For SSL (port 465), create SSL context and connect directly
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.hostname, self.port, context=context)
                logger.debug("SSL connection established")
            else:
                logger.debug(f"Attempting SMTP connection with STARTTLS to {self.hostname}:{self.port}")
                # For STARTTLS (port 587), connect first then upgrade
                server = smtplib.SMTP(self.hostname, self.port)
                server.starttls()
                logger.debug("STARTTLS upgrade successful")

            if self.username and self.password:
                logger.debug(f"Attempting login with username: {self.username}")
                server.login(self.username, self.password)
                logger.debug("Login successful")

            logger.debug(f"Sending message to recipients: {recipients}")
            server.send_message(msg, to_addrs=recipients)
            logger.info(f"Email sent successfully to {to_email}")

        except Exception as e:
            logger.warning(f"Primary send method failed: {str(e)}")
            # If SSL fails, try fallback methods
            if server:
                try:
                    server.quit()
                except:
                    pass
                server = None

            # Try alternative approach: plain SMTP with manual STARTTLS
            try:
                logger.debug(f"Fallback: Attempting plain SMTP with STARTTLS to {self.hostname}:{self.port}")
                server = smtplib.SMTP(self.hostname, self.port)
                server.starttls()
                logger.debug("Fallback STARTTLS successful")

                if self.username and self.password:
                    logger.debug(f"Fallback: Attempting login with username: {self.username}")
                    server.login(self.username, self.password)
                    logger.debug("Fallback login successful")

                logger.debug(f"Fallback: Sending message to recipients: {recipients}")
                server.send_message(msg, to_addrs=recipients)
                logger.info(f"Email sent successfully (fallback method) to {to_email}")

            except Exception as e2:
                logger.warning(f"Fallback STARTTLS method failed: {str(e2)}")
                # If that also fails, try without SSL/TLS (not recommended for production)
                if server:
                    try:
                        server.quit()
                    except:
                        pass
                    server = None

                try:
                    logger.debug(f"Second fallback: Attempting plain SMTP without TLS to {self.hostname}:{self.port}")
                    server = smtplib.SMTP(self.hostname, self.port)

                    if self.username and self.password:
                        logger.debug(f"Second fallback: Attempting login with username: {self.username}")
                        server.login(self.username, self.password)
                        logger.debug("Second fallback login successful")

                    logger.debug(f"Second fallback: Sending message to recipients: {recipients}")
                    server.send_message(msg, to_addrs=recipients)
                    logger.info(f"Email sent successfully (plain SMTP fallback) to {to_email}")

                except Exception as e3:
                    logger.error(f"All send methods failed. SSL error: {str(e)}, STARTTLS error: {str(e2)}, Plain error: {str(e3)}")
                    # Re-raise the original error with more context
                    raise Exception(f"Failed to send email. Tried SSL, STARTTLS, and plain SMTP. Original error: {str(e)}")

        finally:
            if server:
                try:
                    server.quit()
                    logger.debug("SMTP connection closed")
                except:
                    pass
