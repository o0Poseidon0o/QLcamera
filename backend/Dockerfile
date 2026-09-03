# Sử dụng Python 3.11 Slim (nhẹ, bảo mật, tối ưu cho Linux)
FROM python:3.11-slim

# Thiết lập múi giờ Việt Nam
ENV TZ=Asia/Ho_Chi_Minh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Cài đặt curl để kiểm tra healthcheck và các thư viện hệ thống cần thiết
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt thư viện Python trước để tận dụng Docker cache layer
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn backend
COPY . .

# Port FastAPI
EXPOSE 8000

# Chạy ứng dụng FastAPI bằng Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
