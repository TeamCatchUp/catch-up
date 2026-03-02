import re

def reformat_name(full_name: str) -> str:
    if not full_name:
        return ""
    
    parts = full_name.strip().split()
    
    if len(parts) < 2:
        return full_name.strip()
    
    given_name = parts[0]
    family_name = parts[-1]
    
    if re.search(r"[ㄱ-ㅎㅏ-ㅣ가-힣]", full_name):
        return f"{family_name}{given_name}"
    
    return f"{given_name} {family_name}"
