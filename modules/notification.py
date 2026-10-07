"""
客户通知模块 - 自动生成贸易全流程的客户通知内容
在贸易的不同阶段自动生成对应的通知文案，可通过邮件/微信/短信等渠道发送

通知类型：
1. 行情提醒 - 当价差信号触发时，自动通知关注的客户
2. 合同通知 - 合同审查完成后，通知客户合同已就绪/需要修改
3. 付款通知 - 发票生成后，通知客户付款（含PayPal付款链接）
4. 到账确认 - 付款成功后，自动确认到账并感谢
5. 发货通知 - 付款后触发发货，通知客户物流信息
6. 收货确认 - 提醒客户确认收货并反馈
7. 售后跟进 - 交易完成后跟进客户满意度

所有通知内容都用模板生成，支持变量替换（客户名称、金额、日期等）。
"""

from datetime import datetime, timedelta


# ============================================================
# 通知模板
# ============================================================

NOTIFICATION_TEMPLATES = {
    "market_alert": {
        "subject": "【行情提醒】{product}价差信号触发 - 收敛概率{probability}%",
        "body": """尊敬的{customer_name}：

您好！

我们的AI行情监测系统检测到 {product} 出现价差收敛信号，具体信息如下：

📊 信号详情：
- 信号类型：{signal_name}
- 当前状态：{direction}
- 参考收敛概率：{probability}%
- 置信度：{confidence}
- z-score：{z_value}
- 信号日期：{date}

📝 信号说明：
{reasons}

💡 操作建议：
当前价差偏离历史均值，存在向均值回归的可能性。建议您结合自身采购计划和风险承受能力，考虑是否把握此次交易机会。

如需了解更多详情或希望我们的业务团队与您联系，请随时回复本邮件。

祝商祺！

{company_name}
AI智能贸易助手
{date}""",
    },

    "contract_ready": {
        "subject": "【合同通知】合同{contract_id}已通过AI审查，请确认",
        "body": """尊敬的{customer_name}：

您好！

您的合同（编号：{contract_id}）已通过我们的AI智能合同审查系统审查。

📋 审查结果：
- 问题总数：{total_issues} 个
- 高风险问题：{high_count} 个
- 中风险问题：{medium_count} 个
- 低风险问题：{low_count} 个

{issues_summary}

📎 附件：
- 合同原文
- AI审查报告（含详细修改建议）

请您查阅合同及审查报告，如有疑问请随时与我们联系。确认无误后，我们将进入下一步流程。

祝商祺！

{company_name}
AI智能贸易助手
{date}""",
    },

    "payment_request": {
        "subject": "【付款通知】{payment_type_name} - 金额{currency} {amount}",
        "body": """尊敬的{customer_name}：

您好！

您的{payment_type_name}已生成，请通过以下链接完成支付：

💰 付款信息：
- 发票编号：{invoice_number}
- 支付类型：{payment_type_name}
- 金额：{currency} {amount}
- 关联合同：{contract_id}

🔗 付款链接：
{payment_url}

（请点击上方链接，通过PayPal安全完成支付。支持PayPal余额、信用卡、借记卡等多种支付方式。）

📝 说明：
{note}

支付完成后，系统将自动确认到账并触发后续流程。如有任何支付问题，请随时联系我们。

祝商祺！

{company_name}
AI智能贸易助手
{date}""",
    },

    "payment_confirmed": {
        "subject": "【到账确认】已收到您的付款 {currency} {amount}，感谢！",
        "body": """尊敬的{customer_name}：

您好！

我们已收到您的付款，详情如下：

✅ 付款确认：
- 发票编号：{invoice_number}
- 支付类型：{payment_type_name}
- 金额：{currency} {amount}
- 交易号：{transaction_id}
- 到账时间：{paid_at}

🎉 后续流程已自动启动：
{next_actions}

我们将尽快为您安排后续事宜。如需了解进度，请随时联系我们。

感谢您的信任与支持！

{company_name}
AI智能贸易助手
{date}""",
    },

    "shipping_notice": {
        "subject": "【发货通知】您的货物已发出，请注意查收",
        "body": """尊敬的{customer_name}：

您好！

您的货物已发出，物流信息如下：

🚚 发货信息：
- 合同编号：{contract_id}
- 货物名称：{product_name}
- 数量：{quantity}
- 发货日期：{ship_date}
- 预计到货：{estimated_arrival}
- 物流公司：{logistics_company}
- 运单号：{tracking_number}

🔍 物流查询：
您可通过 {logistics_company} 官网或客服热线查询物流状态，运单号：{tracking_number}

📝 收货须知：
1. 请在收货时当场验收货物数量和外观
2. 如发现货物损坏或数量不符，请在收货后24小时内联系我们
3. 质量异议期为货到后{quality_objection_days}天，请在此期限内提出质量异议

如有任何问题，请随时联系我们。

祝商祺！

{company_name}
AI智能贸易助手
{date}""",
    },

    "delivery_confirmation": {
        "subject": "【收货提醒】请确认货物已收到并反馈",
        "body": """尊敬的{customer_name}：

您好！

根据物流信息，您的货物（合同编号：{contract_id}）预计已于 {estimated_arrival} 送达。

📦 请您确认：
1. 货物是否已收到？
2. 数量是否正确？
3. 外观是否完好？
4. 质量是否符合要求？

如货物已收到且无异议，请回复"确认收货"，我们将完成交易闭环。
如有任何问题，请及时联系我们，我们将竭诚为您解决。

💡 温馨提示：
质量异议期为货到后{quality_objection_days}天，请在此期限内提出。

感谢您的配合！

{company_name}
AI智能贸易助手
{date}""",
    },

    "after_sales": {
        "subject": "【售后跟进】交易完成，感谢您的信任！",
        "body": """尊敬的{customer_name}：

您好！

您的订单（合同编号：{contract_id}）已完成全部交易流程。感谢您的信任与支持！

📊 本次交易回顾：
- 产品：{product_name}
- 数量：{quantity}
- 金额：{currency} {amount}
- 交易完成日期：{completion_date}

🔄 信任升级：
本次交易的顺利完成，标志着我们双方已建立初步信任。后续合作中，您可以享受：
- 更大额度的公对公直接交易（无需PayPal担保）
- 更优先的货源安排
- 更灵活的付款条件
- 专属客户经理服务

📞 持续服务：
我们的AI行情监测系统将持续为您提供市场动态。如有采购需求，请随时联系我们。

期待与您的长期合作！

{company_name}
AI智能贸易助手
{date}""",
    },
}


# ============================================================
# 通知生成函数
# ============================================================

def generate_notification(notification_type: str, **kwargs) -> dict:
    """
    生成客户通知内容（主入口）

    参数：
        notification_type: 通知类型（market_alert/contract_ready/payment_request/
                          payment_confirmed/shipping_notice/delivery_confirmation/after_sales）
        **kwargs: 模板变量（customer_name, company_name, date, amount等）

    返回：
        {
            "type": 通知类型,
            "type_name": 通知类型中文名,
            "subject": 邮件标题,
            "body": 邮件正文,
            "variables": 使用的变量,
        }
    """
    if notification_type not in NOTIFICATION_TEMPLATES:
        return {"error": f"未知的通知类型: {notification_type}"}

    template = NOTIFICATION_TEMPLATES[notification_type]

    # 默认变量
    defaults = {
        "company_name": "TradePilot AI 贸易有限公司",
        "date": datetime.now().strftime("%Y年%m月%d日"),
        "customer_name": "尊敬的客户",
    }
    defaults.update(kwargs)

    # 渲染标题和正文
    try:
        subject = template["subject"].format(**defaults)
        body = template["body"].format(**defaults)
    except KeyError as e:
        return {"error": f"模板变量缺失: {e}"}

    # 通知类型中文名
    type_names = {
        "market_alert": "行情提醒",
        "contract_ready": "合同通知",
        "payment_request": "付款通知",
        "payment_confirmed": "到账确认",
        "shipping_notice": "发货通知",
        "delivery_confirmation": "收货提醒",
        "after_sales": "售后跟进",
    }

    return {
        "type": notification_type,
        "type_name": type_names.get(notification_type, notification_type),
        "subject": subject,
        "body": body,
        "variables": defaults,
    }


def generate_trade_workflow_notifications(
    customer_name: str,
    contract_id: str,
    product_name: str,
    quantity: str,
    amount: float,
    currency: str = "CNY",
    company_name: str = "TradePilot AI 贸易有限公司",
) -> list:
    """
    生成一笔完整交易的全流程通知序列（演示用）

    返回从合同到售后的7个通知，按时间顺序排列
    """
    base_date = datetime.now()
    notifications = []

    # 0. 行情提醒（贸易流程的起点，建立专业信任）
    notifications.append(generate_notification(
        "market_alert",
        customer_name=customer_name,
        company_name=company_name,
        product="黑色系大宗商品",
        signal_name="冷轧-螺纹价差",
        direction="收敛",
        probability=60.0,
        confidence="高",
        z_value=1.5,
        reasons="当前价差偏离历史均值，存在向均值回归的可能性。建议结合自身采购计划考虑是否把握此次交易机会。",
        date=base_date.strftime("%Y年%m月%d日"),
    ))

    # 1. 合同通知
    notifications.append(generate_notification(
        "contract_ready",
        customer_name=customer_name,
        company_name=company_name,
        contract_id=contract_id,
        total_issues=3,
        high_count=1,
        medium_count=2,
        low_count=0,
        issues_summary="主要问题：缺少质量验收条款（高风险）、违约金比例未约定（中风险）、不可抗力条款过于简单（中风险）。建议修改后签署。",
        date=base_date.strftime("%Y年%m月%d日"),
    ))

    # 2. 付款通知（样品费/试单）
    notifications.append(generate_notification(
        "payment_request",
        customer_name=customer_name,
        company_name=company_name,
        payment_type_name="小额试单支付",
        currency=currency,
        amount=amount,
        invoice_number=f"TP-{base_date.strftime('%Y%m%d')}-0001",
        contract_id=contract_id,
        payment_url="https://www.sandbox.paypal.com/invoice/payerView/details/INV-DEMO1234",
        note="这是您首次合作的小额试单，使用PayPal安全支付通道，交易可追溯，降低首次合作信任门槛。试单成功后可转为大额公对公交易。注意：B2B大宗商品交易可能不适用PayPal标准买家保护，具体以PayPal条款为准。",
        date=base_date.strftime("%Y年%m月%d日"),
    ))

    # 3. 到账确认
    notifications.append(generate_notification(
        "payment_confirmed",
        customer_name=customer_name,
        company_name=company_name,
        currency=currency,
        amount=amount,
        invoice_number=f"TP-{base_date.strftime('%Y%m%d')}-0001",
        payment_type_name="小额试单支付",
        transaction_id="TXN-DEMO567890ABCD",
        paid_at=(base_date + timedelta(hours=2)).strftime("%Y年%m月%d日 %H:%M"),
        next_actions="1. 已自动发送到账确认通知\n2. 已通知仓库安排备货\n3. 已更新交易档案状态\n4. 试单完成后将引导转为大额公对公交易",
        date=base_date.strftime("%Y年%m月%d日"),
    ))

    # 4. 发货通知
    ship_date = base_date + timedelta(days=1)
    notifications.append(generate_notification(
        "shipping_notice",
        customer_name=customer_name,
        company_name=company_name,
        contract_id=contract_id,
        product_name=product_name,
        quantity=quantity,
        ship_date=ship_date.strftime("%Y年%m月%d日"),
        estimated_arrival=(ship_date + timedelta(days=3)).strftime("%Y年%m月%d日"),
        logistics_company="顺丰物流",
        tracking_number="SF1234567890",
        quality_objection_days="7",
        date=ship_date.strftime("%Y年%m月%d日"),
    ))

    # 5. 收货提醒
    delivery_date = ship_date + timedelta(days=3)
    notifications.append(generate_notification(
        "delivery_confirmation",
        customer_name=customer_name,
        company_name=company_name,
        contract_id=contract_id,
        estimated_arrival=delivery_date.strftime("%Y年%m月%d日"),
        quality_objection_days="7",
        date=delivery_date.strftime("%Y年%m月%d日"),
    ))

    # 6. 售后跟进
    completion_date = delivery_date + timedelta(days=7)
    notifications.append(generate_notification(
        "after_sales",
        customer_name=customer_name,
        company_name=company_name,
        contract_id=contract_id,
        product_name=product_name,
        quantity=quantity,
        currency=currency,
        amount=amount,
        completion_date=completion_date.strftime("%Y年%m月%d日"),
        date=completion_date.strftime("%Y年%m月%d日"),
    ))

    return notifications


if __name__ == "__main__":
    # 测试：生成一笔完整交易的全流程通知
    print("=== TradePilot AI 客户通知模块测试 ===\n")

    notifications = generate_trade_workflow_notifications(
        customer_name="上海建工材料有限公司",
        contract_id="GM20260915001",
        product_name="热轧带肋钢筋 HRB400E Φ16mm",
        quantity="50吨（试单）",
        amount=18250.00,
        currency="CNY",
    )

    for i, notif in enumerate(notifications, 1):
        print(f"\n{'='*60}")
        print(f"通知 {i}: {notif['type_name']}")
        print(f"{'='*60}")
        print(f"标题: {notif['subject']}")
        print(f"\n正文:\n{notif['body'][:300]}...")  # 只显示前300字

    print(f"\n\n共生成 {len(notifications)} 条通知，覆盖交易全流程。")
