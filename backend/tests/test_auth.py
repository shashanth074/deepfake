"""Registration, login and token handling."""

from __future__ import annotations

import uuid

from app.security import create_access_token, decode_access_token, hash_password, verify_password


class TestPasswordHashing:
    def test_hash_is_not_the_password(self):
        digest = hash_password("correct-horse-battery")
        assert digest != "correct-horse-battery"
        assert verify_password("correct-horse-battery", digest)

    def test_wrong_password_is_rejected(self):
        assert not verify_password("wrong", hash_password("right-password"))

    def test_same_password_hashes_differently(self):
        """Distinct salts: identical passwords must not produce identical hashes."""
        assert hash_password("same-password") != hash_password("same-password")


class TestTokens:
    def test_round_trips_the_subject(self):
        token, expires_in = create_access_token("user-123", {"email": "a@b.com"})
        payload = decode_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "a@b.com"
        assert expires_in > 0

    def test_tampered_token_is_rejected(self):
        token, _ = create_access_token("user-123")
        assert decode_access_token(token[:-4] + "AAAA") is None

    def test_garbage_token_is_rejected(self):
        assert decode_access_token("not.a.token") is None


class TestAuthEndpoints:
    def test_register_returns_a_usable_token(self, client):
        email = f"new-{uuid.uuid4().hex[:8]}@example.com"
        response = client.post(
            "/api/auth/register", json={"email": email, "password": "password12345"}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["email"] == email

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert me.status_code == 200 and me.json()["email"] == email

    def test_duplicate_email_is_rejected(self, client):
        email = f"dupe-{uuid.uuid4().hex[:8]}@example.com"
        payload = {"email": email, "password": "password12345"}
        assert client.post("/api/auth/register", json=payload).status_code == 201
        assert client.post("/api/auth/register", json=payload).status_code == 409

    def test_email_is_normalised_to_lowercase(self, client):
        email = f"Mixed-{uuid.uuid4().hex[:8]}@Example.COM"
        client.post("/api/auth/register", json={"email": email, "password": "password12345"})
        response = client.post(
            "/api/auth/login", json={"email": email.lower(), "password": "password12345"}
        )
        assert response.status_code == 200

    def test_short_password_is_rejected(self, client):
        response = client.post(
            "/api/auth/register",
            json={"email": f"short-{uuid.uuid4().hex[:6]}@example.com", "password": "abc"},
        )
        assert response.status_code == 422

    def test_wrong_password_returns_401(self, client):
        email = f"wrong-{uuid.uuid4().hex[:8]}@example.com"
        client.post("/api/auth/register", json={"email": email, "password": "password12345"})
        response = client.post("/api/auth/login", json={"email": email, "password": "nope-nope"})
        assert response.status_code == 401

    def test_unknown_email_gives_the_same_error_as_a_wrong_password(self, client):
        """The response must not reveal whether an account exists."""
        unknown = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "password12345"},
        )
        email = f"known-{uuid.uuid4().hex[:8]}@example.com"
        client.post("/api/auth/register", json={"email": email, "password": "password12345"})
        wrong = client.post("/api/auth/login", json={"email": email, "password": "bad-password"})

        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["detail"] == wrong.json()["detail"]

    def test_me_requires_a_token(self, client):
        assert client.get("/api/auth/me").status_code == 401
