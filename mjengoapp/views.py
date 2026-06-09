from django.shortcuts import render
from rest_framework import generics
from .models import Job, WorkerProfile
from .serializers import JobSerializer ,WorkerProfileSerializer


class JobListCreateView(generics.ListCreateAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer

class WorkerProfileListCreateView(generics.ListCreateAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer

    def perform_create(self, serializer):
     serializer.save(user=self.request.user) 


class WorkerProfileDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer

