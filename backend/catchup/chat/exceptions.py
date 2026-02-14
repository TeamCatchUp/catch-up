class FeedbackImmutableError(Exception):
    """부정 피드백 수정 불가"""
    pass

class LikedWithNegativeFeedbackError(Exception):
    """긍정 피드백에 부정 피드백 혼입"""
