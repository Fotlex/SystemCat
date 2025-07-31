from django.contrib import admin
from panel.models import *


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'first_name', 'last_name', 'role')
    fields = ('id', 'username', 'first_name', 'last_name', 'role')

    exclude = ('data',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    search_fields = [
        'id', 
        'client__name', 
        'client__phone_number',
        'client__address',
    ]

    list_filter = ('status', 'order_type')

admin.site.register(Client)


