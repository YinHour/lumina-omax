# MCP 集成

连接 Claude Desktop、VS Code 和其他 MCP 客户端。

---

## 概述

Lumiton·Omax 支持 MCP（Model Context Protocol），允许外部工具直接访问你的研究笔记本。

---

## 配置

在客户端的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "lumina-omax": {
      "url": "http://localhost:5055/api/mcp"
    }
  }
}
```

---

## 支持的客户端

- Claude Desktop
- VS Code（通过 MCP 扩展）
- 其他兼容 MCP 的工具
