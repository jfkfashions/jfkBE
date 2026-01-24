from django.contrib.auth.models import AbstractUser, Group, Permission
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from datetime import datetime

User = get_user_model()

# class CustomUser(AbstractUser):
#     ROLE_CHOICES = [
#         ('admin', 'Admin'),
#         ('client', 'Client'),
#     ]
#     role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='client')
#     groups = models.ManyToManyField(
#         Group,
#         related_name='customuser_groups',  # Add this to avoid conflict
#         blank=True,
#         help_text='The groups this user belongs to.',
#         verbose_name='groups',
#     )
#     user_permissions = models.ManyToManyField(
#         Permission,
#         related_name='customuser_permissions',  # Add this to avoid conflict
#         blank=True,
#         help_text='Specific permissions for this user.',
#         verbose_name='user permissions',
#     )

# class CustomUser(AbstractUser):
#     pass
#
#     def __str__(self):
#         return self.username


class Biodata(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    role = models.CharField(max_length=100)
    gender = models.CharField(max_length=10)

    def __str__(self):
        return self.name


# Create your models here.


class UserProfile(models.Model):
    username = models.CharField(max_length=100, unique=True)
    # username = models.OneToOneField(User, on_delete=models.CASCADE)
    password = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    phonenumber = models.CharField(max_length=100)
    email = models.CharField(max_length=100, unique=True)
    gender = models.CharField(max_length=100, blank=True, null=True)
    birthdate = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CustomizationOption(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("in_progress", "In Progress"),
        ("fitting", "fitting"),
    ]

    order_id = models.CharField(max_length=20, unique=True, blank=True)
    # client = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    client = models.CharField(max_length=100)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default="Pending")
    order_date = models.DateTimeField(auto_now_add=True)
    customization_options = models.ManyToManyField(CustomizationOption, blank=True)
    measurements = models.TextField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_date = models.DateTimeField(blank=True, null=True)
    completed_date = models.DateTimeField(blank=True, null=True)
    expected_date = models.DateField(blank=True, null=True)
    event_type = models.CharField(max_length=100, blank=True, null=True)
    material = models.BooleanField(default=False)
    preferred_Color = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.order_id:
            # Generate order_id with format JFKDDMMYYYY0001
            today = datetime.now()
            date_prefix = today.strftime("JFK%d%m%Y")

            # Get the last order with the same date prefix
            last_order = (
                Order.objects.filter(order_id__startswith=date_prefix)
                .order_by("order_id")
                .last()
            )

            if last_order and last_order.order_id:
                # Extract the sequence number and increment
                last_sequence = int(last_order.order_id[-4:])
                new_sequence = last_sequence + 1
            else:
                # First order of the day
                new_sequence = 1

            # Format with leading zeros (4 digits)
            self.order_id = f"{date_prefix}{new_sequence:04d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_id} - {self.client}"


class Measurement(models.Model):
    username = models.CharField(max_length=100, unique=True, blank=True, null=True)
    neck = models.CharField(max_length=100, blank=True, null=True)
    chest = models.CharField(max_length=100, blank=True, null=True)
    waist = models.CharField(max_length=100, blank=True, null=True)
    hip = models.CharField(max_length=100, blank=True, null=True)
    shoulder = models.CharField(max_length=100, blank=True, null=True)
    sleeve = models.CharField(max_length=100, blank=True, null=True)
    armhole = models.CharField(max_length=100, blank=True, null=True)
    bicep = models.CharField(max_length=100, blank=True, null=True)
    wrist = models.CharField(max_length=100, blank=True, null=True)
    inseam = models.CharField(max_length=100, blank=True, null=True)
    outseam = models.CharField(max_length=100, blank=True, null=True)
    thigh = models.CharField(max_length=100, blank=True, null=True)
    rise = models.CharField(max_length=100, blank=True, null=True)
    bodylength = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.username


class NotificationLog(models.Model):
    ORDER_NOTIFICATION_TYPE = [
        ("email", "Email"),
        ("sms", "SMS"),
    ]

    # order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='notifications')
    order = models.CharField(max_length=100)
    notification_type = models.CharField(max_length=10, choices=ORDER_NOTIFICATION_TYPE)
    message = models.TextField()
    recipient = models.CharField(max_length=255)  # Email address or phone number
    status = models.CharField(max_length=50)  # Success, Failed, etc.
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return (
            f"{self.notification_type.capitalize()} to {self.recipient} ({self.status})"
        )


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"Reset token for {self.user.username}"
