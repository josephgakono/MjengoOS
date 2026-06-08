from django.db import models
from django.contrib.auth.models import User


class User(AbstractUser):
    USER_TYPES = (
        ('customer', 'Customer'),
        ('worker', 'Worker'),
        ('contractor', 'Contractor'),
        ('admin', 'Admin'),
    )

    user_type = models.CharField(max_length=20, choices=USER_TYPES)
    phone = models.CharField(max_length=15)

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
