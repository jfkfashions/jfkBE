from django.shortcuts import render, get_object_or_404
from django.http import Http404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny
from django.conf import settings
import uuid
import re
from datetime import timedelta
from django.utils import timezone
from rest_framework import generics, permissions
from django.contrib.auth.models import User
from rest_framework import serializers
from .serializers import CustomTokenObtainPairSerializer
from rest_framework.permissions import IsAdminUser
from .models import Biodata, Measurement
from .models import UserProfile, Order
from .models import PasswordResetToken
from .serializers import BiodataSerializer
from .serializers import UserProfileSerializer, OrderSerializer, MeasurementSerializer
from rest_framework.decorators import api_view
from .notification_service import NotificationService
from django.contrib.auth.hashers import check_password, make_password
import pdb

from rest_framework.permissions import IsAuthenticated


class CustomTokenObtainPairView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer


class UserProfileListView(generics.ListAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            allusers = UserProfile.objects.all()
            serializer = UserProfileSerializer(allusers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status.HTTP_400_BAD_REQUEST)


class BiodataCreateView(generics.CreateAPIView):
    queryset = Biodata.objects.all()
    serializer_class = BiodataSerializer
    permission_classes = [
        permissions.IsAuthenticated
    ]  # Ensure only authenticated users can submit

    def perform_create(self, serializer):
        # Attach the currently logged-in user to the biodata entry
        serializer.save(user=self.request.user)


class CreateUserView(generics.CreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.AllowAny]

    # def perform_create(self, serializer):
    def create(self, request, *args, **kwargs):
        username = request.data.get("username")
        email = request.data.get("email")

        # Reject duplicate username or email before hitting the serializer
        if UserProfile.objects.filter(username=username).exists():
            return Response(
                {"error": "User already exists"}, status=status.HTTP_400_BAD_REQUEST
            )

        if UserProfile.objects.filter(email=email).exists():
            return Response(
                {"error": "Email already in use"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            serializer = UserProfileSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=self.request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserVerficationView(APIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        # serializer = UserProfileSerializer(data=request.data)
        try:

            username = request.data["username"]
            password = request.data["password"]
        except KeyError:
            return Response(
                {"error": "Missing username or password"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not username or not password:
            return Response(
                {"error": "Please provide both username and password"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user_profile = UserProfile.objects.get(username=username)
            passcheck = check_password(password, user_profile.password)
            print(passcheck)
            if passcheck:
                return Response({"role": user_profile.role}, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Username and password do not match"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Username and password do not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            # Log the exception here (optional)
            print(f"Internal server error: {e}")
            return Response(
                {"error": "Internal server error. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ForgotPasswordRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Use filter to handle multiple records gracefully
            user_profiles = UserProfile.objects.filter(email=email)

            if not user_profiles.exists():
                return Response(
                    {"error": "Email not found"}, status=status.HTTP_404_NOT_FOUND
                )

            # If multiple exist, use the first one (will be prevented by unique constraint after migration)
            user_profile = user_profiles.first()

            print(f"📧 Found user profile for {email}: {user_profile.username}")
        except Exception as e:
            print(f"❌ Error finding user profile: {str(e)}")
            return Response(
                {"error": "Error processing your request"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Create reset token valid for 1 hour
        token = str(uuid.uuid4())
        expires_at = timezone.now() + timedelta(hours=1)
        PasswordResetToken.objects.create(
            user=user_profile, token=token, expires_at=expires_at
        )

        reset_base = (
            getattr(settings, "FRONTEND_RESET_URL", None)
            or "http://localhost:3000/reset-password"
        )
        reset_link = f"{reset_base}?token={token}"

        email_body = f"""
        <div style='font-family: Arial, sans-serif; line-height:1.6;'>
            <h2>Password Reset Requested</h2>
            <p>Hello {user_profile.firstname},</p>
            <p>We received a request to reset the password for your account. Click the button below to reset your password. This link will expire in 1 hour.</p>
            <p style='text-align:center; margin:24px 0;'>
                <a href='{reset_link}' style='background:#8B4513; color:#ffffff; padding:12px 20px; text-decoration:none; border-radius:6px;'>Reset Password</a>
            </p>
            <p>If you did not request this, you can safely ignore this email. If you continue to receive these emails, please contact an administrator.</p>
            <p>Thank you,<br/>JFK Team</p>
        </div>
        """

        try:
            email_sent = NotificationService.send_email_notification(
                to_email=user_profile.email,
                subject="Reset your JFK password",
                message=email_body,
            )

            if not email_sent:
                print(
                    f"❌ Email notification service returned False for {user_profile.email}"
                )
                return Response(
                    {"error": "Unable to send reset email at this time"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            print(f"✅ Password reset email sent successfully to {user_profile.email}")
            return Response(
                {"message": "Password reset link has been sent to your email"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            print(f"❌ Exception in forgot password request: {str(e)}")
            import traceback

            traceback.print_exc()
            return Response(
                {"error": f"Error sending reset email: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ResetPasswordConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not token:
            return Response(
                {"error": "Reset token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not new_password or not confirm_password:
            return Response(
                {"error": "Both password fields are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"error": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not re.search(r"[A-Z]", new_password):
            return Response(
                {"error": "Password must contain at least one uppercase letter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not re.search(r"[0-9]", new_password):
            return Response(
                {"error": "Password must contain at least one number"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not re.search(r"[^A-Za-z0-9]", new_password):
            return Response(
                {"error": "Password must contain at least one special character"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reset_token = (
            PasswordResetToken.objects.filter(
                token=token, used=False, expires_at__gte=timezone.now()
            )
            .select_related("user")
            .first()
        )

        if not reset_token:
            return Response(
                {"error": "Invalid or expired reset token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reset_token.user.password = make_password(new_password)
            reset_token.user.save()
            reset_token.used = True
            reset_token.save()
            PasswordResetToken.objects.filter(user=reset_token.user, used=False).update(
                used=True
            )
            return Response(
                {"message": "Password has been reset successfully"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserProfileDetailView(APIView):
    # permission_classes = [IsAuthenticated]
    permission_classes = [permissions.AllowAny]

    def get(self, request, username, *args, **kwargs):
        try:
            user_profile = UserProfile.objects.get(username=username)
            serializer = UserProfileSerializer(user_profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "User profile not found."}, status=status.HTTP_404_NOT_FOUND
            )

    def put(self, request, username, *args, **kwargs):
        try:
            user_profile = UserProfile.objects.get(username=username)
            serializer = UserProfileSerializer(
                user_profile, data=request.data, partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "User profile not found."}, status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, username, *args, **kwargs):
        try:
            user_profile = UserProfile.objects.get(username=username)
            user_profile.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "User profile not found."}, status=status.HTTP_404_NOT_FOUND
            )


class OrderCreateView(generics.CreateAPIView):
    # pdb.set_trace()
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        # pdb.set_trace()
        username = self.request.data.get("username")

        try:
            user_profile = UserProfile.objects.get(username=username)
            serializer.save(client=user_profile.username)
        except UserProfile.DoesNotExist:
            raise serializers.ValidationError(
                {"error": "User with the provided username does not exist."}
            )

        except Exception as e:

            print(f"Error creating order: {e}")
            # Return a generic error response
            return Response(
                {"error": "An error occurred while placing the order."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrderConfirmView(APIView):
    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            order.is_confirmed = True
            order.confirmed_date = timezone.now()
            order.save()

            # Send email notification to client
            try:
                user_profile = UserProfile.objects.get(username=order.client)
                email_body = f"""
                <div style='font-family: Arial, sans-serif; line-height:1.6;'>
                    <h2 style='color: #8B4513;'>Order Confirmation</h2>
                    <p>Hello {user_profile.firstname} {user_profile.lastname},</p>
                    <p>We are pleased to inform you that your order has been successfully confirmed by our team.</p>
                    <div style='background: #f5f5f5; padding: 15px; border-radius: 6px; margin: 20px 0;'>
                        <p style='margin: 5px 0;'><strong>Order ID:</strong> {order.order_id}</p>
                        <p style='margin: 5px 0;'><strong>Client Name:</strong> {user_profile.firstname} {user_profile.lastname}</p>
                        <p style='margin: 5px 0;'><strong>Status:</strong> Confirmed</p>
                        <p style='margin: 5px 0;'><strong>Event Type:</strong> {order.event_type or 'N/A'}</p>
                    </div>
                    <p>Our skilled tailors have begun working on your custom garment. We will keep you informed at every stage of the production process. You can also log in to your dashboard at any time to track the progress of your order.</p>
                    <p>We appreciate your trust in our craftsmanship and look forward to delivering a garment that exceeds your expectations.</p>
                    <p style='margin-top: 30px;'>Thank you for your patronage.</p>
                    <p>Warm regards,<br/>The JFK Tailoring Team</p>
                </div>
                """
                NotificationService.send_email_notification(
                    to_email=user_profile.email,
                    subject=f"Order Confirmed - {order.order_id}",
                    message=email_body,
                )
            except UserProfile.DoesNotExist:
                print(f"User profile not found for client: {order.client}")
            except Exception as e:
                print(f"Error sending confirmation email: {e}")

            return Response(
                {"message": "Order confirmed successfully."}, status=status.HTTP_200_OK
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )


class OrderUpdateView(APIView):
    def put(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            if order.is_confirmed:
                return Response(
                    {"error": "Cannot modify a confirmed order."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update order fields based on request data
            order.measurements = request.data.get("measurements", order.measurements)
            order.expected_date = request.data.get("expected_date", order.expected_date)
            order.event_type = request.data.get("event_type", order.event_type)
            order.material = request.data.get("material", order.material)
            order.comments = request.data.get("comments", order.comments)
            order.preferred_Color = request.data.get(
                "preferred_Color", order.preferred_Color
            )
            order.save()

            return Response(
                {"message": "Order updated successfully."}, status=status.HTTP_200_OK
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )


class OrderUpdateStatusView(APIView):
    def put(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            if not order.is_confirmed:
                return Response(
                    {"error": "Cannot modify order unless it is confirmed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            new_status = request.data.get("status", order.status)
            order.status = new_status

            # Set completed_date when status changes to Completed
            if new_status == "Completed" and not order.completed_date:
                order.completed_date = timezone.now()

            order.save()

            # Send email notification based on status
            try:
                user_profile = UserProfile.objects.get(username=order.client)

                email_templates = {
                    "in_progress": {
                        "subject": f"🚀 Production Update - Order {order.order_id} In Progress",
                        "title": "Your Order Is Now In Production",
                        "intro": "Great news! Your custom garment has entered the production phase.",
                        "body": "Our expert tailors are currently working on your order. This stage involves careful cutting, stitching, and assembly of your garment according to your specifications and measurements. We take pride in our attention to detail and craftsmanship.",
                        "action": "You can monitor the progress of your order by logging into your dashboard at any time. We will notify you when your order moves to the next stage.",
                    },
                    "fitting": {
                        "subject": f"👔 Ready for Fitting - Order {order.order_id}",
                        "title": "Your Garment Is Ready for Fitting",
                        "intro": "Excellent news! Your custom garment has been completed and is ready for a fitting session.",
                        "body": "We invite you to visit our office at your earliest convenience for a fitting appointment. During this session, we will ensure the garment fits perfectly and make any necessary adjustments to guarantee your complete satisfaction.",
                        "action": "Please contact us to schedule a convenient time for your fitting. Our team is available to accommodate your schedule. Remember, minor adjustments are part of our commitment to delivering the perfect fit.",
                    },
                    "Completed": {
                        "subject": f"✅ Order Complete - {order.order_id} Ready for Collection",
                        "title": "Your Order Is Complete!",
                        "intro": "Congratulations! Your custom garment is now complete and ready for collection.",
                        "body": "We are delighted to inform you that your order has been finished to our highest standards. All adjustments have been completed, and your garment is perfectly tailored to your measurements and preferences.",
                        "action": "You may collect your order at our office during business hours. Please bring your order confirmation for a smooth collection process. We look forward to seeing you and hope you enjoy wearing your new garment.",
                    },
                }

                if new_status in email_templates:
                    template = email_templates[new_status]
                    email_body = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <style>
                            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
                            .email-container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
                            .email-header {{ background: linear-gradient(135deg, #8B4513 0%, #A0522D 100%); padding: 30px 20px; text-align: center; color: white; }}
                            .logo {{ font-size: 28px; font-weight: bold; margin-bottom: 10px; }}
                            .order-details {{ padding: 30px; background: rgba(139, 69, 19, 0.05); border-radius: 8px; margin: 20px 0; }}
                            .detail-item {{ display: flex; margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid rgba(139, 69, 19, 0.1); }}
                            .detail-label {{ font-weight: 600; color: #8B4513; min-width: 180px; }}
                            .detail-value {{ font-weight: 500; color: #222; }}
                            .content {{ padding: 30px; }}
                            .footer {{ background: linear-gradient(135deg, #8B4513 0%, #A0522D 100%); padding: 25px; color: white; text-align: center; }}
                            h2 {{ color: #8B4513; margin-bottom: 15px; }}
                            p {{ margin: 15px 0; }}
                        </style>
                    </head>
                    <body>
                        <div class="email-container">
                            <div class="email-header">
                                <div class="logo">JFK TAILOR SHOP</div>
                                <div>Order Status Update</div>
                            </div>
                            <div class="content">
                                <h2>{template['title']}</h2>
                                <p>Hello {user_profile.firstname} {user_profile.lastname},</p>
                                <p>{template['intro']}</p>
                                
                                <div class="order-details">
                                    <div class="detail-item">
                                        <span class="detail-label">Order ID:</span>
                                        <span class="detail-value">{order.order_id}</span>
                                    </div>
                                    <div class="detail-item">
                                        <span class="detail-label">Client Name:</span>
                                        <span class="detail-value">{user_profile.firstname} {user_profile.lastname}</span>
                                    </div>
                                    <div class="detail-item">
                                        <span class="detail-label">Current Status:</span>
                                        <span class="detail-value">{template['title'].replace('Your Order Is Now ', '').replace('Your Garment Is ', '').replace('Your Order Is ', '')}</span>
                                    </div>
                                    <div class="detail-item">
                                        <span class="detail-label">Event Type:</span>
                                        <span class="detail-value">{order.event_type or 'N/A'}</span>
                                    </div>
                                </div>
                                
                                <p>{template['body']}</p>
                                <p><strong>{template['action']}</strong></p>
                                
                                <p style="margin-top: 30px; text-align: center; font-size: 16px;">
                                    Thank you for choosing <strong style="color: #8B4513;">JFK Tailor Shop</strong>!
                                </p>
                            </div>
                            <div class="footer">
                                <p>JFK Tailor Shop | Where Excellence Meets Elegance</p>
                                <p>Need help? Contact us at support@jfktailorshop.com</p>
                                <p style="margin-top: 15px; font-style: italic;">Best regards,<br/>The JFK Tailor Shop Team</p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    NotificationService.send_email_notification(
                        to_email=user_profile.email,
                        subject=template["subject"],
                        message=email_body,
                    )
            except UserProfile.DoesNotExist:
                print(f"User profile not found for client: {order.client}")
            except Exception as e:
                print(f"Error sending status update email: {e}")

            return Response(
                {"message": "Order updated successfully."}, status=status.HTTP_200_OK
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        username = self.request.query_params.get("username")
        try:
            user = UserProfile.objects.get(username=username)
            Orderlist = Order.objects.filter(client=username)
            return Orderlist
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"error": "User with the provided username does not exist."}
            )
        except Exception as e:
            print(f"Error fetching orders: {e}")
            return Order.objects.none()


class OrderDetailsView(generics.GenericAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        order_id = kwargs.get("order_id")
        # order_id = self.request.query_params.get('order_id')
        try:
            order = Order.objects.get(id=order_id)
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )


class OrderDeleteView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):

        try:
            order_id = kwargs.get("order_id")
            order = Order.objects.get(id=order_id)
            if order.is_confirmed:
                return Response(
                    {"error": "Cannot delete a confirmed order."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            order.delete()
            return Response(
                {"message": "Order deleted successfully."}, status=status.HTTP_200_OK
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )


class MeasurementCreateView(generics.CreateAPIView):
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        try:
            username = request.data.get("username")

            # Check if user exists
            user_profile = UserProfile.objects.get(username=username)

            # Check if measurement already exists for this user
            existing_measurement = Measurement.objects.filter(username=username).first()

            if existing_measurement:
                # Update existing measurement
                serializer = self.get_serializer(
                    existing_measurement, data=request.data, partial=True
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(
                    {
                        "message": "Measurement updated successfully.",
                        "data": serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                # Create new measurement
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                serializer.save(username=username)
                return Response(
                    {
                        "message": "Measurement created successfully.",
                        "data": serializer.data,
                    },
                    status=status.HTTP_201_CREATED,
                )

        except UserProfile.DoesNotExist:
            return Response(
                {"error": "User with the provided username does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MeasurementUpdateView(generics.UpdateAPIView):
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        username = self.request.data.get("username")
        # Get the first measurement object by username (in case of duplicates)
        # Order by id descending to get the most recent one
        measurement = (
            Measurement.objects.filter(username=username).order_by("-id").first()
        )
        if not measurement:
            raise Http404("Measurement not found for this user")
        return measurement

    def update(self, request, *args, **kwargs):
        # Fetch the object to be updated
        measurement = self.get_object()

        # Partially update the object (this allows only the provided fields to be updated)
        serializer = self.get_serializer(measurement, data=request.data, partial=True)

        # Check if the provided data is valid
        if serializer.is_valid():
            # Save the updates
            self.perform_update(serializer)
            return Response(
                {
                    "message": "Measurement updated successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        else:
            # Return validation errors if the data is not valid
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeasurementDetailView(generics.RetrieveAPIView):
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            username = request.query_params.get("username")
            # Get the first measurement (most recent if there are duplicates)
            # Order by id descending to get the latest record
            measurement = (
                Measurement.objects.filter(username=username).order_by("-id").first()
            )

            if not measurement:
                return Response(
                    {"error": "Measurements not found for this user"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = self.get_serializer(measurement)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SendEmailView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserProfileSerializer

    def post(self, request, *args, **kwargs):
        try:
            username = self.request.data.get("username")
            user_profile = UserProfile.objects.get(username=username)
            email = user_profile.email
            message = request.data.get("message")
            subject = request.data.get("subject")
            email_sent = NotificationService.send_email_notification(
                email, subject, message
            )
            if email_sent:
                return Response(
                    {"success": "Email sent successfully."}, status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"error": "Failed to send email."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "User with the provided username does not exist."},
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminDashboardView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        total_clients = UserProfile.objects.count()
        total_orders = Order.objects.count()
        pending_orders = Order.objects.filter(
            status="Pending", is_confirmed="True"
        ).count()
        in_progress_orders = Order.objects.filter(
            status="in_progress", is_confirmed="True"
        ).count()
        fitting_orders = Order.objects.filter(
            status="fitting", is_confirmed="True"
        ).count()
        completed_orders = Order.objects.filter(
            status="Completed", is_confirmed="True"
        ).count()
        unconfirmed_orders = Order.objects.filter(is_confirmed="False").count()
        # total_notifications = NotificationLog.objects.count()

        data = {
            "total_clients": total_clients,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "in_progress_orders": in_progress_orders,
            "fitting_orders": fitting_orders,
            "completed_orders": completed_orders,
            "unconfirmed_orders": unconfirmed_orders,
            # "total_notifications": total_notifications,
        }
        return Response(data)


class AdminOrderListView(generics.ListAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):

        try:
            type = request.query_params.get("type")

            if type == "confirmed":
                orderlist = Order.objects.filter(is_confirmed="True")
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == "unconfirmed":
                orderlist = Order.objects.filter(is_confirmed="False")
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == "pending":
                orderlist = Order.objects.filter(status="Pending", is_confirmed="True")
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == "in_progress":
                orderlist = Order.objects.filter(
                    status="in_progress", is_confirmed="True"
                )
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == "fitting":
                orderlist = Order.objects.filter(status="fitting", is_confirmed="True")
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == "completed":
                orderlist = Order.objects.filter(
                    status="Completed", is_confirmed="True"
                )
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == "all":
                orderlist = Order.objects.all()
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Type not found."}, status=status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminOrderUpdateView(generics.UpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def update(self, request, *args, **kwargs):

        try:
            order = self.get_object()
            serializer = self.get_serializer(order, data=request.data, partial=True)
            if serializer.is_valid():
                self.perform_update(serializer)
                return Response(
                    {"message": "Order updated successfully."},
                    status=status.HTTP_200_OK,
                )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found for this user."},
            )


class AdminCreateOrderView(generics.CreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]

    def create(self, request, *args, **kwargs):
        client_id = self.request.data.get(
            "client_id"
        )  # Expect client ID in request body
        try:
            client = UserProfile.objects.get(username=client_id)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Client does not exist"}, status=status.HTTP_404_NOT_FOUND
            )

        # Now, create the order on behalf of the client
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(client=client)  # Attach the client to the order
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
