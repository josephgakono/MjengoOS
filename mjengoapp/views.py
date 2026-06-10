from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import (
    CustomerProfile,
    Job,
    Message,
    Notification,
    Portfolio,
    Project,
    Quotation,
    Review,
    WorkerProfile,
)
from .serializers import (
    CustomerProfileSerializer,
    JobSerializer,
    MessageSerializer,
    NotificationSerializer,
    PortfolioSerializer,
    ProjectSerializer,
    QuotationSerializer,
    ReviewSerializer,
    WorkerProfileSerializer,
)


class JobListCreateView(generics.ListCreateAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]


class WorkerProfileListCreateView(generics.ListCreateAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WorkerProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]


class CustomerProfileListCreateView(generics.ListCreateAPIView):
    queryset = CustomerProfile.objects.all()
    serializer_class = CustomerProfileSerializer
    permission_classes = [IsAuthenticated]


class CustomerProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomerProfile.objects.all()
    serializer_class = CustomerProfileSerializer
    permission_classes = [IsAuthenticated]


class QuotationListCreateView(generics.ListCreateAPIView):
    queryset = Quotation.objects.all()
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]


class QuotationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Quotation.objects.all()
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]


class ProjectListCreateView(generics.ListCreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]


class ReviewListCreateView(generics.ListCreateAPIView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]


class PortfolioListCreateView(generics.ListCreateAPIView):
    queryset = Portfolio.objects.all()
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]


class PortfolioDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Portfolio.objects.all()
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]


class MessageListCreateView(generics.ListCreateAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]


class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]


class NotificationListCreateView(generics.ListCreateAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]


class NotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
