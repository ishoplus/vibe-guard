# 推送时自动跑测试（CI）

CI 就是「每次推送代码，GitHub 自动帮你跑一遍测试」。测试没过，就在 GitHub 上显示红叉；配合平台设置，可以做到**测试不过就不上线**。

**前提**：项目已经有测试（`npm test` 或 `pytest` 能跑）。还没有测试的，先别加 CI —— 空跑没有意义，先用 small-steps 给核心流程补测试。

## 做法
1. 按项目类型复制模板到项目里：
   - Node 项目：`templates/ci-node.yml` → `.github/workflows/ci.yml`
   - Python 项目：`templates/ci-python.yml` → `.github/workflows/ci.yml`
2. 按项目实际情况改测试命令（模板里标了要改的地方）
3. 推送后到 GitHub 仓库的 Actions 页面，确认出现绿色勾
4. **让测试挡住上线**（二选一）：
   - 在 GitHub 仓库 Settings → Branches 给 main 设保护规则，要求 CI 通过才能合并；日常改动走分支 + PR
   - 或在托管平台的设置里，要求 GitHub 检查通过后才部署（Vercel、Netlify 等有这类选项）
5. 在 AGENTS.md「上线与回滚」一节写上：推送会自动跑测试，红叉时不要上线

## 注意
- CI 里需要的密钥放在 GitHub 仓库的 Settings → Secrets，**不要写进 workflow 文件**
- 公开仓库的 Actions 日志任何人都看得到，别在测试里打印密钥
