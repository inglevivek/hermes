import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# 1️⃣ SMTP configuration
SMTP_HOST = "smtp.gmail.com"          # e.g., 'smtp.gmail.com'
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))# usually 587 for TLS
SMTP_USER = "samuraidemon513@gmail.com"        # your email
SMTP_PASS = "babwvfnsxbveiszz"         # your password or app password

# 2️⃣ Compose the email
def create_email(to_email, subject, html_content):
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))
    return msg

# 3️⃣ Send the email
def send_email(to_email, subject, html_content):
    msg = create_email(to_email, subject, html_content)
    
    try:
        # Connect to SMTP server
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()                  # Upgrade to secure TLS connection
            server.login(SMTP_USER, SMTP_PASS) # Authenticate
            server.send_message(msg)           # Send email
        print(f"Email sent to {to_email}")
    except Exception as e:
        print("Error sending email:", e)

# 4️⃣ Usage example
if __name__ == "__main__":
    send_email(
        "vivekingle315@gmail.com",
        "Test Email",
        "<h1>Hello!</h1><p>This is a test email sent from Python.</p>"
    )


#kgwo bqyw xnnk zkgd
#babw vfns xbve iszz