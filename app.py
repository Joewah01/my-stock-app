import akshare as ak
import pandas as pd
from datetime import datetime
import streamlit as st

# 页面配置：适配 iPhone 13 Pro 宽屏
st.set_page_config(page_title="纪律交易助手", layout="wide", page_icon="🛡️")

class DisciplineTrader:
    def __init__(self, total_capital=100000):
        self.total_capital = total_capital # 你的总资金，可在侧边栏修改
        self.risk_per_trade = 0.02         # 单笔最大亏损占总资金 2%
        self.stop_loss_pct = 0.05          # 固定止损比例 5%
        self.take_profit_pct = 0.15        # 止盈比例 15% (盈亏比 3:1)
        
    def get_market_status(self):
        """判断大盘环境：上证指数是否站上 20 日均线"""
        try:
            sh_df = ak.stock_zh_index_daily(symbol="sh000001").tail(25)
            current_price = sh_df['close'].iloc[-1]
            ma20 = sh_df['close'].rolling(window=20).mean().iloc[-1]
            return current_price > ma20, current_price, ma20
        except Exception as e:
            return False, 0, 0

    def select_stocks(self, sector_filter=None):
        """筛选符合趋势的股票，支持板块过滤"""
        try:
            stock_df = ak.stock_zh_a_spot()
            
            # 基础筛选：避免追高，过滤流动性差的
            candidates = stock_df[
                (stock_df['涨跌幅'] > -2) & 
                (stock_df['涨跌幅'] < 4) & # 放宽一点上限，捕捉启动初期
                (stock_df['换手率'] > 2) & 
                (stock_df['换手率'] < 15) &
                (stock_df['量比'] > 1.2)   # 量比要求更高，确保有资金关注
            ]
            
            # 如果有板块过滤，这里简化处理：通过名称关键词匹配（实际项目中应接板块接口）
            if sector_filter and sector_filter.strip():
                keywords = [k.strip() for k in sector_filter.split('、') if k.strip()]
                # 简单匹配：股票名称或行业包含关键词
                mask = candidates['名称'].str.contains('|'.join(keywords), na=False) | \
                       candidates['行业'].str.contains('|'.join(keywords), na=False)
                candidates = candidates[mask]

            # 按量比排序，取前 10 个
            selected = candidates.nlargest(10, '量比')
            return selected[['代码', '名称', '最新价', '涨跌幅', '量比', '换手率', '行业']]
        except Exception as e:
            st.error(f"筛选股票失败: {e}")
            return pd.DataFrame()

    def calculate_position(self, buy_price, stop_price):
        """核心风控：计算该买多少股"""
        if buy_price <= stop_price:
            return 0
        # 每股最大亏损
        loss_per_share = buy_price - stop_price
        # 允许的最大总亏损金额
        max_loss_amount = self.total_capital * self.risk_per_trade
        # 可买股数 (向下取整到 100 的倍数)
        shares = int(max_loss_amount / loss_per_share / 100) * 100
        return shares

    def generate_plan(self, row):
        """生成带仓位管理的交易计划"""
        current_price = row['最新价']
        stop_price = current_price * (1 - self.stop_loss_pct)
        take_profit_price = current_price * (1 + self.take_profit_pct)
        
        # 计算仓位
        shares = self.calculate_position(current_price, stop_price)
        cost = shares * current_price
        
        return {
            "代码": row['代码'],
            "名称": row['名称'],
            "行业": row['行业'],
            "建议买入价": round(current_price, 2),
            "🛑严格止损价": round(stop_price, 2),
            "🎯目标止盈价": round(take_profit_price, 2),
            "✅建议买入股数": shares,
            "💰预计占用资金": round(cost, 2)
        }

# --- 界面布局 ---
st.title("🛡️ 纪律交易助手 · 回本专用版")
st.markdown("> &zwnj;**核心原则**&zwnj;：宁可错过，不可做错。止损是铁律，仓位是生命。")

# 侧边栏：个性化设置
with st.sidebar:
    st.header("⚙️ 个人设置")
    total_capital = st.number_input("我的总资金 (元)", value=100000, step=10000)
    sector_filter = st.text_input("只看哪些板块？(用、隔开)", placeholder="例如：半导体、光伏")
    st.divider()
    st.info("💡 提示：\n1. 只有大盘安全才显示标的\n2. 建议股数已根据 2% 风控自动计算\n3. 触发止损请无条件执行")

# 主逻辑区
if st.button("🔄 生成今日铁血策略", type="primary", use_container_width=True):
    trader = DisciplineTrader(total_capital=total_capital)
    
    # 1. 检查大盘
    is_safe, cur_idx, ma20_idx = trader.get_market_status()
    
    if not is_safe:
        st.error(f"⚠️ &zwnj;**危险信号**&zwnj;：上证指数 ({cur_idx:.2f}) 低于 20 日均线 ({ma20_idx:.2f})")
        st.warning("🚫 &zwnj;**今日禁止开新仓！**&zwnj; 请管住手，空仓观望是最好的操作。")
        st.stop() # 停止运行
    else:
        st.success(f"✅ 大盘安全 (指数: {cur_idx:.2f} > MA20: {ma20_idx:.2f})")

    # 2. 筛选股票
    with st.spinner("正在扫描全市场，寻找高胜率标的..."):
        stocks = trader.select_stocks(sector_filter)
        
    if stocks.empty:
        st.warning("😴 今日无符合【量比+趋势+板块】要求的标的，建议休息。")
    else:
        st.subheader("📋 今日交易计划表")
        plans = [trader.generate_plan(row) for _, row in stocks.iterrows()]
        plan_df = pd.DataFrame(plans)
        
        # 展示表格，重点突出止损和仓位
        st.dataframe(
            plan_df.style
            .highlight_max(axis=0, subset=['✅建议买入股数'], color='lightgreen')
            .set_properties(**{'background-color': '#ffcccc', 'font-weight': 'bold'}, subset=['🛑严格止损价']),
            use_container_width=True,
            hide_index=True
        )
        
        st.balloons()
        st.caption("注：以上数据基于实时行情计算，请在开盘后 9:30-10:00 间参考使用。")

# 底部版权
st.divider()
st.caption(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源: Akshare")
