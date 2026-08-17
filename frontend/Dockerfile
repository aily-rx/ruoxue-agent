# Ruoxue Frontend — React + Nginx
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
# 官方源在 CI（GitHub runner）已验证可用; 本地构建的国内网络问题应靠 Docker 代理解决
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost:80/ || exit 1
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
