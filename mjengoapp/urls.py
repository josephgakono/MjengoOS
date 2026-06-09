from django.urls import path
from .views import JobListCreateView ,JobDetailView,WorkerProfileListCreateView,WorkerProfileDetailView

urlpatterns = [
    path('jobs/', JobListCreateView.as_view(), name='jobs'),
    path('jobs/<int:pk>/', JobDetailView.as_view(), name='job-detail'),
    path('workerprofile/',WorkerProfileListCreateView.as_view(),name='workerprofile'),
    path('workerprofile/<int:pk>/',WorkerProfileDetailView.as_view(),name='workerprofile-detail')
]