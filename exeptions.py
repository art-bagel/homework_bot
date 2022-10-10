
class APIRequestError(Exception):
    """Вызывается при возникновении проблем с API Яндекс-практикума."""

    pass


class APITimeoutError(Exception):
    """Вызывается при истечении ожидания ответа от сервера."""

    pass


class APIUnauthorized(Exception):
    """Вызывается при передаче некорректный данных авторизации."""

    pass


class ConnectionError(Exception):
    """Вызывается при проблеме с соединением."""

    pass


class APIIncorrectParametersError(Exception):
    """Вызывается если в запросе переданы некорректные параметры."""

    pass
