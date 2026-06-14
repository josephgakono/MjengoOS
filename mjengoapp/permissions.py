from rest_framework import permissions


def is_admin_user(user):
    return bool(
        user
        and user.is_authenticated
        and (user.user_type == 'admin' or user.is_staff or user.is_superuser)
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
        return getattr(job, 'customer_id', None) == request.user.id


class IsProjectWorker(permissions.BasePermission):
    """Allow access only to the worker assigned to a project."""

    def has_object_permission(self, request, view, obj):
        if is_admin_user(request.user):
            return True

        project = getattr(obj, 'project', obj)
        worker = getattr(project, 'worker', None)
        return bool(worker and worker.user_id == request.user.id)


class IsProjectCustomer(permissions.BasePermission):
    """Allow access only to the customer who owns a project's job."""

    def has_object_permission(self, request, view, obj):
        if is_admin_user(request.user):
            return True

        project = getattr(obj, 'project', obj)
        job = getattr(project, 'job', None)
        return bool(job and job.customer_id == request.user.id)
