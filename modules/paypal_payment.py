"""
PayPal结算模块 - 大宗商品贸易新客户信任建立期的支付结算
用PayPal沙箱API实现：生成发票、发送付款链接、查询付款状态、自动触发后续流程

核心场景（信任建立期的小额支付）：
1. 样品费支付 - 新客户索要样品，自动生成PayPal样品费发票
2. 小额试单支付 - 新客户第一次合作，用PayPal安全支付通道降低信任门槛
3. 诚意保证金 - 大额订单前支付小额保证金，证明购买诚意
4. 跨境服务费 - 跨境贸易中的检验、物流、咨询等小额服务费

PayPal API使用的是沙箱环境（Sandbox），所有交易都是虚拟的，不涉及真实资金。
支持两种模式：
- API模式（LIVE SANDBOX）：调用PayPal沙箱API真实生成发票（需要配置PayPal开发者账号）
- 演示模式（DEMO）：用模拟数据展示完整流程（无需API密钥，需用户显式选择）

重要说明：
- PayPal标准买家保护主要适用于消费者购物场景，B2B大宗商品交易可能不适用。
- 本模块的价值在于提供便捷、可追溯的小额支付通道，降低新客户首次合作的信任门槛，
  不构成支付保障承诺。具体保障范围以PayPal官方条款为准。
"""

import os
import uuid
import requests
from datetime import datetime
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

# 环境变量（可选）
try:
    from dotenv import load_dotenv
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# PayPal沙箱API端点
PAYPAL_SANDBOX_API = "https://api-m.sandbox.paypal.com"

# 内存存储（演示用，实际项目应使用数据库或session存储）
_invoice_store = {}


# ============================================================
# 工具函数
# ============================================================

def _to_decimal(value) -> Decimal:
    """安全转换为Decimal，保留两位小数"""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_merchant_email() -> str:
    """
    获取PayPal商家邮箱（必须是沙箱账号中已验证的邮箱）
    从环境变量 PAYPAL_MERCHANT_EMAIL 读取，未配置则返回空字符串
    """
    return os.getenv("PAYPAL_MERCHANT_EMAIL", "")


def get_merchant_name() -> str:
    """获取商家名称，从环境变量 PAYPAL_MERCHANT_NAME 读取，有默认值"""
    return os.getenv("PAYPAL_MERCHANT_NAME", "TradePilot AI")


# ============================================================
# PayPal API 认证
# ============================================================

def get_paypal_access_token() -> str:
    """
    获取PayPal API访问令牌（OAuth2 Client Credentials）
    需要环境变量：PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET
    """
    client_id = os.getenv("PAYPAL_CLIENT_ID", "")
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return ""

    try:
        auth = (client_id, client_secret)
        data = {"grant_type": "client_credentials"}
        response = requests.post(
            f"{PAYPAL_SANDBOX_API}/v1/oauth2/token",
            auth=auth,
            data=data,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"获取PayPal令牌失败: {e}")
        return ""


def is_paypal_configured() -> bool:
    """
    检查PayPal API是否已完整配置
    需要：CLIENT_ID、CLIENT_SECRET、MERCHANT_EMAIL
    """
    return bool(
        os.getenv("PAYPAL_CLIENT_ID")
        and os.getenv("PAYPAL_CLIENT_SECRET")
        and os.getenv("PAYPAL_MERCHANT_EMAIL")
    )


# ============================================================
# 发票生成（API模式 - LIVE SANDBOX）
# ============================================================

def create_invoice_api(
    buyer_email: str,
    buyer_name: str,
    items: list,
    note: str = "",
    currency: str = "USD",
) -> dict:
    """
    调用PayPal API创建发票（草稿状态）

    参数：
        buyer_email: 买家邮箱
        buyer_name: 买家名称
        items: 商品列表，每个item包含 name(名称), quantity(数量), unit_price(单价)
        note: 发票备注
        currency: 货币代码（USD/CNY/EUR等）

    返回：发票信息字典，失败返回 {"success": False, "error": "..."}
    """
    access_token = get_paypal_access_token()
    if not access_token:
        return {"success": False, "error": "无法获取PayPal访问令牌，请检查API密钥配置"}

    merchant_email = get_merchant_email()
    if not merchant_email:
        return {"success": False, "error": "未配置PayPal商家邮箱（PAYPAL_MERCHANT_EMAIL），该邮箱必须是沙箱账号中已验证的邮箱"}

    try:
        # 【修复1】加 Prefer: return=representation，确保创建后返回完整发票JSON
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Prefer": "return=representation",
        }

        # 构造发票明细
        invoice_items = []
        total = Decimal("0.00")
        for item in items:
            # 【修复3】quantity 使用字符串（PayPal schema要求string，支持最多5位小数）
            quantity_str = str(item["quantity"])
            # 【修复4】金额使用 Decimal 计算，避免浮点精度问题
            unit_price_dec = _to_decimal(item["unit_price"])
            quantity_dec = Decimal(str(item["quantity"]))
            item_total = (unit_price_dec * quantity_dec).quantize(Decimal("0.01"))
            total += item_total

            invoice_items.append({
                "name": item["name"],
                "quantity": quantity_str,
                "unit_amount": {
                    "currency_code": currency,
                    "value": str(unit_price_dec),
                },
            })

        invoice_number = f"TP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        payload = {
            "detail": {
                "currency_code": currency,
                "note": note,
                "invoice_number": invoice_number,
            },
            # 【修复2】使用环境变量配置的真实沙箱商家邮箱，不硬编码
            "invoicer": {
                "name": {"full_name": get_merchant_name()},
                "email_address": merchant_email,
            },
            "primary_recipients": [
                {
                    "billing_info": {
                        "name": {"full_name": buyer_name},
                        "email_address": buyer_email,
                    }
                }
            ],
            "items": invoice_items,
            # 注意：创建发票时不传 amount 字段，PayPal会根据items自动计算总金额。
            # 如果传入amount，PayPal会进行校验，可能因计算方式差异返回 calculation_error。
        }

        response = requests.post(
            f"{PAYPAL_SANDBOX_API}/v2/invoicing/invoices",
            headers=headers,
            json=payload,
            timeout=15,
        )
        response.raise_for_status()

        # 解析响应（因为设置了 return=representation，这里应该有完整JSON body）
        resp_data = {}
        if response.content:
            try:
                resp_data = response.json()
            except Exception:
                pass

        invoice_id = resp_data.get("id", "")
        # 【修复6】从响应中读取 recipient_view_url（买家付款页面URL），不使用 Location header
        recipient_view_url = resp_data.get("detail", {}).get("metadata", {}).get("recipient_view_url", "")
        if not recipient_view_url:
            # 兼容：有些响应结构可能在其他位置
            recipient_view_url = resp_data.get("recipient_view_url", "")
        # 从响应中读取发票编号
        resp_invoice_number = resp_data.get("detail", {}).get("invoice_number", invoice_number)

        if not invoice_id:
            return {"success": False, "error": "PayPal创建发票成功但未返回发票ID，请检查API响应"}

        return {
            "success": True,
            "mode": "LIVE_SANDBOX",
            "invoice_id": invoice_id,
            "invoice_number": resp_invoice_number,
            "recipient_view_url": recipient_view_url,
            "payment_url": recipient_view_url,  # 统一字段名，方便前端使用
            "status": "DRAFT",
            "total": float(total),
            "currency": currency,
            "buyer_email": buyer_email,
            "buyer_name": buyer_name,
            "items": items,
            "note": note,
            "created_at": datetime.now().isoformat(),
        }

    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.response.json().get("message", str(e))
        except Exception:
            error_detail = str(e)
        return {"success": False, "error": f"PayPal API HTTP错误: {error_detail}"}
    except Exception as e:
        return {"success": False, "error": f"创建PayPal发票失败: {str(e)}"}


def send_invoice_api(invoice_id: str) -> dict:
    """
    发送发票（将草稿发票发送给买家，生成付款链接）

    返回：{"success": bool, "error": str}
    """
    access_token = get_paypal_access_token()
    if not access_token or not invoice_id:
        return {"success": False, "error": "未授权或发票ID为空"}

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        response = requests.post(
            f"{PAYPAL_SANDBOX_API}/v2/invoicing/invoices/{invoice_id}/send",
            headers=headers,
            json={"send_to_invoicer": True},
            timeout=10,
        )
        response.raise_for_status()
        return {"success": True}
    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.response.json().get("message", str(e))
        except Exception:
            error_detail = str(e)
        return {"success": False, "error": f"发送发票HTTP错误: {error_detail}"}
    except Exception as e:
        return {"success": False, "error": f"发送PayPal发票失败: {str(e)}"}


def get_invoice_status_api(invoice_id: str) -> dict:
    """
    查询发票状态（PAID/UNPAID/SENT/DRAFT等）
    返回：{"success": bool, "status": ..., ...}
    """
    access_token = get_paypal_access_token()
    if not access_token or not invoice_id:
        return {"success": False, "error": "未授权或发票ID为空"}

    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{PAYPAL_SANDBOX_API}/v2/invoicing/invoices/{invoice_id}",
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        payments = data.get("payments") or []
        if isinstance(payments, dict):
            payments = [payments]
        first_payment = payments[0] if isinstance(payments, list) and payments else {}
        if not isinstance(first_payment, dict):
            first_payment = {}

        paid_at = first_payment.get("date") or first_payment.get("payment_date") or ""
        transaction_id = (
            first_payment.get("payment_id")
            or first_payment.get("transaction_id")
            or ""
        )

        return {
            "success": True,
            "mode": "LIVE_SANDBOX",
            "status": data.get("status", "UNKNOWN"),
            "amount": data.get("amount", {}).get("value", "0"),
            "currency": data.get("amount", {}).get("currency_code", "USD"),
            "invoice_number": data.get("detail", {}).get("invoice_number", ""),
            "recipient_view_url": data.get("detail", {}).get("metadata", {}).get("recipient_view_url", ""),
            "paid_at": paid_at,
            "transaction_id": transaction_id,
        }
    except Exception as e:
        return {"success": False, "error": f"查询PayPal发票状态失败: {str(e)}"}


# ============================================================
# 演示模式（DEMO - 模拟完整支付流程）
# ============================================================

def create_invoice_demo(
    payment_type: str,
    buyer_name: str,
    buyer_email: str,
    amount: float,
    currency: str = "USD",
    contract_id: str = "",
) -> dict:
    """
    演示模式：生成模拟发票（不调用真实API）

    参数：
        payment_type: 支付类型
        buyer_name: 买家名称
        buyer_email: 买家邮箱
        amount: 金额
        currency: 货币
        contract_id: 关联合同编号

    返回：完整的发票信息（含模拟付款链接）
    """
    invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    invoice_number = f"TP-{datetime.now().strftime('%Y%m%d')}-{len(_invoice_store) + 1:04d}"

    # 支付类型对应的商品描述
    type_descriptions = {
        "sample_fee": {
            "name": "样品费 - 黑色系大宗商品样品",
            "note": "新客户样品费用，含样品成本及快递费。样品确认满意后可转为正式订单。",
        },
        "trial_order": {
            "name": "小额试单 - 安全支付通道",
            # 【修复表述】去掉"买家保护机制"，改为"安全支付通道+可追溯"
            "note": "新客户首次合作小额试单，使用PayPal安全支付通道，交易可追溯，降低首次合作信任门槛。试单成功后可转为大额公对公交易。注意：B2B大宗商品交易可能不适用PayPal标准买家保护，具体以PayPal条款为准。",
        },
        "deposit": {
            "name": "诚意保证金",
            "note": "大额订单诚意保证金，证明购买诚意。保证金可在后续大额货款中抵扣。",
        },
        "service_fee": {
            "name": "跨境服务费",
            "note": "跨境贸易相关服务费（检验、物流、咨询等），支持多币种支付。",
        },
    }

    type_info = type_descriptions.get(payment_type, type_descriptions["sample_fee"])

    invoice = {
        "success": True,
        "mode": "DEMO",
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "status": "DRAFT",  # DRAFT -> SENT -> PAID
        "payment_type": payment_type,
        "payment_type_name": type_info["name"],
        "buyer_name": buyer_name,
        "buyer_email": buyer_email,
        "amount": float(_to_decimal(amount)),
        "currency": currency,
        "note": type_info["note"],
        "contract_id": contract_id,
        "created_at": datetime.now().isoformat(),
        "sent_at": None,
        "paid_at": None,
        "payment_method": None,
        "transaction_id": None,
        # 模拟付款链接（实际API会返回真实的PayPal付款页面URL）
        "payment_url": f"https://www.sandbox.paypal.com/invoice/payerView/details/{invoice_id}",
        "recipient_view_url": f"https://www.sandbox.paypal.com/invoice/payerView/details/{invoice_id}",
    }

    # 存入内存
    _invoice_store[invoice_id] = invoice
    return invoice


def send_invoice_demo(invoice_id: str) -> dict:
    """
    演示模式：发送发票（状态从DRAFT变为SENT，生成付款链接）
    """
    if invoice_id not in _invoice_store:
        return {"success": False, "error": "发票不存在"}

    invoice = _invoice_store[invoice_id]
    invoice["status"] = "SENT"
    invoice["sent_at"] = datetime.now().isoformat()

    return {
        "success": True,
        "invoice_id": invoice_id,
        "status": "SENT",
        "payment_url": invoice["payment_url"],
        "message": f"发票已发送至 {invoice['buyer_email']}，买家可通过付款链接完成支付。",
    }


def simulate_payment_demo(invoice_id: str, payment_method: str = "paypal_balance") -> dict:
    """
    演示模式：模拟买家完成付款（状态从SENT变为PAID）
    实际项目中，这一步由买家在PayPal页面完成付款，系统通过Webhook或轮询监听状态变化。
    """
    if invoice_id not in _invoice_store:
        return {"success": False, "error": "发票不存在"}

    invoice = _invoice_store[invoice_id]
    if invoice["status"] != "SENT":
        return {"success": False, "error": f"发票当前状态为{invoice['status']}，无法付款"}

    invoice["status"] = "PAID"
    invoice["paid_at"] = datetime.now().isoformat()
    invoice["payment_method"] = payment_method
    invoice["transaction_id"] = f"TXN-{uuid.uuid4().hex[:12].upper()}"

    return {
        "success": True,
        "invoice_id": invoice_id,
        "status": "PAID",
        "paid_at": invoice["paid_at"],
        "transaction_id": invoice["transaction_id"],
        "amount": invoice["amount"],
        "currency": invoice["currency"],
        "message": f"付款成功！收到 {invoice['currency']} {invoice['amount']:.2f}，交易号 {invoice['transaction_id']}。",
        # 付款成功后应触发的后续动作（实际项目中自动执行）
        "next_actions": [
            "自动发送到账确认通知给买家",
            "通知仓库安排备货/发货",
            "更新交易档案状态",
            "如果是样品费：触发样品发货流程",
            "如果是试单：触发试单发货流程，完成后引导转为大额公对公交易",
            "如果是保证金：记录保证金，后续大额货款中自动抵扣",
        ],
    }


def get_invoice_demo(invoice_id: str) -> dict:
    """获取演示发票详情"""
    return _invoice_store.get(invoice_id, {})


def list_invoices_demo() -> list:
    """列出所有演示发票"""
    return list(_invoice_store.values())


# ============================================================
# 主入口函数
# ============================================================

def create_and_send_invoice(
    payment_type: str,
    buyer_name: str,
    buyer_email: str,
    amount: float,
    currency: str = "USD",
    contract_id: str = "",
    use_api: bool = True,
) -> dict:
    """
    创建并发送发票（主入口）

    【修复8】API模式失败时返回错误，不自动回退演示模式。
    演示模式只能由用户显式选择（use_api=False）。

    参数：
        payment_type: 支付类型
        buyer_name: 买家名称
        buyer_email: 买家邮箱
        amount: 金额
        currency: 货币
        contract_id: 关联合同编号
        use_api: True=尝试API模式（失败返回错误），False=强制演示模式

    返回：发票信息（含付款链接），失败返回 {"success": False, "error": "..."}
    """
    if use_api:
        if not is_paypal_configured():
            return {
                "success": False,
                "error": "PayPal API未完整配置。需要设置 PAYPAL_CLIENT_ID、PAYPAL_CLIENT_SECRET、PAYPAL_MERCHANT_EMAIL 环境变量。如需体验演示流程，请选择演示模式。",
                "mode": "NOT_CONFIGURED",
            }

        # API模式：创建发票
        items = [{
            "name": f"{payment_type} - TradePilot AI",
            "quantity": "1",  # 【修复3】字符串
            "unit_price": float(_to_decimal(amount)),
        }]
        invoice = create_invoice_api(buyer_email, buyer_name, items, currency=currency)

        if not invoice.get("success"):
            # 【修复8】API失败直接返回错误，不静默回退演示模式
            return invoice

        # 【修复5】检查发送结果，失败则返回错误
        send_result = send_invoice_api(invoice["invoice_id"])
        if not send_result.get("success"):
            return {
                "success": False,
                "error": f"发票创建成功但发送失败: {send_result.get('error', '未知错误')}",
                "invoice_id": invoice["invoice_id"],
                "mode": "LIVE_SANDBOX",
            }

        invoice["status"] = "SENT"
        invoice["sent_at"] = datetime.now().isoformat()
        return invoice

    # 演示模式（用户显式选择 use_api=False）
    invoice = create_invoice_demo(payment_type, buyer_name, buyer_email, amount, currency, contract_id)
    result = send_invoice_demo(invoice["invoice_id"])
    invoice["status"] = "SENT"
    invoice["send_result"] = result
    return invoice


def check_payment_status(invoice_id: str, use_api: bool = True) -> dict:
    """
    查询付款状态（主入口）

    【修复7】API模式真实查询PayPal发票状态，支持刷新按钮调用
    """
    if use_api and is_paypal_configured():
        status = get_invoice_status_api(invoice_id)
        if status.get("success"):
            return status
        # API查询失败返回错误
        return status

    # 演示模式
    invoice = get_invoice_demo(invoice_id)
    if invoice:
        return {
            "success": True,
            "mode": "DEMO",
            "status": invoice["status"],
            "amount": invoice["amount"],
            "currency": invoice["currency"],
            "paid_at": invoice.get("paid_at"),
            "transaction_id": invoice.get("transaction_id"),
            "invoice_number": invoice.get("invoice_number"),
        }
    return {"success": False, "status": "NOT_FOUND", "error": "发票不存在"}


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=== TradePilot AI PayPal结算模块测试（演示模式） ===\n")

    # 1. 创建并发送样品费发票
    print("1. 创建样品费发票（演示模式）...")
    invoice = create_and_send_invoice(
        payment_type="sample_fee",
        buyer_name="上海建工材料有限公司",
        buyer_email="buyer@example.com",
        amount=150.00,
        currency="USD",
        contract_id="GM20260915001",
        use_api=False,  # 强制演示模式
    )
    print(f"   模式: {invoice.get('mode')}")
    print(f"   发票号: {invoice['invoice_number']}")
    print(f"   金额: {invoice['currency']} {invoice['amount']:.2f}")
    print(f"   状态: {invoice['status']}")
    print(f"   付款链接: {invoice['payment_url']}")

    # 2. 模拟买家付款
    print("\n2. 模拟买家付款...")
    payment_result = simulate_payment_demo(invoice["invoice_id"])
    print(f"   结果: {payment_result['message']}")
    print(f"   交易号: {payment_result['transaction_id']}")

    # 3. 查询最终状态
    print("\n3. 查询发票最终状态...")
    status = check_payment_status(invoice["invoice_id"], use_api=False)
    print(f"   状态: {status['status']}")
    print(f"   付款时间: {status.get('paid_at', 'N/A')}")

    # 4. 测试API未配置时的错误返回（不静默回退）
    print("\n4. 测试API模式（未配置时应返回错误，不回退演示）...")
    result = create_and_send_invoice(
        payment_type="sample_fee",
        buyer_name="测试客户",
        buyer_email="test@example.com",
        amount=100.00,
        use_api=True,  # 尝试API模式
    )
    if not result.get("success"):
        print(f"   ✅ 正确返回错误（不静默回退）: {result['error'][:60]}...")
    else:
        print(f"   ⚠️ API模式意外成功: {result}")

    print("\n=== 测试完成 ===")
