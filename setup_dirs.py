"""
폴더 구조 자동 생성 스크립트
C드라이브: 핵심 엔진 / D드라이브: 봉 데이터
"""
import os
import sys


DIRS = [
    # ── C드라이브 (SSD) ──
    r'C:\trading\app\core',
    r'C:\trading\app\ai\models',
    r'C:\trading\app\backtest',
    r'C:\trading\app\ui',
    r'C:\trading\models\brains',
    r'C:\trading\models\meta',
    r'C:\trading\db',
    r'C:\trading\config',
    r'C:\trading\logs',
    # ── D드라이브 (HDD) ──
    r'D:\trading_data\price_bar\1min',
    r'D:\trading_data\price_bar\5min',
    r'D:\trading_data\price_bar\30min',
    r'D:\trading_data\price_bar\60min',
    r'D:\trading_data\price_bar\day',
    r'D:\trading_data\tick',
    r'D:\trading_data\answer_book\history',
    r'D:\trading_data\backtest\results',
    r'D:\trading_data\logs\trade',
    r'D:\trading_data\slip_record',
]


def create_dirs(dirs: list) -> dict:
    results = {'created': [], 'existing': [], 'failed': []}
    for d in dirs:
        if os.path.exists(d):
            results['existing'].append(d)
        else:
            try:
                os.makedirs(d, exist_ok=True)
                results['created'].append(d)
                print(f'[생성] {d}')
            except Exception as e:
                results['failed'].append((d, str(e)))
                print(f'[실패] {d} — {e}')
    return results


if __name__ == '__main__':
    print('=' * 60)
    print('  AI 자동매매 — 폴더 구조 생성')
    print('=' * 60)
    results = create_dirs(DIRS)
    print()
    print(f'생성: {len(results["created"])}개')
    print(f'기존: {len(results["existing"])}개')
    print(f'실패: {len(results["failed"])}개')
    if results['failed']:
        print('실패 목록:')
        for path, err in results['failed']:
            print(f'  {path}: {err}')
    print('\n폴더 생성 완료!')
