# library/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.patron_dashboard, name="patron_dashboard"),
    path("resources/", views.resource_list, name="resource_list"),
    path("resources/<int:pk>/", views.resource_detail, name="resource_detail"),
    path("resources/<int:pk>/checkout/", views.checkout_resource, name="checkout_resource"),
    path("resources/<int:pk>/reserve/", views.reserve_resource, name="reserve_resource"),
    path("checkouts/<int:checkout_id>/return/", views.return_resource, name="return_resource"),

    path("staff/dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("staff/checkouts/<int:checkout_id>/return/", views.staff_process_return, name="staff_process_return"),
    path("staff/reports/popular/", views.generate_popular_resources_report, name="popular_resources_report"),

    path("admin/staff/", views.admin_staff_list, name="admin_staff_list"),
    path("admin/staff/<int:user_id>/promote/", views.admin_promote_to_staff, name="admin_promote_to_staff"),
    path("admin/staff/<int:user_id>/deactivate/", views.admin_deactivate_staff, name="admin_deactivate_staff"),
]
