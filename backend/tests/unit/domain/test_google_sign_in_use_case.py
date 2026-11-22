from domain.models import User, UserRole
from domain.use_cases import GoogleSignIn

PAYLOAD = {
    "sub": "google-sub-1",
    "email": "user@gmail.com",
    "email_verified": True,
    "nonce": "n",
}


class FakeUserRepository:
    def __init__(self, by_google_id=None, by_email=None):
        self.by_google_id = by_google_id
        self.by_email = by_email
        self.saved = []

    async def get_by_google_id(self, google_id):
        return self.by_google_id

    async def get_by_email(self, email):
        return self.by_email

    async def save(self, user):
        self.saved.append(user)
        return user


async def test_existing_google_id_logs_in_without_asking_about_email():
    user = User(email="other@gmail.com", google_id="google-sub-1", role=UserRole.NEGOCIO)
    repo = FakeUserRepository(by_google_id=user, by_email=User(email="x@y.com"))
    outcome = await GoogleSignIn(repo, auto_create=True).execute(dict(PAYLOAD))
    assert outcome.state == "signed_in"
    assert outcome.user is user
    assert repo.saved == []


async def test_email_match_without_google_id_is_always_link_pending():
    # Even with a verified gmail: RF-P1-10 forbids auto-linking by email.
    existing = User(email="user@gmail.com", role=UserRole.CUSTOMER)
    repo = FakeUserRepository(by_google_id=None, by_email=existing)
    outcome = await GoogleSignIn(repo, auto_create=True).execute(dict(PAYLOAD))
    assert outcome.state == "link_pending"
    assert outcome.user is existing
    assert repo.saved == []


async def test_unverified_gmail_email_match_is_also_link_pending():
    payload = dict(PAYLOAD, email_verified=False)
    existing = User(email="user@gmail.com")
    repo = FakeUserRepository(by_google_id=None, by_email=existing)
    outcome = await GoogleSignIn(repo, auto_create=True).execute(payload)
    assert outcome.state == "link_pending"


async def test_new_email_creates_user_when_auto_create_is_on():
    repo = FakeUserRepository(by_google_id=None, by_email=None)
    outcome = await GoogleSignIn(repo, auto_create=True).execute(dict(PAYLOAD))
    assert outcome.state == "signed_in"
    assert len(repo.saved) == 1
    created = repo.saved[0]
    assert created.google_id == "google-sub-1"
    assert created.email == "user@gmail.com"
    assert created.role == UserRole.CUSTOMER
    assert outcome.user is created


async def test_new_email_is_no_account_when_auto_create_is_off():
    repo = FakeUserRepository(by_google_id=None, by_email=None)
    outcome = await GoogleSignIn(repo, auto_create=False).execute(dict(PAYLOAD))
    assert outcome.state == "no_account"
    assert outcome.user is None
    assert repo.saved == []
