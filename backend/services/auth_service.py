import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from config import settings
from database import get_db, get_vn_now

logger = logging.getLogger("camera_manager.auth")

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Tạo hash mật khẩu bảo mật sử dụng PBKDF2-HMAC-SHA256 với salt ngẫu nhiên."""
        salt = secrets.token_hex(16)
        iterations = 100_000
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations
        )
        return f"{salt}${iterations}${key.hex()}"

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Kiểm tra mật khẩu nhập vào khớp với hash đã lưu."""
        try:
            parts = hashed_password.split("$")
            if len(parts) != 3:
                return False
            salt, iterations, stored_hex = parts[0], int(parts[1]), parts[2]
            key = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations
            )
            return hmac.compare_digest(key.hex(), stored_hex)
        except Exception as e:
            logger.error(f"Lỗi kiểm tra mật khẩu: {e}")
            return False

    @staticmethod
    def create_token(username: str, role: str = "admin") -> str:
        """Tạo JWT-like token ký điện tử bằng HMAC-SHA256 không phụ thuộc thư viện ngoài."""
        header = {"alg": "HS256", "typ": "JWT"}
        exp = int(time.time()) + (settings.token_expire_days * 86400)
        payload = {
            "sub": username,
            "role": role,
            "exp": exp,
            "iat": int(time.time())
        }

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signing_input = f"{header_b64}.{payload_b64}"

        signature = hmac.new(
            settings.secret_key.encode(),
            signing_input.encode(),
            hashlib.sha256
        ).digest()
        sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        return f"{signing_input}.{sig_b64}"

    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """Xác thực token ký điện tử và trả về thông tin payload nếu hợp lệ."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_b64, payload_b64, sig_b64 = parts[0], parts[1], parts[2]
            signing_input = f"{header_b64}.{payload_b64}"

            # Verify signature
            expected_sig = hmac.new(
                settings.secret_key.encode(),
                signing_input.encode(),
                hashlib.sha256
            ).digest()
            expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")

            if not hmac.compare_digest(sig_b64, expected_sig_b64):
                return None

            # Decode payload
            rem = len(payload_b64) % 4
            if rem > 0:
                payload_b64 += "=" * (4 - rem)
            payload_json = base64.urlsafe_b64decode(payload_b64.encode()).decode()
            payload = json.loads(payload_json)

            # Check expiration
            if payload.get("exp", 0) < int(time.time()):
                return None

            return payload
        except Exception as e:
            logger.warning(f"Lỗi giải mã token: {e}")
            return None

    @classmethod
    async def init_admin_user(cls):
        """Khởi tạo tài khoản quản trị mặc định trong MongoDB nếu chưa tồn tại."""
        db = get_db()
        admin_username = settings.admin_default_username
        user = await db.users.find_one({"username": admin_username})
        if not user:
            logger.info(f"Chưa có tài khoản admin. Tiến hành khởi tạo tài khoản mặc định: {admin_username}")
            pwd_hash = cls.hash_password(settings.admin_default_password)
            now = get_vn_now()
            await db.users.insert_one({
                "username": admin_username,
                "password_hash": pwd_hash,
                "role": "admin",
                "display_name": "Quản Trị Viên",
                "created_at": now,
                "updated_at": now
            })
            logger.info("Khởi tạo tài khoản admin thành công!")
        else:
            logger.info(f"Tài khoản admin '{admin_username}' đã tồn tại trong cơ sở dữ liệu.")

    @classmethod
    async def authenticate(cls, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Xác thực người dùng từ database."""
        db = get_db()
        user = await db.users.find_one({"username": username})
        if not user:
            return None
        if not cls.verify_password(password, user.get("password_hash", "")):
            return None
        return user

    @classmethod
    async def change_password(cls, username: str, old_password: str, new_password: str) -> tuple[bool, str]:
        """Đổi mật khẩu cho người dùng sau khi xác thực mật khẩu cũ."""
        db = get_db()
        user = await db.users.find_one({"username": username})
        if not user:
            return False, "Người dùng không tồn tại"

        if not cls.verify_password(old_password, user.get("password_hash", "")):
            return False, "Mật khẩu cũ không chính xác"

        if len(new_password.strip()) < 6:
            return False, "Mật khẩu mới phải có tối thiểu 6 ký tự"

        new_hash = cls.hash_password(new_password)
        now = get_vn_now()
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"password_hash": new_hash, "updated_at": now}}
        )
        return True, "Đổi mật khẩu thành công"
