import logging.config
import os
import sys
import time
from http import HTTPStatus
from typing import Any, Dict, List

import requests
import telegram
from dotenv import load_dotenv

from exeptions import (
    APIIncorrectParametersError, APIRequestError, APITimeoutError,
    APIUnauthorized, ConnectionError, TelegramError)
from loging_config import LOGGING_CONFIG


load_dotenv()

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('homework')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение о статусе работы пользователю в телеграмм."""
    try:
        logging.info(f'Отправляем сообщение: {message}')
        bot.sendMessage(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение {message} отправлено!')
    except telegram.TelegramError as error:
        raise TelegramError(f'Сообщение ({message}) не отправлено! '
                            f'Возникла ошибка: {error}')


def get_api_answer(current_timestamp: int) -> Dict[str, Any]:
    """Запрашивает статус домашней работы у АPI практикума."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            raise APIUnauthorized(
                'Предоставлены некорректные учетные данные')
        if response.status_code == HTTPStatus.BAD_REQUEST:
            raise APIIncorrectParametersError(
                'Некорректный формат переданного параметра from_date')
        if response.status_code != HTTPStatus.OK:
            raise APIRequestError(f'HTTPError: code - {response.status_code}')
    except requests.exceptions.ConnectionError:
        raise ConnectionError('Возникли проблемы с соединением')
    except requests.exceptions.Timeout:
        raise APITimeoutError('Истекло время ожидания ответа  от сервера')
    except requests.exceptions.RequestException:
        raise APIRequestError(f'Ошибка при запросе к эндпоинту: {ENDPOINT}')
    else:
        return response.json()


def check_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Проверяет ответ API на корретность данных."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        raise KeyError(
            'Ключ homeworks отсутствует в ответе API')
    if 'current_date' not in response:
        raise KeyError(
            'Ключ current_date отсутствует в ответе API')
    current_date = response.get('current_date')
    homework = response.get('homeworks')
    if not isinstance(current_date, int):
        raise TypeError(
            'Значение по ключу current_date не является целым числом')
    if not isinstance(homework, list):
        raise TypeError(
            'Значение по ключу homeworks не является списком')
    return homework


def parse_status(homework: Dict[str, Any]) -> str:
    """Формирует сообщение о статусе домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ homework_name')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ status')
    if homework['status'] not in HOMEWORK_STATUSES:
        raise ValueError(
            f'Неизвестный статус работы: {homework["status"]}')
    verdict = HOMEWORK_STATUSES.get(homework['status'])
    return 'Изменился статус проверки работы "{}". {}'.format(
        homework['homework_name'], verdict)


def check_tokens() -> bool:
    """Проверяем наличие всех api токенов."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения: '
                        'PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID')
        sys.exit('Отсутствуют обязательные переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message, new_message, homework_status = None, None, None
    while True:
        try:
            homework_status = get_api_answer(current_timestamp)
            homeworks = check_response(homework_status)
            if homeworks:
                new_message = parse_status(homeworks[0])
                send_message(bot, new_message)
            else:
                logger.debug('Статус работы не изменился')
            current_timestamp = homework_status.get('current_date')
        except TelegramError as error:
            logger.error(error)
        except Exception as error:
            logger.error(error)
            new_message = str(error)
            if new_message != last_message:
                send_message(bot, new_message)
                last_message = new_message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
