from pydantic import BaseModel


class AuditActor(BaseModel):
    sub: str | None = None
    user_id: int | None = None
    email: str | None = None
    name: str | None = None
    role: str | None = None
    department: str | None = None
    
    @classmethod
    def from_user_snapshot(
        cls,
        data: dict | None
    ) -> "AuditActor":
        
        if not data or not isinstance(data, dict):
            return None
        
        obj_type = data.get("__type__")
        
        sub = data.get("sub", "")
        user_id = data.get("user_id") or data.get("id")
        
        if obj_type == "User":
            return cls(
                sub=sub,
                user_id=user_id,
                email=data.get("email"),
                name=data.get("name"),
                role=data.get("role"),
                department=data.get("department")
            )

        if obj_type == "OAuthUser":
            return cls(
                sub=sub,
                user_id=user_id,
                email=data.get("email")
            )
            
        # case) data: dict | None
        return cls(
            sub=sub,
            user_id=user_id,
            email=data.get("email"),
            role=data.get("role"),
            department=data.get("department")
        )
    
    @classmethod
    def from_token_payload(
        cls,
        payload: dict[str, str]
    ):
        return cls(
            sub=payload.get("sub"),
            user_id=payload.get("id") or payload.get("user_id"),
            email=payload.get("email"),
            role=payload.get("role")
        )