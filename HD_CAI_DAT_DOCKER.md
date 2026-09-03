# 🚀 HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG QUẢN LÝ CAMERA BẰNG DOCKER TRÊN LINUX

Hệ thống đã được đóng gói hoàn chỉnh bằng **Docker & Docker Compose**. Bạn có thể mang toàn bộ thư mục mã nguồn này lên bất kỳ máy chủ Linux nào (Ubuntu, Debian, CentOS, Rocky Linux...) để chạy chỉ với **1 câu lệnh duy nhất**.

---

## 📁 1. Cấu Trúc Docker Đã Thiết Lập

* **`backend/Dockerfile`**: Chạy FastAPI trên Python 3.11 Slim, tự động thiết lập múi giờ Việt Nam (`Asia/Ho_Chi_Minh`), kết nối MongoDB Atlas và giám sát đầu thu camera.
* **`frontend/Dockerfile`**: Multi-stage build (Node 20 build React & Nginx Alpine phục vụ giao diện + Reverse proxy `/api`).
* **`docker-compose.yml`**: Điều phối 2 container kết nối mạng nội bộ, tự động khởi động lại khi máy chủ reboot (`restart: always`).
* **`.env`**: Chứa chuỗi kết nối MongoDB Atlas đã cấu hình sẵn.

---

## 🖥️ 2. Chuẩn Bị Máy Chủ Linux

### Bước 2.1: Cài đặt Docker & Docker Compose (Nếu máy chủ chưa có)

Trên **Ubuntu / Debian**, chỉ cần chạy lệnh sau:
```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt Docker tự động từ script chính thức
curl -fsSL https://get.docker.com | sh

# Cho phép user hiện tại dùng Docker không cần gõ sudo
sudo usermod -aG docker $USER
newgrp docker

# Kiểm tra phiên bản Docker
docker --version
docker compose version
```

---

## 📤 3. Quy Trình Đồng Bộ Qua GitHub (Khuyên Dùng)

### Bước 3.1: Đẩy mã nguồn từ máy tính lên GitHub
1. Truy cập [GitHub](https://github.com) và tạo một **Repository mới** (ví dụ đặt tên `quanlycamera`, chọn chế độ **Private** để bảo mật).
2. Mở Terminal / PowerShell tại thư mục dự án trên máy tính của bạn và chạy:
   ```bash
   git remote add origin <LINK_REPO_GITHUB_CUA_BAN>
   git branch -M main
   git push -u origin main
   ```

---

### Bước 3.2: Tải về và khởi chạy lần đầu trên máy chủ Linux
Trên máy chủ Linux, bạn chỉ cần chạy:
```bash
# 1. Tải mã nguồn từ GitHub về
git clone <LINK_REPO_GITHUB_CUA_BAN>

# 2. Vào thư mục dự án
cd quanlycamera

# 3. Cấp quyền chạy cho file cập nhật tự động
chmod +x update.sh

# 4. Khởi chạy toàn bộ hệ thống bằng Docker
docker compose up -d --build
```

---

### 🔄 3.3. Quy Trình Cập Nhật Cực Nhanh (Khi Bạn Sửa Code Xong)

Mỗi lần bạn sửa xong tính năng hoặc giao diện trên máy tính, quy trình cập nhật chỉ mất 10 giây:

1. **Trên máy tính:**
   ```bash
   git add .
   git commit -m "Cập nhật tính năng mới"
   git push
   ```

2. **Trên máy chủ Linux (Chỉ cần 1 lệnh):**
   ```bash
   ./update.sh
   ```
   *(File `update.sh` sẽ tự động `git pull` mã mới nhất về và tự động build lại Docker container chạy ngầm mà không làm mất dữ liệu!)*

> ⏱️ *Lần đầu tiên chạy sẽ mất khoảng 1 - 2 phút để Docker tải image và build bundle.*

---

## 🌐 5. Truy Cập Hệ Thống

Sau khi container khởi động xong, bạn mở trình duyệt bất kỳ và truy cập:

* **Cổng truy cập ứng dụng:** `http://<IP_MAY_CHU_LINUX>:91`

*(Ví dụ: `http://192.168.1.100:91` hoặc `http://10.10.7.10:91`)*

---

## 🛠️ 6. Các Lệnh Quản Lý Thông Dụng

| Thao tác | Câu lệnh trên Linux |
| :--- | :--- |
| **Xem trạng thái container** | `docker compose ps` |
| **Xem log realtime (Backend & Quét)** | `docker compose logs -f backend` |
| **Xem log tất cả dịch vụ** | `docker compose logs -f` |
| **Khởi động lại toàn bộ hệ thống** | `docker compose restart` |
| **Dừng hệ thống** | `docker compose down` |
| **Build lại sau khi sửa code** | `docker compose up -d --build` |

---

## 🔒 7. Lưu Ý Về Tường Lửa (Firewall)
Nếu máy chủ Linux có bật tường lửa (`ufw`), bạn hãy mở cổng 91:
```bash
sudo ufw allow 91/tcp
sudo ufw reload
```
Đồng thời, đảm bảo máy chủ Linux có thể ping / kết nối đến dải IP của đầu thu (`10.10.7.x` và `192.168.5.x` qua VPN) để hệ thống lấy dữ liệu camera liên tục.
