import json
import time 
import requests
import logging

from celery import shared_task

from config import config
from .models import StartOrder

logger = logging.getLogger(__name__)

@shared_task
def send_first_message(id: int):
    try:
        order = StartOrder.objects.get(id=id)
    except StartOrder.DoesNotExist:
        print('Не получается найти рассылку, возможно она была удалена')
        return

    
    try:
        response = requests.post(
            url=f'https://api.telegram.org/bot{config.BOT_WORKER_TOKEN}/sendMessage',
            json={
                'chat_id': order.chat_id,
                'text': order.capture,
            }
        )
        
        logger.info(f"Ответ от Telegram для чата {response.text}")

        response.raise_for_status() 
    except Exception as e:
        logger.error(f"HTTP ошибка при отправке в чат: {e}")