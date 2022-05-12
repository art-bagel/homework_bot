import logging.config
import os
import time

import requests
import telegram
from requests import ConnectionError, HTTPError
from dotenv import load_dotenv

from loging_config import LOGGING_CONFIG

load_dotenv()

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('homework')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/1'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message) -> bool:
    """Отправляет сообщение о статусе работы пользователю в телеграмм."""
    try:
        bot.sendMessage(TELEGRAM_CHAT_ID, message)
        return True
    except Exception as error:
        logger.error(f'Сообщение ({message}) не отправлено! '
                     f'Возникла ошибка {error}')
        return False


def get_api_answer(current_timestamp):
    """Запрашивает статус домашней работы у АPI практикума."""
    params = {'from_date': current_timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()


def check_response(response):
    """Проверяет ответ api на корретность данных."""
    return response.get('homeworks')


def parse_status(homework):
    """Формирует сообщение о статусе домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверяем наличие всех api токенов."""
    is_tokens = True
    if not PRACTICUM_TOKEN:
        logger.critical(
            'Отсутствует обязательная переменная окружения: PRACTICUM_TOKEN')
        is_tokens = False
    if not TELEGRAM_TOKEN:
        logger.critical(
            'Отсутствует обязательная переменная окружения: TELEGRAM_TOKEN')
        is_tokens = False
    if not TELEGRAM_CHAT_ID:
        logger.critical(
            'Отсутствует обязательная переменная окружения: TELEGRAM_CHAT_ID')
        is_tokens = False
    return is_tokens


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return None
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time() - (30 * 24 * 60 * 60))
    message_last, message_new = '', ''
    while True:
        try:
            homework_status = get_api_answer(current_timestamp)
            homeworks = check_response(homework_status)
            if homeworks:
                message_new = parse_status(homeworks[0])
                current_timestamp = homework_status.get('current_date')
        except HTTPError as error:
            message_new = f'Хьюстон у нас проблемы: {error}'
            logger.error(message_new)
        except ConnectionError as error:
            logger.error(f'Проблемы соединения с сетью интернет: {error}')
            time.sleep(RETRY_TIME)
            continue
        except Exception as error:
            message_new = f'Сбой в работе программы: {error}'
            logger.error(message_new)
        else:
            ...
        finally:
            if message_last != message_new and send_message(bot, message_new):
                message_last = message_new

            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
