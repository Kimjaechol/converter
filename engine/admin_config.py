"""
관리자 전용 설정 관리
=======================
Upstage API 키 등 관리자만 접근할 수 있는 설정을 관리합니다.

보안 주의사항:
- admin_config.json 파일은 소스코드에 포함하지 않습니다
- 앱 배포 시 별도로 관리합니다
- .gitignore에 추가되어 있어야 합니다
"""

import os
import json
from pathlib import Path

class AdminConfig:
    """관리자 전용 설정 관리"""

    def __init__(self):
        # 설정 파일 위치 (우선순위 순서)
        self.config_paths = [
            # 1. 앱 실행 경로의 admin_config.json
            Path(os.path.dirname(os.path.abspath(__file__))) / "admin_config.json",
            # 2. 사용자 홈 디렉토리의 관리자 설정
            Path.home() / ".lawpro" / "admin_config.json",
            # 3. 환경 변수 (빌드 시 주입)
            None  # 환경 변수는 별도 처리
        ]

        self._config = {}
        self._load_config()

    def _load_config(self):
        """설정 파일 로드"""
        # 파일에서 로드 시도
        for config_path in self.config_paths:
            if config_path and config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        self._config = json.load(f)
                    print(f"[AdminConfig] 설정 로드됨: {config_path}")
                    return
                except Exception as e:
                    print(f"[AdminConfig] 설정 로드 실패: {e}")

        # 환경 변수에서 로드
        self._load_from_env()

    def _load_from_env(self):
        """환경 변수에서 설정 로드"""
        env_keys = {
            'UPSTAGE_API_KEY': 'upstage_api_key',
            'LAWPRO_ADMIN_KEY': 'admin_key'
        }

        for env_key, config_key in env_keys.items():
            value = os.environ.get(env_key)
            if value:
                self._config[config_key] = value
                print(f"[AdminConfig] 환경 변수에서 로드됨: {env_key}")

    @property
    def upstage_api_key(self) -> str:
        """Upstage API 키 반환"""
        return self._config.get('upstage_api_key', '')

    @property
    def is_configured(self) -> bool:
        """관리자 설정이 되어있는지 확인"""
        return bool(self.upstage_api_key)

    def get(self, key: str, default=None):
        """설정 값 가져오기"""
        return self._config.get(key, default)


# 싱글톤 인스턴스
_admin_config = None

def get_admin_config() -> AdminConfig:
    """관리자 설정 인스턴스 반환"""
    global _admin_config
    if _admin_config is None:
        _admin_config = AdminConfig()
    return _admin_config
