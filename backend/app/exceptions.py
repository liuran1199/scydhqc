class AppError(Exception):
    def __init__(self, status: int, msg: str, code: str = "ERROR"):
        self.status, self.msg, self.code = status, msg, code
