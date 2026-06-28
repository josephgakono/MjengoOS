from rest_framework import serializers
from .mpesa import normalize_mpesa_phone_number
from .models import User, WorkerProfile, CustomerProfile, Job, Quotation, Project, Payment, ProgressUpdate, Review, Portfolio, Message, Notification


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'profile_picture',
            'user_type',
        ]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'password',
            'user_type',
            'phone',
            'profile_picture',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        if user.user_type == "customer":
            CustomerProfile.objects.get_or_create(
                user=user,
                defaults={
                    "location": "",
                    "preferred_contact": "Phone",
                },
            )

        elif user.user_type in ["worker", "contractor"]:
            WorkerProfile.objects.get_or_create(
                user=user,
                defaults={
                    "profession": "",
                    "experience_years": 0,
                    "location": "",
                    "bio": "",
                    "hourly_rate": 0,
                },
            )

        return user


class WorkerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerProfile
        fields = '__all__'
        read_only_fields = ['user']


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = '__all__'


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = '__all__'
        read_only_fields = ['customer']


class QuotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        fields = '__all__'
        read_only_fields = [
            'worker',
            'status'
        ]


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = [
            'customer',
            'status',
            'checkout_request_id',
            'mpesa_receipt_number',
            'transaction_date',
            'escrow_status',
            'released_at',
            'created_at',
        ]

    def validate_phone_number(self, value):
        try:
            return normalize_mpesa_phone_number(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))


class StkPushSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    phone_number = serializers.CharField(max_length=15)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
    payment_type = serializers.ChoiceField(choices=Payment.PAYMENT_TYPE_CHOICES)

    def validate_phone_number(self, value):
        try:
            return normalize_mpesa_phone_number(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))


class ProgressUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgressUpdate
        fields = '__all__'


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['customer']


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = '__all__'
        read_only_fields = ['worker']


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'
        read_only_fields = ['sender']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'

