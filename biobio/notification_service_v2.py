# biobio/notification_service_v2.py
from django.core.mail import send_mail
from twilio.rest import Client
from django.conf import settings
from .models import NotificationLog


class NotificationServiceV2:

    @staticmethod
    def send_email_notification(to_email, subject, message, order_id=None):
        try:
            send_mail(
                subject=subject,
                message="",  # Plain-text fallback
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=message,  # HTML body
                fail_silently=False,
            )
            # Log success
            try:
                NotificationLog.objects.create(
                    order=order_id or "",
                    notification_type="email",
                    recipient=to_email,
                    message=message,
                    status="Success",
                )
            except Exception:
                pass
            return True
        except Exception as e:
            print("❌ Email sending failed:", e)
            try:
                NotificationLog.objects.create(
                    order=order_id or "",
                    notification_type="email",
                    recipient=to_email,
                    message=message,
                    status=f"Failed: {str(e)}",
                )
            except Exception:
                pass
            return False

    @staticmethod
    def send_sms_notification(to_phone, message, order_id=None):
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to_phone,
            )
            try:
                NotificationLog.objects.create(
                    order=order_id or "",
                    notification_type="sms",
                    recipient=to_phone,
                    message=message,
                    status="Success",
                )
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"Error sending SMS: {e}")
            try:
                NotificationLog.objects.create(
                    order=order_id or "",
                    notification_type="sms",
                    recipient=to_phone,
                    message=message,
                    status=f"Failed: {str(e)}",
                )
            except Exception:
                pass
            return False

    @staticmethod
    def notify_client(order, message):
        # Send both email and SMS notification
        user_profile = order.client  # Assuming order has a ForeignKey to UserProfile
        email_sent = NotificationServiceV2.send_email_notification(
            user_profile.email, "Order Status Update", message
        )
        # sms_sent = NotificationServiceV2.send_sms_notification(user_profile.phonenumber, message)

        return email_sent

    @staticmethod
    def log_notification(order, notification_type, recipient, message, status):
        # Create a log entry for the notification
        NotificationLog.objects.create(
            order=order,
            notification_type=notification_type,
            recipient=recipient,
            message=message,
            status=status,
        )
