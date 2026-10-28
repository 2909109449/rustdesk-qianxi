# Qianxi(RustDesk) 定制客户端 · GitHub 构建仓库（私有）

> **本仓库不保存任何服务器地址、公钥或密钥。**
> 服务器配置通过 **仓库 Variables**（Settings → Secrets and variables → Actions → Variables）
> 或每次 **Run workflow** 的输入框注入，编译时才写进客户端源码。

每次运行工作流时它会：

1. 克隆官方 `rustdesk/rustdesk` 的指定 tag（默认 `1.5.0`）；
2. 用 `branding/apply-branding.py` 现场打补丁（名称 / ID / 中继 / API / 公钥 / 图标），配置由环境变量注入；
3. 用官方同款工具链（Rust 1.75 + Flutter 3.24.5 + LLVM 15 + vcpkg）编译 Windows x64；
4. 产出：便携单文件 `Qianxi(RustDesk)-1.5.0-x86_64.exe`、绿色目录版、以及（尽力而为的）`.msi`。

## 需要配置的 Variables（5 个）

| 变量名 | 含义 |
| --- | --- |
| `QIANXI_APP_NAME` | 显示名称，例如 `Qianxi(RustDesk)` |
| `QIANXI_ID_SERVER` | ID 服务器 IP 或域名 |
| `QIANXI_RELAY_SERVER` | 中继服务器 IP 或域名 |
| `QIANXI_API_SERVER` | API 服务器，形如 `https://你的域名`（不要结尾斜杠） |
| `QIANXI_PUBLIC_KEY` | 服务器公钥（`/opt/rustdesk/server/id_ed25519.pub` 的内容） |

没配也能跑：Run workflow 时在 5 个输入框里临时填（不落库，但会出现在该次运行的输入记录里）。

## 改图标 / 改版本

- 图标：替换 `branding/icons/app.ico`（多尺寸 ico）与 `app-256.png`
- 版本：改 `.github/workflows/build-windows.yml` 里的 `RUSTDESK_REF` 与 `APP_VERSION`
