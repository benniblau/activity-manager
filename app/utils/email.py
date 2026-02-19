"""Email utility for sending notifications"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import logging

logger = logging.getLogger(__name__)


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
    if not current_app.config.get('SMTP_SERVER'):
        logger.warning('SMTP not configured, skipping email send')
        return False

    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config['FROM_EMAIL']
        msg['To'] = to_email

        # Attach plain text and HTML versions
        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        # Send email
        with smtplib.SMTP(current_app.config['SMTP_SERVER'], current_app.config['SMTP_PORT']) as server:
            server.starttls()
            server.login(current_app.config['SMTP_USERNAME'], current_app.config['SMTP_PASSWORD'])
            server.send_message(msg)

        logger.info(f'Email sent successfully to {to_email}')
        return True

    except Exception as e:
        logger.error(f'Failed to send email to {to_email}: {str(e)}')
        return False


def send_coach_invitation_email(coach_email, coach_name, athlete_name, app_url):
    """Send invitation email to coach

    Args:
        coach_email: Coach's email address
        coach_name: Coach's name
        athlete_name: Athlete's name who sent the invitation
        app_url: Base URL of the application

    Returns:
        True if email sent successfully, False otherwise
    """
    subject = f'{athlete_name} has invited you to be their coach'

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
          </ul>

          <p>To accept or reject this invitation, please log in to your account:</p>

          <div style="margin: 30px 0;">
            <a href="{app_url}/admin/profile"
               style="background-color: #fc4c02; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
              View Invitation
            </a>
          </div>

          <p style="color: #666; font-size: 14px;">
            If you did not expect this invitation, you can safely ignore this email or reject the invitation in your profile.
          </p>

          <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

          <p style="color: #999; font-size: 12px;">
            This is an automated message from Activity Manager. Please do not reply to this email.
          </p>
        </div>
      </body>
    </html>
    """

    text_body = f"""
New Coach Invitation

Hi {coach_name},

{athlete_name} has invited you to be their coach on the Activity Manager platform.

As a coach, you will be able to:
- View {athlete_name}'s activities and training data
- Monitor their progress and performance metrics
- Access detailed reports and analytics

To accept or reject this invitation, please log in to your account and visit:
{app_url}/admin/profile

If you did not expect this invitation, you can safely ignore this email or reject the invitation in your profile.

---
This is an automated message from Activity Manager. Please do not reply to this email.
    """

    return send_email(coach_email, subject, html_body, text_body)
