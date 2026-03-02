class GlobalState:
    is_admin_initiated: bool = False
    has_ever_uploaded_user_list_export: bool = False
    
state = GlobalState()