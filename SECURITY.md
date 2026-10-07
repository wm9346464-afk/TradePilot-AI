# 安全与隐私说明

## 支持范围

本项目是公开Demo，不是生产级交易、支付或合同系统。请勿提交真实密钥、
未公开策略参数、真实客户合同或真实支付账号。

## 密钥管理

- 不要提交 `.env`、`secrets.toml`、API Key、私钥或访问令牌。
- Streamlit Community Cloud 应使用 Advanced settings 的 root-level Secrets。
- 本仓库的 `.env.example` 只包含占位符。
- 如果怀疑密钥泄露，请立即在对应平台轮换密钥。

## 数据流

| 外部服务 | 触发条件 | 涉及数据 | 本地保存 |
|---|---|---|---|
| 本地 Demo | 默认模式，无需配置 | 仅读取 `data/demo_market_data.csv` 合成数据 | 不发送外部请求 |
| PayPal API | 显式启用 PayPal 沙箱 API 并创建发票 | 买家名称、邮箱、金额、币种、合同编号(reference)、支付类型 | 当前 Streamlit session 中的发票草稿与状态 |
| 远程信号 API | 配置非占位符 `SIGNAL_API_URL` | 请求头 API Key、信号服务端点 | 不写入数据库 |
| LLM API | 显式启用 AI 合同审查并调用 | 合同全文（可能包含敏感信息） | 不额外持久化，结果仅保留在当前 session |

使用前必须取得数据主体同意，并遵守适用的隐私与数据保护要求。

## Demo安全边界

- 所有行情、合同、通知、付款链接和物流单号均为演示内容。
- Demo 发票只保存在当前 Streamlit session，不写入数据库。
- 可选的 `APP_PASSWORD` 只提供轻量访问门槛，不替代企业身份认证和访问控制。
- 生产环境需要补充认证、授权、速率限制、审计日志、密钥托管和支付回调验签。

## 漏洞报告

请通过 GitHub Issue 或仓库维护者邮箱私下报告潜在漏洞。不要在公开 Issue 中
粘贴真实密钥、真实客户数据或可利用的支付凭据。
