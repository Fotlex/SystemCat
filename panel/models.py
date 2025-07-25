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
        ('F', 'Замерщик'),
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
    type_1_count = models.IntegerField(default=0, verbose_name='Решетка на замках, количество')
    type_2_count = models.IntegerField(default=0, verbose_name='Решетка на шпингалете, количество')
    type_3_count = models.IntegerField(default=0, verbose_name='Вольер, количество')
    type_4_count = models.IntegerField(default=0, verbose_name='Ограничитель, количество')
    type_5_count = models.IntegerField(default=0, verbose_name='Дверь, количество')
    type_6_count = models.IntegerField(default=0, verbose_name='Нестандарт(На барашках)')

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='created', verbose_name="Статус заказа")
    responsible_employee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name="Ответственный сотрудник")
    chat_location = models.CharField(max_length=50, blank=True, null=True, verbose_name="Чат, в котором находится заказ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время создания")

    measurement_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Стоимость замера")
    product_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Стоимость изделия")
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Стоимость монтажа")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, blank=True, null=True, verbose_name="Статус оплаты", editable=False)
    current_work_place = models.CharField(max_length=20, choices=WORK_PLACE_CHOICES, null=True, blank=True, verbose_name='Стол в цехе')

    cancellation_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cans_orders', verbose_name="Отменивший сотрудник")
    cancellation_reason = models.TextField(blank=True, null=True, verbose_name="Причина отмены")
    canceled_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата и время отмены", editable=False)
    
    current_caption = models.TextField(null=True, blank=True, editable=False)

    active_messages_info = models.JSONField(
        default=dict, 
        blank=True, 
        null=True,
        editable=False,
    )


    def __str__(self):
        return f"Заказ {self.id}"
    
    
    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
    
    
class OrderPhoto(models.Model):
    order = models.ForeignKey(Order, related_name='photos', on_delete=models.CASCADE)
    file_id = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Фото для заказа №{self.order.id}"