"""키움 REST API 어댑터.

API 명세는 계정 승인 후 내려받은 최신 JSON 명세에 맞춰 endpoint/tr_id 매핑을
확정해야 한다. 비밀키는 브라우저나 GitHub Pages에 절대 노출하지 않는다.
"""
from os import getenv

class KiwoomClient:
    def __init__(self):
        self.app_key=getenv('KIWOOM_APP_KEY','')
        self.secret_key=getenv('KIWOOM_SECRET_KEY','')
        self.base_url=getenv('KIWOOM_BASE_URL','https://api.kiwoom.com')

    @property
    def configured(self): return bool(self.app_key and self.secret_key)

    def market_indices(self):
        raise NotImplementedError('최신 키움 JSON API 명세의 업종 실시간시세 매핑이 필요합니다.')

    def investor_rankings(self):
        raise NotImplementedError('최신 키움 JSON API 명세의 기관·외국인 순위 매핑이 필요합니다.')
