import os
import struct
import zlib

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from main import app
from data.accent import accent_fold
from data.models import Base
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_product_repository import SQLProductRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.products.dependencies import (
    get_media_root,
    get_product_repository,
)
from domain.models import User, UserRole


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _register_sqlite_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "accent_fold", 1, accent_fold, deterministic=True
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def media_root(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    return root


@pytest_asyncio.fixture
async def client(db_session, media_root):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_settings_repository():
        yield SQLSettingsRepository(db_session)

    async def override_get_ingredient_repository():
        yield SQLIngredientRepository(db_session)

    async def override_get_product_repository():
        yield SQLProductRepository(db_session)

    def override_get_media_root():
        return media_root

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    app.dependency_overrides[get_product_repository] = override_get_product_repository
    app.dependency_overrides[get_media_root] = override_get_media_root
    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


async def _admin_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com"}
    )
    assert response.status_code == 200
    return response.cookies["auth_token"]


async def _customer_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "customer@example.com"}
    )
    assert response.status_code == 200
    return response.cookies["auth_token"]


async def _create_product(client: AsyncClient, headers):
    ingredient = await client.post(
        "/api/v1/ingredients",
        json={
            "name": "Almendra molida",
            "unit": "kg",
            "price_per_unit": 280000,
            "stock_qty": 10,
        },
        headers=headers,
    )
    assert ingredient.status_code == 201, ingredient.text
    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Budín de Almendra",
            "category": "Budines",
            "recipe": [
                {
                    "ingredient_id": ingredient.json()["id"],
                    "qty": "250",
                    "unit": "g",
                }
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def _png(width: int, height: int) -> bytes:
    ihdr = _png_chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    )
    raw = b"".join(b"\x00" + b"\x11\x22\x33" * width for _ in range(height))
    idat = _png_chunk(b"IDAT", zlib.compress(raw))
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + _png_chunk(b"IEND", b"")


def _jpeg(width: int, height: int) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof0 = (
        b"\xff\xc0"
        + struct.pack(">H", 9)
        + b"\x08"
        + struct.pack(">HH", height, width)
        + b"\x01"
        + b"\x01\x11\x00"
    )
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


def _webp(width: int, height: int) -> bytes:
    payload = b"\x00" + b"\x00\x00\x00" + struct.pack("<I", width - 1)[:3] + struct.pack("<I", height - 1)[:3]
    chunk = b"VP8X" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


async def _upload(client: AsyncClient, product_id: str, data: bytes, headers, content_type="application/octet-stream"):
    return await client.post(
        f"/api/v1/products/{product_id}/image",
        files={"file": ("foto.png", data, content_type)},
        headers=headers,
    )




@pytest.mark.asyncio
async def test_upload_valid_png(client, media_root):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    response = await _upload(client, product["id"], _png(300, 300), headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["image_url"] == f"/media/products/{product['id']}.png"
    disk = media_root / "products" / f"{product['id']}.png"
    assert disk.is_file()
    assert disk.read_bytes() == _png(300, 300)
    detail = await client.get(f"/api/v1/products/{product['id']}", headers=headers)
    assert detail.json()["image_url"] == body["image_url"]


@pytest.mark.asyncio
async def test_upload_valid_jpeg(client, media_root):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    response = await _upload(client, product["id"], _jpeg(400, 300), headers)
    assert response.status_code == 201, response.text
    assert response.json()["image_url"] == f"/media/products/{product['id']}.jpg"
    assert (media_root / "products" / f"{product['id']}.jpg").is_file()


@pytest.mark.asyncio
async def test_upload_valid_webp(client, media_root):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    response = await _upload(client, product["id"], _webp(320, 240), headers)
    assert response.status_code == 201, response.text
    assert response.json()["image_url"] == f"/media/products/{product['id']}.webp"




@pytest.mark.asyncio
async def test_upload_invalid_type_ignores_content_type(client, media_root):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    gif = b"GIF89a" + b"\x00" * 64
    response = await _upload(
        client, product["id"], gif, headers, content_type="image/jpeg"
    )
    assert response.status_code == 422
    assert response.json()["code"] == "image_invalid_type"
    assert not (media_root / "products").exists() or not list(
        (media_root / "products").iterdir()
    )


@pytest.mark.asyncio
async def test_upload_oversize_is_422(client, media_root):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    huge = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(
            b"IHDR", struct.pack(">IIBBBBB", 300, 300, 8, 2, 0, 0, 0)
        )
        + _png_chunk(b"IDAT", zlib.compress(os.urandom(6 * 1024 * 1024)))
        + _png_chunk(b"IEND", b"")
    )
    response = await _upload(client, product["id"], huge, headers, "image/png")
    assert response.status_code == 422
    assert response.json()["code"] == "image_too_large"
    assert not (media_root / "products").exists() or not list(
        (media_root / "products").iterdir()
    )


@pytest.mark.asyncio
async def test_upload_small_dimensions_is_422(client, media_root):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    response = await _upload(client, product["id"], _png(100, 100), headers)
    assert response.status_code == 422
    assert response.json()["code"] == "image_too_small"




@pytest.mark.asyncio
async def test_upload_forbidden_for_customer(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    customer_headers = {
        "Authorization": f"Bearer {await _customer_token(client)}"
    }
    response = await _upload(
        client, product["id"], _png(300, 300), customer_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_anonymous_is_401(client):
    product = await _create_product(
        client, {"Authorization": f"Bearer {await _admin_token(client)}"}
    )
    response = await _upload(client, product["id"], _png(300, 300), {})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_nonexistent_product_is_404(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    response = await _upload(client, "no-existe", _png(300, 300), headers)
    assert response.status_code == 404




@pytest.mark.asyncio
async def test_replace_deletes_old_file(client, media_root):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    await _upload(client, product["id"], _png(300, 300), headers)
    response = await _upload(client, product["id"], _jpeg(400, 300), headers)
    assert response.status_code == 201, response.text
    assert response.json()["image_url"] == f"/media/products/{product['id']}.jpg"
    assert (media_root / "products" / f"{product['id']}.png").exists() is False
    assert (media_root / "products" / f"{product['id']}.jpg").is_file()


@pytest.mark.asyncio
async def test_delete_image(client, media_root):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    await _upload(client, product["id"], _png(300, 300), headers)
    response = await client.delete(
        f"/api/v1/products/{product['id']}/image", headers=headers
    )
    assert response.status_code == 204
    assert not (media_root / "products" / f"{product['id']}.png").exists()
    detail = await client.get(f"/api/v1/products/{product['id']}", headers=headers)
    assert detail.json()["image_url"] is None


@pytest.mark.asyncio
async def test_delete_without_image_is_404(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    product = await _create_product(client, headers)
    response = await client.delete(
        f"/api/v1/products/{product['id']}/image", headers=headers
    )
    assert response.status_code == 404
