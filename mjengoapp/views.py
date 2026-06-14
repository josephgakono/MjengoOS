from django.db.models import Q
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from .models import (
    CustomerProfile,
    Job,
    Message,
    Notification,
    Portfolio,
    ProgressUpdate,
    Project,
    Quotation,
    Review,
    WorkerProfile,
)
from .permissions import (
    IsCustomer,
    IsJobOwner,
    IsProjectCustomer,
    IsProjectWorker,
    IsWorker,
    is_admin_user,
)
from .serializers import (
    CustomerProfileSerializer,
    JobSerializer,
    MessageSerializer,
    NotificationSerializer,
    PortfolioSerializer,
    ProgressUpdateSerializer,
    ProjectSerializer,
    QuotationSerializer,
    ReviewSerializer,
    WorkerProfileSerializer,
)


SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def get_worker_profile(user):
    return WorkerProfile.objects.filter(user=user).first()


class JobListCreateView(generics.ListCreateAPIView):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Business rule: only customers can create jobs; admins keep full access.
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsCustomer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Business rule: admins see all jobs, customers see their own jobs, workers can browse open work.
        user = self.request.user
        if is_admin_user(user) or user.user_type == 'worker':
            return Job.objects.all()
        return Job.objects.filter(customer=user)

    def perform_create(self, serializer):
        # Business rule: clients cannot spoof job ownership; creator is always the authenticated customer.
        serializer.save(customer=self.request.user)


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: workers may view jobs, but only owners/admins can reach customer-owned details.
        user = self.request.user
        if is_admin_user(user) or user.user_type == 'worker':
            return Job.objects.all()
        return Job.objects.filter(customer=user)

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method in SAFE_METHODS:
            return

        # Business rule: workers can view jobs but cannot edit them.
        if request.user.user_type == 'worker' and not is_admin_user(request.user):
            raise PermissionDenied('Workers cannot modify jobs.')

        # Business rule: only the customer who created a job can update or delete it.
        IsJobOwner().has_object_permission(request, self, obj) or self.permission_denied(
            request,
            message='Only the job owner can modify this job.',
        )

        # Business rule: completed jobs are locked against further modification.
        if obj.status == 'completed' and not is_admin_user(request.user):
            raise PermissionDenied('Completed jobs cannot be modified.')


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
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Business rule: only workers can create quotations; customers cannot quote on jobs.
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsWorker()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Business rule: admins see all quotes; customers see quotes on their jobs; workers see their own quotes.
        user = self.request.user
        if is_admin_user(user):
            return Quotation.objects.all()
        if user.user_type == 'customer':
            return Quotation.objects.filter(job__customer=user)
        if user.user_type == 'worker':
            return Quotation.objects.filter(worker__user=user)
        return Quotation.objects.none()

    def perform_create(self, serializer):
        # Business rule: clients cannot create quotes for another worker profile.
        worker = get_worker_profile(self.request.user)
        if worker is None:
            raise PermissionDenied('A worker profile is required to create quotations.')
        serializer.save(worker=worker)


class QuotationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: object lookup is scoped to records the user is allowed to know exist.
        user = self.request.user
        if is_admin_user(user):
            return Quotation.objects.all()
        if user.user_type == 'customer':
            return Quotation.objects.filter(job__customer=user)
        if user.user_type == 'worker':
            return Quotation.objects.filter(worker__user=user)
        return Quotation.objects.none()

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method in SAFE_METHODS:
            return

        # Business rule: only the worker who created a quotation can edit it.
        if obj.worker.user_id != request.user.id and not is_admin_user(request.user):
            raise PermissionDenied('Only the quotation owner can modify this quotation.')

        # Business rule: accepted quotations become immutable.
        if obj.status == 'accepted' and not is_admin_user(request.user):
            raise PermissionDenied('Accepted quotations cannot be edited.')


class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: admins see every project; customers/workers see only projects they participate in.
        user = self.request.user
        if is_admin_user(user):
            return Project.objects.all()
        return Project.objects.filter(Q(job__customer=user) | Q(worker__user=user))

    def perform_create(self, serializer):
        job = serializer.validated_data['job']
        worker = serializer.validated_data['worker']

        # Business rule: project owners create projects for their jobs after accepting a quotation.
        if job.customer_id != self.request.user.id and not is_admin_user(self.request.user):
            raise PermissionDenied('Only the job owner can create a project for this job.')

        # Business rule: projects can only be created from accepted quotations.
        if not Quotation.objects.filter(job=job, worker=worker, status='accepted').exists():
            raise ValidationError('A project can only be created from an accepted quotation.')

        serializer.save(job=job, worker=worker)


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: assigned workers and project owners can view details; other users receive 404.
        user = self.request.user
        if is_admin_user(user):
            return Project.objects.all()
        return Project.objects.filter(Q(job__customer=user) | Q(worker__user=user))

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)

        if request.method in SAFE_METHODS:
            allowed = (
                IsProjectWorker().has_object_permission(request, self, obj)
                or IsProjectCustomer().has_object_permission(request, self, obj)
            )
            allowed or self.permission_denied(
                request,
                message='Only assigned workers and project owners can view project details.',
            )
            return

        # Business rule: only admins can delete projects; participant edits are still scoped by queryset.
        if request.method == 'DELETE' and not is_admin_user(request.user):
            raise PermissionDenied('Only admins can delete projects.')


class ProgressUpdateListCreateView(generics.ListCreateAPIView):
    serializer_class = ProgressUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: customers view updates for their projects; workers view updates for assigned projects.
        user = self.request.user
        if is_admin_user(user):
            return ProgressUpdate.objects.all()
        return ProgressUpdate.objects.filter(Q(project__job__customer=user) | Q(project__worker__user=user))

    def perform_create(self, serializer):
        project = serializer.validated_data['project']

        # Business rule: only the assigned worker can create progress updates.
        if project.worker.user_id != self.request.user.id and not is_admin_user(self.request.user):
            raise PermissionDenied('Only the assigned worker can create progress updates.')

        # Business rule: completed projects do not accept new progress updates.
        if project.status == 'completed' and not is_admin_user(self.request.user):
            raise PermissionDenied('Completed projects cannot receive progress updates.')

        serializer.save(project=project)


class ProgressUpdateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProgressUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: object access is limited to the assigned worker, project owner, or admin.
        user = self.request.user
        if is_admin_user(user):
            return ProgressUpdate.objects.all()
        return ProgressUpdate.objects.filter(Q(project__job__customer=user) | Q(project__worker__user=user))

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method in SAFE_METHODS:
            return

        # Business rule: only assigned workers maintain progress records before completion.
        if obj.project.worker.user_id != request.user.id and not is_admin_user(request.user):
            raise PermissionDenied('Only the assigned worker can modify progress updates.')
        if obj.project.status == 'completed' and not is_admin_user(request.user):
            raise PermissionDenied('Completed project progress cannot be modified.')


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Business rule: only customers can create reviews; admins retain full access.
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsCustomer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Business rule: customers see reviews for their projects; workers see reviews about themselves.
        user = self.request.user
        if is_admin_user(user):
            return Review.objects.all()
        if user.user_type == 'customer':
            return Review.objects.filter(customer=user)
        if user.user_type == 'worker':
            return Review.objects.filter(worker__user=user)
        return Review.objects.none()

    def perform_create(self, serializer):
        project = serializer.validated_data['project']
        worker = serializer.validated_data['worker']
        customer = self.request.user

        # Business rule: customer must own the reviewed project.
        if project.job.customer_id != customer.id and not is_admin_user(customer):
            raise PermissionDenied('Only the project owner can review this project.')

        # Business rule: reviews are allowed only after project completion.
        if project.status != 'completed' and not is_admin_user(customer):
            raise PermissionDenied('Only completed projects can be reviewed.')

        # Business rule: a worker cannot review themselves through a customer account.
        if worker.user_id == customer.id and not is_admin_user(customer):
            raise PermissionDenied('Workers cannot review themselves.')

        # Business rule: reviewed worker must be the worker assigned to the project.
        if worker.id != project.worker_id and not is_admin_user(customer):
            raise ValidationError('Reviews must target the assigned project worker.')

        # Business rule: only one review is allowed per customer per project.
        if Review.objects.filter(project=project, customer=customer).exists():
            raise ValidationError('This customer has already reviewed this project.')

        serializer.save(project=project, customer=customer, worker=worker)


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: review detail visibility is limited to the author, reviewed worker, or admin.
        user = self.request.user
        if is_admin_user(user):
            return Review.objects.all()
        return Review.objects.filter(Q(customer=user) | Q(worker__user=user))

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)

        # Business rule: reviews become read-only after creation for non-admin users.
        if request.method not in SAFE_METHODS and not is_admin_user(request.user):
            raise PermissionDenied('Reviews are read-only after creation.')


class PortfolioListCreateView(generics.ListCreateAPIView):
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Business rule: only workers can create portfolio entries.
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsWorker()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return Portfolio.objects.all()

    def perform_create(self, serializer):
        # Business rule: portfolio ownership is always the authenticated worker profile.
        worker = get_worker_profile(self.request.user)
        if worker is None:
            raise PermissionDenied('A worker profile is required to create portfolio entries.')
        serializer.save(worker=worker)


class PortfolioDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.all() if is_admin_user(self.request.user) else Portfolio.objects.all()

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method in SAFE_METHODS:
            return

        # Business rule: workers can only edit or delete their own portfolio entries.
        if obj.worker.user_id != request.user.id and not is_admin_user(request.user):
            raise PermissionDenied('Only the portfolio owner can modify this entry.')


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: users can only view messages where they are sender or receiver.
        user = self.request.user
        if is_admin_user(user):
            return Message.objects.all()
        return Message.objects.filter(Q(sender=user) | Q(receiver=user))

    def perform_create(self, serializer):
        # Business rule: clients cannot spoof the message sender.
        serializer.save(sender=self.request.user)


class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: messages belonging to other users are hidden with 404.
        user = self.request.user
        if is_admin_user(user):
            return Message.objects.all()
        return Message.objects.filter(Q(sender=user) | Q(receiver=user))


class NotificationListCreateView(generics.ListCreateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: users can only view their own notifications.
        user = self.request.user
        if is_admin_user(user):
            return Notification.objects.all()
        return Notification.objects.filter(user=user)

    def perform_create(self, serializer):
        # Business rule: regular users can only create notifications for themselves.
        if serializer.validated_data.get('user') != self.request.user and not is_admin_user(self.request.user):
            raise PermissionDenied('Users cannot create notifications for other users.')
        serializer.save()


class NotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: notifications belonging to other users are hidden with 404.
        user = self.request.user
        if is_admin_user(user):
            return Notification.objects.all()
        return Notification.objects.filter(user=user)
