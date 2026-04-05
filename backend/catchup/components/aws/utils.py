import re

"""
[ARN 구조]

e.g.

arn:aws:bedrock:ap-northeast-2:{{ACCOUND_ID}}:inference-profile/global.anthropic.claude-sonnet-4-5-20250929-v1:0"

- model id: global.anthropic.claude-sonnet-4-5-20250929-v1:0
    - routing prefix: global
    - provider: anthropic
    - base model id: claude-sonnet-4-5
    - version suffix: 20250929-v1:0
"""

def extract_model_id_from_arn(arn: str) -> str:
    """
    ARN에서 model ID 부분을 추출한다. (routing prefix, provider, base model, version)
    CloudWatch Dimension 등 model ID 전체가 필요한 경우에 사용.
    
    e.g) arn:aws:bedrock:.../global.anthropic.claude-sonnet-4-5-20250929-v1:0
      -> global.anthropic.claude-sonnet-4-5-20250929-v1:0
    """
    if not arn.startswith('arn:'):
        return arn
    return arn.split('/')[-1]


def extract_base_model_id_from_arn(arn: str) -> str:
    """
    ARN에서 base model ID만 추출한다.
    pricing 매핑 등 버전에 무관하게 모델을 식별해야 하는 경우에 사용.
    
    e.g) arn:aws:bedrock:.../global.anthropic.claude-sonnet-4-5-20250929-v1:0
      -> claude-sonnet-4-5
    """
    model_id = extract_model_id_from_arn(arn)
    
    # routing prefix 제거
    model_id = re.sub(r"^(global|us|eu|ap)\.", "", model_id)
    
    # provider 제거
    model_id = re.sub(r"^[^.]+\.", "", model_id)
    
    # version suffix 제거
    model_id = re.sub(r"-\d{8}.*$|:\d+$", "", model_id)
    
    return model_id
