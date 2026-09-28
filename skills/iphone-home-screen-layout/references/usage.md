# 使用指南

以下命令均从 skill 根目录执行（即包含 `SKILL.md` 的目录），需要 Python 3.9+。输出及备份请放到独立工作目录，避免技能升级影响它们。

## 真机流程

安装 Apple Configurator，并在其菜单中安装 Automation Tools；也支持 app 内的 cfgutil 路径。通过 USB 连接已解锁且信任 Mac 的 iPhone。运行 `cfgutil list` 获取 ECID，下列 `YOUR_ECID` 应替换为该值。

```sh
layout_work_dir="$(mktemp -d)"
python3 scripts/iphone-layout.py read --ecid YOUR_ECID --out "$layout_work_dir/current.json"
python3 scripts/iphone-layout.py plan "$layout_work_dir/current.json" examples/categories.json --out "$layout_work_dir/plan.json"
python3 scripts/iphone-layout.py apply "$layout_work_dir/plan.json" --ecid YOUR_ECID
python3 scripts/iphone-layout.py apply "$layout_work_dir/plan.json" --ecid YOUR_ECID --commit --expect-plan-sha256 PREVIEW_DIGEST --backups "$layout_work_dir/backups"
python3 scripts/iphone-layout.py restore "$layout_work_dir/backups/BACKUP_ID.json" --ecid YOUR_ECID
python3 scripts/iphone-layout.py restore "$layout_work_dir/backups/BACKUP_ID.json" --ecid YOUR_ECID --commit --expect-plan-sha256 PREVIEW_DIGEST --backups "$layout_work_dir/backups"
```

示例 rules 中的 ID 仅用于示例；真机必须换成实际 read 得到的 ID。`backup --ecid ... --out backup.json` 是 read 的明确备份别名。`import raw.json --ecid ... --out snapshot.json` 仅用于已有 cfgutil 导出。设备命令支持 `--cfgutil /absolute/path/to/cfgutil`。

对“社交放一起，Dock 不动，不确定的保留”这样的请求，Agent 从 current.json 选择真实 ID，生成 categories 格式的规则，运行 plan 并展示结果。默认未分类图标留在原页面/文件夹，空文件夹删除，图标位置收紧，新文件夹追加到末页。可以生成多页文件夹。不自动从网络推断 App 类别。

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

本次开发机器能找到 cfgutil，但执行 `cfgutil help` 异常退出（134）；未对真实设备读写。示例是合成数据，不是用户手机导出。离线和模拟测试结果不能替代真机验收。

## 格式依据

主要依据本机 Apple Configurator 附带的 `Contents/Resources/cfgutil.1`（get-icon-layout、set-icon-layout 和 --ecid）。它明确提示遗漏图标或超页容量会产生异常。
多页文件夹编码参照 [iphone-layout-tool 原始项目说明](https://github.com/tmad4000/iphone-layout-tool#layout-format)，尚待用户真实导出验证。没有实现该项目的协议逆向或 SpringBoard 后端。

提交必须传入预览返回的 `plan_sha256`（将 PREVIEW_DIGEST 替换为实际摘要）；文件内容改变会拒绝提交。进程锁覆盖提交期间全部设备读取与写入，同一 macOS 用户的本工具实例互斥；不能阻止其他用户、直接 cfgutil 或手机手动修改。Python execute API 由调用方负责持有已授权的 proposal 对象。

恢复范围特别说明：App Library-only、隐藏页面状态和 widget 可能未被 cfgutil 导出。写回可能影响这些未导出的状态，旧布局 JSON 无法保证恢复它们；依赖这些状态的设备不应使用本 MVP 提交。图标守恒仅对导出可见 ID 成立。
