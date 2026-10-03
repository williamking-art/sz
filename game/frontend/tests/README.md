# frontend/tests · 前端测试入口

> 层归属：**游戏本体**（前端工程测试）。

## 关键内容
| 文件 | 说明 |
|---|---|
| `setup.ts` | vitest 全局设置：jsdom 环境 + `@testing-library/jest-dom` 匹配器注册 |

## 怎么跑
```powershell
cd D:\codebuddy\sz\game\frontend
npm test            # vitest run（测试文件与用例会持续变化）
```
用例与源码同放（`src/**/__tests__/*.test.ts(x)`），**不集中在本目录**；本目录只放公共设置。
---
