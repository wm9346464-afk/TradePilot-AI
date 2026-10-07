# TradePilot AI — 大宗商品贸易新客户准入与信任建立智能体

> **AI + PayPal Powered Trust Establishment Agent for Bulk Commodity Trade**

[![PayPal AI Hackathon 2026](https://img.shields.io/badge/PayPal%20AI%20Hackathon-2026-003087.svg)](https://paypalaihackathon.devpost.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.50.0-FF4B4B.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

---

## 📖 项目简介 / Project Overview

**TradePilot AI** 是一个面向大宗商品贸易（黑色系：铁矿石、半成品金属等）的**新客户准入与信任建立智能体**。

在大宗商品贸易中，新客户之间的**信任建立**是最大的痛点：买卖双方互不了解，大额交易风险高，传统公对公转账缺乏信任缓冲机制。

本项目构建了一个覆盖贸易全流程的AI智能体系统，用 **AI市场观察 + AI合同审查 + PayPal安全支付通道 + 自动化客户通知** 解决新客户首次合作的信任问题。

**核心叙事：信任建立三层模型**
1. **专业信任** — AI市场观察与价差分析展示专业能力，成为贸易流程的入口
2. **交易信任** — PayPal安全支付通道用于信任建立期的小额支付（样品费、试单担保、诚意保证金），交易可追溯，降低首次合作门槛
3. **长期信任** — 全流程自动化服务 + 复购引导，试单成功后转为大额公对公交易

> **English**: TradePilot AI is an intelligent agent for new customer onboarding and trust establishment in bulk commodity trade (ferrous metals: iron ore, semi-finished metals, etc.). It solves the trust problem in first-time cooperation through AI market observation, AI contract review, PayPal secure payment channels, and automated customer notifications.

---

## 📢 公开版本说明 / Public Version Notice

本仓库是 TradePilot AI 的**公开演示版本**，用于 PayPal AI Hackathon 2026 参赛提交。

### 行情信号模块 / Market Signal Module

本公开仓库中的行情信号模块使用 **Demo Signal Provider**，基于**合成演示数据**运行，用于展示系统架构和用户流程。

- ✅ **完整可运行**：无需任何额外配置，克隆后即可运行
- ✅ **架构完整**：采用 Signal Provider 抽象接口设计，支持接入生产信号服务
- ⚠️ **演示数据**：`data/demo_market_data.csv` 为合成数据，不代表真实市场表现
- ⚠️ **非生产策略**：Demo 信号基于简化逻辑生成，不包含任何生产级策略参数或回测结果

生产级信号系统不在本仓库范围内。如需接入，请通过配置 `SIGNAL_API_URL` 环境变量使用 `RemoteSignalProvider`（详见配置说明）。

---

## 🎯 解决的问题 / Problem Statement

大宗商品贸易面临的信任痛点：

| 痛点 | 传统方式 | TradePilot AI 解决方案 |
|---|---|---|
| 新客户互不信任 | 靠人脉介绍、线下考察 | AI市场观察展示专业能力，建立第一印象 |
| 首次合作风险高 | 直接大额公对公转账 | PayPal小额支付通道（样品费/试单），交易可追溯 |
| 合同审查依赖人工 | 法务逐条审核，效率低 | AI + 规则双重审查，秒级完成 |
| 客户沟通成本高 | 手动发邮件/微信 | 7种通知模板，全流程自动生成 |
| 复购转化低 | 无系统引导 | 试单成功后自动引导转为大额公对公交易 |

---

## ✨ 核心功能 / Core Features

### 1. 📊 AI市场观察模块 / Market Observation Module

黑色系大宗商品市场观察与价差分析，采用 Signal Provider 架构设计：

- **3个观察维度**：冷轧-螺纹价差、冷轧-热卷价差、螺纹基差
- **Signal Provider 架构**：
  - `DemoSignalProvider` — 默认，合成数据，无需配置即可运行
  - `RemoteSignalProvider` — 可选，调用私有生产服务获取信号
- **信号状态展示**：观望/关注/触发三种状态，置信度和参考概率
- **价格走势图表**：最近180个交易日价格走势可视化
- **演示模式标识**：明确标注当前为演示模式，使用合成数据
- **免责声明**：仅供贸易决策参考，不构成投资建议

### 2. 📝 AI合同审查模块 / Contract Review Module

基础规则检查 + 大模型AI深度审查的双重审查体系：

- **三种模式区分**：
  - `AI_LIVE` — 真实大模型深度审查（需配置LLM API Key）
  - `RULE_ONLY` — 仅基础规则检查（AI未配置时自动降级）
  - `DEMO_FIXTURE` — 演示模式（用户显式选择，不注入真实合同）
- **基础规则检查**：错别字、金额一致性、日期有效性、关键条款缺失检测
- **AI深度审查**：法律风险识别、条款完整性评估、修改建议生成
- **Schema校验**：AI返回结果自动校验格式，过滤无效条目
- **风险分级**：高/中/低风险分类，优先处理高风险问题
- **"订金"vs"定金"**：法律含义差异风险提示（不简单标为错别字）

### 3. 💰 PayPal结算模块 / PayPal Payment Module

基于PayPal REST API（沙箱环境）的信任建立期小额支付结算：

- **4种支付场景**：
  - 样品费支付 — 新客户索要样品
  - 小额试单支付 — 首次合作小额试单
  - 诚意保证金 — 大额订单前的保证金
  - 跨境服务费 — 检验、物流、咨询等服务费
- **真实沙箱API**：调用PayPal Invoicing API真实生成发票
- **完整流程**：创建发票 → 发送发票 → 生成付款链接 → 查询付款状态 → 触发后续流程
- **付款状态刷新**：支持实时查询PayPal发票状态
- **演示模式**：无需API密钥即可演示完整流程（需用户显式选择）
- **合规说明**：B2B大宗商品交易可能不适用PayPal标准买家保护，具体以PayPal条款为准

> **重要说明**：PayPal不用于大额货款结算，仅用于信任建立期的小额支付场景。大额交易仍采用公对公银行转账。

### 4. 📬 客户通知模块 / Customer Notification Module

贸易全流程自动化客户通知内容生成：

- **7种通知模板**：
  1. 行情提醒 — 市场观察信号触发时自动通知（贸易流程起点，建立专业信任）
  2. 合同通知 — 合同审查完成后通知客户
  3. 付款通知 — 发票生成后通知付款（含PayPal付款链接）
  4. 到账确认 — 付款成功后自动确认
  5. 发货通知 — 付款后触发发货，通知物流信息
  6. 收货提醒 — 提醒客户确认收货并反馈
  7. 售后跟进 — 交易完成后跟进满意度，引导复购
- **变量替换**：客户名称、金额、日期、合同号等自动填充
- **多渠道适配**：内容可通过邮件、微信、短信等渠道发送

---

## 🛠️ 技术栈 / Tech Stack

| 类别 | 技术 | 版本 |
|---|---|---|
| 语言 | Python | 3.10+ |
| Web框架 | Streamlit | 1.50.0 |
| 数据处理 | pandas | 2.3.3 |
| 数值计算 | numpy | 1.26.4 |
| HTTP请求 | requests | 2.32.5 |
| 环境变量 | python-dotenv | 1.0.1 |
| 支付API | PayPal REST API (Sandbox) | v2 Invoicing |
| AI审查 | OpenAI兼容API（豆包/DeepSeek等） | 可选 |

---

## 📁 项目结构 / Project Structure

```
TradePilot-AI/
├── app.py                          # Streamlit主应用（5个页面）
├── requirements.txt                # 依赖清单（锁定精确版本）
├── .env.example                    # 环境变量配置模板
├── .gitignore                      # Git忽略规则
├── LICENSE                         # Apache-2.0 开源许可证
├── README.md                       # 项目说明文档
├── data/
│   └── demo_market_data.csv        # 合成演示数据（400行，明确标注）
└── modules/
    ├── __init__.py
    ├── signal_provider.py          # Signal Provider抽象接口（Demo + Remote）
    ├── market_signal.py            # 行情信号模块（薄包装，调用Provider）
    ├── contract_checker.py         # 合同审查模块（规则+AI双重审查）
    ├── paypal_payment.py           # PayPal结算模块（REST API+演示模式）
    └── notification.py             # 客户通知模块（7种通知模板）
```

---

## 🚀 快速开始 / Quick Start

### 1. 克隆仓库 / Clone

```bash
git clone https://github.com/your-username/TradePilot-AI.git
cd TradePilot-AI
```

### 2. 创建虚拟环境 / Create Virtual Environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 3. 安装依赖 / Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量（可选）/ Configure Environment Variables (Optional)

```bash
# 复制模板
cp .env.example .env
# Windows
copy .env.example .env
```

> **注意**：不配置任何环境变量也能完整运行（使用Demo模式）。PayPal和LLM配置仅用于启用对应高级功能。

### 5. 运行应用 / Run the Application

```bash
streamlit run app.py
```

应用将在 **http://localhost:8501** 启动。

---

## ⚙️ 配置说明 / Configuration

### PayPal沙箱配置（可选）/ PayPal Sandbox Setup (Optional)

用于启用真实PayPal沙箱API调用。未配置时自动使用演示模式。

1. 注册免费的 [PayPal Developer](https://developer.paypal.com/) 账号
2. 在 **Dashboard → Apps & Credentials** 创建应用，获取 `Client ID` 和 `Secret`
3. 在 **Sandbox → Accounts** 查看自动创建的商家账号（Business类型）和买家账号（Personal类型）
4. 将配置填入 `.env`：

```env
PAYPAL_CLIENT_ID=your_client_id
PAYPAL_CLIENT_SECRET=your_client_secret
PAYPAL_MERCHANT_EMAIL=your_sandbox_business_email@example.com
PAYPAL_MERCHANT_NAME=TradePilot AI
```

> **注意**：沙箱环境所有交易都是虚拟的，不涉及真实资金。买家账号用于演示付款流程。

### 大模型API配置（可选）/ LLM API Setup (Optional)

用于合同审查的AI深度审查功能，支持OpenAI兼容接口：

```env
LLM_API_KEY=your_api_key
LLM_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
LLM_MODEL_NAME=doubao-1-5-pro-32k-250115
```

未配置时，合同审查自动降级为基础规则检查模式，不影响其他功能使用。

### 生产信号服务配置（可选）/ Production Signal Service (Optional)

用于接入私有生产级信号服务。未配置时使用Demo Signal Provider（合成数据）。

```env
SIGNAL_API_URL=https://your-private-signal-service.example.com/api
SIGNAL_API_KEY=your_signal_service_key  # 可选
```

> **重要**：私有信号API只应返回信号状态（watch/trigger/confidence），不应返回策略参数、z-score计算细节、原始数据或回测结果。生产级信号系统的实现和部署不在本公开仓库范围内。

---

## 📺 演示 / Demo

### 在线演示 / Live Demo

部署后访问：**[待部署 Streamlit Community Cloud URL]**

### 演示视频 / Demo Video

**[待录制 3分钟演示视频]**

演示流程：
1. 市场观察页面 — 展示3个价差观察维度及价格走势
2. 合同审查页面 — 加载示例合同，展示AI+规则双重审查结果
3. PayPal结算页面 — 创建真实沙箱发票，获取付款链接
4. 买家付款 — 用沙箱买家账号完成付款
5. 刷新状态 — 显示PAID状态及付款信息
6. 客户通知 — 一键生成7条全流程通知

---

## 🏆 比赛信息 / Hackathon Info

- **比赛名称**：PayPal AI Hackathon 2026
- **比赛官网**：https://paypalaihackathon.devpost.com/
- **提交截止**：2026年11月12日 12:00 PST
- **奖金池**：$67,500+
- **参赛赛道**：Agentic Commerce（智能商务）

### 为什么选择PayPal？/ Why PayPal?

大宗商品贸易中，大额货款通常采用公对公银行转账，不使用PayPal。但**信任建立期的小额支付场景**（样品费、试单、保证金、服务费）非常适合PayPal：

- **便捷**：买家无需银行转账，点击链接即可支付
- **可追溯**：所有交易记录在PayPal系统中可查
- **降低门槛**：新客户首次合作只需支付小额费用即可建立信任
- **跨境友好**：支持多币种，适合跨境贸易场景

> **合规声明**：本项目不宣称PayPal买家保护适用于B2B大宗商品交易。PayPal标准买家保护主要适用于消费者购物场景，B2B交易可能不适用。本项目的价值在于提供便捷、可追溯的小额支付通道，降低新客户首次合作的信任门槛，不构成支付保障承诺。具体保障范围以PayPal官方条款为准。

---

## 🏗️ 架构设计 / Architecture

### Signal Provider 模式

行情信号模块采用**依赖倒置**设计，将信号获取抽象为 `SignalProvider` 接口：

```
Streamlit Frontend
       │
       ▼
market_signal.py (薄包装)
       │
       ▼
SignalProvider (抽象接口)
       ├── DemoSignalProvider   ← 默认，合成数据，公开可运行
       └── RemoteSignalProvider ← 可选，私有生产服务
```

**设计优势**：
- 公开仓库完整可运行，不依赖任何私有服务
- 生产策略完全隔离，不在公开仓库中
- 接口稳定，前端无需修改即可切换信号来源
- 符合比赛"所有必要源码"要求（Demo Provider是完整的可运行实现）

---

## 🤝 贡献 / Contributing

欢迎提交Issue和Pull Request！

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 许可证 / License

本项目采用 **Apache License 2.0** — 详见 [LICENSE](LICENSE) 文件。

---

## ⚠️ 免责声明 / Disclaimer

1. **投资建议**：本项目的行情观察信号仅供贸易决策参考，不构成任何投资建议。演示数据不代表真实市场表现。
2. **支付保障**：本项目不宣称PayPal买家保护适用于B2B大宗商品交易。具体保障范围以PayPal官方条款为准。
3. **法律意见**：合同审查模块提供的修改建议仅供参考，不构成法律意见。重要合同请咨询专业律师。
4. **数据隐私**：本项目不会上传任何用户数据到第三方服务器。所有数据处理在本地完成。
5. **沙箱环境**：PayPal配置默认使用沙箱环境，所有交易都是虚拟的，不涉及真实资金。
6. **演示数据**：本公开仓库使用合成演示数据，不代表任何真实市场表现或交易建议。

---

## 📞 联系方式 / Contact

- **项目维护者**：[Your Name]
- **邮箱**：[your-email@example.com]
- **GitHub**：[your-username](https://github.com/your-username)

---

*Made with ❤️ for PayPal AI Hackathon 2026*
