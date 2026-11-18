from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


class SessionCodec:
    def __init__(self, secret: str, max_age: int):
        self.s = URLSafeTimedSerializer(secret)
        self.max_age = max_age

    def dumps(self, data: dict) -> str:
        return self.s.dumps(data)

    def loads(self, token: str) -> dict | None:
        try:
            return self.s.loads(token, max_age=self.max_age)
        except (BadSignature, SignatureExpired):
            return None
