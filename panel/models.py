import uuid
from django.db import models


class User(models.Model):
    ROLE_CHOICES = (
        ('A', 'Администратор'),
        ('B', 'Ст. Менеджер'),
        ('V', 'Менеджер'), 
        ('G', 'Водитель'),
        ('D', 'Рабочий цеха'),
        ('E', 'Маляр'),
        ('F', 'Менеджер в цеху')
    )
    
    id = models.BigIntegerField('Идентификатор Телеграм', primary_key=True, blank=False)

    username = models.CharField('Юзернейм', max_length=64, null=True, blank=True)
    first_name = models.CharField('Имя', null=True, blank=True)
    last_name = models.CharField('Фамилия', null=True, blank=True)

    role = models.CharField(max_length=1, choices=ROLE_CHOICES, verbose_name="Роль", blank=True, null=True)
    
    created_at = models.DateTimeField('Дата регистрации', auto_now_add=True, blank=True)

    data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f'id{self.id} | @{self.username or "-"} {self.first_name or "-"} {self.role or "-"}'

    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        
        
class Client(models.Model):
    phone_number = models.CharField(max_length=20, verbose_name="Номер телефона")
    name = models.CharField(max_length=255, verbose_name="Имя клиента")
    address = models.TextField(blank=True, null=True, verbose_name="Адрес клиента")

    def __str__(self):
        return f"{self.name} | {self.address} | {self.phone_number} "
    
    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
    
    
class Order(models.Model):
    ORDER_TYPE_CHOICES = (
        ('measurement', 'Замер'),
        ('delivery', 'Самостоятельный замер'),
    )
    MEASUREMENT_SUBTYPE_CHOICES = (
        ('city', 'Город'),
        ('intercity', 'Межгород'),
    )
    DELIVERY_SUBTYPE_CHOICES = (
        ('city', 'Город'),
        ('intercity', 'Межгород'),
        ('pickup', 'Самовывоз'),
    )
    WINDOW_STYLE_CHOISES = (
        ('w_type_1', 'ПВХ'),
        ('w_type_2', 'Фасад'),
        ('w_type_3', 'Деревянные'),
        ('w_type_4', 'Раздвижные'),
    )
    WINDOW_TYPE_CHOICES = (
        ('type_1', 'Решетка на замках'),
        ('type_2', 'Решетка на шпингалете'),
        ('type_3', 'Вольер'),
        ('type_4', 'Ограничитель'),
        ('type_5', 'Дверь'),
        ('type_6', 'Нестандарт(На барашках)'),
    )
    WORK_PLACE_CHOICES = (
        ('first', 'Стол 1'),
        ('second', 'Стол 2'),
        ('thirt', 'Стол 3'),
    )
    STATUS_CHOICES = (
        ('created', 'Создан'),
        ('accepted', 'Принят'),
        ('measurement_added', 'Замер внесён'),
        ('take_size', 'Замер принят'),
        ('sent_to_size', 'Отправлен на замер'),
        ('sent_to_workshop', 'Отправлен в цех'),
        ('workshop_completed', 'Завершён цехом'),
        ('on_delivery', 'На доставке'),
        ('completed', 'Завершён'),
        ('canceled', 'Отменён'),
    )
    PAYMENT_STATUS_CHOICES = (
        ('full_payment', 'Полная оплата'),
        ('advance', 'Аванс'),
        ('awaiting_payment', 'Ожидает доплаты'),
    )


    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='orders', verbose_name="Клиент", blank=True, null=True)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, verbose_name="Тип заказа", blank=True, null=True)
    subtype = models.CharField(max_length=50, blank=True, null=True, verbose_name="Подтип заказа", editable=False)
    #window_type = models.CharField(max_length=30, choices=WINDOW_TYPE_CHOICES, blank=True, null=True, verbose_name="Тип окна (для замера)")
    type_1_count = models.IntegerField(default=0, verbose_name='ПВХ, количество')
    type_2_count = models.IntegerField(default=0, verbose_name='Фасад, количество')
    type_3_count = models.IntegerField(default=0, verbose_name='Деревянные, количество')
    type_4_count = models.IntegerField(default=0, verbose_name='Раздвижные, количество')

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='created', verbose_name="Статус заказа")
    responsible_employee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name="Ответственный сотрудник")
    chat_location = models.CharField(max_length=50, blank=True, null=True, verbose_name="Чат, в котором находится заказ")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время создания")
    work_place_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата отправки в цех')
    work_place_at_end = models.DateTimeField(null=True, blank=True, verbose_name='Дата завершения в цеху')
    size_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата начала замера')
    size_at_end = models.DateTimeField(null=True, blank=True, verbose_name='Дата завершения замера')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время завершения")
    
    measurement_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Стоимость замера")
    genral_cost_info = models.CharField(null=True, blank=True, verbose_name='Статус оплаты')
    comments = models.TextField(null=True, blank=True, verbose_name='Коментарии')
    sizes = models.TextField(null=True, blank=True, verbose_name='Замеры')
    
    choise_pay = models.CharField(null=True, blank=True, verbose_name='Способ оплаты')

    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, blank=True, null=True, verbose_name="Статус оплаты", editable=False)
    current_work_place = models.CharField(max_length=20, choices=WORK_PLACE_CHOICES, null=True, blank=True, verbose_name='Стол в цехе')

    cancellation_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cans_orders', verbose_name="Отменивший сотрудник")
    cancellation_reason = models.TextField(blank=True, null=True, verbose_name="Причина отмены")
    
    current_caption = models.TextField(null=True, blank=True, verbose_name='Текущее сообщение заказа')

    active_messages_info = models.JSONField(
        default=dict, 
        blank=True, 
        null=True,
        editable=False,
    )


    def __str__(self):
        address_info = (self.client and self.client.address) or 'Клиент не привязан к заказу'
        return f"Заказ {self.id} на адрес: {address_info}"
    
    
    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
    
    
class OrderPhoto(models.Model):
    order = models.ForeignKey(Order, related_name='photos', on_delete=models.CASCADE)
    file_id = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Фото для заказа №{self.order.id}"
    
    
class OrderItem(models.Model):
    PRODUCT_TYPE_CHOICES = (
        ('type_1', 'Решетка на замках'),
        ('type_2', 'Решетка на шпингалете'),
        ('type_3', 'Вольер'),
        ('type_4', 'Ограничитель'),
        ('type_5', 'Дверь'),
        ('type_6', 'Нестандарт(На барашках)'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Заказ")
    product_type = models.CharField(max_length=30, choices=PRODUCT_TYPE_CHOICES, verbose_name="Тип изделия")
    
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    size = models.CharField(max_length=100, blank=True, null=True, verbose_name="Размер")
    color = models.CharField(max_length=100, blank=True, null=True, verbose_name="Цвет")
    price = models.IntegerField(default=0, verbose_name="Цена за единицу")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    def __str__(self):
        return f'{self.get_product_type_display()} ({self.quantity} шт.) для заказа №{self.order.id}'
    

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'
        
        
class OrderAssignmentLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='assignment_logs')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignment_logs')
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name="Время назначения")

    def __str__(self):
        return f"Заказ №{self.order.id} назначен {self.employee} в {self.assigned_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = 'Запись о назначении заказа'
        verbose_name_plural = 'Журнал назначений заказов'