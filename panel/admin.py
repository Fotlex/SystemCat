from django.contrib import admin
from panel.models import *


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'first_name', 'last_name', 'role')
    fields = ('id', 'username', 'first_name', 'last_name', 'role')

    exclude = ('data',)


admin.site.register(Client)
admin.site.register(Order)
