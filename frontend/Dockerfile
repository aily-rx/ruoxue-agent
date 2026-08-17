# Ruoxue Frontend — React + Nginx
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
# 国内环境 registry 直连超时（npm ci 在容器内访问官方源会卡死）
RUN npm config set registry https://registry.npmmirror.com
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost:80/ || exit 1
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
