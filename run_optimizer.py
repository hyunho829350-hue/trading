"""
파라미터 최적화 실행 스크립트

사용법:
    # 개별 전략 최적화
    python app/test/run_optimizer.py --strategy rsi --code 005930
    python app/test/run_optimizer.py --strategy rsi --all

    # 복합전략 threshold 최적화
    python app/test/run_optimizer.py --threshold
    python app/test/run_optimizer.py --threshold --code 005930

    # 복합전략 가중치 최적화
    python app/test/run_optimizer.py --weights
    python app/test/run_optimizer.py --weights --code 005930

    # 전략 가지치기
    python app/test/run_optimizer.py --prune

    # 전체 최적화 (threshold + weights + prune)
    python app/test/run_optimizer.py --full
"""

import sys
sys.path.insert(0, r"C:\trading\app")

import argparse
from datetime import datetime
from backtest.grid_optimizer   import GridOptimizer
from backtest.weight_optimizer import WeightOptimizer


def main():
    parser = argparse.ArgumentParser(description="파라미터 최적화")

    # 모드 선택
    parser.add_argument("--strategy",  type=str, default=None,
                        help="개별 전략 최적화 (예: rsi, trend)")
    parser.add_argument("--threshold", action="store_true",
                        help="복합전략 threshold 최적화")
    parser.add_argument("--weights",   action="store_true",
                        help="복합전략 가중치 최적화")
    parser.add_argument("--prune",     action="store_true",
                        help="전략 가지치기")
    parser.add_argument("--full",      action="store_true",
                        help="전체 최적화 (threshold + weights + prune)")

    # 옵션
    parser.add_argument("--code",    type=str, default=None,
                        help="단일 종목코드 (예: 005930)")
    parser.add_argument("--all",     action="store_true",
                        help="전 종목 대상")
    parser.add_argument("--capital", type=int, default=10_000_000,
                        help="초기 자본금")
    parser.add_argument("--start",   type=str, default=None,
                        help="시작일 (예: 2024-01-01)")
    parser.add_argument("--end",     type=str, default=None,
                        help="종료일 (예: 2024-12-31)")
    args = parser.parse_args()

    print()
    print("🔧 파라미터 최적화 시작")
    print("━" * 50)
    start_time = datetime.now()

    # ── 개별 전략 최적화 ─────────────────────
    if args.strategy:
        optimizer = GridOptimizer(
            capital=args.capital, start=args.start, end=args.end
        )

        if args.code:
            print("📌 단일 종목: " + args.strategy + " / " + args.code)
            optimizer.optimize(args.strategy, code=args.code)
        else:
            print("📌 전 종목: " + args.strategy)
            optimizer.optimize_all_codes(args.strategy)

    # ── Threshold 최적화 ─────────────────────
    elif args.threshold:
        optimizer = WeightOptimizer(
            capital=args.capital, start=args.start, end=args.end
        )
        if args.code:
            print("📌 Threshold 최적화: " + args.code)
            optimizer.optimize_threshold(code=args.code)
        else:
            print("📌 Threshold 최적화: 전 종목")
            optimizer.optimize_threshold()

    # ── 가중치 최적화 ────────────────────────
    elif args.weights:
        optimizer = WeightOptimizer(
            capital=args.capital, start=args.start, end=args.end
        )
        if args.code:
            print("📌 가중치 최적화: " + args.code)
            optimizer.optimize_weights(code=args.code)
        else:
            print("📌 가중치 최적화: 전 종목")
            optimizer.optimize_weights()

    # ── 가지치기 ─────────────────────────────
    elif args.prune:
        optimizer = WeightOptimizer(
            capital=args.capital, start=args.start, end=args.end
        )
        print("📌 전략 가지치기")
        optimizer.prune_strategies(code=args.code)

    # ── 전체 최적화 ──────────────────────────
    elif args.full:
        optimizer = WeightOptimizer(
            capital=args.capital, start=args.start, end=args.end
        )

        print("📌 [1/3] Threshold 최적화")
        th_results = optimizer.optimize_threshold(code=args.code)

        print()
        print("📌 [2/3] 가중치 최적화")
        wt_results = optimizer.optimize_weights(code=args.code)

        print()
        print("📌 [3/3] 전략 가지치기")
        pr_results = optimizer.prune_strategies(code=args.code)

        # 최종 요약
        print()
        print("━" * 60)
        print("  📊 최적화 최종 요약")
        print("━" * 60)

        if th_results:
            best_th = th_results[0]
            print("  [Threshold]  buy=" +
                  str(best_th["buy_threshold"]) +
                  " / sell=" + str(best_th["sell_threshold"]) +
                  " → 수익률 " + str(best_th["avg_return"]) + "%")

        if wt_results:
            best_wt = wt_results[0]
            print("  [가중치]     " +
                  best_wt.get("weights", "") +
                  " → 수익률 " + str(best_wt["avg_return"]) + "%")

        if pr_results:
            removable = [r["removed"] for r in pr_results
                        if r["change"] > 0 and r["removed"] != "NONE (기준)"]
            if removable:
                print("  [가지치기]   제거 추천: " + str(removable))
            else:
                print("  [가지치기]   모든 전략 유지 ✅")

        print("━" * 60)

    else:
        parser.print_help()
        return

    elapsed = (datetime.now() - start_time).total_seconds()
    print()
    print("⏱️  소요 시간: " + str(round(elapsed, 1)) + "초")
    print("✅ 최적화 완료!")


if __name__ == "__main__":
    main()