"""
설정 파일 로더
paths.yaml을 읽어 전역 CONFIG 딕셔너리로 제공
"""
import os
import sys

# 기본 설정 (yaml 로드 실패 시 폴백)
DEFAULT_CONFIG = {
    'mode': 'paper',
    'account_number': '',
    'initial_capital': 800_000,
    'target_capital': 100_000_000,
    'telegram_token': '',
    'telegram_chat_id': '',
    'max_buy_daily': 10,
    'max_sell_daily': 10,
    'stop_loss': -0.02,
    'take_profit': 0.03,
    'trailing_stop': True,
    'trailing_pct': 0.015,
    'max_positions': 2,
    'ai_server_port': 5555,
    'ai_model_dir': r'C:\trading\models\brains',
    'db_path': r'C:\trading\db\trading.db',
    'trade_log': r'D:\trading_data\trade_book.csv',
    'bar_5min': r'D:\trading_data\price_bar\5min',
    'bar_1min': r'D:\trading_data\price_bar\1min',
    'buy_fee': 0.00015,
    'sell_fee': 0.00015,
    'tax_kosdaq': 0.0023,
    'etf_exclude': ['KODEX', 'TIGER', 'ARIRANG', 'KINDEX', 'HANARO',
                    '레버리지', '인버스', '파생'],
}

def _load_yaml(path: str) -> dict:
    try:
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data or {}
    except Exception:
        return {}

def _find_config_path() -> str:
    candidates = [
        r'C:\trading\config\paths.yaml',
        os.path.join(os.path.dirname(__file__), 'paths.yaml'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'paths.yaml'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ''

# 설정 로드
_config_path = _find_config_path()
_file_config  = _load_yaml(_config_path) if _config_path else {}

# 파일 설정이 기본 설정을 덮어씀
CONFIG = {**DEFAULT_CONFIG, **_file_config}


def get(key: str, default=None):
    """설정값 조회"""
    return CONFIG.get(key, default)


def is_live() -> bool:
    return CONFIG.get('mode', 'paper') == 'live'


def is_paper() -> bool:
    return not is_live()
