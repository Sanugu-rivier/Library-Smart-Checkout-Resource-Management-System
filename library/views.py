from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Count

from .models import Resource, Checkout, Return, Reservation, Notification, User, Report


# ---------- Helpers for role checks ----------

def staff_required(view_func):
    """
    Wraps a view so that only authenticated users with role STAFF can access.
    """
    # First apply user_passes_test to the view, then wrap that with login_required.
    decorated_view = login_required(
        user_passes_test(lambda u: u.is_authenticated and u.is_staff_user())(view_func)
    )
    return decorated_view


def admin_required(view_func):
    """
    Wraps a view so that only authenticated users with role ADMIN can access.
    """
    decorated_view = login_required(
        user_passes_test(lambda u: u.is_authenticated and u.is_admin_user())(view_func)
    )
    return decorated_view


# ---------- Business logic helpers ----------

MAX_ACTIVE_RESERVATIONS_PER_PATRON = 10  # NF requirement


def calculate_due_date():

    return timezone.now() + timedelta(days=14)


def calculate_overdue_fine(checkout: Checkout) -> float:
    """
    Simple fine rule: $1 per day overdue.
    """
    if not checkout.is_overdue():
        return 0.0
    days_overdue = (timezone.now() - checkout.due_date).days
    return max(0, days_overdue) * 1.0


def create_notification(user: User, ntype: str, message: str):
    Notification.objects.create(user=user, notification_type=ntype, message=message)


# ---------- Patron views ----------

@login_required
def patron_dashboard(request):
    """
    Patron view: shows current checkouts, reservations, and notifications.
    """
    patron = request.user
    if not patron.is_patron():
        return redirect("staff_dashboard")

    active_checkouts = Checkout.objects.filter(patron=patron, status=Checkout.STATUS_ACTIVE)
    reservations = Reservation.objects.filter(patron=patron).exclude(
        status=Reservation.STATUS_CANCELLED
    )
    notifications = Notification.objects.filter(user=patron).order_by("-created_at")[:10]

    context = {
        "active_checkouts": active_checkouts,
        "reservations": reservations,
        "notifications": notifications,
    }
    return render(request, "library/dashboard.html", context)


@login_required
def resource_list(request):
    """
    Search and browse resources.
    Implements FR6–FR8.
    """
    query = request.GET.get("q", "")
    resources = Resource.objects.all()
    if query:
        resources = resources.filter(title__icontains=query)
    context = {"resources": resources, "query": query}
    return render(request, "library/resource_list.html", context)


@login_required
def resource_detail(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    current_checkout = Checkout.objects.filter(resource=resource, status=Checkout.STATUS_ACTIVE).first()
    context = {"resource": resource, "current_checkout": current_checkout}
    return render(request, "library/resource_detail.html", context)


@login_required
def checkout_resource(request, pk):
    """
    Patron checks out a resource (FR9–FR12).
    """
    patron = request.user
    if not patron.is_patron():
        messages.error(request, "Only patrons can checkout resources.")
        return redirect("resource_detail", pk=pk)

    resource = get_object_or_404(Resource, pk=pk)
    if resource.status != Resource.STATUS_AVAILABLE:
        messages.error(request, "Resource is not available for checkout.")
        return redirect("resource_detail", pk=pk)

    due_date = calculate_due_date()
    checkout = Checkout.objects.create(
        patron=patron,
        resource=resource,
        due_date=due_date,
    )
    resource.status = Resource.STATUS_CHECKED_OUT
    resource.save()

    create_notification(
        patron,
        Notification.TYPE_NEW_RESOURCE,
        f"You have checked out '{resource.title}'. Due on {due_date:%Y-%m-%d}."
    )

    messages.success(request, f"Checked out '{resource.title}'.")
    return redirect("patron_dashboard")


@login_required
def return_resource(request, checkout_id):
    """
    Patron returns a resource (FR21–FR22).
    Handles overdue and fine calculation.
    """
    patron = request.user
    checkout = get_object_or_404(Checkout, id=checkout_id, patron=patron)

    if checkout.status != Checkout.STATUS_ACTIVE:
        messages.error(request, "Checkout is not active.")
        return redirect("patron_dashboard")

    fine = calculate_overdue_fine(checkout)
    Return.objects.create(checkout=checkout, fine_amount=fine)
    checkout.status = Checkout.STATUS_RETURNED
    checkout.save()

    resource = checkout.resource
    resource.status = Resource.STATUS_AVAILABLE
    resource.save()

    if fine > 0:
        create_notification(
            patron,
            Notification.TYPE_OVERDUE,
            f"Returned '{resource.title}' with an overdue fine of ${fine:.2f}."
        )
    else:
        create_notification(
            patron,
            Notification.TYPE_EVENT,
            f"Successfully returned '{resource.title}'."
        )

    messages.success(request, f"Returned '{resource.title}'. Fine: ${fine:.2f}.")
    return redirect("patron_dashboard")


@login_required
def reserve_resource(request, pk):
    """
    Patron reserves an unavailable resource (FR13–FR15).
    Enforces max 10 active reservations.
    """
    patron = request.user
    resource = get_object_or_404(Resource, pk=pk)

    active_res_count = Reservation.objects.filter(
        patron=patron,
        status=Reservation.STATUS_PENDING
    ).count()
    if active_res_count >= MAX_ACTIVE_RESERVATIONS_PER_PATRON:
        messages.error(request, "Reservation limit reached (max 10).")
        return redirect("resource_detail", pk=pk)

    if resource.status == Resource.STATUS_AVAILABLE:
        messages.info(request, "Resource is available. Consider checking it out instead.")
        return redirect("resource_detail", pk=pk)

    Reservation.objects.create(patron=patron, resource=resource)
    resource.status = Resource.STATUS_RESERVED
    resource.save()

    create_notification(
        patron,
        Notification.TYPE_RESERVATION_AVAILABLE,
        f"Reservation placed for '{resource.title}'. You will be notified when it becomes available."
    )

    messages.success(request, f"Reservation placed for '{resource.title}'.")
    return redirect("patron_dashboard")


# ---------- Staff views ----------

@staff_required
def staff_dashboard(request):
    """
    Staff dashboard: real-time availability and overdue items (FR24–FR31).
    """
    resources = Resource.objects.all()
    overdue_checkouts = Checkout.objects.filter(
        status=Checkout.STATUS_ACTIVE,
        due_date__lt=timezone.now(),
    )

    popular_resources = Resource.objects.annotate(
        checkout_count=Count("checkouts")
    ).order_by("-checkout_count")[:10]

    context = {
        "resources": resources,
        "overdue_checkouts": overdue_checkouts,
        "popular_resources": popular_resources,
    }
    return render(request, "library/staff_dashboard.html", context)


@staff_required
def staff_process_return(request, checkout_id):
    """
    Staff processes return on behalf of patron (FR34).
    """
    checkout = get_object_or_404(Checkout, id=checkout_id)
    if checkout.status != Checkout.STATUS_ACTIVE:
        messages.error(request, "Checkout is not active.")
        return redirect("staff_dashboard")

    fine = calculate_overdue_fine(checkout)
    Return.objects.create(checkout=checkout, fine_amount=fine)
    checkout.status = Checkout.STATUS_RETURNED
    checkout.save()

    resource = checkout.resource
    resource.status = Resource.STATUS_AVAILABLE
    resource.save()

    create_notification(
        checkout.patron,
        Notification.TYPE_OVERDUE if fine > 0 else Notification.TYPE_EVENT,
        f"Return processed by staff for '{resource.title}'. Fine: ${fine:.2f}."
    )

    messages.success(request, f"Return processed for '{resource.title}'. Fine: ${fine:.2f}.")
    return redirect("staff_dashboard")


# ---------- Admin views ----------

@admin_required
def admin_staff_list(request):
    """
    Admin manages staff accounts (FR35–FR37).
    """
    staff_members = User.objects.filter(role=User.ROLE_STAFF)
    context = {"staff_members": staff_members}
    return render(request, "library/admin_staff_list.html", context)


@admin_required
def admin_promote_to_staff(request, user_id):
    """
    Admin promotes a user to staff.
    """
    user = get_object_or_404(User, id=user_id)
    user.role = User.ROLE_STAFF
    user.save()
    messages.success(request, f"{user.username} promoted to staff.")
    return redirect("admin_staff_list")


@admin_required
def admin_deactivate_staff(request, user_id):
    """
    Admin deactivates staff account.
    """
    user = get_object_or_404(User, id=user_id, role=User.ROLE_STAFF)
    user.is_active = False
    user.save()
    messages.success(request, f"{user.username} deactivated.")
    return redirect("admin_staff_list")




@staff_required
def generate_popular_resources_report(request):
    """
    Generates a simple 'Popular Resources' report (FR28).
    """
    popular_resources = Resource.objects.annotate(
        checkout_count=Count("checkouts")
    ).order_by("-checkout_count")[:20]

    data = [
        {"title": r.title, "checkout_count": r.checkout_count}
        for r in popular_resources
    ]

    report = Report.objects.create(
        report_type=Report.TYPE_POPULAR_RESOURCES,
        data=data,
    )

    messages.success(request, f"Popular Resources report generated (ID: {report.id}).")
    return redirect("staff_dashboard")
