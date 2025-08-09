import openpyxl

from openpyxl.styles import Font
from io import BytesIO

from django.contrib import admin
from panel.models import *
from django.http import HttpResponse


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'first_name', 'last_name', 'role')
    fields = ('id', 'username', 'first_name', 'last_name', 'role')

    exclude = ('data',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem  
    
    fields = ('product_type', 'quantity', 'size', 'color', 'price',)
    
    extra = 1  
    

def auto_adjust_column_width(worksheet):
    for column_cells in worksheet.columns:
        max_length = 0
        column_letter = column_cells[0].column_letter 
        for cell in column_cells:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        
        adjusted_width = (max_length + 2)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def export_to_excel(modeladmin, request, queryset):
    wb = openpyxl.Workbook()
    ws_clients = wb.create_sheet("Клиенты")
    ws_orders = wb.create_sheet("Заказы")
    ws_users = wb.create_sheet("Сотрудники")
    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])

    client_row_map = {}
    user_row_map = {}
    
    bold_font = Font(bold=True)

    user_headers = ['ID Сотрудника', 'Юзернейм', 'Имя', 'Фамилия', 'Роль', 'Дата регистрации']
    ws_users.append(user_headers)
    for cell in ws_users[1]: 
        cell.font = bold_font 

    users = User.objects.all()
    for row_num, user in enumerate(users, 2):
        ws_users.append([
            user.id, user.username, user.first_name, user.last_name,
            user.get_role_display(),
            user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else ''
        ])
        user_row_map[user.id] = row_num

    
    client_headers = ['ID Клиента', 'Имя', 'Номер телефона', 'Адрес']
    ws_clients.append(client_headers)
    for cell in ws_clients[1]:
        cell.font = bold_font

    clients = Client.objects.all()
    for row_num, client in enumerate(clients, 2):
        ws_clients.append([client.id, client.name, client.phone_number, client.address])
        client_row_map[client.id] = row_num

    order_headers = [
        'ID Заказа', 'Клиент', 'Тип заказа', 'Подтип', 'Статус', 'Ответственный сотрудник',
        'Стоимость замера', 'Расчет', 'Комментарии', 'Замеры', 'Способ оплаты', 'Статус оплаты',
        'Стол в цехе', 'Отменивший сотрудник', 'Причина отмены', 'Дата создания',
        'Решетка на замках (кол-во)', 'Решетка на шпингалете (кол-во)', 'Вольер (кол-во)',
        'Ограничитель (кол-во)', 'Дверь (кол-во)', 'Нестандарт (кол-во)'
    ]
    ws_orders.append(order_headers)
    for cell in ws_orders[1]:
        cell.font = bold_font

    orders = Order.objects.all().select_related('client', 'responsible_employee', 'cancellation_user')
    for row_num, order in enumerate(orders, 2):
        client_cell_value = str(order.client) if order.client else "N/A"
        responsible_cell_value = str(order.responsible_employee) if order.responsible_employee else "N/A"
        canceled_by_cell_value = str(order.cancellation_user) if order.cancellation_user else "N/A"
        
        row_data = [
            order.id, client_cell_value, order.get_order_type_display(), order.subtype,
            order.get_status_display(), responsible_cell_value, order.measurement_cost,
            order.genral_cost_info, order.comments, order.sizes, order.choise_pay,
            order.get_payment_status_display(), order.get_current_work_place_display(),
            canceled_by_cell_value, order.cancellation_reason,
            order.created_at.strftime('%Y-%m-%d %H:%M') if order.created_at else '',
            order.type_1_count, order.type_2_count, order.type_3_count,
            order.type_4_count, order.type_5_count, order.type_6_count,
        ]
        ws_orders.append(row_data)

        if order.client and order.client.id in client_row_map:
            client_row_in_excel = client_row_map[order.client.id]
            client_cell = ws_orders.cell(row=row_num, column=2)
            client_cell.hyperlink = f"#'Клиенты'!A{client_row_in_excel}"
            client_cell.style = "Hyperlink"

        if order.responsible_employee and order.responsible_employee.id in user_row_map:
            user_row_in_excel = user_row_map[order.responsible_employee.id]
            user_cell = ws_orders.cell(row=row_num, column=6)
            user_cell.hyperlink = f"#'Сотрудники'!A{user_row_in_excel}"
            user_cell.style = "Hyperlink"

        if order.cancellation_user and order.cancellation_user.id in user_row_map:
            user_row_in_excel = user_row_map[order.cancellation_user.id]
            cancel_user_cell = ws_orders.cell(row=row_num, column=14)
            cancel_user_cell.hyperlink = f"#'Сотрудники'!A{user_row_in_excel}"
            cancel_user_cell.style = "Hyperlink"

    
    auto_adjust_column_width(ws_clients)
    auto_adjust_column_width(ws_orders)
    auto_adjust_column_width(ws_users)
    
    
    virtual_workbook = BytesIO()
    wb.save(virtual_workbook)
    virtual_workbook.seek(0)
    
    response = HttpResponse(
        virtual_workbook.read(), 
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="orders_report.xlsx"'
    
    return response



export_to_excel.short_description = "Экспортировать все данные в Excel"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    search_fields = [
        'id', 
        'client__name', 
        'client__phone_number',
        'client__address',
    ]

    list_filter = ('status', 'order_type')
    
    actions = [export_to_excel]
    
    inlines = [
        OrderItemInline,
    ]

admin.site.register(Client)


