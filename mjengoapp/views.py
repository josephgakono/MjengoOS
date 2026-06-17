from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from datetime import datetime
from .models import (
    CustomerProfile,
    Job,
    Message,
    Notification,
    Payment,
    Portfolio,
    ProgressUpdate,
    Project,
    Quotation,
    Review,
    WorkerProfile,
)
from .mpesa import DarajaService, DarajaServiceError
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
    PaymentSerializer,
    PortfolioSerializer,
    ProgressUpdateSerializer,
    ProjectSerializer,
    QuotationSerializer,
    ReviewSerializer,
    StkPushSerializer,
    WorkerProfileSerializer,
)


SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def get_worker_profile(user):
    return WorkerProfile.objects.filter(user=user).first()


def get_callback_item(metadata_items, item_name):
    # Daraja callback metadata is a list of name/value pairs, so this helper safely extracts one value.
    for item in metadata_items:
        if item.get('Name') == item_name:
            return item.get('Value')
    return None


def parse_mpesa_transaction_date(raw_transaction_date):
    if not raw_transaction_date:
        return None
    parsed_date = datetime.strptime(str(raw_transaction_date), '%Y%m%d%H%M%S')
    return timezone.make_aware(parsed_date, timezone.get_current_timezone())


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


class PaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Business rule: only customers can create payment records; admins retain full access.
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsCustomer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Business rule: admins see all payments; customers see only payments for their projects.
        user = self.request.user
        if is_admin_user(user):
            return Payment.objects.all()
        return Payment.objects.filter(project__job__customer=user)

    def perform_create(self, serializer):
        project = serializer.validated_data['project']

        # Business rule: workers cannot initiate payments and customers can only pay for their own projects.
        if project.job.customer_id != self.request.user.id and not is_admin_user(self.request.user):
            raise PermissionDenied('Only the project owner can create a payment for this project.')

        customer = project.job.customer if is_admin_user(self.request.user) else self.request.user
        serializer.save(customer=customer)


class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: payment details are scoped to the project owner unless the requester is an admin.
        user = self.request.user
        if is_admin_user(user):
            return Payment.objects.all()
        return Payment.objects.filter(project__job__customer=user)

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method in SAFE_METHODS:
            return

        
        if not is_admin_user(request.user):
            raise PermissionDenied('Only admins can modify payment records.')


class StkPushView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        serializer = StkPushSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = get_object_or_404(Project, pk=serializer.validated_data['project_id'])
        phone_number = serializer.validated_data['phone_number']
        amount = serializer.validated_data['amount']
        payment_type = serializer.validated_data['payment_type']

        if project.job.customer_id != request.user.id and not is_admin_user(request.user):
            raise PermissionDenied('Only the project owner can initiate this payment.')

        customer = project.job.customer if is_admin_user(request.user) else request.user

    
        payment = Payment.objects.create(
            project=project,
            customer=customer,
            amount=amount,
            payment_type=payment_type,
            phone_number=phone_number,
        )

        try:
            daraja_response = DarajaService.send_stk_push(
                phone_number=phone_number,
                amount=amount,
                account_reference=f'PROJECT-{project.id}',
                transaction_desc=f'{payment_type.title()} payment for {project.job.title}',
            )
        except DarajaServiceError as exc:
            payment.status = 'failed'
            payment.save(update_fields=['status'])
            raise ValidationError({'daraja': str(exc)})

        # Daraja may return the tracking id under different keys depending on API/SDK.
        checkout_request_id = (
            daraja_response.get('CheckoutRequestID')
            or daraja_response.get('CheckoutRequestId')
            or daraja_response.get('checkoutRequestID')
            or ''
        )
        if not checkout_request_id:
            # Keep payment row consistent but make it obvious in the response.
            # (Callback will not be able to match without this.)
            return Response(
                {
                    **PaymentSerializer(payment).data,
                    'daraja_response': daraja_response,
                    'error': 'Daraja did not return CheckoutRequestID (cannot match callback).',
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payment.checkout_request_id = str(checkout_request_id)
        payment.save(update_fields=['checkout_request_id'])


        response_data = PaymentSerializer(payment).data
        response_data['daraja_response'] = daraja_response
        return Response(response_data, status=status.HTTP_201_CREATED)


class MpesaCallbackView(APIView):
    # CRITICAL: Allow Safaricom's webhook to hit your server without a JWT token or session
    permission_classes = [AllowAny]
    authentication_classes = [] 

    def post(self, request, *args, **kwargs):
        # 1. Grab the raw payload sent by M-Pesa
        callback_data = request.data
        
        # 2. Safely extract core identifiers from the nested JSON
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')

        # Callback tracking id might vary in key casing.
        checkout_request_id = (
            stk_callback.get('CheckoutRequestID')
            or stk_callback.get('CheckoutRequestId')
            or stk_callback.get('checkoutRequestID')
            or None
        )

        if not checkout_request_id:
            # Fallback handling in case of an invalid payload structure
            return Response(
                {"ResultCode": 1, "ResultDesc": "Invalid payload format: missing CheckoutRequestID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        checkout_request_id = str(checkout_request_id)
        print(f"[MPESA CALLBACK] checkout_request_id={checkout_request_id} result_code={result_code}")

        try:
            # 3. Locate the corresponding payment record in your database
            payment = Payment.objects.get(checkout_request_id=checkout_request_id)

            # 4. Handle successful payments (ResultCode 0)
            if result_code == 0:
                metadata = stk_callback.get('CallbackMetadata', {}).get('Item', []) or []

                mpesa_receipt_number = get_callback_item(metadata, 'MpesaReceiptNumber')
                transaction_date = get_callback_item(metadata, 'TransactionDate')
                parsed_date = parse_mpesa_transaction_date(transaction_date)

                payment.status = 'successful'  # Matches your model's STATUS_CHOICES
                payment.mpesa_receipt_number = mpesa_receipt_number
                payment.transaction_date = parsed_date
                payment.save()

                print(
                    f"[MPESA CALLBACK] Payment successful checkout_id={checkout_request_id} receipt={mpesa_receipt_number}"
                )
            else:
                # 5. Handle failed/canceled payments
                payment.status = 'failed'
                payment.save(update_fields=['status'])

                result_desc = stk_callback.get('ResultDesc', 'Unknown error')
                print(
                    f"[MPESA CALLBACK] Payment failed checkout_id={checkout_request_id} desc={result_desc}"
                )

        except Payment.DoesNotExist:
            # Don't silently ignore: return non-200 so you can spot mismatches.
            print(
                f"[MPESA CALLBACK] ERROR: Callback received for untracked checkout_request_id={checkout_request_id}"
            )
            return Response(
                {"ResultCode": 1, "ResultDesc": "Payment record not found for CheckoutRequestID"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Tell Safaricom you received the message successfully.
        return Response(
            {"ResultCode": 0, "ResultDesc": "Callback processed successfully"},
            status=status.HTTP_200_OK,
        )





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
