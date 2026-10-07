#!/usr/bin/env python3
"""
TradePilot AI - 大宗商品贸易新客户准入与信任建立智能体
PayPal AI Hackathon 参赛项目

核心功能：
1. 行情信号 - 黑色系大宗商品市场观察与价差分析（演示模式）
2. 合同审查 - AI智能合同检查（文字错误、条款完整性、数据一致性、风险提示）
3. PayPal结算 - 信任建立期小额支付（样品费、试单、保证金、跨境服务费）
4. 客户通知 - 贸易全流程自动通知生成

技术栈：Streamlit + Python + pandas + numpy + PayPal REST API + 大模型API
"""

import sys
import html
import logging
import os
from pathlib import Path

# 确保能导入modules包
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import numpy as np

# 导入四个核心模块
from modules.market_signal import (
    get_all_signals,
    get_price_chart_data,
    get_provider_info,
)
from modules.contract_checker import check_contract, SAMPLE_CONTRACT, is_ai_configured
from modules.paypal_payment import (
    create_and_send_invoice,
    retry_send_invoice,
    simulate_payment_demo,
    check_payment_status,
    list_invoices_demo,
    clear_invoices_demo,
    format_amount,
    is_paypal_configured,
)
from modules.notification import generate_notification, generate_trade_workflow_notifications
from modules.config import get_llm_config_status, get_paypal_config_status


logger = logging.getLogger(__name__)


# ============================================================
# Contract review shortcut callbacks
# ============================================================

def _load_sample_contract():
    '''Load the built-in sample contract for the review page.'''
    st.session_state['contract_text'] = SAMPLE_CONTRACT


def _clear_contract():
    '''Clear the contract input for the review page.'''
    st.session_state['contract_text'] = ''


# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="TradePilot AI - 大宗商品贸易智能体",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_signals():
    """缓存远程/演示信号，避免每次rerun都打远程API。"""
    return get_all_signals()

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-box {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
    }
    .signal-high { color: #d32f2f; font-weight: bold; }
    .signal-medium { color: #f57c00; font-weight: bold; }
    .signal-low { color: #388e3c; font-weight: bold; }
    .workflow-step {
        display: flex;
        align-items: center;
        padding: 0.8rem;
        background: #f0f4f8;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }
    .step-number {
        background: #2d5a87;
        color: white;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        margin-right: 1rem;
        flex-shrink: 0;
    }
    .mode-live {
        background: #e8f5e9;
        color: #2e7d32;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .mode-demo {
        background: #fff3e0;
        color: #e65100;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 侧边栏导航
# ============================================================

with st.sidebar:
    st.markdown("### 📊 TradePilot AI")
    st.markdown("**大宗商品贸易智能体**")
    st.markdown("---")

    page = st.radio(
        "功能导航",
        [
            "🏠 首页 / 项目介绍",
            "📈 行情信号看板",
            "📝 AI合同审查",
            "💳 PayPal结算",
            "📧 客户通知",
        ],
        index=0,
    )

    app_password = os.getenv("APP_PASSWORD", "")
    if app_password:
        entered_password = st.text_input("访问密码", type="password")
        if entered_password != app_password:
            st.warning("请输入访问密码")
            st.stop()

    st.markdown("---")
    st.markdown("### 系统状态")

    paypal_status = get_paypal_config_status()
    llm_status = get_llm_config_status()
    paypal_class = "mode-live" if paypal_status["state"] == "usable" else "mode-demo"
    llm_class = "mode-live" if llm_status["state"] == "usable" else "mode-demo"
    st.markdown(
        f"PayPal API: <span class='{paypal_class}'>{paypal_status['label']}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"AI合同审查: <span class='{llm_class}'>{llm_status['label']}</span>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("### 关于")
    st.markdown("PayPal AI Hackathon 2026 参赛项目")
    st.markdown("用AI+PayPal解决大宗商品贸易新客户信任问题")


# ============================================================
# 页面1：首页 / 项目介绍
# ============================================================

if page == "🏠 首页 / 项目介绍":
    st.markdown('<p class="main-header">TradePilot AI</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">大宗商品贸易新客户准入与信任建立智能体 | 用AI + PayPal 降低贸易信任门槛</p>', unsafe_allow_html=True)

    st.markdown("### 🎯 我们解决什么问题")
    st.markdown("""
    大宗商品贸易中，**新客户的第一次合作**是最大的痛点：
    - 买方怕付了款不发货，卖方怕发了货收不到钱
    - 大额公对公转账需要建立信任，但信任需要时间积累
    - 样品费、小额试单、保证金等小额支付场景缺乏便捷的支付工具
    - 合同审查依赖人工，效率低且容易遗漏风险
    """)

    st.markdown("### 💡 我们的解决方案")
    st.markdown("""
    **TradePilot AI** 构建了一个覆盖贸易全流程的智能体系统，用AI + PayPal解决新客户信任问题：

    1. **规则行情信号** — 市场观察与价差分析，为客户提供专业的市场洞察（演示数据）
    2. **AI合同审查** — 自动检查合同中的文字错误、条款缺失、数据不一致和法律风险
    3. **PayPal安全支付通道** — 样品费、小额试单、诚意保证金通过PayPal支付，交易可追溯，降低信任门槛
    4. **全流程自动通知** — 从合同到发货到售后，自动生成专业的客户通知

    > **说明**：PayPal标准买家保护主要适用于消费者购物场景，B2B大宗商品交易可能不适用。本项目的价值在于提供便捷、可追溯的小额支付通道，降低新客户首次合作的信任门槛，不构成支付保障承诺。
    """)

    st.markdown("### 🔄 新客户信任建立工作流")
    col1, col2 = st.columns([2, 1])
    with col1:
        steps = [
            ("新客户询盘", "规则行情系统提供专业市场分析，建立初步专业信任"),
            ("样品费支付", "通过PayPal支付样品费（小额、便捷、可追溯），降低首次合作门槛"),
            ("AI合同审查", "自动审查合同，确保条款完整、数据一致、风险可控"),
            ("小额试单支付", "通过PayPal完成小额试单，金额可控，交易可追溯"),
            ("试单成功 → 信任建立", "试单顺利完成，双方建立信任"),
            ("转为大额公对公交易", "信任建立后，后续大额交易转为传统公对公银行转账"),
        ]
        for i, (title, desc) in enumerate(steps, 1):
            st.markdown(f"""
            <div class="workflow-step">
                <div class="step-number">{i}</div>
                <div>
                    <strong>{title}</strong><br/>
                    <span style="color: #666; font-size: 0.9rem;">{desc}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    with col2:
        st.markdown("#### 📊 核心数据")
        st.markdown('<div class="metric-box"><h3>4大模块</h3><p>覆盖贸易全流程</p></div>', unsafe_allow_html=True)
        st.markdown('<div class="metric-box"><h3>3种模式</h3><p>AI真实/规则检查/演示</p></div>', unsafe_allow_html=True)
        st.markdown('<div class="metric-box"><h3>PayPal API</h3><p>沙箱环境真实集成</p></div>', unsafe_allow_html=True)

    st.markdown("### 🏗️ 技术架构")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("#### 📈 行情信号")
        st.markdown("- Python + pandas + numpy\n- Signal Provider架构设计\n- Demo/Remote双模式\n- 3个观察维度")
    with col2:
        st.markdown("#### 📝 合同审查")
        st.markdown("- 正则基础检查\n- 大模型API深度审查\n- Schema校验\n- 演示模式显式选择")
    with col3:
        st.markdown("#### 💳 PayPal结算")
        st.markdown("- PayPal REST API\n- 沙箱环境\n- 发票生成/发送/查询\n- Decimal金额精度")
    with col4:
        st.markdown("#### 📧 客户通知")
        st.markdown("- 7种通知模板\n- 变量自动替换\n- 全流程覆盖\n- 多渠道适配")

    st.markdown("---")
    st.markdown("### 🚀 开始体验")
    st.markdown("点击左侧导航栏，依次体验四大核心功能。")


# ============================================================
# 页面2：行情信号看板
# ============================================================

elif page == "📈 行情信号看板":
    st.title("📈 行情信号看板")
    st.markdown("黑色系大宗商品市场观察与价差分析")

    signal_bundle = _cached_get_all_signals()
    signals = signal_bundle.get("signals", {})
    provider_info = get_provider_info(signal_bundle)

    if signal_bundle.get("degraded"):
        st.warning(
            "远程信号已降级为Demo模式："
            f"{signal_bundle.get('fallback_reason', '远程响应格式无效')}"
        )
    elif provider_info.get("is_demo"):
        st.warning("⚠️ 当前为演示模式，使用合成数据展示系统功能。信号仅供演示，不构成投资建议。")

    st.caption(
        f"信号来源：{provider_info.get('signals_source', 'N/A')} | "
        f"图表来源：{provider_info.get('chart_source', 'N/A')} | "
        f"数据截止：{provider_info.get('as_of', 'N/A')}"
    )

    # 数据截止日期提示
    try:
        data_path = PROJECT_ROOT / "data" / "demo_market_data.csv"
        df_check = pd.read_csv(data_path)
        last_date = df_check.iloc[-1, 0] if len(df_check) > 0 else "未知"
        st.info(
            f"📅 演示数据截止日期：{last_date}。本模块监测价差变化，不预测价格涨跌，"
            "仅供贸易决策参考，不构成投资建议。"
        )
    except Exception as exc:
        logger.warning("读取演示数据截止日期失败: %s", exc)
        st.info(
            f"📅 数据截止日期：{provider_info.get('as_of', '未知')}。"
            "本模块不预测价格涨跌，仅供贸易决策参考，不构成投资建议。"
        )

    st.markdown("### 📊 当前信号概览")
    cols = st.columns(3)
    for i, (key, sig) in enumerate(signals.items()):
        with cols[i]:
            zh = html.escape(str(sig.get("zh", "")))
            direction = html.escape(str(sig.get("direction", "")))
            confidence = str(sig.get("confidence", "低"))
            confidence = confidence if confidence in {"高", "中", "低"} else "低"
            conf_class = {
                "高": "signal-high",
                "中": "signal-medium",
                "低": "signal-low",
            }.get(confidence, "signal-low")
            probability = sig.get("probability", 0.0)
            probability = float(probability) if isinstance(probability, (int, float)) else 0.0
            z_value = sig.get("z")
            z_text = (
                f"{z_value:.2f}"
                if isinstance(z_value, (int, float)) and np.isfinite(z_value)
                else "N/A"
            )
            if sig.get("triggered"):
                st.markdown(f"""
                <div class="metric-box" style="border-top: 4px solid #d32f2f;">
                    <h3 style="color: #d32f2f;">{direction}</h3>
                    <p><strong>{zh}</strong></p>
                    <p class="{conf_class}">置信度: {html.escape(confidence)}</p>
                    <p>参考概率: {probability:.1%}</p>
                    <p>z-score: {z_text}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-box" style="border-top: 4px solid #999;">
                    <h3 style="color: #999;">{direction}</h3>
                    <p><strong>{zh}</strong></p>
                    <p>置信度: {html.escape(confidence)}</p>
                    <p>z-score: {z_text}</p>
                    <p style="font-size: 0.8rem; color: #999;">未触发（建议观望）</p>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("### 📋 信号详情")
    for key, sig in signals.items():
        with st.expander(f"{sig['zh']} - {sig['direction']}（点击展开详情）", expanded=sig["triggered"]):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"**信号名称**: {sig['zh']}")
                st.markdown(f"**当前状态**: {sig['direction']}")
                st.markdown(f"**置信度**: {sig['confidence']}")
                st.markdown(f"**参考收敛概率**: {sig['probability']:.1%}")
                z_val = sig.get('z')
                # 【修复】if sig.get('z') 会把合法的0.0当成缺失，改用is not None
                if isinstance(z_val, (int, float)) and np.isfinite(z_val):
                    st.markdown(f"**z-score**: {z_val:.2f}")
                else:
                    st.markdown("**z-score**: N/A")
                st.markdown(f"**信号日期**: {sig['date']}")
                current_spread = sig.get('current_spread')
                if isinstance(current_spread, (int, float)) and np.isfinite(current_spread):
                    st.markdown(f"**当前价差**: {current_spread:.0f}")
                roll_mean = sig.get('roll_mean')
                if isinstance(roll_mean, (int, float)) and np.isfinite(roll_mean):
                    st.markdown(f"**120日均值**: {roll_mean:.0f}")
            with col2:
                st.markdown("**信号说明**:")
                reasons = sig.get("reasons") or []
                if isinstance(reasons, str):
                    reasons = [reasons]
                for reason in reasons:
                    st.markdown(f"- {reason}")

    st.markdown("### 📉 价格走势（最近180个数据点）")
    chart_data = get_price_chart_data()
    df_chart = pd.DataFrame({
        "日期": pd.to_datetime(chart_data["dates"]),
        "冷轧现货": chart_data["cold_roll"],
        "热卷期货": chart_data["hc_futures"],
        "螺纹期货": chart_data["rb_futures"],
        "螺纹现货": chart_data["rb_spot"],
    })
    df_chart = df_chart.set_index("日期")
    st.line_chart(df_chart, use_container_width=True)
    st.caption(f"图表数据来源：{provider_info.get('chart_source', 'N/A')}")

    with st.expander("📖 信号模块说明（点击展开）"):
        st.markdown("""
        ### 模块定位
        本行情信号模块是 TradePilot AI 系统的**市场上下文组件**，为贸易决策提供价差观察和市场状态参考。

        ### 公开版本说明
        本公开仓库使用 **Demo Signal Provider**，基于合成数据运行，用于展示系统架构和用户流程。
        生产级信号系统不在本仓库范围内，可通过配置 `SIGNAL_API_URL` 环境变量接入私有信号服务。

        ### 信号类型
        - 冷轧-螺纹价差观察
        - 冷轧-热卷价差观察
        - 螺纹基差观察

        ### 架构设计
        采用 Signal Provider 抽象接口设计，支持：
        - `DemoSignalProvider`：默认，合成数据，无需配置即可运行
        - `RemoteSignalProvider`：可选，调用私有生产服务获取信号

        ### 重要声明
        本模块信号仅作为贸易决策参考，不构成投资建议。演示数据不代表真实市场表现。
        """)


# ============================================================
# 页面3：AI合同审查
# ============================================================

elif page == "📝 AI合同审查":
    st.title("📝 AI合同审查")
    st.markdown("智能合同检查 | 文字错误 · 条款完整性 · 数据一致性 · 风险提示 · 合规性")

    # 【修复】用session_state管理contract_text，解决按钮不工作的问题
    if "contract_text" not in st.session_state:
        st.session_state["contract_text"] = ""
    if "contract_result" not in st.session_state:
        st.session_state["contract_result"] = None
    if "contract_processing" not in st.session_state:
        st.session_state["contract_processing"] = False

    st.warning(
        "⚠️ 启用AI深度审查后，合同全文将发送到配置的LLM服务。"
        "请先获得用户同意，并不要提交包含敏感信息的合同。"
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        contract_text = st.text_area(
            "请粘贴合同文本（或点击右侧按钮加载示例合同）",
            height=300,
            key="contract_text",
            placeholder="在此粘贴合同内容...",
            max_chars=20000,
        )
    with col2:
        st.markdown("#### 快捷操作")
        st.button("📄 加载示例合同", use_container_width=True, on_click=_load_sample_contract)
        st.button("🗑️ 清空", use_container_width=True, on_click=_clear_contract)

        # 【修复】演示模式显式开关
        force_demo = st.checkbox(
            "演示模式（预设模拟结果）",
            value=False,
            help="勾选后使用预设的模拟审查结果。不勾选时，若配置了AI API则进行真实AI审查，否则仅运行基础规则检查。"
        )
        use_ai = st.checkbox("启用AI深度审查", value=False, help="需要配置LLM_API_KEY环境变量，默认关闭")
        st.markdown("---")
        st.markdown("**检查维度**:")
        st.markdown("- 文字错误（错别字/标点）")
        st.markdown("- 条款完整性")
        st.markdown("- 数据一致性")
        st.markdown("- 风险提示")
        st.markdown("- 合规性")

    if st.button(
        "🔍 开始审查",
        type="primary",
        use_container_width=True,
        disabled=st.session_state["contract_processing"],
    ):
        if not contract_text or not contract_text.strip():
            st.warning("请先输入合同内容")
        else:
            st.session_state["contract_processing"] = True
            st.session_state["pending_contract_text"] = contract_text
            st.session_state["pending_use_ai"] = use_ai
            st.session_state["pending_force_demo"] = force_demo
            st.session_state["contract_result"] = None
            st.rerun()

    if st.session_state["contract_processing"]:
        pending_text = st.session_state.get("pending_contract_text", "")
        with st.spinner("正在审查合同，请稍候..."):
            result = check_contract(
                pending_text,
                use_ai=st.session_state.get("pending_use_ai", False),
                force_demo=st.session_state.get("pending_force_demo", False),
            )
        st.session_state["contract_result"] = result
        st.session_state["contract_processing"] = False
        st.rerun()

    result = st.session_state.get("contract_result")
    if result:
        st.markdown("### 📋 审查结果")

        mode_code = result.get("mode_code", "RULE_ONLY")
        mode_label = result.get("mode_label", result.get("mode", ""))
        if mode_code == "AI_LIVE":
            st.markdown(f"当前模式: <span class='mode-live'>{html.escape(mode_label)}</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"当前模式: <span class='mode-demo'>{html.escape(mode_label)}</span>", unsafe_allow_html=True)

        st.info(f"**{result['summary']}**")

        if result.get("ai_error"):
            st.warning(f"⚠️ {result['ai_error']}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("问题总数", result["total_issues"])
        with col2:
            st.metric("🔴 高风险", result["high_count"])
        with col3:
            st.metric("🟡 中风险", result["medium_count"])
        with col4:
            st.metric("🟢 低风险", result["low_count"])

        st.markdown("### 📝 问题详情")
        for i, issue in enumerate(result["issues"], 1):
            severity_color = {
                "高": "🔴 高风险",
                "中": "🟡 中风险",
                "低": "🟢 低风险",
            }.get(issue.get("severity", "低"), issue.get("severity", ""))
            with st.expander(
                f"{i}. {severity_color} | {issue['type']} | {str(issue['original'])[:30]}...",
                expanded=issue.get("severity") == "高",
            ):
                st.markdown(f"**问题类型**: {issue['type']}")
                st.markdown(f"**严重程度**: {severity_color}")
                st.markdown(f"**原文内容**: {issue['original']}")
                st.markdown(f"**修改建议**: {issue['suggestion']}")
                st.markdown(f"**详细说明**: {issue['description']}")

    st.markdown("---")
    st.caption("⚠️ **免责声明**：本工具提供的合同审查结果仅供参考，不构成法律意见。合同签署前请咨询专业律师。AI审查可能存在遗漏或误判，请结合人工审核。")


# ============================================================
# 页面4：PayPal结算
# ============================================================

elif page == "💳 PayPal结算":
    st.title("💳 PayPal结算")
    st.markdown("信任建立期小额支付 | 样品费 · 小额试单 · 诚意保证金 · 跨境服务费")

    paypal_status = get_paypal_config_status()
    if paypal_status["state"] == "usable":
        st.success("✅ PayPal 配置可用，将使用真实沙箱环境（LIVE SANDBOX）")
    elif paypal_status["state"] == "unverified":
        st.warning("⚠️ 已填写配置（未验证）：PayPal 配置格式未通过本地校验，请检查后重试。")
    else:
        st.warning(
            "⚠️ 当前为演示模式（DEMO MODE）。未配置PayPal API密钥，使用模拟数据展示流程。"
            "如需真实沙箱体验，请配置 PAYPAL_CLIENT_ID、PAYPAL_CLIENT_SECRET、"
            "PAYPAL_MERCHANT_EMAIL 环境变量。"
        )

    with st.expander("📖 关于PayPal支付保障（点击展开）"):
        st.markdown("""
        **重要说明**：
        - PayPal标准买家保护主要适用于消费者购物场景，B2B大宗商品交易可能不适用。
        - 本项目使用PayPal Invoicing API提供便捷、可追溯的小额支付通道，降低新客户首次合作的信任门槛。
        - 本项目不构成支付保障承诺，具体保障范围以PayPal官方条款为准。
        - 所有交易均在PayPal Sandbox（沙箱）环境中进行，不涉及真实资金。
        """)

    st.markdown("### 📝 创建付款发票")
    col1, col2 = st.columns(2)
    with col1:
        payment_type = st.selectbox(
            "支付类型",
            options=[
                ("sample_fee", "样品费 - 新客户样品费用"),
                ("trial_order", "小额试单 - 安全支付通道"),
                ("deposit", "诚意保证金"),
                ("service_fee", "跨境服务费"),
            ],
            format_func=lambda x: x[1],
        )
        buyer_name = st.text_input("买家名称", value="上海建工材料有限公司")
        buyer_email = st.text_input("买家邮箱", value="buyer@example.com")
    with col2:
        amount = st.number_input("金额", min_value=0.01, value=150.00, step=10.0)
        currency = st.selectbox(
            "货币",
            options=["USD", "CNY", "EUR"],
            index=0,
            help="PayPal 对 CNY 的支持受商家账户和国家限制；CNY 通常仅作为支付货币或 in-country 余额支持。",
        )
        contract_id = st.text_input("关联合同编号", value="GM20260915001")

    # 【修复】模式选择
    use_api = st.checkbox(
        "使用真实PayPal沙箱API",
        value=is_paypal_configured(),
        disabled=not is_paypal_configured(),
        help="未配置API密钥时此选项不可用，将使用演示模式。"
    )

    if "invoice_processing" not in st.session_state:
        st.session_state["invoice_processing"] = False
    if "last_invoice_result" not in st.session_state:
        st.session_state["last_invoice_result"] = None

    if st.button(
        "💰 创建并发送发票",
        type="primary",
        use_container_width=True,
        disabled=st.session_state["invoice_processing"],
    ):
        st.session_state["pending_invoice_args"] = {
            "payment_type": payment_type[0],
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "amount": amount,
            "currency": currency,
            "contract_id": contract_id,
            "use_api": use_api,
        }
        st.session_state["invoice_processing"] = True
        st.session_state["last_invoice_result"] = None
        st.rerun()

    if st.session_state["invoice_processing"]:
        invoice_args = st.session_state.get("pending_invoice_args", {})
        with st.spinner("正在创建PayPal发票..."):
            invoice_result = create_and_send_invoice(**invoice_args)
        st.session_state["last_invoice_result"] = invoice_result
        st.session_state["invoice_processing"] = False
        st.session_state["last_invoice_use_api"] = bool(invoice_args.get("use_api"))
        st.rerun()

    invoice = st.session_state.get("last_invoice_result")
    if invoice:
        if not invoice.get("success", True):
            invoice_id = invoice.get("invoice_id", "")
            if invoice.get("status") == "DRAFT" and invoice_id:
                st.warning(
                    f"发票草稿已创建（ID: {invoice_id}），但发送失败："
                    f"{invoice.get('detail') or invoice.get('error', '未知错误')}"
                )
                st.session_state["last_invoice_id"] = invoice_id
                if st.button("🔁 重试发送（只发送，不重新创建）", key="retry_send_invoice"):
                    retry_result = retry_send_invoice(
                        invoice_id,
                        use_api=st.session_state.get("last_invoice_use_api", True),
                    )
                    st.session_state["last_invoice_result"] = retry_result
                    st.rerun()
            else:
                st.error(f"❌ 发票创建失败: {invoice.get('error', '未知错误')}")
            mode = invoice.get("mode", "")
            if mode:
                st.caption(f"模式: {mode}")
        else:
            inv_mode = invoice.get("mode", "DEMO")
            if inv_mode == "LIVE_SANDBOX":
                st.success("✅ 发票创建并发送成功！（真实PayPal沙箱）")
                st.markdown("<span class='mode-live'>LIVE SANDBOX</span>", unsafe_allow_html=True)
            else:
                st.success("✅ 发票创建成功（演示模式，未实际发送）")
                st.markdown("<span class='mode-demo'>DEMO MODE</span>", unsafe_allow_html=True)

            invoice_amount = invoice.get("total", invoice.get("amount", 0.0))
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**发票编号**: {invoice.get('invoice_number', 'N/A')}")
                st.markdown(f"**支付类型**: {invoice.get('payment_type_name', 'N/A')}")
                st.markdown(f"**金额**: {format_amount(invoice_amount, invoice.get('currency', ''))}")
                st.markdown(f"**状态**: {invoice.get('status', 'N/A')}")
            with col2:
                st.markdown(f"**买家**: {invoice.get('buyer_name', 'N/A')}")
                st.markdown(f"**邮箱**: {invoice.get('buyer_email', 'N/A')}")
                st.markdown(f"**关联合同**: {invoice.get('contract_id', 'N/A')}")

            st.markdown("#### 🔗 付款链接")
            payment_url = invoice.get("payment_url", "") or invoice.get("recipient_view_url", "")
            if payment_url and inv_mode == "LIVE_SANDBOX":
                st.markdown(f"[{payment_url}]({payment_url})")
            elif payment_url:
                st.code(payment_url, language=None)
                st.caption("（模拟链接，不可用）")
            else:
                st.info("发票已创建，付款链接将在发送后生成。")

            if inv_mode == "LIVE_SANDBOX":
                st.info("买家点击上方链接，通过PayPal安全完成支付。支付成功后，可点击下方'刷新付款状态'按钮查询最新状态。")
            else:
                st.info("演示模式不会实际发送发票或打开真实付款页面；可点击下方按钮模拟买家付款。")
            st.session_state["last_invoice_id"] = invoice.get("invoice_id", "")

    # 付款操作
    st.markdown("---")
    st.markdown("### 💳 付款操作")

    last_invoice_id = st.session_state.get("last_invoice_id", "")
    last_use_api = st.session_state.get("last_invoice_use_api", False)
    invoice_id_to_pay = st.text_input("发票ID", value=last_invoice_id, help="输入要操作的发票ID")

    col1, col2 = st.columns(2)
    with col1:
        # 【修复】刷新付款状态按钮（真实查询）
        if st.button("🔄 刷新付款状态", use_container_width=True):
            if not invoice_id_to_pay:
                st.warning("请先创建发票或输入发票ID")
            else:
                with st.spinner("正在查询付款状态..."):
                    status = check_payment_status(invoice_id_to_pay, use_api=last_use_api)
                if status.get("success", False):
                    st.success(f"当前状态: **{status.get('status', 'UNKNOWN')}**")
                    if status.get("status") == "PAID":
                        st.markdown(f"**付款时间**: {status.get('paid_at', 'N/A')}")
                        st.markdown(f"**交易号**: {status.get('transaction_id', 'N/A')}")
                else:
                    st.error(f"查询失败: {status.get('error', '未知错误')}")

    with col2:
        # 模拟付款（仅演示模式）
        if st.button("✅ 模拟买家付款（演示模式）", use_container_width=True, disabled=last_use_api):
            if not invoice_id_to_pay:
                st.warning("请先创建发票或输入发票ID")
            elif last_use_api:
                st.info("真实沙箱模式下，请买家通过付款链接完成真实付款，然后点击'刷新付款状态'查询。")
            else:
                with st.spinner("正在处理付款..."):
                    result = simulate_payment_demo(invoice_id_to_pay)
                if result.get("success"):
                    st.success("🎉 付款成功！（演示模式）")
                    st.markdown(f"**交易号**: {result['transaction_id']}")
                    st.markdown(f"**金额**: {format_amount(result.get('amount', 0), result.get('currency', ''))}")
                    st.markdown(f"**到账时间**: {result['paid_at']}")
                    st.markdown("#### 🔄 演示：以下动作将在生产环境中自动触发")
                    for action in result["next_actions"]:
                        st.markdown(f"- {action}")
                else:
                    st.error(f"付款失败: {result.get('error', '未知错误')}")

    # 发票列表
    st.markdown("---")
    st.markdown("### 📋 发票记录（演示模式）")
    invoices = list_invoices_demo()
    if invoices:
        df_invoices = pd.DataFrame([{
            "发票编号": inv.get("invoice_number", ""),
            "类型": inv.get("payment_type_name", ""),
            "买家": inv.get("buyer_name", ""),
            "金额": format_amount(inv.get('total', inv.get('amount', 0)), inv.get('currency', '')),
            "状态": inv.get("status", ""),
            "创建时间": str(inv.get("created_at", ""))[:19],
        } for inv in invoices])
        st.dataframe(df_invoices, use_container_width=True)
        if st.button("🗑️ 清空当前会话发票", use_container_width=False):
            clear_invoices_demo()
            st.session_state["last_invoice_result"] = None
            st.session_state["last_invoice_id"] = ""
            st.rerun()
    else:
        st.info("暂无发票记录，请先创建发票")


# ============================================================
# 页面5：客户通知
# ============================================================

elif page == "📧 客户通知":
    st.title("📧 客户通知")
    st.markdown("贸易全流程自动通知生成 | 行情提醒 · 合同通知 · 付款通知 · 到账确认 · 发货通知 · 收货提醒 · 售后跟进")
    st.warning("⚠️ 所有通知为演示文案，未实际发送，不可直接复制使用")
    st.caption("当前为演示模式，仅生成通知文案，不实际发送。")

    mode = st.radio(
        "生成模式",
        ["单条通知生成", "完整交易流程通知（7条）"],
        horizontal=True,
    )

    if mode == "单条通知生成":
        col1, col2 = st.columns(2)
        with col1:
            notification_type = st.selectbox(
                "通知类型",
                options=[
                    ("market_alert", "📈 行情提醒"),
                    ("contract_ready", "📝 合同通知"),
                    ("payment_request", "💰 付款通知"),
                    ("payment_confirmed", "✅ 到账确认"),
                    ("shipping_notice", "🚚 发货通知"),
                    ("delivery_confirmation", "📦 收货提醒"),
                    ("after_sales", "🤝 售后跟进"),
                ],
                format_func=lambda x: x[1],
            )
            customer_name = st.text_input("客户名称", value="上海建工材料有限公司")
            company_name = st.text_input("我方公司名称", value="TradePilot AI 贸易有限公司")
        with col2:
            if notification_type[0] == "market_alert":
                product = st.text_input("产品", value="黑色系大宗商品")
                signal_name = st.text_input("信号名称", value="冷轧-螺纹价差")
                direction = st.text_input("信号方向", value="收敛")
                probability = st.number_input("参考概率(%)", value=60.0, min_value=0.0, max_value=100.0)
                confidence = st.text_input("置信度", value="高")
                z_value = st.number_input("z-score", value=1.23)
                extra_vars = {
                    "product": product, "signal_name": signal_name,
                    "direction": direction, "probability": probability,
                    "confidence": confidence, "z_value": z_value,
                    "reasons": "当前价差偏离历史均值，存在向均值回归的可能性（演示数据）。",
                    "date": "2026年10月05日",
                }
            elif notification_type[0] == "contract_ready":
                contract_id = st.text_input("合同编号", value="GM20260915001")
                total_issues = st.number_input("问题总数", value=3)
                high_count = st.number_input("高风险", value=1)
                medium_count = st.number_input("中风险", value=2)
                low_count = st.number_input("低风险", value=0)
                extra_vars = {
                    "contract_id": contract_id, "total_issues": int(total_issues),
                    "high_count": int(high_count), "medium_count": int(medium_count),
                    "low_count": int(low_count),
                    "issues_summary": "主要问题：缺少质量验收条款（高风险）、违约金比例未约定（中风险）。",
                    "date": "2026年10月05日",
                }
            elif notification_type[0] == "payment_request":
                payment_type_name = st.text_input("支付类型", value="小额试单支付")
                amount = st.number_input("金额", value=18250.00)
                currency = st.text_input("货币", value="CNY")
                invoice_number = st.text_input("发票编号", value="TP-20261005-0001")
                contract_id = st.text_input("合同编号", value="GM20260915001")
                payment_url = st.text_input(
                    "付款链接（模拟链接，不可用）",
                    value="https://www.sandbox.paypal.com/invoice/payerView/details/INV-DEMO",
                )
                extra_vars = {
                    "payment_type_name": payment_type_name, "amount": amount,
                    "currency": currency, "invoice_number": invoice_number,
                    "contract_id": contract_id, "payment_url": payment_url,
                    "note": "首次合作小额试单，使用PayPal安全支付通道，交易可追溯。",
                    "date": "2026年10月05日",
                }
            elif notification_type[0] == "payment_confirmed":
                amount = st.number_input("金额", value=18250.00)
                currency = st.text_input("货币", value="CNY")
                invoice_number = st.text_input("发票编号", value="TP-20261005-0001")
                payment_type_name = st.text_input("支付类型", value="小额试单支付")
                transaction_id = st.text_input("交易号", value="TXN-DEMO123456")
                paid_at = st.text_input("到账时间", value="2026年10月05日 16:30")
                extra_vars = {
                    "amount": amount, "currency": currency,
                    "invoice_number": invoice_number, "payment_type_name": payment_type_name,
                    "transaction_id": transaction_id, "paid_at": paid_at,
                    "next_actions": "1. 生产环境将发送到账确认通知\n2. 生产环境将通知仓库备货\n3. 生产环境将更新交易档案",
                    "date": "2026年10月05日",
                }
            elif notification_type[0] == "shipping_notice":
                contract_id = st.text_input("合同编号", value="GM20260915001")
                product_name = st.text_input("产品名称", value="热轧带肋钢筋 HRB400E Φ16mm")
                quantity = st.text_input("数量", value="50吨")
                ship_date = st.text_input("发货日期", value="2026年10月06日")
                estimated_arrival = st.text_input("预计到货", value="2026年10月09日")
                logistics_company = st.text_input("物流公司", value="顺丰物流")
                tracking_number = st.text_input("运单号（示例单号）", value="SF1234567890")
                extra_vars = {
                    "contract_id": contract_id, "product_name": product_name,
                    "quantity": quantity, "ship_date": ship_date,
                    "estimated_arrival": estimated_arrival,
                    "logistics_company": logistics_company, "tracking_number": tracking_number,
                    "quality_objection_days": "7",
                    "date": "2026年10月06日",
                }
            elif notification_type[0] == "delivery_confirmation":
                contract_id = st.text_input("合同编号", value="GM20260915001")
                estimated_arrival = st.text_input("预计到货日期", value="2026年10月09日")
                extra_vars = {
                    "contract_id": contract_id,
                    "estimated_arrival": estimated_arrival,
                    "quality_objection_days": "7",
                    "date": "2026年10月09日",
                }
            else:
                contract_id = st.text_input("合同编号", value="GM20260915001")
                product_name = st.text_input("产品名称", value="热轧带肋钢筋 HRB400E Φ16mm")
                quantity = st.text_input("数量", value="50吨")
                amount = st.number_input("金额", value=18250.00)
                currency = st.text_input("货币", value="CNY")
                completion_date = st.text_input("完成日期", value="2026年10月16日")
                extra_vars = {
                    "contract_id": contract_id, "product_name": product_name,
                    "quantity": quantity, "amount": amount, "currency": currency,
                    "completion_date": completion_date,
                    "date": "2026年10月16日",
                }

        if st.button("📧 生成通知", type="primary", use_container_width=True):
            result = generate_notification(
                notification_type[0],
                customer_name=customer_name,
                company_name=company_name,
                **extra_vars,
            )
            if "error" in result:
                st.error(result["error"])
            else:
                st.success("✅ 通知文案生成成功（未发送）！")
                st.markdown(f"**标题**: {result['subject']}")
                st.markdown("**正文**:")
                st.text_area("通知内容", value=result["body"], height=400)

    else:
        st.markdown("### 🔄 生成一笔完整交易的全流程通知（7条）")
        st.markdown("从行情提醒到售后跟进，覆盖新客户信任建立的完整生命周期。")

        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input("客户名称", value="上海建工材料有限公司", key="wf_customer")
            contract_id = st.text_input("合同编号", value="GM20260915001", key="wf_contract")
            product_name = st.text_input("产品名称", value="热轧带肋钢筋 HRB400E Φ16mm", key="wf_product")
        with col2:
            quantity = st.text_input("数量", value="50吨（试单）", key="wf_quantity")
            amount = st.number_input("金额", value=18250.00, key="wf_amount")
            currency = st.text_input("货币", value="CNY", key="wf_currency")
            company_name = st.text_input("我方公司名称", value="TradePilot AI 贸易有限公司", key="wf_company")

        if st.button("🔄 生成全流程通知", type="primary", use_container_width=True):
            with st.spinner("正在生成7条通知..."):
                notifications = generate_trade_workflow_notifications(
                    customer_name=customer_name,
                    contract_id=contract_id,
                    product_name=product_name,
                    quantity=quantity,
                    amount=amount,
                    currency=currency,
                    company_name=company_name,
                )

            st.success(f"✅ 成功生成 {len(notifications)} 条通知文案（未发送）！")

            for i, notif in enumerate(notifications, 1):
                with st.expander(f"通知 {i}: {notif['type_name']} - {notif['subject'][:40]}...", expanded=(i == 1)):
                    st.markdown(f"**标题**: {notif['subject']}")
                    st.markdown("**正文**:")
                    st.text_area(f"通知内容_{i}", value=notif["body"], height=300, key=f"notif_{i}")


# ============================================================
# 页脚
# ============================================================

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #999; font-size: 0.85rem;'>"
    "TradePilot AI © 2026 | PayPal AI Hackathon 参赛项目 | "
    "用AI + PayPal 解决大宗商品贸易新客户信任问题"
    "</div>",
    unsafe_allow_html=True,
)
