# iPhone Home Screen Layout

在 macOS 上通过自然语言整理 iPhone 主屏幕。Agent 理解需求，Python core 生成与校验布局计划，Apple Configurator 的 `cfgutil` 负责设备读写。没有内置 LLM/API Key，无 Python 运行时依赖。

## 安装 Skill

需要 Node.js/npm 来运行社区 skills 安装器。发布到 GitHub 后，将下面的 `YOUR_NAME/apple-app-layout` 替换为实际仓库地址：

```sh
# 交互选择目标 Agent 和安装范围
npx skills@latest add YOUR_NAME/apple-app-layout

# 全局安装到 Codex
npx skills@latest add YOUR_NAME/apple-app-layout --skill iphone-home-screen-layout -a codex -g

# 列出仓库可用技能，不安装
npx skills@latest add YOUR_NAME/apple-app-layout --list
```

本地开发时，可在仓库根目录安装：

```sh
npx skills@latest add ./skills/iphone-home-screen-layout -a codex
```

安装器支持 Codex、Claude Code、Cursor 等宿主，详见 [skills CLI](https://github.com/vercel-labs/skills)。技能运行需要宿主支持本地 Python 命令；真机操作仅支持 macOS，并需要 Apple Configurator Automation Tools、已解锁且信任 Mac 的连接设备。

安装后可以请求：使用 `iphone-home-screen-layout`，将社交应用放进一个文件夹，保留 Dock，先展示计划。

## 快速离线演示

Python 3.9+，无需 pip 安装。在仓库根目录运行；`mktemp` 创建独立输出目录：

```sh
layout_demo_dir="$(mktemp -d)"
python3 skills/iphone-home-screen-layout/scripts/iphone-layout.py import skills/iphone-home-screen-layout/examples/raw-layout.json --ecid 123 --out "$layout_demo_dir/current.json"
python3 skills/iphone-home-screen-layout/scripts/iphone-layout.py plan "$layout_demo_dir/current.json" skills/iphone-home-screen-layout/examples/categories.json --out "$layout_demo_dir/plan.json"
python3 -m unittest discover -s tests -v
```

可选：在仓库根目录运行 `python3 -m pip install -e .` 安装 `iphone-layout` 命令。Python 包安装与 skill 安装是独立步骤；使用 skill 无需安装 Python 包。

## 目录

```text
skills/iphone-home-screen-layout/
  SKILL.md             Agent 入口
  scripts/             可从任意工作目录调用的脚本
  iphone_layout/       Python 实现
  schemas/             布局 Schema
  examples/            合成离线数据
  references/usage.md  设备流程、模型与限制
tests/                 离线与模拟设备测试
pyproject.toml         Python CLI 打包配置
TESTING.md             验证记录
```

技能子目录包含全部运行依赖，可以独立复制安装。维护者文档和测试留在仓库根目录。开发源码位置改变后，应保持技能内部引用相对于技能根目录。

## 使用与验证范围

详见 [使用指南](skills/iphone-home-screen-layout/references/usage.md)、[Agent 指令](skills/iphone-home-screen-layout/SKILL.md) 和 [测试记录](TESTING.md)。输出及备份应放在技能目录之外，避免升级时受到影响。

当前为 MVP：已有离线和模拟设备测试，尚未完成真机读写验收。widget、隐藏页面、App Library-only 等状态可能无法完整导出；依赖这些状态的设备不应执行提交。应用前需预览具体计划并授权，备份只覆盖 cfgutil 可见布局。

## 社区发布

将仓库上传至 GitHub 后，更新上面的仓库地址，并选择适合项目的开源许可证。当前尚未声明许可证；目录整理不代替作者的授权选择。发布前从独立目录安装技能并执行离线演示，确认脚本、模块、Schema 和参考文档均包含在安装结果中。
