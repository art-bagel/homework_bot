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
    APIUnauthorized, ConnectionError)
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


def send_message(bot: telegram.Bot, message: str) -> bool:
    """Отправляет сообщение о статусе работы пользователю в телеграмм."""
    try:
        bot.sendMessage(TELEGRAM_CHAT_ID, message)
        logging.info(f'Сообщение {message} отправлено!')
        return True
    except telegram.TelegramError as error:
        logger.error(f'Сообщение ({message}) не отправлено! '
                     f'Возникла ошибка: {error}')
        return False


def get_api_answer(current_timestamp: int) -> Dict[str, Any]:
    """Запрашивает статус домашней работы у АPI практикума."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        response.raise_for_status()
        homework_status = response.json()
        logger.info('Запрос к API выполнен успешно')
        return homework_status
    except requests.exceptions.HTTPError as error:
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            raise APIUnauthorized(
                'Предоставлены некорректные учетные данные')
        elif response.status_code == HTTPStatus.BAD_REQUEST:
            raise APIIncorrectParametersError(
                'Некорректный формат переданного параметра from_date')
        raise APIRequestError(f'HTTPError {error}')
    except requests.exceptions.ConnectionError:
        raise ConnectionError('Возникли проблемы с соединением')
    except requests.exceptions.Timeout:
        raise APITimeoutError('Истекло время ожидания ответа  от сервера')
    except requests.exceptions.RequestException:
        raise APIRequestError(f'Ошибка при запросе к эндпоинту: {ENDPOINT}')
    except Exception as error:
        raise APIRequestError(f'Проблемы при обращении к API: {error}')


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
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        raise TypeError(
            'Значение по ключу homeworks не является списком')
    return homework


def parse_status(homework: Dict[str, Any]) -> str:
    """Формирует сообщение о статусе домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError('Отсутствует ключ homework_name')
    if homework_status is None:
        raise KeyError('Отсутствует ключ status')
    if homework_status not in HOMEWORK_STATUSES:
        raise ValueError(
            f'Неизвестный статус работы: {homework_status}')
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
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time() - (30 * 24 * 60 * 60))
    last_message, new_message, homework_status = None, None, None
    while True:
        try:
            homework_status = get_api_answer(current_timestamp)
            homeworks = check_response(homework_status)
            if homeworks:
                new_message = parse_status(homeworks[0])
            else:
                logger.debug('Статус работы не изменился')
        except Exception as error:
            new_message = str(error)
            logger.error(new_message)
        else:
            current_timestamp = homework_status.get('current_date')
        finally:
            if last_message != new_message and send_message(bot, new_message):
                last_message = new_message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
