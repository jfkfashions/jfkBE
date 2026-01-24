from django.http import JsonResponse
from django.urls import path
from django.conf.urls import handler500
from .views import (
    CustomTokenObtainPairView,
    UserProfileListView,
    BiodataCreateView,
    CreateUserView,
    UserVerficationView,
    UserProfileDetailView,
    ForgotPasswordRequestView,
    ResetPasswordConfirmView,
)
from .views import (
    OrderCreateView,
    OrderListView,
    MeasurementCreateView,
    MeasurementUpdateView,
    MeasurementDetailView,
    SendEmailView,
    AdminCreateOrderView,
)
from .views import (
    AdminDashboardView,
    AdminOrderListView,
    OrderConfirmView,
    OrderUpdateView,
    OrderDetailsView,
    OrderDeleteView,
    OrderUpdateStatusView,
)

urlpatterns = [
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("userprofile/", UserProfileListView.as_view(), name="biodata-list"),
    path(
        "biodata/", BiodataCreateView.as_view(), name="biodata-create"
    ),  # Biodata submission route for clients
    path("signup/", CreateUserView.as_view(), name="signup"),
    path("verify/", UserVerficationView.as_view(), name="verify"),
    path(
        "forgot-password/", ForgotPasswordRequestView.as_view(), name="forgot-password"
    ),
    path("reset-password/", ResetPasswordConfirmView.as_view(), name="reset-password"),
    path(
        "profile/<str:username>/",
        UserProfileDetailView.as_view(),
        name="user-profile-detail",
    ),  # Profile detail endpoint
    path("orders/", OrderListView.as_view(), name="order-list"),
    path("orders/new/", OrderCreateView.as_view(), name="order-create"),
    path(
        "orders/<str:username>/", OrderListView.as_view(), name="order-list-username"
    ),  # Use URL parameter
    path(
        "orders/view/<int:order_id>/", OrderDetailsView.as_view(), name="order-details"
    ),
    path(
        "orders/confirm/<int:order_id>/",
        OrderConfirmView.as_view(),
        name="confirm-order",
    ),
    path(
        "orders/update/<int:order_id>/", OrderUpdateView.as_view(), name="update-order"
    ),
    path(
        "orders/updatestatus/<int:order_id>/",
        OrderUpdateStatusView.as_view(),
        name="update-status",
    ),
    path(
        "orders/delete/<int:order_id>/", OrderDeleteView.as_view(), name="delete-order"
    ),
    path(
        "measurements/new/", MeasurementCreateView.as_view(), name="measurement-create"
    ),
    path(
        "measurements/update/",
        MeasurementUpdateView.as_view(),
        name="measurement-update",
    ),
    path(
        "measurements/view/", MeasurementDetailView.as_view(), name="measurement-detail"
    ),
    path("notifications/email", SendEmailView.as_view(), name="notifications"),
    path("admin/dashboard", AdminDashboardView.as_view(), name="admin-dashboard"),
    path(
        "admin/orders/create/",
        AdminCreateOrderView.as_view(),
        name="admin-create-order",
    ),
    path("admin/orders", AdminOrderListView.as_view(), name="admin-orders"),
]
