"""
行情信号模块（公开版）

本模块是 SignalProvider 的薄包装，为 Streamlit 前端提供统一接口。
默认使用 DemoSignalProvider（合成演示数据），无需任何配置即可运行。
如需接入生产信号服务，请配置 SIGNAL_API_URL 环境变量。

重要声明：
本公开仓库中的行情信号模块使用合成演示数据，仅用于展示系统架构和用户流程。
不包含任何生产级策略参数、真实回测结果或交易建议。
生产级信号系统不在本仓库范围内。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.signal_provider import get_default_provider, SignalProvider

def _get_provider() -> SignalProvider:
    """每次调用创建 provider，避免共享可变降级状态。"""
    return get_default_provider()


def get_all_signals() -> dict:
    """
    返回结构化的信号结果

    返回格式：
    {
        "source": str,
        "degraded": bool,
        "error_code": str,
        "fallback_reason": str,
        "as_of": str,
        "signals": {"cold_fut_rb": {...}, ...},
    }
    """
    return _get_provider().get_all_signals()


def get_price_chart_data() -> dict:
    """
    返回价格走势图表数据（最近180个数据点）

    返回格式：
    {
        "dates": ["YYYY-MM-DD", ...],
        "cold_roll": [float, ...],
        "hc_futures": [float, ...],
        "rb_futures": [float, ...],
        "rb_spot": [float, ...],
    }
    """
    return _get_provider().get_price_chart_data()


def get_provider_info(bundle: dict = None) -> dict:
    """返回配置信息；传入 bundle 时返回该次调用的降级状态。"""
    provider = _get_provider()
    if bundle is None:
        bundle = provider.get_all_signals()
    return {
        "name": provider.provider_name,
        "is_demo": bool(bundle.get("is_demo", provider.is_demo)),
        "signals_source": bundle.get("source", getattr(provider, "signals_source", provider.provider_name)),
        "chart_source": getattr(provider, "chart_source", provider.provider_name),
        "fallback_reason": bundle.get("fallback_reason", ""),
        "as_of": bundle.get("as_of", getattr(provider, "as_of", "N/A")),
        "degraded": bool(bundle.get("degraded", False)),
        "error_code": bundle.get("error_code", ""),
    }
