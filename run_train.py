"""
AI 모델 학습 실행 스크립트
위치: C:\trading\run_train.py

사용법:
    python run_train.py                          # 전 종목 학습 (ML만)
    python run_train.py --lstm                   # LSTM 포함
    python run_train.py --code 005930            # 단일 종목
    python run_train.py --evaluate               # 학습 + 평가
"""

import sys
sys.path.insert(0, r"C:\trading\app")

import argparse
from datetime import datetime
from backtest.data_loader import DataLoader
from ai.brain import AIBrain
from ai.feature_builder import FeatureBuilder
from ai.label_maker import LabelMaker


def main():
    parser = argparse.ArgumentParser(description="AI 모델 학습")
    parser.add_argument("--lstm",     action="store_true",
                        help="LSTM 포함 학습")
    parser.add_argument("--code",     type=str, default=None,
                        help="단일 종목코드")
    parser.add_argument("--evaluate", action="store_true",
                        help="학습 후 평가 실행")
    parser.add_argument("--horizon",  type=int, default=5,
                        help="예측 기간 (일)")
    parser.add_argument("--threshold", type=float, default=0.02,
                        help="매수/매도 기준 수익률")
    args = parser.parse_args()

    print()
    print("🧠 AI 모델 학습 시작")
    print("━" * 50)
    print("  LSTM:     " + ("ON" if args.lstm else "OFF"))
    print("  예측기간: " + str(args.horizon) + "일")
    print("  기준:     ±" + str(args.threshold * 100) + "%")
    print("━" * 50)

    start_time = datetime.now()

    # 데이터 로드
    loader = DataLoader()

    if args.code:
        codes = [args.code]
    else:
        codes = loader.get_available_codes("day")

    print("  종목 수:  " + str(len(codes)) + "개")
    print()

    # bars 로드
    bars_dict = {}
    for code in codes:
        bars = loader.load(code, "day")
        if len(bars) >= 80:
            bars_dict[code] = bars
            print("  ✅ " + code + ": " + str(len(bars)) + "봉")

    print()
    print("  유효 종목: " + str(len(bars_dict)) + "개")
    print()

    # 브레인 학습
    brain = AIBrain(use_lstm=args.lstm)
    brain.label_maker = LabelMaker(
        horizon=args.horizon,
        threshold=args.threshold,
    )
    brain.train_all(bars_dict, save=True)

    # 평가
    if args.evaluate:
        print()
        print("���" * 50)
        print("  📊 모델 평가")
        print("━" * 50)

        builder = FeatureBuilder()
        maker = LabelMaker(horizon=args.horizon,
                          threshold=args.threshold)

        for code in list(bars_dict.keys())[:5]:  # 상위 5개만
            bars = bars_dict[code]
            features, names = builder.build(bars)
            labels, _ = maker.make(bars)

            # 유효 데이터
            X = []
            y = []
            for i in range(len(features)):
                if i < len(labels) and labels[i] is not None:
                    X.append(features[i])
                    y.append(labels[i])

            if len(X) < 20:
                continue

            # 후반 20% 평가
            split = int(len(X) * 0.8)
            X_test = X[split:]
            y_test = y[split:]

            print()
            print("  [" + code + "]")
            for name in ["random_forest", "xgboost"]:
                model = brain.models.get(name)
                if model and model.is_trained:
                    result = model.evaluate(X_test, y_test)
                    acc = result.get("accuracy", 0)
                    print("    " + name + ": " +
                          str(round(acc * 100, 1)) + "%")

    elapsed = (datetime.now() - start_time).total_seconds()
    print()
    print("⏱️  소요 시간: " + str(round(elapsed, 1)) + "초")
    print("✅ AI 학습 완료!")
    print("📁 모델 저장: C:\\trading\\models\\brains\\")


if __name__ == "__main__":
    main()