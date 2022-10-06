import http
import logging
import os

from telegram import Bot, Update
from telegram.ext import CallbackContext, CommandHandler, Updater
import requests
import time
from dotenv import load_dotenv

from exceptions import MessageError, PageIsNotAvailable

load_dotenv()
PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: int = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME: int = 600
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICT: dict = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s - %(lineno)s'
           ' - %(filename')
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def send_message(bot: Bot, message: str) -> None:
    """Формируем и отправляем сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение успешно отправлено: {message}')
    except MessageError:
        logger.error('сообщение не отправлено')


def get_api_answer(current_timestamp: int) -> dict:
    """Получения данных по API."""
    timestamp: int = current_timestamp
    params: dict = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=params)
        if response.status_code != http.HTTPStatus.OK:
            logger.error('Страница недоступна')
            raise PageIsNotAvailable('Страница недоступна')
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.error('Ошибка подключения')
    except requests.exceptions.RequestException as request_error:
        logger.error(f'Ошибка запроса {request_error}')


def check_response(response: dict) -> dict:
    """Проверяем ответ API на корректность."""
    if type(response) is not dict:
        raise TypeError('В функцию check_response передан не словарь.')
    if 'homeworks' not in response:
        raise KeyError('Ключ homeworks отсутствует.')
    if type(response.get('homeworks')) is not list:
        raise TypeError('Объект homeworks не является списком.')
    if response.get('homeworks') == []:
        return {}
    return response.get('homeworks')[0]


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if 'status' not in homework or type(homework) is str:
        logger.error('Ключ status отсутствует в homework')
        raise KeyError('Ключ status отсутствует в homework')
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутствует в homework')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICT.keys():
        raise ValueError('Значение не соответствует справочнику статусов')
    verdict = HOMEWORK_VERDICT[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверяем доступность переменных окружения."""
    env_variables: set = {'PRACTICUM_TOKEN',
                          'TELEGRAM_TOKEN',
                          'TELEGRAM_CHAT_ID'}
    error_env_variables: set = set()
    for variable in env_variables:
        if globals().get(variable) is None:
            error_env_variables.add(variable)

    if len(error_env_variables) != 0:
        logger.critical('Токен не задан для элемента(ов):'
                        f'{" ,".join(error_env_variables)}')
        return False
    return True


def all_homeworks(update: Update, context: CallbackContext) -> None:
    """Показать все задания."""
    response = get_api_answer(0)
    homeworks = check_response(response)
    if homeworks:
        rezult: list = list()
        for homework in homeworks:
            if 'status' not in homework or type(homework) is str:
                logger.error('Ключ status отсутствует в homework')
                raise KeyError('Ключ status отсутствует в homework')
            if 'homework_name' not in homework:
                raise KeyError('Ключ homework_name отсутствует в homework')
            homework_name = homework.get('homework_name')
            homework_status = homework.get('status')
            if homework_status not in HOMEWORK_VERDICT.keys():
                raise ValueError('Значение не соответствует'
                                 'справочнику статусов')
            verdict = HOMEWORK_VERDICT[homework_status]
            rezult.append(f'--Работа "{homework_name}"'
                          f'- статус {verdict}\n\r\n\r')
    update.message.reply_text(f'{"".join(rezult)}')


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError('Отсутствует токен')
    bot = Bot(token=TELEGRAM_TOKEN)
    updater = Updater(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            updater.dispatcher.add_handler(CommandHandler('all',
                                                          all_homeworks))
            updater.start_polling()
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework)
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)
        time.sleep(RETRY_TIME)
        current_timestamp = int(time.time() - RETRY_TIME)


if __name__ == '__main__':
    main()
