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
| PayPal API | 显式启用 PayPal 沙箱 API 并创建/查询发票 | 买家名称、邮箱、金额、币种、合同编号(reference)、支付类型、发票与交易状态 | 当前 session；配置 `TRUSTLOOP_STORE_PATH` 时写入本地 SQLite |
| 远程信号 API | 配置非占位符 `SIGNAL_API_URL` | 请求头 API Key、信号服务端点 | 不写入数据库 |
| LLM API | 显式启用 AI 合同审查并调用 | 合同全文（可能包含敏感信息） | 不额外持久化，结果仅保留在当前 session |

使用前必须取得数据主体同意，并遵守适用的隐私与数据保护要求。

## Demo安全边界

- 所有行情、合同、通知、付款链接和物流单号均为演示内容。
- 配置 `TRUSTLOOP_STORE_PATH` 后，运行快照、审批、发票索引和审计链会写入本地 SQLite；未配置时只保存在当前 session。
- 可选的 `APP_PASSWORD` 只提供轻量访问门槛，不替代企业身份认证和访问控制。
- Webhook 端点会先调用 PayPal 官方验签接口，再重新查询发票状态，不直接信任回调 body。
- PayPal 返回的 `PAID` 金额与币种必须和人工批准的里程碑完全一致，否则拒绝推进。
- 所有里程碑均为 `PAID` 后才允许签发 Trust Passport。
- Replay Bundle 只读加载，不会回写或覆盖线上运行数据库。
- 配置 `TRUSTLOOP_PASSPORT_SIGNING_KEY` 后，Passport 使用 HMAC-SHA256 做发行方签名；验证时必须使用同一服务端密钥。
- 生产环境仍需补充企业身份认证、授权、分布式速率限制、集中式日志、密钥托管和持久化备份。

## 漏洞报告

请通过 GitHub Issue 或仓库维护者邮箱私下报告潜在漏洞。不要在公开 Issue 中
粘贴真实密钥、真实客户数据或可利用的支付凭据。

完整的支付安全审计、历史风险模式映射和残余风险见
[`docs/PAYMENT_SECURITY_AUDIT.md`](docs/PAYMENT_SECURITY_AUDIT.md)。
