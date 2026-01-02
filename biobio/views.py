from django.shortcuts import render, get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny
from rest_framework import generics, permissions
from django.contrib.auth.models import User
from rest_framework import serializers
from .serializers import CustomTokenObtainPairSerializer
from rest_framework.permissions import IsAdminUser
from .models import Biodata, Measurement
from .models import UserProfile, Order
from .serializers import BiodataSerializer
from .serializers import UserProfileSerializer, OrderSerializer, MeasurementSerializer
from rest_framework.decorators import api_view
from .notification_service import NotificationService
from django.contrib.auth.hashers import check_password
import pdb
import threading

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
            return Response({'error': str(e)}, status.HTTP_400_BAD_REQUEST)


class BiodataCreateView(generics.CreateAPIView):
    queryset = Biodata.objects.all()
    serializer_class = BiodataSerializer
    permission_classes = [permissions.IsAuthenticated]  # Ensure only authenticated users can submit

    def perform_create(self, serializer):
        # Attach the currently logged-in user to the biodata entry
        serializer.save(user=self.request.user)


class CreateUserView(generics.CreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.AllowAny]

    # def perform_create(self, serializer):
    def create(self, request, *args, **kwargs):
        # username = serializer.validated_data['username']
        username = request.data.get('username')

        # Check if user with the same username already exists
        if UserProfile.objects.filter(username=username).exists():
            return Response({'error': 'User already exists'}, status=status.HTTP_400_BAD_REQUEST)

        # Save the user profile if no existing user is found
        try:
            serializer = UserProfileSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=self.request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserVerficationView(APIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        # serializer = UserProfileSerializer(data=request.data)
        try:

            username = request.data['username']
            password = request.data['password']
        except KeyError:
            return Response({'error': 'Missing username or password'}, status=status.HTTP_400_BAD_REQUEST)

        if not username or not password:
            return Response({'error': 'Please provide both username and password'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_profile = UserProfile.objects.get(username=username)
            passcheck = check_password(password, user_profile.password)
            print(passcheck)
            if passcheck:
                return Response({"role": user_profile.role}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Username and password do not match"}, status=status.HTTP_400_BAD_REQUEST)
        except UserProfile.DoesNotExist:
            return Response({"error": "Username and password do not match"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # Log the exception here (optional)
            print(f"Internal server error: {e}")
            return Response({"error": "Internal server error. Please try again later."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserProfileDetailView(APIView):
    # permission_classes = [IsAuthenticated]
    permission_classes = [permissions.AllowAny]

    def get(self, request, username, *args, **kwargs):
        try:
            user_profile = UserProfile.objects.get(username=username)
            serializer = UserProfileSerializer(user_profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, username, *args, **kwargs):
        try:
            user_profile = UserProfile.objects.get(username=username)
            serializer = UserProfileSerializer(user_profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, username, *args, **kwargs):
        try:
            user_profile = UserProfile.objects.get(username=username)
            user_profile.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)


class OrderCreateView(generics.CreateAPIView):
    #pdb.set_trace()
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        #pdb.set_trace()
        username = self.request.data.get('username')

        try:
            user_profile = UserProfile.objects.get(username=username)
            serializer.save(client=user_profile.username)
        except UserProfile.DoesNotExist:
            raise serializers.ValidationError({"error": "User with the provided username does not exist."})

        except Exception as e:

            print(f"Error creating order: {e}")
            # Return a generic error response
            return Response({"error": "An error occurred while placing the order."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OrderConfirmView(APIView):
    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            order.is_confirmed = True
            order.save()
            return Response({"message": "Order confirmed successfully."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)


class OrderUpdateView(APIView):
    def put(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            if order.is_confirmed:
                return Response({"error": "Cannot modify a confirmed order."}, status=status.HTTP_400_BAD_REQUEST)

            # Update order fields based on request data
            order.measurements = request.data.get('measurements', order.measurements)
            order.expected_date = request.data.get('expected_date', order.expected_date)
            order.event_type = request.data.get('event_type', order.event_type)
            order.material = request.data.get('material', order.material)
            order.comments = request.data.get('comments', order.comments)
            order.preferred_Color = request.data.get('preferred_Color', order.preferred_Color)
            order.save()

            return Response({"message": "Order updated successfully."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

class OrderUpdateStatusView(APIView):
    def put(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            if not order.is_confirmed:
                return Response({"error": "Cannot modify order unless it is confirmed."}, status=status.HTTP_400_BAD_REQUEST)
            order.status = request.data.get('status', order.status)
            order.save()

            return Response({"message": "Order updated successfully."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        username = self.request.query_params.get('username')
        try:
            user = UserProfile.objects.get(username=username)
            Orderlist = Order.objects.filter(client=username)
            return Orderlist
        except User.DoesNotExist:
            raise serializers.ValidationError({"error": "User with the provided username does not exist."})
        except Exception as e:
            print(f"Error fetching orders: {e}")
            return Order.objects.none()


class OrderDetailsView(generics.GenericAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        order_id = kwargs.get('order_id')
        # order_id = self.request.query_params.get('order_id')
        try:
            order = Order.objects.get(id=order_id)
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)


class OrderDeleteView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):

        try:
            order_id = kwargs.get('order_id')
            order = Order.objects.get(id=order_id)
            if order.is_confirmed:
                return Response({"error": "Cannot delete a confirmed order."}, status=status.HTTP_400_BAD_REQUEST)
            order.delete()
            return Response({"message": "Order deleted successfully."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)


class MeasurementCreateView(generics.CreateAPIView):
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.AllowAny]

    # @api_view(['POST'])
    def perform_create(self, serializer):
        try:
            user_profile = UserProfile.objects.get(username=self.request.data.get('username'))
            serializer.save(username=user_profile.username)
            return Response({"message": "Measurement created successfully."}, status=status.HTTP_200_OK)

        except UserProfile.DoesNotExist:
            return Response({"error": "User with the provided username does not exist."}, )
        except:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)


class MeasurementUpdateView(generics.UpdateAPIView):
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        username = self.request.data.get('username')
        # Ensure we get the correct measurement object by username
        return get_object_or_404(Measurement, username=username)

    def update(self, request, *args, **kwargs):
        # Fetch the object to be updated
        measurement = self.get_object()

        # Partially update the object (this allows only the provided fields to be updated)
        serializer = self.get_serializer(measurement, data=request.data, partial=True)

        # Check if the provided data is valid
        if serializer.is_valid():
            # Save the updates
            self.perform_update(serializer)
            return Response({
                "message": "Measurement updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        else:
            # Return validation errors if the data is not valid
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeasurementDetailView(generics.RetrieveAPIView):
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            username = request.query_params.get('username')
            measurement = Measurement.objects.get(username=username)
            serializer = self.get_serializer(measurement)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Measurement.DoesNotExist:
            return Response({"error": "Measurements not found for this user"}, status=status.HTTP_404_NOT_FOUND)


class SendEmailView2(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserProfileSerializer

    def post(self, request, *args, **kwargs):
        try:
            username = self.request.data.get('username')
            user_profile = UserProfile.objects.get(username=username)
            email = user_profile.email
            message = request.data.get('message')
            subject = request.data.get('subject')
            email_sent = NotificationService.send_email_notification(email, subject, message)
            if email_sent:
                return Response({"success": "Email sent successfully."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Failed to send email."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except UserProfile.DoesNotExist:
            return Response({"error": "User with the provided username does not exist."}, )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def send_email_background(email, subject, message):
    """
    Runs outside the request lifecycle.
    Any failure here will NOT affect the HTTP response.
    """
    try:
        NotificationService.send_email_notification(
            email,
            subject,
            message,
        )
        print("✅ Email sent to:", email)
    except Exception as e:
        print("❌ Email sending failed:", e)


class SendEmailView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserProfileSerializer

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        subject = request.data.get("subject")
        message = request.data.get("message")

        user_profile = get_object_or_404(UserProfile, username=username)

        # 🔥 Run email sending in background
        threading.Thread(
            target=send_email_background,
            args=(user_profile.email, subject, message),
            daemon=True,  # Ensures it won't block shutdown
        ).start()

        # ✅ Immediate response → no timeout ever
        return Response(
            {"success": "Email queued successfully."},
            status=status.HTTP_200_OK,
        )


class AdminDashboardView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        total_clients = UserProfile.objects.count()
        total_orders = Order.objects.count()
        pending_orders = Order.objects.filter(status="Pending", is_confirmed="True").count()
        in_progress_orders = Order.objects.filter(status="in_progress", is_confirmed="True").count()
        completed_orders = Order.objects.filter(status="Completed", is_confirmed="True").count()
        unconfirmed_orders = Order.objects.filter(is_confirmed="False").count()
        #total_notifications = NotificationLog.objects.count()

        data = {
            "total_clients": total_clients,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "in_progress_orders": in_progress_orders,
            "completed_orders": completed_orders,
            "unconfirmed_orders": unconfirmed_orders
            #"total_notifications": total_notifications,
        }
        return Response(data)


class AdminOrderListView(generics.ListAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):

        try:
            type = request.query_params.get('type')

            if type == 'confirmed':
                orderlist = Order.objects.filter(is_confirmed='True')
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == 'unconfirmed':
                orderlist = Order.objects.filter(is_confirmed='False')
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == 'pending':
                orderlist = Order.objects.filter(status="Pending", is_confirmed='True')
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == 'in_progress':
                orderlist = Order.objects.filter(status="in_progress", is_confirmed='True')
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == 'completed':
                orderlist = Order.objects.filter(status="Completed", is_confirmed='True')
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            if type == 'all':
                orderlist = Order.objects.all()
                serializer = OrderSerializer(orderlist, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Type not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                return Response({"message": "Order updated successfully."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order not found for this user."}, )


class AdminCreateOrderView(generics.CreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]

    def create(self, request, *args, **kwargs):
        client_id = self.request.data.get('client_id')  # Expect client ID in request body
        try:
            client = UserProfile.objects.get(username=client_id)
        except UserProfile.DoesNotExist:
            return Response({"error": "Client does not exist"}, status=status.HTTP_404_NOT_FOUND)

        # Now, create the order on behalf of the client
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(client=client)  # Attach the client to the order
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
