"""
main.py
AI 자동매매 시스템 진입점

실행:
  실전 모드:       python main.py --mode live
  백테스트 모드:   python main.py --mode backtest
  데이터 수집:     python main.py --mode data
  모델 학습:       python main.py --mode train
  환경 점검:       python main.py --mode check
"""

import sys
import os
import argparse

# 경로 설정 (어느 폴더에서 실행해도 작동)
APP_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_ROOT)

from utils.logger import get_logger, get_system_logger
from utils.paths import Paths
from utils.resource_monitor import ResourceMonitor

log = get_logger("MAIN")


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI 자동매매 시스템"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["live", "backtest", "data", "train", "check"],
        default="check",
        help="실행 모드"
    )
    return parser.parse_args()


def mode_check():
    print()
    print("=" * 50)
    print("  환경 점검")
    print("=" * 50)

    # Python 버전
    bit = "64bit" if sys.maxsize > 2**32 else "32bit"
    print(f"  Python  : {sys.version[:6]} ({bit})")

    # 경로 확인
    p = Paths()
    checks = [
        ("DB 경로",    p.db),
        ("5분봉 경로", p.price_bar("5min")),
        ("모델 경로",  p.model("UPTREND", "cnn")),
        ("로그 경로",  p.log("system")),
    ]
    print()
    for name, path in checks:
        exists = os.path.exists(os.path.dirname(path)) \
                 or os.path.exists(path)
        mark = "OK" if exists else "없음"
        print(f"  [{mark}] {name}: {path}")

    # 리소스
    print()
    rm = ResourceMonitor()
    rm.print_status()

    print("  ✅ 환경 점검 완료")
    print()


def mode_live():
    log.info("실전 모드 시작")
    # Phase 8 완료 후 구현
    print("  [준비중] Phase 8 스케줄러 완료 후 활성화")


def mode_backtest():
    log.info("백테스트 모드 시작")
    # Phase 7 완료 후 구현
    print("  [준비중] Phase 7 백테스터 완료 후 활성화")


def mode_data():
    log.info("데이터 수집 모드 시작")
    # Phase 2 완료 후 구현
    print("  [준비중] Phase 2 데이터 수신 완료 후 활성화")


def mode_train():
    log.info("모델 학습 모드 시작")
    # Phase 5 완료 후 구현
    print("  [준비중] Phase 5 AI 두뇌 완료 후 활성화")


def main():
    args = parse_args()

    log.info(f"모드: {args.mode}")

    if args.mode == "check":
        mode_check()

    elif args.mode == "live":
        mode_check()           # 실전 전 항상 점검
        mode_live()

    elif args.mode == "backtest":
        mode_backtest()

    elif args.mode == "data":
        mode_data()

    elif args.mode == "train":
        mode_train()


if __name__ == "__main__":
    main()