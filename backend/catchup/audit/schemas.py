from pydantic import BaseModel


class AuditActor(BaseModel):
    user_id: str | None = None
    email: str | None = None
    role: str | None = None
    department: str | None = None
    
    @classmethod
    def from_dict(
        cls,
        data: dict | None
    ) -> "AuditActor":
        
        if not data or not isinstance(data, dict):
            return cls()
        
        obj_type = data.get("__type__")        
        user_id = data.get("sub") or str(data.get("id") or "")
        
        if obj_type == "User":
            return cls(
                user_id=user_id,
                email=data.get("email"),
                role=data.get("role"),
                department=data.get("department")
            )

        if obj_type == "OAuthUser":
            return cls(
                user_id=data.get("sub"),
                email=data.get("email")
            )
            
        # case) data: dict | None
        return cls(
            user_id=user_id,
            email=data.get("email"),
            role=data.get("role"),
            department=data.get("department")
        )