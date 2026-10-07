"""
合同审查模块 - AI智能合同检查
用大模型API自动检查贸易合同中的问题

检查维度：
1. 文字错误：错别字、标点错误、格式不一致
2. 条款完整性：关键条款是否缺失（标的、数量、价格、交货、付款、违约、争议解决）
3. 数据一致性：金额大小写是否一致、数量单位是否统一、日期是否合理
4. 风险提示：不利条款、模糊表述、潜在法律风险
5. 合规检查：是否符合大宗商品贸易惯例

三种运行模式：
- AI_LIVE：调用大模型API进行真实审查（需要配置API密钥）
- RULE_ONLY：仅运行基础正则检查（AI未配置或调用失败时）
- DEMO_FIXTURE：显式演示模式，返回预设模拟结果（需用户明确选择）

重要：AI未配置或调用失败时，不会自动注入演示结果，只返回基础检查结果，
并明确标注当前模式。演示固定结果只能由用户显式选择（force_demo=True）。
"""

import os
import re
import json
import requests
from datetime import datetime
from pathlib import Path

# 环境变量管理（python-dotenv可选，没装也能运行）
try:
    from dotenv import load_dotenv
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass  # 没有安装python-dotenv时跳过，直接用系统环境变量


# 合法的问题严重程度
VALID_SEVERITIES = {"高", "中", "低"}
# 合法的问题类型
VALID_TYPES = {"文字错误", "条款完整性", "数据一致性", "数据错误", "风险提示", "合规性", "格式问题"}


# ============================================================
# 配置检查
# ============================================================

def is_ai_configured() -> bool:
    """检查AI API是否已配置（需要 LLM_API_KEY 环境变量）"""
    return bool(os.getenv("LLM_API_KEY", ""))


# ============================================================
# Schema 校验
# ============================================================

def validate_issue(issue: dict) -> bool:
    """
    校验单个问题对象是否符合schema要求
    必须包含：type, severity, original, suggestion, description
    severity 必须是 高/中/低 之一
    """
    if not isinstance(issue, dict):
        return False
    required_fields = ["type", "severity", "original", "suggestion", "description"]
    for field in required_fields:
        if field not in issue or not issue[field]:
            return False
    if issue["severity"] not in VALID_SEVERITIES:
        return False
    return True


def validate_issues(issues: list) -> list:
    """过滤并校验问题列表，只返回符合schema的问题"""
    if not isinstance(issues, list):
        return []
    return [issue for issue in issues if validate_issue(issue)]


# ============================================================
# 基础检查（不依赖API，用正则表达式做简单的文本检查）
# ============================================================

def basic_text_check(contract_text: str) -> list:
    """
    基础文本检查（正则表达式，不依赖API）
    检查：常见错别字、金额格式、日期格式、关键条款缺失
    """
    issues = []

    # 1. 检查常见错别字（贸易合同中常见的）
    common_typos = {
        "签定": "签订",
        "做为": "作为",
        "帐户": "账户",
        "帐号": "账号",
        "按装": "安装",
        "部置": "部署",
        "即然": "既然",
        "交待": "交代",
    }
    for wrong, right in common_typos.items():
        if wrong in contract_text:
            count = contract_text.count(wrong)
            issues.append({
                "type": "文字错误",
                "severity": "中",
                "original": wrong,
                "suggestion": right,
                "description": f"发现「{wrong}」{count}处，建议改为「{right}」。",
            })

    # 【修复】"订金"不是错别字，是法律含义不同的词，改为风险提示
    if "订金" in contract_text:
        count = contract_text.count("订金")
        issues.append({
            "type": "风险提示",
            "severity": "中",
            "original": "订金",
            "suggestion": "明确为「定金」或「预付款」，并约定相应效力",
            "description": f"发现「订金」{count}处。「订金」和「定金」法律含义不同：「定金」有担保效力，违约方需双倍返还；「订金」仅为预付款，不具有担保效力。请明确约定其性质和效力。",
        })

    # "其它"改为"其他"（用于事物时）
    if "其它" in contract_text:
        count = contract_text.count("其它")
        issues.append({
            "type": "文字错误",
            "severity": "低",
            "original": "其它",
            "suggestion": "其他",
            "description": f"发现「其它」{count}处。用于事物时规范写法为「其他」。",
        })

    # 2. 检查金额格式（人民币大写是否存在）
    money_pattern = r'[\d,]+(\.\d+)?\s*[元万元]'
    money_matches = re.findall(money_pattern, contract_text)
    if money_matches and not any(kw in contract_text for kw in ["人民币", "大写", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖", "拾"]):
        issues.append({
            "type": "条款完整性",
            "severity": "高",
            "original": "金额仅有阿拉伯数字",
            "suggestion": "添加人民币大写金额",
            "description": "合同中发现金额数字，但未找到人民币大写。贸易合同应同时标注大写金额，防止篡改。",
        })

    # 3. 检查关键条款是否缺失
    key_clauses = {
        "标的": ["品名", "品种", "规格", "材质", "货物", "产品名称"],
        "数量": ["数量", "吨", "重量", "千克"],
        "价格": ["单价", "总价", "金额", "价格", "元/吨"],
        "质量标准": ["质量标准", "质量要求", "符合", "标准", "GB/T", "GB "],
        "交货": ["交货", "交付", "发货", "运输", "物流"],
        "付款": ["付款", "支付", "结算", "货款"],
        "违约责任": ["违约", "赔偿", "违约金"],
        "争议解决": ["争议", "仲裁", "诉讼", "法院", "管辖"],
        "不可抗力": ["不可抗力"],
        "合同期限": ["有效期", "期限", "生效", "终止"],
    }
    for clause_name, keywords in key_clauses.items():
        if not any(kw in contract_text for kw in keywords):
            issues.append({
                "type": "条款完整性",
                "severity": "高" if clause_name in ["标的", "数量", "价格", "付款", "质量标准"] else "中",
                "original": f"缺少「{clause_name}」条款",
                "suggestion": f"补充「{clause_name}」相关条款",
                "description": f"合同中未找到「{clause_name}」相关内容。{clause_name}是贸易合同的重要条款，建议补充。",
            })

    # 4. 检查日期格式是否合理（用datetime验证，包括2月31日等）
    date_pattern = r'(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})[日]?'
    dates = re.findall(date_pattern, contract_text)
    for year, month, day in dates:
        try:
            datetime(int(year), int(month), int(day))
        except ValueError:
            issues.append({
                "type": "数据错误",
                "severity": "高",
                "original": f"{year}年{month}月{day}日",
                "suggestion": "检查日期是否正确",
                "description": f"发现不合理的日期：{year}年{month}月{day}日，该日期不存在，请核实。",
            })

    # 5. 检查是否有空白占位符（模板未填完）
    placeholders = ["____", "XXXX", "待定", "待填", "【】", "[]"]
    for ph in placeholders:
        if ph in contract_text:
            count = contract_text.count(ph)
            issues.append({
                "type": "格式问题",
                "severity": "中",
                "original": ph,
                "suggestion": "填写完整内容",
                "description": f"发现空白占位符「{ph}」{count}处，合同模板可能未填写完整。",
            })

    return issues


# ============================================================
# AI深度审查（调用大模型API）
# ============================================================

def ai_deep_check(contract_text: str) -> dict:
    """
    调用大模型API进行深度合同审查

    返回：
        {
            "success": bool,           # 是否成功
            "issues": list,            # 问题列表（已通过schema校验）
            "error": str,              # 错误信息（失败时）
            "mode": str,               # 模式：AI_LIVE / AI_NOT_CONFIGURED / AI_ERROR
        }
    """
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        return {
            "success": False,
            "issues": [],
            "error": "未配置LLM_API_KEY环境变量",
            "mode": "AI_NOT_CONFIGURED",
        }

    api_url = os.getenv("LLM_API_URL", "https://ark.cn-beijing.volces.com/api/v3/chat/completions")
    model_name = os.getenv("LLM_MODEL_NAME", "doubao-1-5-pro-32k-250115")

    # 构造提示词
    prompt = f"""你是一位专业的大宗商品贸易合同审查专家。请仔细审查以下合同，找出所有问题。

审查维度：
1. 文字错误：错别字、标点错误、语法错误、格式不一致
2. 条款完整性：标的、数量、质量、价格、交货、付款、违约责任、争议解决、不可抗力等关键条款是否完整
3. 数据一致性：金额大小写是否一致、数量单位是否统一、日期是否合理、数字计算是否正确（如数量×单价是否等于总价）
4. 风险提示：不利条款、模糊表述、权责不清、潜在法律风险
5. 合规性：是否符合大宗商品贸易惯例和相关法规

合同内容：
{contract_text}

请以JSON格式返回审查结果，格式如下：
[
  {{
    "type": "问题类型（文字错误/条款完整性/数据一致性/数据错误/风险提示/合规性/格式问题）",
    "severity": "严重程度（高/中/低）",
    "original": "原文内容",
    "suggestion": "修改建议",
    "description": "详细说明"
  }}
]

只返回JSON数组，不要返回其他内容。每个问题必须包含全部5个字段。"""

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        data = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        response = requests.post(api_url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # 解析JSON（处理可能的markdown代码块包裹）
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        raw_issues = json.loads(content)

        # 【修复3】schema校验，过滤不符合格式的问题
        valid_issues = validate_issues(raw_issues)
        if isinstance(raw_issues, list):
            filtered_count = len(raw_issues) - len(valid_issues)
        else:
            # 非数组响应无法逐条计数，计为至少1条格式异常，避免误报“未发现问题”。
            filtered_count = 1

        return {
            "success": True,
            "issues": valid_issues,
            "error": "",
            "mode": "AI_LIVE",
            "filtered_count": filtered_count,
        }

    except requests.exceptions.HTTPError as e:
        error_detail = str(e)
        try:
            error_detail = e.response.json().get("error", {}).get("message", str(e))
        except Exception:
            pass
        return {
            "success": False,
            "issues": [],
            "error": f"AI API HTTP错误: {error_detail}",
            "mode": "AI_ERROR",
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "issues": [],
            "error": f"AI返回结果JSON解析失败: {str(e)}",
            "mode": "AI_ERROR",
        }
    except Exception as e:
        return {
            "success": False,
            "issues": [],
            "error": f"AI审查调用失败: {str(e)}",
            "mode": "AI_ERROR",
        }


# ============================================================
# 演示模式（预设的模拟审查结果，仅在用户显式选择时使用）
# ============================================================

def demo_check_result() -> list:
    """
    演示模式：返回预设的模拟审查结果
    仅在用户显式选择演示模式（force_demo=True）时使用
    """
    return [
        {
            "type": "文字错误",
            "severity": "中",
            "original": "签定合同",
            "suggestion": "签订合同",
            "description": "「签定」应为「签订」。「签定」不是规范用法，法律上应使用「签订合同」。",
        },
        {
            "type": "风险提示",
            "severity": "中",
            "original": "订金",
            "suggestion": "明确为「定金」或「预付款」",
            "description": "「订金」和「定金」法律含义不同。「定金」有担保效力，违约方需双倍返还；「订金」仅为预付款，不具有担保效力。请明确约定。",
        },
        {
            "type": "条款完整性",
            "severity": "高",
            "original": "缺少质量验收标准",
            "suggestion": "补充质量验收条款，明确标准、检验方法和异议期限",
            "description": "合同未约定质量验收标准和异议期限。大宗商品贸易中，质量异议期通常为货到后7-15天，建议明确约定，避免后续纠纷。",
        },
        {
            "type": "数据一致性",
            "severity": "高",
            "original": "金额大写缺失",
            "suggestion": "添加人民币大写金额",
            "description": "合同总金额仅有阿拉伯数字，未标注人民币大写。贸易合同应同时标注大写金额，防止金额被篡改。",
        },
        {
            "type": "风险提示",
            "severity": "中",
            "original": "不可抗力条款过于简单",
            "suggestion": "细化不可抗力范围、通知义务和减损措施",
            "description": "不可抗力条款仅一句话带过。建议明确：1）不可抗力的具体范围；2）发生后多少小时内通知对方；3）双方的减损义务；4）持续多少天可以解除合同。",
        },
        {
            "type": "风险提示",
            "severity": "中",
            "original": "违约金比例未约定",
            "suggestion": "明确逾期付款和逾期交货的违约金比例",
            "description": "合同未约定逾期违约金比例。建议约定：买方逾期付款，按日万分之五支付违约金；卖方逾期交货，按日万分之三支付违约金。",
        },
        {
            "type": "合规性",
            "severity": "低",
            "original": "争议解决方式未明确",
            "suggestion": "明确约定仲裁或诉讼管辖",
            "description": "合同未明确争议解决方式。建议约定：因本合同引起的争议，双方协商解决；协商不成的，提交有管辖权的人民法院诉讼解决，或提交仲裁委员会仲裁。",
        },
    ]


# ============================================================
# 主入口函数
# ============================================================

def check_contract(
    contract_text: str,
    use_ai: bool = True,
    force_demo: bool = False,
) -> dict:
    """
    合同审查主入口

    【修复】三种模式明确区分，AI未配置/失败时不自动注入演示结果：
    - AI_LIVE：use_ai=True 且 API已配置 且 调用成功 → 基础检查 + AI深度审查
    - RULE_ONLY：use_ai=True 但API未配置/调用失败，或 use_ai=False → 仅基础检查
    - DEMO_FIXTURE：force_demo=True → 基础检查 + 预设演示结果（需用户显式选择）

    参数：
        contract_text: 合同文本内容
        use_ai: 是否尝试使用AI深度审查
        force_demo: 是否强制使用演示模式（显式选择，优先级高于use_ai）

    返回：
        {
            "total_issues": 问题总数,
            "high_count": 高严重程度数量,
            "medium_count": 中严重程度数量,
            "low_count": 低严重程度数量,
            "issues": [问题列表],
            "summary": "审查总结",
            "mode": "运行模式",
            "ai_error": "AI错误信息（如有）",
            "filtered_count": "AI返回但被schema过滤的问题数量",
        }
    """
    if not contract_text or not contract_text.strip():
        return {
            "total_issues": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "issues": [],
            "summary": "请输入合同内容",
            "mode": "空",
            "ai_error": "",
            "filtered_count": 0,
        }

    # 1. 基础检查（始终运行）
    all_issues = basic_text_check(contract_text)
    mode = "基础规则检查"
    ai_error = ""
    filtered_count = 0

    # 2. 演示模式（用户显式选择 force_demo=True）
    if force_demo:
        demo_issues = demo_check_result()
        # 避免重复：只添加基础检查没有覆盖的问题
        existing_keys = {(i["type"], i["original"]) for i in all_issues}
        for issue in demo_issues:
            key = (issue["type"], issue["original"])
            if key not in existing_keys:
                all_issues.append(issue)
        mode = "演示模式（预设模拟结果，非真实AI审查）"

    # 3. AI深度检查（如果启用且不是演示模式）
    elif use_ai:
        ai_result = ai_deep_check(contract_text)
        filtered_count = int(ai_result.get("filtered_count", 0) or 0)

        if ai_result["success"] and ai_result["issues"]:
            # AI审查成功
            all_issues.extend(ai_result["issues"])
            mode = "AI完整审查（真实大模型）"
            if ai_result.get("filtered_count", 0) > 0:
                ai_error = f"AI返回中有{ai_result['filtered_count']}条问题格式不符合要求，已自动过滤。"
        elif ai_result["mode"] == "AI_NOT_CONFIGURED":
            # 【修复】AI未配置：只返回基础检查，不注入演示结果
            mode = "基础规则检查（AI未配置，如需AI审查请配置LLM_API_KEY）"
        elif ai_result["mode"] == "AI_ERROR":
            # 【修复】AI调用失败：只返回基础检查，标注错误
            mode = "基础规则检查（AI调用失败，已降级为仅规则检查）"
            ai_error = ai_result["error"]
        else:
            if ai_result["success"]:
                if filtered_count > 0:
                    mode = (
                        f"AI审查完成，但返回的问题格式异常已被过滤（{filtered_count}条），"
                        "仅展示基础规则检查结果"
                    )
                    ai_error = (
                        f"AI返回的{filtered_count}条问题均不符合格式要求，已自动过滤；"
                        "当前仅展示基础规则检查结果。"
                    )
                else:
                    # AI调用成功但没有发现问题
                    mode = "AI完整审查（真实大模型，未发现额外问题）"
            else:
                # 兼容未知失败模式，避免误报为审查通过
                mode = "基础规则检查（AI审查未完成）"
                ai_error = ai_result.get("error", "AI审查未返回明确结果")

    # 4. 统计
    high_count = sum(1 for i in all_issues if i.get("severity") == "高")
    medium_count = sum(1 for i in all_issues if i.get("severity") == "中")
    low_count = sum(1 for i in all_issues if i.get("severity") == "低")

    # 5. 按严重程度排序（高>中>低）
    severity_order = {"高": 0, "中": 1, "低": 2}
    all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "低"), 3))

    # 6. 生成总结
    if high_count > 0:
        summary = f"发现 {len(all_issues)} 个问题，其中 {high_count} 个高风险问题建议立即修改。"
    elif medium_count > 0:
        summary = f"发现 {len(all_issues)} 个问题，主要为中低风险，建议逐条核对修改。"
    elif all_issues:
        summary = f"发现 {len(all_issues)} 个低风险问题，建议优化。"
    else:
        summary = "未发现明显问题，合同较为规范。"

    if filtered_count > 0:
        summary += f" AI返回的问题中有{filtered_count}条因格式不符合要求已被过滤。"

    return {
        "total_issues": len(all_issues),
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "issues": all_issues,
        "summary": summary,
        "mode": mode,
        "ai_error": ai_error,
        "filtered_count": filtered_count,
    }


# ============================================================
# 示例合同文本（用于演示）
# ============================================================

SAMPLE_CONTRACT = """钢材购销合同

合同编号：GM20260915001
签订日期：2026年9月15日
签定地点：上海市

甲方（买方）：上海建工材料有限公司
乙方（卖方）：唐山钢铁贸易有限公司

一、产品名称、规格、数量、价格
1. 产品名称：热轧带肋钢筋（螺纹钢）
2. 规格：HRB400E Φ16mm
3. 数量：500吨
4. 单价：3650元/吨
5. 总金额：¥1,825,000.00（大写：壹佰捌拾贰万伍仟元整）

二、质量标准
产品质量符合国家标准GB/T 1499.2-2018。

三、交货时间及地点
1. 交货时间：2026年10月15日前
2. 交货地点：甲方指定仓库（上海市宝山区）
3. 运输方式：乙方负责运输，运费由乙方承担。

四、付款方式
货到验收合格后15日内，甲方以银行转账方式支付全部货款。

五、违约责任
1. 甲方逾期付款的，应承担违约责任。
2. 乙方逾期交货的，应承担违约责任。

六、不可抗力
因不可抗力导致本合同无法履行的，双方互不承担责任。

七、其他
本合同一式两份，甲乙双方各执一份，具有同等法律效力。

甲方（盖章）：                    乙方（盖章）：
法定代表人：                      法定代表人：
日期：                            日期：
"""


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=== TradePilot AI 合同审查模块测试 ===\n")

    # 测试1：AI未配置时（应只返回基础检查，不注入演示结果）
    print("测试1: AI未配置时（use_ai=True，应只返回基础检查）")
    result = check_contract(SAMPLE_CONTRACT, use_ai=True)
    print(f"  模式: {result['mode']}")
    print(f"  问题总数: {result['total_issues']}")
    print(f"  高/中/低: {result['high_count']}/{result['medium_count']}/{result['low_count']}")
    print(f"  AI错误: {result.get('ai_error', '无')}")
    print()

    # 测试2：显式演示模式（force_demo=True，应返回演示固定结果）
    print("测试2: 显式演示模式（force_demo=True）")
    result = check_contract(SAMPLE_CONTRACT, use_ai=False, force_demo=True)
    print(f"  模式: {result['mode']}")
    print(f"  问题总数: {result['total_issues']}")
    print(f"  高/中/低: {result['high_count']}/{result['medium_count']}/{result['low_count']}")
    print()

    # 测试3：仅基础规则检查（use_ai=False）
    print("测试3: 仅基础规则检查（use_ai=False）")
    result = check_contract(SAMPLE_CONTRACT, use_ai=False)
    print(f"  模式: {result['mode']}")
    print(f"  问题总数: {result['total_issues']}")
    print()

    # 测试4：验证示例合同金额正确
    print("测试4: 验证示例合同金额（500吨 × 3650元 = 1,825,000元）")
    if "1,825,000" in SAMPLE_CONTRACT:
        print("  ✅ 示例合同金额正确")
    else:
        print("  ❌ 示例合同金额错误")
    print()

    # 测试5：schema校验函数
    print("测试5: schema校验")
    valid = {"type": "文字错误", "severity": "高", "original": "test", "suggestion": "test", "description": "test"}
    invalid1 = {"type": "文字错误", "severity": "极高"}  # severity不合法
    invalid2 = {"type": "文字错误"}  # 缺字段
    print(f"  合法issue: {validate_issue(valid)}")
    print(f"  非法issue(severity): {validate_issue(invalid1)}")
    print(f"  非法issue(缺字段): {validate_issue(invalid2)}")
    print(f"  列表校验: {len(validate_issues([valid, invalid1, invalid2]))} 条合法")

    print("\n=== 测试完成 ===")
