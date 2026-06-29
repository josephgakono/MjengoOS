from rest_framework import permissions

from .models import CustomerProfile


def is_admin_user(user):
    return bool(
        user
        and user.is_authenticated
        and (user.user_type == 'admin' or user.is_staff or user.is_superuser)
    )


def has_customer_profile(user):
    return bool(
        user
        and user.is_authenticated
        and CustomerProfile.objects.filter(user=user).exists()
    )


class IsAdmin(permissions.BasePermission):
    """Allow platform admins to view, edit, and delete every resource."""

    def has_permission(self, request, view):
        return is_admin_user(request.user)

    def has_object_permission(self, request, view, obj):
        return is_admin_user(request.user)


class IsCustomer(permissions.BasePermission):
    """Allow only authenticated customers, while preserving admin override."""

    def has_permission(self, request, view):
        return is_admin_user(request.user) or (
            request.user.is_authenticated and request.user.user_type == 'customer'
        )


class HasCustomerProfile(permissions.BasePermission):
    """Allow only authenticated users who have completed a customer profile."""

    message = 'A customer profile is required to create this resource.'

    def has_permission(self, request, view):
        return has_customer_profile(request.user)


class IsWorker(permissions.BasePermission):
    """Allow only authenticated workers, while preserving admin override."""

    def has_permission(self, request, view):
        return is_admin_user(request.user) or (
            request.user.is_authenticated and request.user.user_type == 'worker'
        )


class IsContractor(permissions.BasePermission):
    """Allow only authenticated contractors, while preserving admin override."""

    def has_permission(self, request, view):
        return is_admin_user(request.user) or (
            request.user.is_authenticated and request.user.user_type == 'contractor'
        )


class IsJobOwner(permissions.BasePermission):
    """Allow write access only to the customer who owns a job."""

    def has_object_permission(self, request, view, obj):
        if is_admin_user(request.user):
            return True

        job = getattr(obj, 'job', obj)
        job_customer_username = getattr(job, 'customer', None)
        return bool(job_customer_username and job_customer_username.username == request.user.username)



class IsProjectWorker(permissions.BasePermission):
    """Allow access only to the worker assigned to a project."""

    def has_object_permission(self, request, view, obj):
        if is_admin_user(request.user):
            return True

        project = getattr(obj, 'project', obj)
        worker = getattr(project, 'worker', None)
        return bool(worker and worker.user.username == request.user.username)



class IsProjectCustomer(permissions.BasePermission):
    """Allow access only to the customer who owns a project's job."""

    def has_object_permission(self, request, view, obj):
        if is_admin_user(request.user):
            return True

        project = getattr(obj, 'project', obj)
        job = getattr(project, 'job', None)
        return bool(job and job.customer.username == request.user.username)

