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
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .models import (
    CustomerProfile,
    Feedback,
    Notification,

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
    User,
)

from .mpesa import DarajaService, DarajaServiceError
from .permissions import (
    HasCustomerProfile,
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
    UserRegistrationSerializer,
    WorkerProfileSerializer,
    PublicUserSerializer,
    PublicJobSerializer,
    UserSerializer,
    FeedbackSerializer,
)



class PublicOpenJobsListView(generics.ListAPIView):


    """Public endpoint: list only OPEN jobs and include the customer who created them."""

    serializer_class = PublicJobSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


    def get_queryset(self):
        return Job.objects.filter(status='open')




SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def get_worker_profile(user):
    return WorkerProfile.objects.filter(user=user).first()


def get_customer_profile(user):
    return CustomerProfile.objects.filter(user=user).first()


def visible_jobs_for_user(user):
    if is_admin_user(user):
        return Job.objects.all()

    # Customer can only see jobs they created.
    if get_customer_profile(user):
        return Job.objects.filter(customer=user)

    # Worker can only see jobs they have quoted for (pending/accepted quotes) or that are assigned.
    # If their quotation was rejected, it should not grant visibility.
    if get_worker_profile(user):
        return (
            Job.objects.filter(quotation__worker__user=user, quotation__status__in=['pending', 'accepted'])
            | Job.objects.filter(project__worker__user=user)
        ).distinct()

    return Job.objects.none()


def visible_projects_for_user(user):
    if is_admin_user(user):
        return Project.objects.all()
    if get_customer_profile(user):
        return Project.objects.filter(job__customer=user)
    if get_worker_profile(user):
        return Project.objects.filter(worker__user=user)
    return Project.objects.none()


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


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = PublicUserSerializer
    permission_classes = [AllowAny]


class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]



class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    authentication_classes = []

class MyProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class JobListCreateView(generics.ListCreateAPIView):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Business rule: only users with a customer profile can create jobs.
        if self.request.method == 'POST':
            return [IsAuthenticated(), HasCustomerProfile()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Business rule: jobs revolve around the authenticated customer/worker profile.
        return visible_jobs_for_user(self.request.user)

    def perform_create(self, serializer):
        # Business rule: clients cannot spoof job ownership; creator is always the authenticated customer.
        serializer.save(customer=self.request.user)


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: job details are limited to visible work for this user.
        return visible_jobs_for_user(self.request.user)

    def check_object_permissions(self, request, obj):
        # Enforce visibility for all requests.
        if not is_admin_user(request.user):
            if not visible_jobs_for_user(request.user).filter(pk=obj.pk).exists():
                raise PermissionDenied('You do not have access to this job.')

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
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_admin_user(user):
            return WorkerProfile.objects.all()
        if get_worker_profile(user):
            return WorkerProfile.objects.filter(user=user)
        if get_customer_profile(user):
            return WorkerProfile.objects.filter(project__job__customer=user).distinct()
        return WorkerProfile.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WorkerProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_admin_user(user):
            return WorkerProfile.objects.all()
        if get_worker_profile(user):
            return WorkerProfile.objects.filter(user=user)
        if get_customer_profile(user):
            return WorkerProfile.objects.filter(project__job__customer=user).distinct()
        return WorkerProfile.objects.none()


class CustomerProfileListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_admin_user(user):
            return CustomerProfile.objects.all()
        if get_customer_profile(user):
            return CustomerProfile.objects.filter(user=user)
        if get_worker_profile(user):
            return CustomerProfile.objects.filter(user__job__project__worker__user=user).distinct()
        return CustomerProfile.objects.none()


class CustomerProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_admin_user(user):
            return CustomerProfile.objects.all()
        if get_customer_profile(user):
            return CustomerProfile.objects.filter(user=user)
        if get_worker_profile(user):
            return CustomerProfile.objects.filter(user__job__project__worker__user=user).distinct()
        return CustomerProfile.objects.none()


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
        if obj.worker.user.username != request.user.username and not is_admin_user(request.user):
            raise PermissionDenied('Only the quotation owner can modify this quotation.')


        # Business rule: accepted quotations become immutable.
        if obj.status == 'accepted' and not is_admin_user(request.user):
            raise PermissionDenied('Accepted quotations cannot be edited.')


class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Business rule: only users with a customer profile can create projects.
        if self.request.method == 'POST':
            return [IsAuthenticated(), HasCustomerProfile()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Business rule: projects revolve around the authenticated customer/worker profile.
        return visible_projects_for_user(self.request.user)

    def perform_create(self, serializer):
        job = serializer.validated_data['job']
        worker = serializer.validated_data['worker']

        # Business rule: project owners create projects for their jobs after accepting a quotation.
        if job.customer.username != self.request.user.username and not is_admin_user(self.request.user):
            raise PermissionDenied('Only the job owner can create a project for this job.')


        # Business rule: projects can only be created from accepted quotations.
        if not Quotation.objects.filter(job=job, worker=worker, status='accepted').exists():
            raise ValidationError('A project can only be created from an accepted quotation.')

        serializer.save(job=job, worker=worker)


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Business rule: project details are limited to visible work for this user.
        return visible_projects_for_user(self.request.user)

    def check_object_permissions(self, request, obj):
      super().check_object_permissions(request, obj)

      if request.method in SAFE_METHODS:
        return

      # Only assigned worker can update project status
      if request.method in ['PUT', 'PATCH']:
        if (
            obj.worker.user.username != request.user.username
            and not is_admin_user(request.user)

        ):
            raise PermissionDenied(
                'Only the assigned worker can update project status.'
            )

      if request.method == 'DELETE' and not is_admin_user(request.user):
        raise PermissionDenied(
            'Only admins can delete projects.'
        )
    def perform_update(self, serializer):
        project = serializer.save()

        # Business rule: workers cannot mark a project complete unless they have submitted at least
        # two progress updates for the project.
        if (
            project.status == 'completed'
            and not project.actual_completion
            and not is_admin_user(self.request.user)
            and ProgressUpdate.objects.filter(project=project).count() < 2
        ):
            raise ValidationError(
                'At least two progress updates are required before marking the project completed.'
            )

        if project.status == 'completed' and not project.actual_completion:
            project.actual_completion = timezone.now().date()
            project.save()



        project.job.status = 'completed'
        project.job.save()

        payments = Payment.objects.filter(
            project=project,
            status='successful',
            escrow_status='held'
        )

        for payment in payments:
            payment.escrow_status = 'released'
            payment.released_at = timezone.now()
            payment.save()

class PaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Business rule: only customers can create payment records; admins retain full access.
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsCustomer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Business rule: admins see all payments; customers/workers see payments related to their work.
        user = self.request.user
        if is_admin_user(user):
            return Payment.objects.all()
        # Customers see payments for their projects; workers see payments for projects assigned to them.
        # This supports both "payments sent" (customer initiates) and "payments received" (worker completes work).
        return Payment.objects.filter(
            Q(project__job__customer=user) | Q(project__worker__user=user)
        )

    def perform_create(self, serializer):
        project = serializer.validated_data['project']


        # Business rule: workers cannot initiate payments and customers can only pay for their own projects.
        if project.job.customer.username != self.request.user.username and not is_admin_user(self.request.user):
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
        # Customers see payments for their projects; workers see payments for projects assigned to them.
        return Payment.objects.filter(
            Q(project__job__customer=user) | Q(project__worker__user=user)
        )


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

        if project.job.customer.username != request.user.username and not is_admin_user(request.user):
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


@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(APIView):
    # CRITICAL: Allow Safaricom's webhook to hit your server without a CSRF token/session/JWT token
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
                # Idempotency guard: ignore duplicate callbacks for the same payment
                if payment.status == 'successful':
                    return Response(
                        {"ResultCode": 0, "ResultDesc": "Callback already processed"},
                        status=status.HTTP_200_OK,
                    )
                metadata = stk_callback.get('CallbackMetadata', {}).get('Item', []) or []


                mpesa_receipt_number = get_callback_item(metadata, 'MpesaReceiptNumber')
                transaction_date = get_callback_item(metadata, 'TransactionDate')
                parsed_date = parse_mpesa_transaction_date(transaction_date)
                payment.status = 'successful'
                payment.escrow_status = 'held'
                payment.mpesa_receipt_number = mpesa_receipt_number
                payment.transaction_date = parsed_date
                payment.save()

                # Update project payment flag once payment is received
                project = payment.project
                if not project.payment_received:
                    project.payment_received = True
                    project.save(update_fields=['payment_received'])


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
        if project.worker.user.username != self.request.user.username and not is_admin_user(self.request.user):
            raise PermissionDenied('Only the assigned worker can create progress updates.')


        # Business rule: workers cannot submit the first progress update unless the customer has
        # sent the quotation amount and the system has it held.
        if (
            not is_admin_user(self.request.user)
            and ProgressUpdate.objects.filter(project=project).count() == 0
        ):
            required_amount = Quotation.objects.filter(job=project.job, worker=project.worker).values_list('amount', flat=True).first()
            if not required_amount:
                raise ValidationError('Quotation amount not found for this project.')
            if not Payment.objects.filter(
                project=project,
                status='successful',
                escrow_status='held',
                amount=required_amount,
            ).exists():
                raise PermissionDenied('Customer must submit the quotation amount first (payment held) before the first progress update.')

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
        if obj.project.worker.user.username != request.user.username and not is_admin_user(request.user):
            raise PermissionDenied('Only the assigned worker can modify progress updates.')

        if obj.project.status == 'completed' and not is_admin_user(request.user):
            raise PermissionDenied('Completed project progress cannot be modified.')


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Business rule: both customers and workers can create reviews after the project is completed.
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Business rule: authors see reviews they created; admins see all.
        user = self.request.user
        if is_admin_user(user):
            return Review.objects.all()
        if user.user_type == 'customer':
            return Review.objects.filter(customer=user)
        if user.user_type == 'worker':
            # worker reviews are stored with worker=<reviewed worker profile> and customer=<review author user>
            # For worker's own authored reviews we filter by the "customer" field that holds the author.
            return Review.objects.filter(customer=user)
        return Review.objects.none()

    def perform_create(self, serializer):
        project = serializer.validated_data['project']
        worker = serializer.validated_data['worker']

        author = self.request.user  # the user leaving the review (customer OR worker)

        # Business rule: reviews are allowed only after project completion.
        if project.status != 'completed' and not is_admin_user(author):
            raise PermissionDenied('Only completed projects can be reviewed.')

        job_customer = project.job.customer
        project_worker = project.worker.user

        # Determine review target vs author depending on the author type.
        if author.user_type == 'customer':
            # Customer reviews the worker (target = project.worker).
            if job_customer.username != author.username and not is_admin_user(author):
                raise PermissionDenied('Only the project owner can review this project.')

            # Serializer "worker" should match the assigned worker.
            if worker.id != project.worker_id and not is_admin_user(author):
               raise ValidationError('Reviews must target the assigned project worker.')

            serializer.save(project=project, customer=author, worker=project.worker)
            # Update combined rating for the reviewed worker profile (out of 5)
            project.worker.update_combined_rating()
            return


        if author.user_type == 'worker':
            # Worker reviews the customer.
            # Model has only (customer, worker) fields, so we reuse it:
            # - customer = review author (worker in this case)
            # - worker = review target worker profile (project.worker)
            if project_worker.username != author.username and not is_admin_user(author):
                raise PermissionDenied('Only the assigned worker can review this project.')

            if worker.id != project.worker_id and not is_admin_user(author):
              raise ValidationError('Reviews must target the assigned project worker.')

            # Only one review per author per project.
            if Review.objects.filter(project=project, customer=author).exists():
                raise ValidationError('This user has already reviewed this project.')

            serializer.save(project=project, customer=author, worker=project.worker)
            return


        # Contractors/admin follow admin override only.
        raise PermissionDenied('Unsupported user type for reviews.')


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
        if obj.worker.user.username != request.user.username and not is_admin_user(request.user):
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


class AcceptQuotationView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, quotation_id):
        quotation = get_object_or_404(
            Quotation,
            id=quotation_id
        )

        # Only the owner of the job can accept quotations
        if quotation.job.customer.username != request.user.username:
            raise PermissionDenied(
                "Only the job owner can accept quotations."
            )


        # Prevent accepting twice
        if quotation.status == "accepted":
            return Response(
                {"message": "Quotation already accepted."},
                status=status.HTTP_200_OK
            )

        # Reject all other quotations for this job
        Quotation.objects.filter(
            job=quotation.job
        ).exclude(
            id=quotation.id
        ).update(status="rejected")

        # Accept selected quotation
        quotation.status = "accepted"
        quotation.save()

        # Optional: update job status
        quotation.job.status = "quoted"
        quotation.job.save()

        return Response(
            {
                "message": "Quotation accepted successfully.",
                "quotation_id": quotation.id,
            },
            status=status.HTTP_200_OK,
        )
    

class FeedbackListCreateView(generics.ListCreateAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        - Admins can view all feedback.
        - Logged-in users can view only their own feedback.
        - Anonymous users cannot list feedback.
        """

        if not self.request.user.is_authenticated:
            return Feedback.objects.none()

        if is_admin_user(self.request.user):
            return Feedback.objects.all().order_by("-created_at")

        return Feedback.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        """
        Save the logged-in user if available.
        Otherwise allow anonymous feedback.
        """

        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

class FeedbackDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if is_admin_user(self.request.user):
            return Feedback.objects.all().order_by('-created_at')
        return Feedback.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_update(self, serializer):
        # Only admins can update/resolve feedback.
        if not is_admin_user(self.request.user):
            raise PermissionDenied('Only admins can update feedback status.')
        serializer.save()

    def perform_destroy(self, instance):
        if not is_admin_user(self.request.user):
            raise PermissionDenied('Only admins can delete feedback.')
        instance.delete()


class RejectQuotationView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, quotation_id):
        quotation = get_object_or_404(
            Quotation,
            id=quotation_id
        )

        if quotation.job.customer.username != request.user.username:
            raise PermissionDenied(
                "Only the job owner can reject quotations."
            )


        quotation.status = "rejected"
        quotation.save()

        return Response(
            {"message": "Quotation rejected."},
            status=status.HTTP_200_OK
        )    
