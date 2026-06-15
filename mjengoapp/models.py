from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    USER_TYPES = (
        ('customer', 'Customer'),
        ('worker', 'Worker'),
        ('contractor', 'Contractor'),
        ('admin', 'Admin'),
    )

    user_type = models.CharField(max_length=20, choices=USER_TYPES)
    phone = models.CharField(max_length=15)
    profile_picture = models.ImageField(
        upload_to='profiles/',
        null=True,
        blank=True
    )

    def __str__(self):
        return self.username


class WorkerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    profession = models.CharField(max_length=100)
    experience_years = models.PositiveIntegerField()
    location = models.CharField(max_length=100)
    bio = models.TextField()
    verified = models.BooleanField(default=False)

    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    average_rating = models.FloatField(default=0)

    def __str__(self):
        return self.user.username

class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    location = models.CharField(max_length=100)

    preferred_contact = models.CharField(
        max_length=50,
        blank=True
    )

    def __str__(self):
        return self.user.username


class Job(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('quoted', 'Quoted'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=100)

    budget = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open'
    )
    image = models.ImageField(
        upload_to='jobs/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Quotation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    )

    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    estimated_days = models.PositiveIntegerField()

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.worker.user.username} - {self.job.title}"


class Project(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
    )

    job = models.OneToOneField(
        Job,
        on_delete=models.CASCADE
    )

    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE
    )

    start_date = models.DateField()

    expected_completion = models.DateField()

    actual_completion = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    def __str__(self):
        return self.job.title


class Payment(models.Model):
    PAYMENT_TYPE_CHOICES = (
        ('deposit', 'Deposit'),
        ('milestone', 'Milestone'),
        ('final', 'Final'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('successful', 'Successful'),
        ('failed', 'Failed'),
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    checkout_request_id = models.CharField(
        max_length=100,
        blank=True
    )

    mpesa_receipt_number = models.CharField(
        max_length=100,
        blank=True
    )

    transaction_date = models.DateTimeField(
        null=True,
        blank=True
    )

    phone_number = models.CharField(max_length=15)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project.job.title} - {self.amount} ({self.status})"


class ProgressUpdate(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE
    )

    description = models.TextField()
    image = models.ImageField(
        upload_to='progress_updates/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Update for {self.project.job.title}"


class Review(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE
    )

    rating = models.IntegerField()

    comment = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Review {self.rating}/5"


class Portfolio(models.Model):
    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE
    )

    title = models.CharField(max_length=200)

    description = models.TextField()
    image = models.ImageField(
        upload_to='portfolio/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.title


class Message(models.Model):
    sender = models.ForeignKey(
        User,
        related_name='sent_messages',
        on_delete=models.CASCADE
    )

    receiver = models.ForeignKey(
        User,
        related_name='received_messages',
        on_delete=models.CASCADE
    )

    content = models.TextField()

    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}"


class Notification(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    title = models.CharField(max_length=200)

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.title
