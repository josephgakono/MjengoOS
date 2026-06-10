from django.urls import path
from .views import (
    CustomerProfileDetailView,
    CustomerProfileListCreateView,
    JobDetailView,
    JobListCreateView,
    MessageDetailView,
    MessageListCreateView,
    NotificationDetailView,
    NotificationListCreateView,
    PortfolioDetailView,
    PortfolioListCreateView,
    ProjectDetailView,
    ProjectListCreateView,
    QuotationDetailView,
    QuotationListCreateView,
    ReviewDetailView,
    ReviewListCreateView,
    WorkerProfileDetailView,
    WorkerProfileListCreateView,
)

urlpatterns = [
    path('jobs/', JobListCreateView.as_view(), name='jobs'),
    path('jobs/<int:pk>/', JobDetailView.as_view(), name='job-detail'),
    path('workerprofile/', WorkerProfileListCreateView.as_view(), name='workerprofile'),
    path('workerprofile/<int:pk>/', WorkerProfileDetailView.as_view(), name='workerprofile-detail'),
]