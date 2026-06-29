from django.contrib import admin
from .models import *

admin.site.register(User)
admin.site.register(WorkerProfile)
admin.site.register(CustomerProfile)
admin.site.register(Job)
admin.site.register(Quotation)
admin.site.register(Project)
admin.site.register(ProgressUpdate)
admin.site.register(Review)
admin.site.register(Portfolio)
admin.site.register(Message)
admin.site.register(Notification)
admin.site.register(Feedback)

# Register your models here.

