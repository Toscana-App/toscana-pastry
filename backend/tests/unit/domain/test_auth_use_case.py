
import pytest
from domain.use_cases.authenticate_user import AuthenticateUser

class MockUserRepository:
    def __init__(self):
        self.user = None

    async def get_by_email(self, email):
        return self.user

    async def get_by_google_id(self, google_id):
        return self.user

    async def save(self, user):
        self.user = user
        return user

@pytest.mark.asyncio
async def test_authenticate_with_google_new_user():
    repo = MockUserRepository()
    use_case = AuthenticateUser(repo)
    
    user = await use_case.execute(email="new@example.com", google_id="google-123")
    
    assert user.email == "new@example.com"
    assert user.google_id == "google-123"
    assert repo.user is not None

@pytest.mark.asyncio
async def test_authenticate_with_email_new_user():
    repo = MockUserRepository()
    use_case = AuthenticateUser(repo)
    
    user = await use_case.execute(email="new@example.com")
    
    assert user.email == "new@example.com"
    assert user.google_id is None
    assert repo.user is not None

@pytest.mark.asyncio
async def test_authenticate_no_params_raises_error():
    repo = MockUserRepository()
    use_case = AuthenticateUser(repo)
    
    with pytest.raises(ValueError, match="At least one authentication method must be provided"):
        await use_case.execute()
