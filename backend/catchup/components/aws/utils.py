def extract_model_part_from_arn(arn: str) -> str:
    """
    모델 ARN에서 모델 식별자를 추출한다.
    
    Args:
        arn: 모델 ARN e.g) arn:aws:bedrock:.../global.cohere.embed-v4:0
    
    Returns:
        파싱된 모델명 e.g) global.cohere.embed-v4:0
    """
    if not arn.startswith('arn:'):
        return arn
    return arn.split('/')[-1]