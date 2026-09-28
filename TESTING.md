# 验证记录

## 目录整理验证（2026-09-28）

- `python3 -m unittest discover -s tests -v`：23 项通过。
- 将 `skills/iphone-home-screen-layout` 单独复制到临时目录，在仓库外执行脚本的离线 `import` 和 `plan`：通过，未依赖仓库根目录。
- 使用 setuptools 84 构建 `iphone_home_screen_layout-0.1.0-py3-none-any.whl`，确认包含 Python 模块及 `iphone-layout` 命令入口。
- 技能内部 Markdown 资源链接存在，Schema JSON 可解析。
- skill-creator 的 `quick_validate.py` 因缺少 PyYAML 未运行成功；已人工检查 frontmatter 的名称、描述和资源引用。
- 未执行社区 `npx skills` 安装器的端到端安装；发布前应在独立目录验证实际安装结果。

## 测试范围

覆盖原生双向转换、多页文件夹、Web Clip、容量/重复/遗漏/未知类型、分类保留 Dock 与未分配项、分页、默认预览不写入、ECID/过期计划拒绝、二次读取变化拒绝、备份失败阻止写入、写入失败/回读不一致保留备份、apply→restore 往返、恢复保留原生编码、CLI 离线示例、adapter 参数/超时/错误、并发锁、提交缺少摘要时拒绝写入。

所有设备操作使用模拟对象，没有手机读写。此前系统可找到 cfgutil，但 `cfgutil help` 在执行环境退出 134，未完成真机验收。JSON Schema 独立验证器尚未运行；运行时结构和语义校验由无依赖 Python core 完成。

后续真机验收：导出一台明确 ECID 的实际布局，检查是否含不支持的结构；针对两个图标生成小范围计划，经审阅和授权后应用，检查屏幕与回读一致，再用产生的备份恢复。widget/隐藏页面/App Library-only 等限制见技能使用指南。
