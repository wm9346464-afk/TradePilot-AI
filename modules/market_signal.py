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

from modules.signal_provider import get_default_provider, SignalProvider

# 全局provider实例（懒加载）
_provider: SignalProvider = None


def _get_provider() -> SignalProvider:
    """获取全局provider实例（懒加载）"""
    global _provider
    if _provider is None:
        _provider = get_default_provider()
    return _provider


def get_all_signals() -> dict:
    """
    返回所有信号的当前状态

    返回格式：
    {
        "cold_fut_rb": {
            "zh": "冷轧-螺纹价差观察",
            "direction": "观望/价差偏高...",
            "triggered": bool,
            "confidence": "高/中/低",
            "probability": float,
            "z": float,
            "date": "YYYY-MM-DD",
            "current_spread": float,
            "roll_mean": float,
            "reasons": [str, ...],
        },
        ...
    }
    """
    return _get_provider().get_all_signals()


def get_price_chart_data() -> dict:
    """
    返回价格走势图表数据（最近180个交易日）

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


def get_provider_info() -> dict:
    """返回当前信号提供者的信息（用于UI展示）"""
    provider = _get_provider()
    return {
        "name": provider.provider_name,
        "is_demo": provider.is_demo,
    }
