#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qianxi(RustDesk) 客户端定制补丁。

在「上游 rustdesk 源码树」上打三类改动：
  1) 服务器：ID / 中继 / API / 公钥（hbb_common 默认常量 + 运行时 OVERWRITE_SETTINGS 锁定）
  2) 名称：APP_NAME 默认值 + Windows 可执行文件版本资源（产品名/文件说明/原始文件名）
  3) 图标：EXE 图标 / 托盘图标 / 应用内图标 / 快捷方式图标

用法（在构建脚本里）：
    python branding/apply-branding.py --repo src

脚本是「锚点校验」式的：任何一个锚点没匹配到或匹配到多处，都会非 0 退出，
绝不会静默产出「看起来编完了其实是原版」的假货。重复执行是安全的（幂等）。
"""

import argparse
import os
import pathlib
import re
import shutil
import sys

try:  # Windows 控制台/CI 日志统一 UTF-8，避免中文乱码或编码异常
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ============================ 配置（构建时注入，不落仓库）============================
# 本仓库不保存任何服务器地址、公钥或密钥。
# 构建时由 GitHub Actions 注入下列环境变量（workflow_dispatch 输入或仓库 Variables）：
#   QIANXI_APP_NAME / QIANXI_ID_SERVER / QIANXI_RELAY_SERVER / QIANXI_API_SERVER / QIANXI_PUBLIC_KEY
# 缺任何一个都直接报错退出，避免编出「服务器为空」的废包。


def _req_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        print(f"[错误] 缺少环境变量 {name}：服务器配置不再写进仓库，必须由构建环境注入", file=sys.stderr)
        sys.exit(1)
    return v


APP_NAME = _req_env("QIANXI_APP_NAME")            # 显示名称（窗口标题/托盘/关于/程序属性）
ID_SERVER = _req_env("QIANXI_ID_SERVER")          # ID 服务器（rendezvous）
RELAY_SERVER = _req_env("QIANXI_RELAY_SERVER")    # 中继服务器
API_SERVER = _req_env("QIANXI_API_SERVER").rstrip("/")   # API 服务器，结尾斜杠会去掉
PUBLIC_KEY = _req_env("QIANXI_PUBLIC_KEY")        # 服务器公钥（id_ed25519.pub）

# 图标来源（相对本脚本所在目录）
HERE = pathlib.Path(__file__).resolve().parent
ICON_ICO = HERE / "icons" / "app.ico"
ICON_PNG = HERE / "icons" / "app-256.png"

GUARD_FN = "apply_qianxi_branding"
MARKER = "pub fn load_custom_client() {"
# =====================================================================


class Patcher:
    def __init__(self, repo: pathlib.Path):
        self.repo = repo
        self.changed = []

    def read(self, rel: str) -> str:
        p = self.repo / rel
        if not p.is_file():
            self.die(f"找不到文件：{p}（--repo 指向的应是 rustdesk 源码根目录）")
        return p.read_text(encoding="utf-8")

    def write(self, rel: str, text: str):
        (self.repo / rel).write_text(text, encoding="utf-8")
        self.changed.append(rel)

    def die(self, msg: str):
        print(f"[错误] {msg}", file=sys.stderr)
        sys.exit(1)

    def sub_once(self, text: str, pattern: str, repl: str, what: str) -> str:
        new, n = re.subn(pattern, repl, text, count=1)
        if n != 1:
            self.die(f"锚点未命中：{what}\n  期望匹配正则：{pattern}")
        hits = len(re.findall(pattern, text))
        if hits != 1:
            self.die(f"锚点不唯一（{hits} 处）：{what}")
        return new

    # ---------------- 1. hbb_common：服务器地址 / 公钥 / 应用名 ----------------
    def patch_hbb_config(self):
        rel = "libs/hbb_common/src/config.rs"
        src = self.read(rel)
        src = self.sub_once(
            src,
            r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];',
            f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{ID_SERVER}"];',
            "config.rs RENDEZVOUS_SERVERS",
        )
        src = self.sub_once(
            src,
            r'pub const RS_PUB_KEY: &str = "[^"]*";',
            f'pub const RS_PUB_KEY: &str = "{PUBLIC_KEY}";',
            "config.rs RS_PUB_KEY",
        )
        src = self.sub_once(
            src,
            r'pub static ref APP_NAME: RwLock<String> = RwLock::new\("[^"]*"\.to_owned\(\)\);',
            f'pub static ref APP_NAME: RwLock<String> = RwLock::new("{APP_NAME}".to_owned());',
            "config.rs APP_NAME",
        )
        self.write(rel, src)

    # ---------------- 2. src/common.rs：运行时锁定服务器配置 ----------------
    def patch_common_rs(self):
        rel = "src/common.rs"
        src = self.read(rel)

        # 2a. API 服务器兜底值（正常走 OVERWRITE_SETTINGS，这里只是双保险）
        if f'    "{API_SERVER}".to_owned()' not in src:
            src = self.sub_once(
                src,
                r'    "https://admin\.rustdesk\.com"\.to_owned\(\)',
                f'    "{API_SERVER}".to_owned()',
                "common.rs get_api_server_ 兜底 URL",
            )

        # 2b. 在 load_custom_client() 首行注入调用
        if GUARD_FN + "();" not in src:
            src = self.sub_once(
                src,
                re.escape(MARKER),
                MARKER + f"\n    {GUARD_FN}();",
                "common.rs load_custom_client() 函数头",
            )

        # 2c. 追加函数体
        if f"fn {GUARD_FN}()" not in src:
            if not src.endswith("\n"):
                src += "\n"
            src += f'''

/// ===== Qianxi(RustDesk) 定制：预置 ID / 中继 / API 服务器 =====
/// 写进 OVERWRITE_SETTINGS 后，这些项在界面上只读，用户改不动，也不会被本地配置覆盖。
fn {GUARD_FN}() {{
    let mut s = config::OVERWRITE_SETTINGS.write().unwrap();
    s.insert("custom-rendezvous-server".to_owned(), "{ID_SERVER}".to_owned());
    s.insert("relay-server".to_owned(), "{RELAY_SERVER}".to_owned());
    s.insert("api-server".to_owned(), "{API_SERVER}".to_owned());
    s.insert("key".to_owned(), "{PUBLIC_KEY}".to_owned());
}}
'''
        self.write(rel, src)

    # ---------------- 3. Windows 可执行文件版本资源 ----------------
    def patch_runner_rc(self):
        rel = "flutter/windows/runner/Runner.rc"
        src = self.read(rel)
        src = self.sub_once(
            src,
            r'VALUE "FileDescription", "[^"]*"',
            f'VALUE "FileDescription", "{APP_NAME} Remote Desktop"',
            "Runner.rc FileDescription",
        )
        src = self.sub_once(
            src,
            r'VALUE "ProductName", "[^"]*"',
            f'VALUE "ProductName", "{APP_NAME}"',
            "Runner.rc ProductName",
        )
        src = self.sub_once(
            src,
            r'VALUE "OriginalFilename", "[^"]*"',
            f'VALUE "OriginalFilename", "{APP_NAME}.exe"',
            "Runner.rc OriginalFilename",
        )
        src = self.sub_once(
            src,
            r'VALUE "InternalName", "[^"]*"',
            f'VALUE "InternalName", "{APP_NAME}"',
            "Runner.rc InternalName",
        )
        self.write(rel, src)

    # ---------------- 4. 图标 ----------------
    def patch_icons(self):
        for f in (ICON_ICO, ICON_PNG):
            if not f.is_file():
                self.die(f"缺少图标文件：{f}")
        targets = [
            ("flutter/windows/runner/resources/app_icon.ico", ICON_ICO),
            ("res/icon.ico", ICON_ICO),
            ("res/tray-icon.ico", ICON_ICO),
            ("res/icon.png", ICON_PNG),
            ("flutter/assets/icon.png", ICON_PNG),
            ("flutter/assets/icon.ico", ICON_ICO),
        ]
        for rel, src in targets:
            dst = self.repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            self.changed.append(rel)

    # ---------------- 4b. MSI：修 preprocess.py 调 exe 的引号 bug ----------------
    def patch_msi_preprocess(self):
        """官方 preprocess.py 用 shell=True + 未加引号的路径启动 exe；
        产品名里带括号/空格时会被 cmd.exe 拆坏（实测报 “Qianxi 不是内部或外部命令”）。"""
        rel = "res/msi/preprocess.py"
        if not (self.repo / rel).is_file():
            return
        src = self.read(rel)
        if 'f\'"{dist_app}" {args}\'' in src:
            return  # 已修
        src = self.sub_once(
            src,
            r'\s*f"\{dist_app\} \{args\}",',
            '            f\'"{dist_app}" {args}\',',
            "preprocess.py Popen 路径加引号",
        )
        self.write(rel, src)

    def run(self):
        self.patch_hbb_config()
        self.patch_common_rs()
        self.patch_runner_rc()
        self.patch_icons()
        self.patch_msi_preprocess()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="src", help="rustdesk 源码根目录（默认 src）")
    args = ap.parse_args()

    repo = pathlib.Path(args.repo).resolve()
    if not (repo / "src/common.rs").is_file():
        print(f"[错误] {repo} 不像 rustdesk 源码根目录", file=sys.stderr)
        return 1

    p = Patcher(repo)
    p.run()

    print("[完成] 品牌定制已应用：")
    print(f"       名称   : {APP_NAME}")
    print(f"       ID     : {ID_SERVER}")
    print(f"       中继   : {RELAY_SERVER}")
    print(f"       API    : {API_SERVER}")
    print(f"       公钥   : {PUBLIC_KEY[:8]}…{PUBLIC_KEY[-6:]}（已打码）")
    print(f"       改动文件（{len(p.changed)} 个）：")
    for c in p.changed:
        print(f"         - {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
