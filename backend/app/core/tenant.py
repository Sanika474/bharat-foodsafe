import uuid
from app.core.exceptions import AppException


class TenantContext:
    def __init__(self, user_id: uuid.UUID, restaurant_id: uuid.UUID | None, roles: list[str]):
        self.user_id = user_id
        self.restaurant_id = restaurant_id
        self.roles = roles

    def is_platform_admin(self) -> bool:
        return "PLATFORM_ADMIN" in self.roles

    def validate_tenant_access(self, target_restaurant_id: uuid.UUID | str | None) -> None:
        """Enforces multi-tenant isolation.
        Cross-tenant access attempts return HTTP 403 FORBIDDEN.
        """
        if self.is_platform_admin():
            return

        if target_restaurant_id is None:
            return

        target_id_str = str(target_restaurant_id)
        current_id_str = str(self.restaurant_id) if self.restaurant_id else None

        if current_id_str is None or current_id_str != target_id_str:
            raise AppException(
                code="FORBIDDEN_CROSS_TENANT",
                message="Cross-tenant access attempt prohibited.",
                status_code=403,
            )
