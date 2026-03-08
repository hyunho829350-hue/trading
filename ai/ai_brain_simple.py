"""
AI 브레인 (간소화 버전)
Phase 1: LightGBM만 사용 — 빠른 실전 투입
20개 핵심 피처, 매일 장 마감 후 재학습
"""
import os
import pickle
from datetime import datetime


class AIBrainSimple:
    """
    소자본 초기: LightGBM 기반 간소화 AI
    Phase 1 → BUY/HOLD/SELL 3클래스 분류
    """

    FEATURE_NAMES = [
        'change_rate', 'dist_ma5', 'dist_ma20',
        'volume_ratio', 'amount_ratio',
        'rsi_14', 'bb_position', 'macd_signal',
        'velocity', 'acceleration',
        'market_regime_score',
        'spread_rate', 'volume_impact',
        'hour',
        # 조건검색식 원핫 (6개)
        'cond_급등초기', 'cond_VI돌파', 'cond_상한가근접',
        'cond_눌림목반등', 'cond_BB스퀴즈', 'cond_골든크로스',
    ]

    BUY_THRESHOLD  = 0.65
    SELL_THRESHOLD = 0.60
    MODEL_DIR = r'C:\trading\models'

    def __init__(self, model_path: str = None):
        self.model = None
        self.model_path = model_path or os.path.join(self.MODEL_DIR, 'lgbm_brain_latest.pkl')
        self._load_model()

    def _load_model(self):
        """저장된 모델 로드"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
        except Exception:
            self.model = None

    def _save_model(self):
        """모델 저장"""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d')
            versioned = self.model_path.replace('latest', ts)
            with open(versioned, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
        except Exception:
            pass

    def build_features(self, ohlcv_5min: list, ohlcv_1min: list,
                       extra: dict = None) -> list:
        """
        20개 핵심 피처 생성
        ohlcv_5min: [{'open','high','low','close','volume'}, ...]
        extra: 추가 정보 (conditions, market_regime 등)
        Returns: list of 20 floats
        """
        extra = extra or {}
        prices = [b['close'] for b in ohlcv_5min if b.get('close')]
        volumes = [b['volume'] for b in ohlcv_5min if b.get('volume')]

        if not prices:
            return [0.0] * len(self.FEATURE_NAMES)

        cur = prices[-1]

        # 가격 변화율
        change_rate = (cur - prices[-2]) / prices[-2] * 100 if len(prices) >= 2 and prices[-2] > 0 else 0

        # MA 이격
        def ma(n): return sum(prices[-n:]) / n if len(prices) >= n else prices[-1]
        ma5  = ma(5)
        ma20 = ma(20)
        dist_ma5  = (cur - ma5)  / ma5  * 100 if ma5  > 0 else 0
        dist_ma20 = (cur - ma20) / ma20 * 100 if ma20 > 0 else 0

        # 거래량 비율
        avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else (volumes[-1] if volumes else 1)
        vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 and volumes else 1

        # RSI 14
        rsi = extra.get('rsi_14', 50)

        # BB 위치 (0~1)
        if len(prices) >= 20:
            import statistics
            mid = ma(20)
            std = statistics.stdev(prices[-20:])
            upper = mid + 2 * std
            lower = mid - 2 * std
            bb_pos = (cur - lower) / (upper - lower) if upper > lower else 0.5
        else:
            bb_pos = 0.5

        # MACD 신호 (간단 계산)
        ema12 = ma(12)
        ema26 = ma(26) if len(prices) >= 26 else ma5
        macd = ema12 - ema26
        macd_signal = extra.get('macd_signal', macd)

        # 물리량 (속도/가속도)
        velocity = (prices[-1] - prices[-min(5, len(prices))]) / max(1, min(5, len(prices) - 1))
        if len(prices) >= 3:
            v1 = prices[-1] - prices[-2]
            v2 = prices[-2] - prices[-3]
            acceleration = v1 - v2
        else:
            acceleration = 0

        # 시장 국면 점수
        market_score = extra.get('market_regime_score', 50)

        # 스프레드/충격
        spread_rate = extra.get('spread_rate', 0.001)
        volume_impact = extra.get('volume_impact', 0)

        # 시간대
        from datetime import datetime
        hour = datetime.now().hour

        # 조건 원핫
        conditions = extra.get('conditions', {})
        cond_vec = [
            1.0 if conditions.get('급등초기') else 0.0,
            1.0 if conditions.get('VI돌파') else 0.0,
            1.0 if conditions.get('상한가근접') else 0.0,
            1.0 if conditions.get('눌림목반등') else 0.0,
            1.0 if conditions.get('BB스퀴즈') else 0.0,
            1.0 if conditions.get('골든크로스') else 0.0,
        ]

        return [
            change_rate, dist_ma5, dist_ma20,
            vol_ratio, vol_ratio,
            rsi, bb_pos, float(macd > macd_signal),
            velocity, acceleration,
            market_score,
            spread_rate, volume_impact,
            float(hour),
        ] + cond_vec

    def predict(self, features: list) -> dict:
        """
        예측 실행
        Returns: {'BUY': float, 'HOLD': float, 'SELL': float}
        """
        if self.model is None:
            # 모델 없으면 피처 기반 규칙
            return self._rule_based_predict(features)

        try:
            import numpy as np
            feat = np.array(features).reshape(1, -1)
            proba = self.model.predict_proba(feat)[0]
            # 클래스 순서: [SELL, HOLD, BUY] → 보정
            if len(proba) == 3:
                return {'SELL': float(proba[0]), 'HOLD': float(proba[1]), 'BUY': float(proba[2])}
            return {'BUY': float(proba[-1]), 'HOLD': 0.0, 'SELL': float(proba[0])}
        except Exception:
            return self._rule_based_predict(features)

    def _rule_based_predict(self, features: list) -> dict:
        """모델 없을 때 규칙 기반 예측"""
        if len(features) < 6:
            return {'BUY': 0.3, 'HOLD': 0.5, 'SELL': 0.2}

        change_rate = features[0]   # 등락률
        dist_ma5    = features[1]   # MA5 이격
        vol_ratio   = features[3]   # 거래량 비율
        rsi         = features[5]   # RSI

        buy_score = 0.0
        if change_rate > 0: buy_score += 0.2
        if dist_ma5 > -2 and dist_ma5 < 5: buy_score += 0.2
        if vol_ratio >= 2: buy_score += 0.2
        if 40 <= rsi <= 65: buy_score += 0.2
        # 조건검색식 통과 여부 (피처 14~19번)
        cond_sum = sum(features[14:20]) if len(features) >= 20 else 0
        buy_score += min(cond_sum * 0.1, 0.2)

        buy_score = min(buy_score, 0.95)
        sell_score = max(0, 0.1 - buy_score * 0.05)
        hold_score = 1.0 - buy_score - sell_score

        return {'BUY': buy_score, 'HOLD': hold_score, 'SELL': sell_score}

    def train_from_backtest(self, backtest_results: list):
        """
        백테스트 결과로 초기 학습
        backtest_results: [{'features': [], 'label': 1/0}]
        """
        if len(backtest_results) < 50:
            return False

        try:
            import numpy as np
            X = np.array([r['features'] for r in backtest_results])
            y = np.array([r['label'] for r in backtest_results])

            try:
                import lightgbm as lgb
                self.model = lgb.LGBMClassifier(
                    n_estimators=300, max_depth=6,
                    learning_rate=0.05, class_weight='balanced',
                    verbose=-1
                )
            except ImportError:
                from sklearn.ensemble import GradientBoostingClassifier
                self.model = GradientBoostingClassifier(n_estimators=100)

            self.model.fit(X, y)
            self._save_model()
            return True
        except Exception:
            return False

    def daily_retrain(self, new_trades: list):
        """장 마감 후 오늘 매매 결과로 재학습"""
        if not new_trades:
            return False
        return self.train_from_backtest(new_trades)
