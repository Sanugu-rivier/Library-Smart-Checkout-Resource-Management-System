from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator


class User(AbstractUser):
    ROLE_PATRON = "PATRON"
    ROLE_STAFF = "STAFF"
    ROLE_ADMIN = "ADMIN"

    ROLE_CHOICES = [
        (ROLE_PATRON, "Patron"),
        (ROLE_STAFF, "Staff"),
        (ROLE_ADMIN, "Admin"),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_PATRON)

    def is_patron(self):
        return self.role == self.ROLE_PATRON

    def is_staff_user(self):
        return self.role == self.ROLE_STAFF

    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN


class Resource(models.Model):
    TYPE_BOOK = "BOOK"
    TYPE_MEDIA = "MEDIA"
    TYPE_DIGITAL = "DIGITAL"

    TYPE_CHOICES = [
        (TYPE_BOOK, "Book"),
        (TYPE_MEDIA, "Media"),
        (TYPE_DIGITAL, "Digital"),
    ]

    STATUS_AVAILABLE = "AVAILABLE"
    STATUS_CHECKED_OUT = "CHECKED_OUT"
    STATUS_RESERVED = "RESERVED"
    STATUS_LOST = "LOST"

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_CHECKED_OUT, "Checked Out"),
        (STATUS_RESERVED, "Reserved"),
        (STATUS_LOST, "Lost"),
    ]

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    resource_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_BOOK)
    rfid_tag = models.CharField(max_length=64, blank=True, null=True, unique=True)
    barcode = models.CharField(max_length=64, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.get_resource_type_display()})"


class Checkout(models.Model):
    STATUS_ACTIVE = "ACTIVE"
    STATUS_RETURNED = "RETURNED"
    STATUS_LOST = "LOST"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_RETURNED, "Returned"),
        (STATUS_LOST, "Lost"),
    ]

    patron = models.ForeignKey(User, on_delete=models.CASCADE, related_name="checkouts")
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="checkouts")
    checkout_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    def is_overdue(self):
        return self.status == self.STATUS_ACTIVE and timezone.now() > self.due_date

    def __str__(self):
        return f"Checkout #{self.id} - {self.resource} to {self.patron}"


class Return(models.Model):
    checkout = models.OneToOneField(Checkout, on_delete=models.CASCADE, related_name="return_record")
    returned_at = models.DateTimeField(default=timezone.now)
    fine_amount = models.DecimalField(max_digits=6, decimal_places=2, default=0.00,
                                      validators=[MinValueValidator(0)])

    def __str__(self):
        return f"Return #{self.id} for {self.checkout}"


class Reservation(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_NOTIFIED = "NOTIFIED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_EXPIRED = "EXPIRED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_NOTIFIED, "Notified"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    patron = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reservations")
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="reservations")
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    hold_until = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Reservation #{self.id} - {self.resource} for {self.patron}"


class Notification(models.Model):
    TYPE_OVERDUE = "OVERDUE"
    TYPE_RESERVATION_AVAILABLE = "RES_AVAIL"
    TYPE_NEW_RESOURCE = "NEW_RESOURCE"
    TYPE_EVENT = "EVENT"

    TYPE_CHOICES = [
        (TYPE_OVERDUE, "Overdue"),
        (TYPE_RESERVATION_AVAILABLE, "Reservation Available"),
        (TYPE_NEW_RESOURCE, "New Resource"),
        (TYPE_EVENT, "Library Event"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.user}"


class Report(models.Model):
    TYPE_POPULAR_RESOURCES = "POPULAR_RESOURCES"
    TYPE_FREQUENT_PATRONS = "FREQUENT_PATRONS"
    TYPE_INVENTORY_TRENDS = "INVENTORY_TRENDS"

    TYPE_CHOICES = [
        (TYPE_POPULAR_RESOURCES, "Popular Resources"),
        (TYPE_FREQUENT_PATRONS, "Frequent Patrons"),
        (TYPE_INVENTORY_TRENDS, "Inventory Trends"),
    ]

    report_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    generated_at = models.DateTimeField(default=timezone.now)
    data = models.JSONField()

    def __str__(self):
        return f"{self.get_report_type_display()} @ {self.generated_at:%Y-%m-%d}"
