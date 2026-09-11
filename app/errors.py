class APIError(Exception):
    """可直接转换为统一 HTTP 错误的业务异常。"""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
