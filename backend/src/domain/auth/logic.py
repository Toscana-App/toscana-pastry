
from datetime import datetime, timedelta

class MagicLinkToken:
    def __init__(self, user_email: str):
        self.user_email = user_email
        self._original_email = user_email # Store original for integrity
        self.token = None
        self.expiry = None

    def generate(self) -> str:
        self.token = f"token-{self.user_email}"
        self.expiry = datetime.utcnow() + timedelta(minutes=15)
        return self.token

    def validate(self) -> bool:
        if self.expiry < datetime.utcnow():
            return False
        if self.user_email != self._original_email:
            return False
        return True

def validate_google_id_token(payload: dict) -> dict:
    if "sub" not in payload:
        raise ValueError("Missing 'sub' in payload")
    if not payload.get("email_verified"):
        raise ValueError("Email not verified")
    
    return {
        "google_id": payload["sub"],
        "email": payload["email"]
    }
