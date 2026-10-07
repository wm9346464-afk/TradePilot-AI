#!/usr/bin/env python3
'''
生成 TradePilot AI 公开版使用的可复现合成行情数据。

数据不是真实行情，仅用于演示。默认生成 2024-06-03 至 2025-12-12 的
有效交易日（跳过周末和中国法定节假日），随机种子固定为 2026。
'''

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


RANDOM_SEED = 2026
START_DATE = date(2024, 6, 3)
END_DATE = date(2025, 12, 12)


# 2024-2025 年中国法定节假日（含与周末重叠的日期）。
# 生成器只逐日检查；周末本身会被首先跳过。
CHINA_HOLIDAYS = {
    # 2024
    date(2024, 1, 1),
    *[date(2024, 2, day) for day in range(10, 18)],
    *[date(2024, 4, day) for day in range(4, 7)],
    *[date(2024, 5, day) for day in range(1, 6)],
    date(2024, 6, 10),
    *[date(2024, 9, day) for day in range(15, 18)],
    *[date(2024, 10, day) for day in range(1, 8)],
    # 2025
    date(2025, 1, 1),
    *[date(2025, 1, day) for day in range(28, 32)],
    *[date(2025, 2, day) for day in range(1, 5)],
    *[date(2025, 4, day) for day in range(4, 7)],
    *[date(2025, 5, day) for day in range(1, 6)],
    *[date(2025, 5, day) for day in range(31, 32)],
    date(2025, 6, 1),
    date(2025, 6, 2),
    *[date(2025, 10, day) for day in range(1, 9)],
}


def generate_trading_dates(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    skip_china_holidays: bool = True,
):
    if start_date > end_date:
        raise ValueError('start_date must not be after end_date')

    dates = []
    current = start_date
    while current <= end_date:
        is_weekday = current.weekday() < 5
        is_holiday = current in CHINA_HOLIDAYS
        if is_weekday and (not skip_china_holidays or not is_holiday):
            dates.append(current)
        current += timedelta(days=1)
    return dates


def generate_demo_data(
    start_date: date = START_DATE,
    end_date: date = END_DATE,
    skip_china_holidays: bool = True,
):
    dates = generate_trading_dates(
        start_date=start_date,
        end_date=end_date,
        skip_china_holidays=skip_china_holidays,
    )
    np.random.seed(RANDOM_SEED)
    rows = []
    for index, current_date in enumerate(dates):
        trend = index * 0.25
        medium_cycle = 18.0 * np.sin(2.0 * np.pi * index / 60.0)
        slow_cycle = 12.0 * np.sin(2.0 * np.pi * index / 120.0)
        rb_close = 3150.0 + trend + medium_cycle + np.random.normal(0.0, 28.0)
        hc_close = rb_close + 255.0 + slow_cycle + np.random.normal(0.0, 18.0)
        cold_roll_close = (
            hc_close
            + 850.0
            + 10.0 * np.sin(2.0 * np.pi * index / 90.0)
            + np.random.normal(0.0, 22.0)
        )
        rb_spot = (
            rb_close
            + 55.0
            + 9.0 * np.cos(2.0 * np.pi * index / 45.0)
            + np.random.normal(0.0, 16.0)
        )
        rows.append(
            {
                'date': current_date.isoformat(),
                'rb_close': round(float(rb_close), 2),
                'hc_close': round(float(hc_close), 2),
                'cold_roll_close': round(float(cold_roll_close), 2),
                'rb_spot': round(float(rb_spot), 2),
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            'date',
            'rb_close',
            'hc_close',
            'cold_roll_close',
            'rb_spot',
        ],
    )


def main():
    project_root = Path(__file__).resolve().parent.parent
    output_path = project_root / 'data' / 'demo_market_data.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = generate_demo_data()
    df.to_csv(output_path, index=False, encoding='utf-8')
    first_date = df['date'].iloc[0]
    last_date = df['date'].iloc[-1]
    print(f'已生成 {len(df)} 行合成数据：{first_date} 至 {last_date}')
    print(f'输出文件：{output_path}')


if __name__ == '__main__':
    main()
