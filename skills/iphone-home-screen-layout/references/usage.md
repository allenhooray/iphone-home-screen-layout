# 使用指南

以下命令从技能根目录（包含 `SKILL.md` 的目录）执行，需要 Python 3.9+。在源码仓库中先运行 `cd skills/iphone-home-screen-layout`；安装后的技能请使用宿主提供的实际路径。也可以用脚本绝对路径从其他工作目录调用。

## 1. 准备设备和工作目录

真机操作仅支持 macOS。安装 Apple Configurator，并通过其菜单安装 Automation Tools。连接已解锁且信任 Mac 的 iPhone，运行 `cfgutil list` 获取目标 ECID。多台设备时先确认目标。

将 `YOUR_ECID` 替换为实际值。工作目录位于个人目录中，保留备份时不要使用会被系统清理的临时目录；每次规划创建新目录：

```sh
layout_ecid="YOUR_ECID"
mkdir -p "$HOME/iphone-layout-data"
layout_work_dir="$(mktemp -d "$HOME/iphone-layout-data/session.XXXXXX")"
```

设备命令可加 `--cfgutil /absolute/path/to/cfgutil` 指定工具路径。若 `cfgutil` 无法正常启动，先解决工具环境问题，再进行设备操作。

## 2. 读取并编写分类规则

```sh
python3 scripts/iphone-layout.py read --ecid "$layout_ecid" --out "$layout_work_dir/current.json"
```

读取结果包含设备 ECID、原生布局及规范化的 `layout`。`backup` 是 `read` 的别名，也可用于手动保存快照。

根据读取结果，把需要分组的真实图标 ID 写入 `$layout_work_dir/rules.json`。格式参照 [分类规则示例](../examples/categories.json)：

```json
{
  "groups": [
    {"name": "社交", "ids": ["REPLACE_WITH_ACTUAL_APP_ID"]}
  ]
}
```

将占位 ID 替换为快照中实际存在的 ID。仓库示例中的应用 ID 是合成数据，不能直接应用到设备。不要仅凭不确定的 ID 猜测应用用途。

默认分类保留 Dock；未分类图标留在原页面或文件夹，移走图标后空位收紧，空文件夹移除。新文件夹追加到末页，必要时新增页面。

## 3. 生成计划并预览

```sh
python3 scripts/iphone-layout.py plan "$layout_work_dir/current.json" "$layout_work_dir/rules.json" --out "$layout_work_dir/plan.json"
python3 scripts/iphone-layout.py apply "$layout_work_dir/plan.json" --ecid "$layout_ecid"
```

`plan` 在本地生成计划和差异；不带 `--commit` 的 `apply` 会读取设备并检查计划，但不写入布局。查看输出的 `diff` 和 `plan_sha256`，确认具体改动后再提交。

## 4. 应用已确认的计划

将 `APPLY_PREVIEW_DIGEST` 替换为本次预览返回的摘要：

```sh
python3 scripts/iphone-layout.py apply "$layout_work_dir/plan.json" --ecid "$layout_ecid" --commit --expect-plan-sha256 APPLY_PREVIEW_DIGEST --backups "$layout_work_dir/backups"
```

实际写入前自动保存快照；成功写入后回读核对布局，输出 `committed: true` 和 `backup` 路径。如果目标已与设备一致，则不写入，也不创建新备份。保留工作目录和返回的备份路径。

计划或设备布局改变后必须重新读取、规划和预览，不能沿用旧摘要。

## 5. 预览恢复并提交

将 `BACKUP_FILE` 替换为应用时返回的实际备份文件路径：

```sh
layout_backup="BACKUP_FILE"
python3 scripts/iphone-layout.py restore "$layout_backup" --ecid "$layout_ecid"
```

确认恢复差异后，将 `RESTORE_PREVIEW_DIGEST` 替换为这次 **restore 预览** 返回的摘要，不要复用 apply 的摘要：

```sh
python3 scripts/iphone-layout.py restore "$layout_backup" --ecid "$layout_ecid" --commit --expect-plan-sha256 RESTORE_PREVIEW_DIGEST --backups "$layout_work_dir/backups"
```

恢复会在实际写入前再次备份当时的布局。这里只恢复图标布局，不调用整机恢复命令 `cfgutil restore`。

## 错误处理

- `Stale plan`：设备布局已变，重新读取并生成计划。
- 文件已存在：换用新的输出路径，CLI 不覆盖已有 JSON 文件。
- 图标缺失、新增或超容量：核对实际布局和规则，不通过删数据绕过检查。
- 写入失败、超时或回读不一致：保留错误中给出的备份路径，设备状态可能不确定。先重新读取并核对，再决定是否恢复；不要自动重试。

## 模型和模块

- `schemas/layout.schema.json`：统一模型 v1。图标 `{"type":"icon","id":"bundle ID 或 Web Clip URL"}`；文件夹有名称和二维 pages。
- `iphone_layout/core.py`：原生格式转换、结构/容量/重复项校验、图标守恒、规则分类、JSON unified diff。
- `iphone_layout/adapter.py`：仅 macOS、显式 ECID、子进程参数数组、60 秒超时；无 shell、无 --force。
- `iphone_layout/workflow.py`：快照、计划、校验、备份、写回、回读。
- `iphone_layout/cli.py`：用户/Agent 入口。失败返回 2，成功返回 0。
- 仓库根目录的 `tests/`：维护者的离线行为与模拟设备测试，不随 skill 安装，不调用真实手机。

snapshot 保存原生 raw、规范化 layout、ECID、UTC 时间与 raw 的 SHA-256。plan 保存设备、源布局摘要和目标模型；可用 `validate current.json target-layout.json` 和 `diff current.json target-layout.json` 检查独立目标文件。自定义目标通过 `workflow.plan(source, target)` 创建计划。所有文件均 UTF-8；CLI 新建 JSON 文件权限 0600 且拒绝覆盖。

每次提交重新读设备，拒绝过期计划；对 restore 允许当前排列不同，但图标集合必须相同。写入前保存新的可恢复快照并再次检查设备是否变化；写入后回读要求布局完全一致。失败时保留备份并报告路径，不自动重试。SHA-256 用于损坏检测，不是可信签名；只使用你信任的本地计划/备份。

## MVP 边界

仅支持 cfgutil 的数组格式：顶层第一个数组为 Dock，其余为页面；字符串为 App ID 或 Web Clip URL；文件夹为 `[名称, ID, ...]` 或 `[名称, [第一页 ID...], [第二页 ID...]]`。不猜测 JSON 包装格式或 SpringBoard plist 格式。

统一模型保守限制为 Dock 4 项、主屏每页 24 项/最多 15 页、文件夹每页 9 项/最多 15 页；它是本 MVP 支持范围，不是所有 iPhone/iOS 的容量保证。未知结构、重复图标、widget、空文件夹会报错。即使原生导出未暴露 widget，也无法证明屏幕几何位置可完整还原；有 widget/大图标/特殊布局时不要用本 MVP 写回。备份仅含 cfgutil 可见布局，不是整机数据备份，也不是完整已安装 App 清单。

cfgutil 没有事务或原子比较写入：最后一次检查与写入之间仍存在竞争窗口；使用期间避免手动重排或安装/卸载 App。项目不保证任意 Configurator/iOS 组合可用。恢复不会卸载、安装 App，也不会忽略缺失项。

尚未完成真实设备读写验收。示例为合成数据，离线和模拟测试结果不能替代真机验收。当前不声明支持 iPad，容量配置和导出格式尚未针对 iPad 验证。

## 格式依据

主要依据本机 Apple Configurator 附带的 `Contents/Resources/cfgutil.1`（get-icon-layout、set-icon-layout 和 --ecid）。它明确提示遗漏图标或超页容量会产生异常。
多页文件夹编码参照 [iphone-layout-tool 原始项目说明](https://github.com/tmad4000/iphone-layout-tool#layout-format)，尚待用户真实导出验证。没有实现该项目的协议逆向或 SpringBoard 后端。

提交必须传入预览返回的 `plan_sha256`（应用与恢复使用各自预览返回的摘要）；文件内容改变会拒绝提交。进程锁覆盖提交期间全部设备读取与写入，同一 macOS 用户的本工具实例互斥；不能阻止其他用户、直接 cfgutil 或手机手动修改。Python execute API 由调用方负责持有已授权的 proposal 对象。

恢复范围特别说明：App Library-only、隐藏页面状态和 widget 可能未被 cfgutil 导出。写回可能影响这些未导出的状态，旧布局 JSON 无法保证恢复它们；依赖这些状态的设备不应使用本 MVP 提交。图标守恒仅对导出可见 ID 成立。
