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
from .notification_service_v2 import NotificationServiceV2
from django.contrib.auth.hashers import check_password
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
        # username = serializer.validated_data['username']
        username = request.data.get("username")

        # Check if user with the same username already exists
        if UserProfile.objects.filter(username=username).exists():
            return Response(
                {"error": "User already exists"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Save the user profile if no existing user is found
        try:
            serializer = UserProfileSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=self.request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
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
            order.save()
            # Notify client via SMS about confirmation (if phone available)
            try:
                user_profile = UserProfile.objects.get(username=order.client)
                message = f"Your order {order.id} has been confirmed."
                NotificationServiceV2.send_sms_notification(
                    user_profile.phonenumber, message, order_id=order.id
                )
            except Exception:
                # do not block confirmation if notification fails
                pass
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


# (rest of file continues unchanged)
