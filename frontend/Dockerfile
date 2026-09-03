# Bước 1: Build ứng dụng React với Vite
FROM node:20-alpine AS build

WORKDIR /app

# Cài đặt dependencies trước để tối ưu Docker cache
COPY package.json package-lock.json* ./
RUN npm install

# Copy toàn bộ mã nguồn frontend và tiến hành build bundle
COPY . .
RUN npm run build

# Bước 2: Chạy Web Server Nginx phục vụ trang web và Reverse Proxy
FROM nginx:alpine

# Thiết lập múi giờ Việt Nam
ENV TZ=Asia/Ho_Chi_Minh

# Copy cấu hình Nginx tối ưu
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy kết quả build từ Bước 1 vào Nginx
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
