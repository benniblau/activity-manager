"""Quick SMTP test script"""

import os
import sys
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables
load_dotenv()

# SMTP settings from .env
SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
FROM_EMAIL = os.environ.get('FROM_EMAIL') or os.environ.get('SMTP_USERNAME')

print("Testing SMTP configuration...")
print(f"Server: {SMTP_SERVER}:{SMTP_PORT}")
print(f"Username: {SMTP_USERNAME}")
print(f"From Email: {FROM_EMAIL}")
print()

# Get test recipient from command line or use default
if len(sys.argv) > 1:
    test_email = sys.argv[1]
else:
    test_email = SMTP_USERNAME  # Send to self as test

print(f"Sending test email to: {test_email}")
print()

try:
    # Create test message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Activity Manager - SMTP Test'
    msg['From'] = FROM_EMAIL
    msg['To'] = test_email

    html_body = """
    <html>
      <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #fc4c02;">SMTP Test Successful!</h2>
        <p>Your ProtonMail SMTP configuration is working correctly.</p>
        <p><strong>Configuration:</strong></p>
        <ul>
          <li>Server: """ + SMTP_SERVER + """</li>
          <li>Port: """ + str(SMTP_PORT) + """</li>
          <li>From: """ + FROM_EMAIL + """</li>
        </ul>
        <p>Coach invitation emails will now be sent successfully.</p>
      </body>
    </html>
    """

    text_body = f"""
SMTP Test Successful!

Your ProtonMail SMTP configuration is working correctly.

Configuration:
- Server: {SMTP_SERVER}
- Port: {SMTP_PORT}
- From: {FROM_EMAIL}

Coach invitation emails will now be sent successfully.
    """

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    # Send email
    print(f"Connecting to {SMTP_SERVER}...")
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        print("Starting TLS...")
        server.starttls()

        print("Logging in...")
        server.login(SMTP_USERNAME, SMTP_PASSWORD)

        print(f"Sending test email to {test_email}...")
        server.send_message(msg)

    print()
    print("✓ Test email sent successfully!")
    print(f"Check {test_email} for the test message.")

except Exception as e:
    print()
    print("✗ SMTP test failed:")
    print(f"Error: {str(e)}")
    exit(1)
