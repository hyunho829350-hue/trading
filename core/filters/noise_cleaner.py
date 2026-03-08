"""
노이즈 클리너
SG 필터(실시간) + 웨이블릿(백테스트/AI학습)
가격 데이터의 노이즈 제거 후 지표 재계산
"""
import numpy as np

try:
    from scipy.signal import savgol_filter as _scipy_sg
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    import pywt
    HAS_PYWT = True
except ImportError:
    HAS_PYWT = False


class NoiseCleaner:
    """가격 데이터 노이즈 제거"""

    def sg_filter(self, prices: list, window: int = 11, polyorder: int = 3) -> np.ndarray:
        """Savitzky-Golay 필터 (실시간 매매용, < 1ms)"""
        arr = np.array(prices, dtype=float)
        n = len(arr)
        if n < 3:
            return arr

        # 데이터 길이에 맞게 window 조정 (홀수여야 함)
        max_window = n if n % 2 == 1 else n - 1
        w = min(window, max_window)
        if w < polyorder + 2:
            w = polyorder + 2
            if w % 2 == 0:
                w += 1
        if w > n:
            return arr

        if HAS_SCIPY:
            try:
                return _scipy_sg(arr, window_length=w, polyorder=polyorder)
            except Exception:
                pass
        return self._manual_sg_filter(arr, w, polyorder)

    def _manual_sg_filter(self, prices: np.ndarray, window: int = 11, polyorder: int = 3) -> np.ndarray:
        """Scipy 없을 때 가중 이동평균 대체"""
        half = window // 2
        weights = np.exp(-0.5 * (np.arange(-half, half + 1) / (half / 2)) ** 2)
        weights /= weights.sum()

        padded = np.pad(prices, half, mode='edge')
        result = np.convolve(padded, weights, mode='valid')
        return result[:len(prices)]

    def wavelet_filter(self, prices: list, wavelet: str = 'db4', level: int = 4) -> np.ndarray:
        """웨이블릿 필터 (백테스트/AI 학습용)"""
        arr = np.array(prices, dtype=float)
        if not HAS_PYWT or len(arr) < 8:
            return self.sg_filter(prices)

        try:
            coeffs = pywt.wavedec(arr, wavelet, level=level)
            sigma = np.median(np.abs(coeffs[-1])) / 0.6745
            threshold = sigma * np.sqrt(2 * np.log(len(arr)))
            denoised_coeffs = [coeffs[0]] + [
                pywt.threshold(c, threshold, mode='soft') for c in coeffs[1:]
            ]
            return pywt.waverec(denoised_coeffs, wavelet)[:len(arr)]
        except Exception:
            return self.sg_filter(prices)

    def clean(self, prices: list, mode: str = 'realtime') -> np.ndarray:
        """
        통합 인터페이스
        mode='realtime': SG 필터
        mode='backtest'/'ai_train': 웨이블릿
        """
        if mode == 'realtime':
            return self.sg_filter(prices)
        return self.wavelet_filter(prices)

    def calc_clean_indicators(self, clean_prices: np.ndarray, volumes: list = None) -> dict:
        """정제된 가격으로 보조지표 재계산"""
        n = len(clean_prices)
        result = {}

        # 이동평균
        result['ma5']  = float(np.mean(clean_prices[-5:]))  if n >= 5  else float(clean_prices[-1])
        result['ma20'] = float(np.mean(clean_prices[-20:])) if n >= 20 else float(clean_prices[-1])
        result['ma60'] = float(np.mean(clean_prices[-60:])) if n >= 60 else float(clean_prices[-1])

        # RSI (Wilder's 14)
        if n >= 15:
            deltas = np.diff(clean_prices[-15:])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            if avg_loss == 0:
                result['rsi'] = 100.0
            else:
                rs = avg_gain / avg_loss
                result['rsi'] = float(100 - 100 / (1 + rs))
        else:
            result['rsi'] = 50.0

        # 볼린저밴드 (20봉)
        if n >= 20:
            mid = float(np.mean(clean_prices[-20:]))
            std = float(np.std(clean_prices[-20:]))
            result['bb_upper']  = mid + 2 * std
            result['bb_middle'] = mid
            result['bb_lower']  = mid - 2 * std
            result['bb_width']  = (result['bb_upper'] - result['bb_lower']) / mid if mid > 0 else 0
        else:
            p = float(clean_prices[-1])
            result['bb_upper'] = result['bb_middle'] = result['bb_lower'] = p
            result['bb_width'] = 0.0

        return result
