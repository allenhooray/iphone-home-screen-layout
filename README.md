# iPhone Home Screen Layout

通过自然语言规划 iPhone 主屏幕图标、文件夹和 Dock 布局。Agent 理解需求，Python 代码负责分类、校验和差异预览，macOS 上的 Apple Configurator `cfgutil` 负责设备读写。

**状态：实验性 MVP。** 已通过离线和模拟设备测试，尚未完成真机读写验收。当前不声明支持 iPad；widget、隐藏页面和仅存在于 App 资源库中的图标状态可能无法完整导出，依赖这些状态的设备不应执行写入。详见 [使用指南](skills/iphone-home-screen-layout/references/usage.md)。

## 环境要求

- Python 3.9+：技能脚本无第三方 Python 运行时依赖。
- Node.js/npm：仅运行社区 `skills` 安装器时需要。
- Agent 宿主：支持文件型技能和执行本地 Python 命令。
- 真机操作：macOS、Apple Configurator 及 Automation Tools；iPhone 已解锁、连接并信任 Mac。

项目不内置 LLM、不要求单独配置模型 API Key。自然语言理解由所使用的 Agent 宿主提供。

## 安装

通过 [skills CLI](https://github.com/vercel-labs/skills) 安装到 Codex：

```sh
npx skills@latest add allenhooray/iphone-home-screen-layout --skill iphone-home-screen-layout -a codex -g
```

也可以交互选择 Agent 和安装范围，或先列出可用技能：

```sh
npx skills@latest add allenhooray/iphone-home-screen-layout
npx skills@latest add allenhooray/iphone-home-screen-layout --list
```

`-g` 表示用户级安装；省略它则安装到当前项目。安装器还支持 Claude Code、Cursor 等宿主，其兼容范围以安装器文档为准。安装技能不会自动安装 Python 或 Apple Configurator。

安装后向 Agent 发出请求，例如：

> 使用 iphone-home-screen-layout，把已确认的社交应用放进一个文件夹，保持 Dock 不动。先读取布局、展示分类规则和差异，等我确认具体计划后再应用。

## 本地开发与离线演示

```sh
git clone https://github.com/allenhooray/iphone-home-screen-layout.git
cd iphone-home-screen-layout
```

以下演示只使用合成数据，不连接设备，也不会修改手机。输出文件必须不存在，因此每次使用新的临时目录：

```sh
layout_demo_dir="$(mktemp -d)"
python3 skills/iphone-home-screen-layout/scripts/iphone-layout.py import skills/iphone-home-screen-layout/examples/raw-layout.json --ecid 123 --out "$layout_demo_dir/current.json"
python3 skills/iphone-home-screen-layout/scripts/iphone-layout.py plan "$layout_demo_dir/current.json" skills/iphone-home-screen-layout/examples/categories.json --out "$layout_demo_dir/plan.json"
```

第二条 Python 命令输出布局差异及 `plan_sha256`，并保存计划。这里的 ECID `123` 和应用 ID 只用于离线示例。

在仓库根目录安装本地技能：

```sh
npx skills@latest add ./skills/iphone-home-screen-layout -a codex
```

如需单独使用 `iphone-layout` 命令，可选安装 Python 包：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/iphone-layout --help
```

这只安装 Python CLI，不会安装技能文档；通过脚本使用技能无需 pip 安装。

## 使用文档

- [使用指南](skills/iphone-home-screen-layout/references/usage.md)：读取、分类、预览、应用、恢复及错误处理。
- [Agent 指令](skills/iphone-home-screen-layout/SKILL.md)：技能触发与执行流程。
- [测试与验证范围](TESTING.md)：维护者测试命令、已验证能力和未验证事项。

## 项目结构

```text
skills/iphone-home-screen-layout/
  SKILL.md             Agent 入口
  scripts/             Python 脚本入口
  iphone_layout/       布局处理和设备适配实现
  schemas/             布局 Schema
  examples/            合成离线数据
  references/usage.md  使用指南
tests/                 离线与模拟设备测试
pyproject.toml         可选 Python CLI 打包配置
TESTING.md             测试与验证范围
```

技能子目录包含运行所需代码和资源，可以独立安装。测试和维护文档留在仓库根目录。布局快照、计划和备份应保存到技能目录之外。

## 反馈与贡献

请通过 [GitHub Issues](https://github.com/allenhooray/iphone-home-screen-layout/issues) 报告问题，附上 macOS、Python、Configurator 和 iOS 版本、执行命令及错误信息。分享前移除设备 ECID 和私有应用信息；请勿上传未经脱敏的布局或备份。

提交修改前运行 [离线测试](TESTING.md)。设备适配修改应注明是否经过真机验证，以及设备型号和系统版本。

## 许可证

仓库目前尚未声明开源许可证，发布者需另行确定授权条款。
