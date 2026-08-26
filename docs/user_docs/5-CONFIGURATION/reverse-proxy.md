# 反向代理配置

使用 nginx、Caddy、Traefik 部署到自定义域名 + HTTPS。

---

## Nginx（推荐）

```nginx
server {
    listen 443 ssl http2;
    server_name notebook.example.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    client_max_body_size 100M;

    location / {
        proxy_pass http://lumina-omax:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
    }
}
```

## Caddy

```caddy
notebook.example.com {
    reverse_proxy lumina-omax:3000
}
```

Caddy 自动处理 HTTPS。只需代理一个端口（3000），Next.js 内部转发 API 请求。
