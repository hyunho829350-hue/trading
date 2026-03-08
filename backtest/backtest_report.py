"""
백테스트 HTML 리포트 생성
Plotly 기반 인터랙티브 차트
80만원 → 1억 달성 기간 예측
"""
import json
import math
import os
from datetime import datetime


class BacktestReport:
    INITIAL_CAPITAL = 800_000
    TARGET_CAPITAL  = 100_000_000

    def generate(self, result: dict, output_path: str = None) -> str:
        """HTML 리포트 생성, 저장 후 HTML 문자열 반환"""
        if output_path is None:
            output_path = f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        trades = result.get('trades', [])
        equity = result.get('equity_curve', [])
        html = self._build_html(result, trades, equity)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
        except Exception:
            pass

        return html

    def _build_html(self, result: dict, trades: list, equity: list) -> str:
        wr   = result.get('win_rate', 0)
        pr   = result.get('total_profit_rate', 0)
        mdd  = result.get('max_drawdown', 0)
        pf   = result.get('profit_factor', 0)
        total = result.get('total_trades', 0)
        fee  = result.get('total_fee_tax', 0)
        slip = result.get('total_slippage', 0)

        # 일평균 수익률 추정
        n_bars = len(equity)
        daily_return = 0.0
        if n_bars > 78 and equity[0] > 0:
            total_r = equity[-1] / equity[0] - 1
            daily_return = (1 + total_r) ** (1 / max(1, n_bars / 78)) - 1

        proj = self.calc_80만_to_1억_projection(daily_return)

        equity_json = json.dumps(equity[::max(1, len(equity)//1000)])  # 최대 1000포인트
        exit_reasons = result.get('exit_reasons', {})

        trade_rows = ''
        for i, t in enumerate(trades[-200:]):
            clr = 'profit' if t['net_profit'] > 0 else 'loss'
            trade_rows += (
                f'<tr class="{clr}">'
                f'<td>{i+1}</td>'
                f'<td>{t.get("exit_reason","")}</td>'
                f'<td>{t["buy_price"]:,.0f}</td>'
                f'<td>{t["sell_price"]:,.0f}</td>'
                f'<td>{t["quantity"]}</td>'
                f'<td>{t["net_profit"]:+,.0f}원</td>'
                f'<td>{t["net_profit_rate"]*100:+.2f}%</td>'
                f'</tr>'
            )

        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>백테스트 리포트 — 80만→1억</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
body{{font-family:Arial,sans-serif;background:#1a1a2e;color:#eee;margin:0;padding:16px}}
.hdr{{text-align:center;background:#16213e;border-radius:10px;padding:16px;margin-bottom:16px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.card{{background:#16213e;border-radius:8px;padding:16px;flex:1;min-width:120px;text-align:center}}
.val{{font-size:1.8em;font-weight:bold}}
.profit{{color:#00ff88}}.loss{{color:#ff4444}}.neutral{{color:#ffaa00}}
table{{width:100%;border-collapse:collapse;background:#16213e;border-radius:8px;margin-top:12px}}
th,td{{padding:6px 10px;border-bottom:1px solid #333;text-align:right}}
th{{background:#0f3460;text-align:center}}
tr.profit td:nth-last-child(-n+2){{color:#00ff88}}
tr.loss td:nth-last-child(-n+2){{color:#ff4444}}
.chart{{background:#16213e;border-radius:8px;padding:12px;margin-bottom:12px}}
.proj{{background:#0f3460;border-radius:8px;padding:16px;margin-bottom:12px;text-align:center}}
</style>
</head>
<body>
<div class="hdr"><h1>📊 백테스트 리포트</h1>
<p>80만원→1억 프로젝트 · {datetime.now().strftime('%Y-%m-%d %H:%M')}</p></div>

<div class="cards">
<div class="card"><div>총 수익률</div><div class="val {'profit' if pr>=0 else 'loss'}">{pr:+.1f}%</div></div>
<div class="card"><div>승률</div><div class="val {'profit' if wr>=50 else 'loss'}">{wr:.1f}%</div></div>
<div class="card"><div>손익비</div><div class="val neutral">{min(pf,99):.2f}</div></div>
<div class="card"><div>MDD</div><div class="val loss">-{mdd:.1f}%</div></div>
<div class="card"><div>총 매매</div><div class="val neutral">{total}회</div></div>
<div class="card"><div>수수료+세금</div><div class="val loss">-{fee:,.0f}원</div></div>
<div class="card"><div>슬리피지</div><div class="val loss">~{slip:,.0f}원</div></div>
</div>

<div class="proj">
<h2>🎯 80만원 → 1억 달성 예측</h2>
<p>일평균 {proj['daily_return_pct']:.3f}% 복리 기준</p>
<p>예상 달성: <strong>{proj['days_to_target']}거래일 ({proj['months_to_target']:.1f}개월)</strong></p>
<p>주간 {proj['weekly_return_pct']:.2f}% · 월간 {proj['monthly_return_pct']:.2f}%</p>
</div>

<div class="chart"><h2>자산 곡선</h2>
<div id="eq" style="height:280px"></div></div>

<div class="chart"><h2>청산 이유</h2>
<div id="exit" style="height:220px"></div></div>

<h2>매매 내역 (최근 200건)</h2>
<table><tr><th>#</th><th>청산이유</th><th>매수가</th><th>매도가</th><th>수량</th><th>순수익</th><th>수익률</th></tr>
{trade_rows}</table>

<script>
var eq={equity_json};
Plotly.newPlot('eq',[{{y:eq,type:'scatter',line:{{color:'#00ff88'}},name:'자산'}}],
{{paper_bgcolor:'#16213e',plot_bgcolor:'#16213e',font:{{color:'#eee'}},
 shapes:[{{type:'line',y0:{self.INITIAL_CAPITAL},y1:{self.INITIAL_CAPITAL},
           x0:0,x1:eq.length,line:{{color:'#555',dash:'dot'}}}}]}});
Plotly.newPlot('exit',[{{labels:{json.dumps(list(exit_reasons.keys()))},
values:{json.dumps(list(exit_reasons.values()))},type:'pie',hole:0.4}}],
{{paper_bgcolor:'#16213e',font:{{color:'#eee'}}}});
</script></body></html>"""

    def calc_80만_to_1억_projection(self, daily_return: float) -> dict:
        if daily_return <= 0:
            return {'days_to_target': 99999, 'months_to_target': 9999,
                    'daily_return_pct': 0, 'weekly_return_pct': 0, 'monthly_return_pct': 0}
        mult = self.TARGET_CAPITAL / self.INITIAL_CAPITAL
        days = math.log(mult) / math.log(1 + daily_return)
        return {
            'days_to_target': int(days),
            'months_to_target': days / 22,
            'daily_return_pct': daily_return * 100,
            'weekly_return_pct': ((1 + daily_return) ** 5 - 1) * 100,
            'monthly_return_pct': ((1 + daily_return) ** 22 - 1) * 100,
        }

    def compare_strategies(self, results_dict: dict) -> str:
        rows = ''
        best_wr = max((r.get('win_rate', 0) for r in results_dict.values()), default=0)
        for name, r in results_dict.items():
            wr = r.get('win_rate', 0)
            hl = ' style="background:#0f3460"' if wr == best_wr else ''
            rows += (f'<tr{hl}><td>{name}</td>'
                     f'<td>{wr:.1f}%</td>'
                     f'<td>{r.get("total_profit_rate",0):+.1f}%</td>'
                     f'<td>{min(r.get("profit_factor",0),99):.2f}</td>'
                     f'<td>-{r.get("max_drawdown",0):.1f}%</td>'
                     f'<td>{r.get("total_trades",0)}</td></tr>')
        return (f'<table><tr><th>전략</th><th>승률</th><th>수익률</th>'
                f'<th>손익비</th><th>MDD</th><th>거래수</th></tr>{rows}</table>')
