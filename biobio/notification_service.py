# biobio/notification_service.py
from django.core.mail import send_mail
from twilio.rest import Client
from django.conf import settings
from .models import NotificationLog
import os
from django.conf import settings


import resend
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


# class NotificationService:

#     @staticmethod
#     def send_email_notification(to_email, subject, message):
#         try:
#             send_mail(
#                 subject,
#                 message,
#                 settings.DEFAULT_FROM_EMAIL,
#                 [to_email],
#                 fail_silently=False,
#                 html_message=message,  # Use this parameter for HTML content
#             )
#             # NotificationService.log_notification(order, 'email', to_email, message, 'Success')
#             return True
#         except Exception as e:
#             print(f"Error sending email: {e}")
#             # NotificationService.log_notification(order, 'email', to_email, message, f'Failed: {str(e)}')
#             return False


class NotificationService:

    # @staticmethod
    # def send_email_notification(to_email, subject, message):
    #     try:
    #         send_mail(
    #             subject=subject,
    #             message="",  # Plain-text fallback
    #             from_email=settings.DEFAULT_FROM_EMAIL,
    #             recipient_list=[to_email],
    #             html_message=message,  # HTML body
    #             fail_silently=False,
    #         )
    #         return True
    #     except Exception as e:
    #         print("❌ Emailx sending failed:", e)
    #         return FalseFalse

    @staticmethod
    def send_email_notification(to_email, subject, message):
        """
        Send email notification using Resend API
        """
        try:
            # Send email using Resend API
            r = resend.Emails.send({
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": to_email,
                "subject": subject,
                "html": message,
                "text": "",  # Plain text version (optional)
            })
            
            logger.info(f"✅ Email sent successfully to {to_email}. ID: {r['id']}")
            return True
            
        except resend.resend.core.ResendError as e:
            logger.error(f"❌ Resend API error for {to_email}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending email to {to_email}: {str(e)}")
            return False

    @staticmethod
    def send_sms_notification(to_phone, message):
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to_phone,
            )
            return True
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False

    @staticmethod
    def notify_client(order, message):
        # Send both email and SMS notification
        user_profile = order.client  # Assuming order has a ForeignKey to UserProfile
        email_sent = NotificationService.send_email_notification(user_profile.email, "Order Status Update", message)
        #sms_sent = NotificationService.send_sms_notification(user_profile.phonenumber, message)

        #return email_sent, sms_sent
        return email_sent

    def log_notification(order, notification_type, recipient, message, status):
        # Create a log entry for the notification
        NotificationLog.objects.create(
            order=order,
            notification_type=notification_type,
            recipient=recipient,
            message=message,
            status=status
        )
