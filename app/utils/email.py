"""Email utility for sending notifications"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import logging
import sys

logger = logging.getLogger(__name__)
# Also log to console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)


def send_email(to_email, subject, html_body, text_body=None):
    """Send an email using SMTP configuration

    Args:
        to_email: Recipient email address
        subject: Email subject
        html_body: HTML content of email
        text_body: Plain text fallback (optional, will use html_body if not provided)

    Returns:
        True if email sent successfully, False otherwise
    """
    # Check if SMTP is configured
    smtp_server = current_app.config.get('SMTP_SERVER')
    logger.debug(f'SMTP_SERVER config: {smtp_server}')

    if not smtp_server:
        logger.warning('SMTP not configured, skipping email send')
        return False

    try:
        smtp_port = current_app.config['SMTP_PORT']
        smtp_username = current_app.config['SMTP_USERNAME']
        from_email = current_app.config['FROM_EMAIL']

        logger.debug(f'Attempting to send email to {to_email}')
        logger.debug(f'SMTP config: {smtp_server}:{smtp_port}, from={from_email}, user={smtp_username}')

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email

        # Attach plain text and HTML versions
        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        # Send email
        logger.debug(f'Connecting to SMTP server...')
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            logger.debug(f'Starting TLS...')
            server.starttls()
            logger.debug(f'Logging in...')
            server.login(smtp_username, current_app.config['SMTP_PASSWORD'])
            logger.debug(f'Sending message...')
            server.send_message(msg)

        logger.info(f'Email sent successfully to {to_email}')
        return True

    except Exception as e:
        logger.error(f'Failed to send email to {to_email}: {str(e)}', exc_info=True)
        return False


def send_coach_invitation_email(coach_email, coach_name, athlete_name, app_url, is_registered=True):
    """Send invitation email to coach

    Args:
        coach_email: Coach's email address
        coach_name: Coach's name
        athlete_name: Athlete's name who sent the invitation
        app_url: Base URL of the application
        is_registered: Whether the coach is already registered

    Returns:
        True if email sent successfully, False otherwise
    """
    subject = f'{athlete_name} has invited you to be their coach'

    if is_registered:
        # Email for registered coaches
        action_text = "To accept or reject this invitation, please log in to your account:"
        button_text = "View Invitation"
        button_url = f"{app_url}/admin/profile"
    else:
        # Email for unregistered coaches
        action_text = "To get started, you'll need to create a coach account first:"
        button_text = "Create Coach Account"
        button_url = f"{app_url}/auth/user/register"

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
          <h2 style="color: #fc4c02;">New Coach Invitation</h2>

          <p>Hi {coach_name},</p>

          <p><strong>{athlete_name}</strong> has invited you to be their coach on the Activity Manager platform.</p>

          <p>As a coach, you will be able to:</p>
          <ul>
            <li>View {athlete_name}'s activities and training data</li>
            <li>Monitor their progress and performance metrics</li>
            <li>Access detailed reports and analytics</li>
            <li>Add coach comments and feedback</li>
          </ul>

          <p>{action_text}</p>

          <div style="margin: 30px 0;">
            <a href="{button_url}"
               style="background-color: #fc4c02; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
              {button_text}
            </a>
          </div>

          {'<p style="color: #666; font-size: 14px;">After creating your account, go to your <strong>Profile</strong> to view and accept pending invitations.</p>' if not is_registered else ''}

          <p style="color: #666; font-size: 14px;">
            If you did not expect this invitation, you can safely ignore this email{' or reject the invitation in your profile' if is_registered else ''}.
          </p>

          <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

          <p style="color: #999; font-size: 12px;">
            This is an automated message from Activity Manager. Please do not reply to this email.
          </p>
        </div>
      </body>
    </html>
    """

    if is_registered:
        text_body = f"""
New Coach Invitation

Hi {coach_name},

{athlete_name} has invited you to be their coach on the Activity Manager platform.

As a coach, you will be able to:
- View {athlete_name}'s activities and training data
- Monitor their progress and performance metrics
- Access detailed reports and analytics
- Add coach comments and feedback

To accept or reject this invitation, please log in to your account and visit:
{app_url}/admin/profile

If you did not expect this invitation, you can safely ignore this email or reject the invitation in your profile.

---
This is an automated message from Activity Manager. Please do not reply to this email.
        """
    else:
        text_body = f"""
New Coach Invitation

Hi {coach_name},

{athlete_name} has invited you to be their coach on the Activity Manager platform.

As a coach, you will be able to:
- View {athlete_name}'s activities and training data
- Monitor their progress and performance metrics
- Access detailed reports and analytics
- Add coach comments and feedback

To get started, you'll need to create a coach account first:
{app_url}/auth/user/register

After creating your account, go to your Profile to view and accept pending invitations.

If you did not expect this invitation, you can safely ignore this email.

---
This is an automated message from Activity Manager. Please do not reply to this email.
        """

    return send_email(coach_email, subject, html_body, text_body)
