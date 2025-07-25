# Generated by Django 5.2.1 on 2025-07-24 08:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('panel', '0007_alter_order_delivery_cost_alter_order_status'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='client',
            options={'verbose_name': 'Клиент', 'verbose_name_plural': 'Клиенты'},
        ),
        migrations.AlterField(
            model_name='order',
            name='cancellation_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cans_orders', to='panel.user', verbose_name='Отменивший сотрудник'),
        ),
        migrations.AlterField(
            model_name='order',
            name='current_work_place',
            field=models.CharField(blank=True, choices=[('first', 'Стол 1'), ('second', 'Стол 2'), ('thirt', 'Стол 3')], max_length=20, null=True, verbose_name='Стол в цехе'),
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_status',
            field=models.CharField(blank=True, choices=[('full_payment', 'Полная оплата'), ('advance', 'Аванс'), ('awaiting_payment', 'Ожидает доплаты')], editable=False, max_length=20, null=True, verbose_name='Статус оплаты'),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('created', 'Создан'), ('accepted', 'Принят'), ('measurement_added', 'Замер внесён'), ('sent_to_size', 'Отправлен на замер'), ('sent_to_workshop', 'Отправлен в цех'), ('workshop_completed', 'Завершён цехом'), ('on_delivery', 'На доставке'), ('completed', 'Завершён'), ('canceled', 'Отменён')], default='created', max_length=30, verbose_name='Статус заказа'),
        ),
        migrations.AlterField(
            model_name='order',
            name='subtype',
            field=models.CharField(blank=True, editable=False, max_length=50, null=True, verbose_name='Подтип заказа'),
        ),
    ]
