from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import CustomerProfile, Job, Quotation, WorkerProfile


User = get_user_model()


class CustomerProfileCreatePermissionsTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='customer',
            password='password',
            user_type='customer',
            phone='0700000000',
        )
        self.worker_user = User.objects.create_user(
            username='worker',
            password='password',
            user_type='worker',
            phone='0711111111',
        )
        self.worker_profile = WorkerProfile.objects.create(
            user=self.worker_user,
            profession='Mason',
            experience_years=5,
            location='Nairobi',
            bio='Experienced mason',
        )

    def test_user_without_customer_profile_cannot_create_job(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(reverse('jobs'), {
            'title': 'Kitchen repair',
            'description': 'Repair cracked kitchen tiles',
            'location': 'Nairobi',
            'budget': '15000.00',
        })

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Job.objects.exists())

    def test_user_with_customer_profile_can_create_job(self):
        CustomerProfile.objects.create(user=self.customer, location='Nairobi')
        self.client.force_authenticate(self.customer)

        response = self.client.post(reverse('jobs'), {
            'title': 'Kitchen repair',
            'description': 'Repair cracked kitchen tiles',
            'location': 'Nairobi',
            'budget': '15000.00',
        })

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Job.objects.get().customer, self.customer)

    def test_user_without_customer_profile_cannot_create_project(self):
        job = Job.objects.create(
            customer=self.customer,
            title='Roof repair',
            description='Patch leaking roof',
            location='Nairobi',
            budget='30000.00',
        )
        Quotation.objects.create(
            worker=self.worker_profile,
            job=job,
            amount='28000.00',
            estimated_days=7,
            message='Ready to start',
            status='accepted',
        )
        self.client.force_authenticate(self.customer)

        response = self.client.post(reverse('projects'), {
            'job': job.id,
            'worker': self.worker_profile.id,
            'start_date': '2026-07-01',
            'expected_completion': '2026-07-08',
        })

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_with_customer_profile_can_create_project_for_accepted_quote(self):
        CustomerProfile.objects.create(user=self.customer, location='Nairobi')
        job = Job.objects.create(
            customer=self.customer,
            title='Roof repair',
            description='Patch leaking roof',
            location='Nairobi',
            budget='30000.00',
        )
        Quotation.objects.create(
            worker=self.worker_profile,
            job=job,
            amount='28000.00',
            estimated_days=7,
            message='Ready to start',
            status='accepted',
        )
        self.client.force_authenticate(self.customer)

        response = self.client.post(reverse('projects'), {
            'job': job.id,
            'worker': self.worker_profile.id,
            'start_date': '2026-07-01',
            'expected_completion': '2026-07-08',
        })

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
