# composio_client.py (HTML email sender with Gmail, using App Password)

# email_client.py
"""
Production-ready SMTP email client for sending HTML market research reports.
Uses Gmail SMTP with app password authentication.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
import time

# ============================================================================
# SMTP Configuration
# ============================================================================
import os
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")  # Gmail app password


# ============================================================================
# Email Functions
# ============================================================================

def create_email(to_email: str, subject: str, html_content: str) -> MIMEMultipart:
    """
    Create an email message with HTML content.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_content: Full HTML content of the report
        
    Returns:
        MIMEMultipart message object
    """
    msg = MIMEMultipart('alternative')
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    
    # Attach HTML content
    html_part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(html_part)
    
    return msg


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Send an HTML email via Gmail SMTP.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_content: Full HTML report content
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        msg = create_email(to_email, subject, html_content)
        
        # Connect to SMTP server and send
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        
        print(f"✅ Email sent successfully to {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("Please verify your Gmail app password at: https://myaccount.google.com/apppasswords")
        return False
        
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error occurred: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def send_bulk_emails(recipients: List[str], subject: str, html_content: str, 
                    delay: float = 2.0) -> dict:
    """
    Send the same HTML report to multiple recipients.
    
    Args:
        recipients: List of recipient email addresses
        subject: Email subject line
        html_content: Full HTML report content
        delay: Delay in seconds between each email (to avoid rate limits)
        
    Returns:
        Dictionary with success/failure counts and failed addresses
    """
    results = {
        'total': len(recipients),
        'success': 0,
        'failed': 0,
        'failed_addresses': []
    }
    
    for idx, recipient in enumerate(recipients, 1):
        print(f"📤 Sending to {recipient} ({idx}/{len(recipients)})...")
        
        if send_email(recipient, subject, html_content):
            results['success'] += 1
        else:
            results['failed'] += 1
            results['failed_addresses'].append(recipient)
        
        # Delay between emails to avoid Gmail rate limits
        if idx < len(recipients):
            time.sleep(delay)
    
    return results


def send_report_email(recipient_email: str, query: str, html_body: str) -> bool:
    """
    Main function to send market research report.
    Convenience wrapper with formatted subject line.
    
    Args:
        recipient_email: Recipient email address
        query: The original research query (used in subject)
        html_body: Complete HTML report content
        
    Returns:
        True if sent successfully, False otherwise
    """
    # Format professional subject line
    subject = f"Market Research Report: {query[:60]}"
    if len(query) > 60:
        subject += "..."
    
    return send_email(recipient_email, subject, html_body)


def send_report_bulk(recipients: List[str], query: str, html_body: str) -> dict:
    """
    Send market research report to multiple recipients.
    
    Args:
        recipients: List of recipient email addresses
        query: The original research query
        html_body: Complete HTML report content
        
    Returns:
        Dictionary with results summary
    """
    subject = f"Market Research Report: {query[:60]}"
    if len(query) > 60:
        subject += "..."
    
    return send_bulk_emails(recipients, subject, html_body)


# ============================================================================
# Validation
# ============================================================================

def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def parse_recipients(recipient_input: str) -> List[str]:
    """
    Parse recipient email input.
    Supports comma-separated, semicolon-separated, or newline-separated emails.
    
    Args:
        recipient_input: String containing one or more email addresses
        
    Returns:
        List of validated email addresses
    """
    # Split by common separators
    emails = recipient_input.replace(';', ',').replace('\n', ',').split(',')
    
    # Clean and validate
    valid_emails = []
    for email in emails:
        email = email.strip()
        if email and validate_email(email):
            valid_emails.append(email)
    
    return valid_emails


# ============================================================================
# Test Function (for development only)
# ============================================================================



if __name__ == "__main__":
    main()