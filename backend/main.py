import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query, Response, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import settings
from database import connect_to_mongo, close_mongo_connection, get_db, get_vn_now, VN_TZ, to_aware_vn
from services.dahua_service import DahuaService
from services.monitor_service import MonitorService
from services.report_service import ReportService
from services.email_service import EmailService
from services.auth_service import AuthService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("camera_manager.api")

# Pydantic Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class EmailConfigSchema(BaseModel):
    enabled: bool = False
    smtp_host: str = Field("smtp.gmail.com", example="smtp.gmail.com")
    smtp_port: int = Field(587, example=587)
    smtp_user: str = Field("", example="your_email@gmail.com")
    smtp_password: str = Field("", example="app_password")
    sender_email: str = Field("", example="your_email@gmail.com")
    recipient_emails: str = Field("", example="admin@gmail.com, it@gmail.com")
    use_tls: bool = True

# Security Scheme & Dependency
security = HTTPBearer(auto_error=False)

async def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chức năng này yêu cầu đăng nhập tài khoản Quản trị viên (Admin)",
            headers={"WWW-Authenticate": "Bearer"}
        )
    payload = AuthService.verify_token(credentials.credentials)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã hết hạn hoặc không có quyền Quản trị viên",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return payload
class DeviceCreate(BaseModel):
    name: str = Field(..., example="Đầu thu NVR Kho Nội Bộ")
    ip: str = Field(..., example="192.168.1.100")
    port: int = Field(80, example=80)
    username: str = Field("admin", example="admin")
    password: str = Field("", example="Admin@123")
    location: str = Field("Nội bộ (LAN)", example="Nội bộ (LAN) hoặc VPN Tỉnh")
    channel_count: int = Field(8, example=8)
    is_mock: bool = Field(False, description="Bật chế độ mô phỏng để test khi chưa có IP thật")

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    location: Optional[str] = None
    channel_count: Optional[int] = None
    is_mock: Optional[bool] = None

class TestConnectionRequest(BaseModel):
    ip: str
    port: int = 80
    username: str = "admin"
    password: str = ""
    is_mock: bool = False

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None

class EventNoteUpdate(BaseModel):
    note: str

# Lifespan: connect DB, seed demo Dahua devices if empty, start worker
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    db = get_db()

    # Khởi tạo tài khoản Quản trị viên (Admin) mặc định nếu chưa có
    await AuthService.init_admin_user()

    # Seed 4 đầu thu ban đầu (3 Nội bộ, 1 Tỉnh qua VPN) nếu DB trống
    device_count = await db.devices.count_documents({})
    if device_count == 0:
        logger.info("Database trống. Khởi tạo sẵn 4 đầu thu Dahua mẫu theo nhu cầu (3 LAN, 1 VPN Tỉnh)...")
        sample_devices = [
            {
                "name": "NVR 01 - Kho Tổng (Nội bộ)",
                "ip": "192.168.1.101",
                "port": 80,
                "username": "admin",
                "password": "Password123",
                "location": "Nội bộ (LAN)",
                "channel_count": 8,
                "status": "online",
                "is_mock": True,
                "mock_loss_channels": [],
                "last_seen": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc)
            },
            {
                "name": "NVR 02 - Tòa Nhà Văn Phòng (Nội bộ)",
                "ip": "192.168.1.102",
                "port": 80,
                "username": "admin",
                "password": "Password123",
                "location": "Nội bộ (LAN)",
                "channel_count": 8,
                "status": "online",
                "is_mock": True,
                "mock_loss_channels": [3], # Giả lập camera 3 mất tín hiệu
                "last_seen": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc)
            },
            {
                "name": "NVR 03 - Phân Xưởng Sản Xuất (Nội bộ)",
                "ip": "192.168.1.103",
                "port": 80,
                "username": "admin",
                "password": "Password123",
                "location": "Nội bộ (LAN)",
                "channel_count": 8,
                "status": "online",
                "is_mock": True,
                "mock_loss_channels": [],
                "last_seen": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc)
            },
            {
                "name": "NVR 04 - Chi Nhánh Tỉnh (Qua VPN)",
                "ip": "10.8.0.50",
                "port": 80,
                "username": "admin",
                "password": "Password123",
                "location": "Chi nhánh Tỉnh (VPN)",
                "channel_count": 16,
                "status": "online",
                "is_mock": True,
                "mock_loss_channels": [5, 12], # Giả lập camera 5 và 12 mất tín hiệu
                "last_seen": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc)
            },
        ]
        result = await db.devices.insert_many(sample_devices)
        logger.info(f"Đã khởi tạo {len(result.inserted_ids)} đầu thu mẫu thành công.")

    # Thực hiện 1 lần quét ban đầu
    asyncio.create_task(MonitorService.run_single_scan())

    # Khởi chạy background loop
    monitor_task = asyncio.create_task(MonitorService.start_background_loop(settings.scan_interval_seconds))

    yield

    MonitorService.stop_background_loop()
    monitor_task.cancel()
    await close_mongo_connection()

app = FastAPI(
    title="Camera & NVR Management System",
    description="Hệ thống giám sát đầu thu Dahua & camera nội bộ/VPN, báo cáo tháng",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper ObjectId & DateTime serializer (UTC+7 Việt Nam)
def serialize_doc(doc):
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    for key, val in list(doc.items()):
        if isinstance(val, datetime):
            if getattr(val, 'tzinfo', None) is not None:
                doc[key] = val.astimezone(VN_TZ).isoformat()
            else:
                doc[key] = val.replace(tzinfo=timezone.utc).astimezone(VN_TZ).isoformat()
    return doc

# --- API ROUTES ---

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "time": get_vn_now().isoformat(), "timezone": "UTC+7"}

# --- AUTHENTICATION ROUTES ---
@app.post("/api/auth/login")
async def login(payload: LoginRequest):
    """Đăng nhập Quản trị viên (Admin) để lấy Token xác thực."""
    user = await AuthService.authenticate(payload.username.strip(), payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác"
        )
    token = AuthService.create_token(user["username"], user.get("role", "admin"))
    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "role": user.get("role", "admin"),
            "display_name": user.get("display_name", "Quản Trị Viên")
        }
    }

@app.get("/api/auth/me")
async def get_current_user(current_admin: dict = Depends(get_current_admin)):
    """Kiểm tra token và lấy thông tin người dùng hiện tại."""
    return {
        "username": current_admin.get("sub"),
        "role": current_admin.get("role"),
        "is_admin": True
    }

@app.post("/api/auth/change-password")
async def change_password(payload: ChangePasswordRequest, current_admin: dict = Depends(get_current_admin)):
    """Đổi mật khẩu tài khoản quản trị viên."""
    username = current_admin.get("sub")
    success, msg = await AuthService.change_password(username, payload.old_password, payload.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"success": True, "message": msg}

# 1. Device Endpoints
@app.get("/api/devices")
async def list_devices():
    db = get_db()
    cursor = db.devices.find().sort("created_at", 1)
    devices = await cursor.to_list(100)
    return [serialize_doc(d) for d in devices]

@app.post("/api/devices")
async def create_device(payload: DeviceCreate, current_admin: dict = Depends(get_current_admin)):
    db = get_db()
    now = get_vn_now()
    new_dev = payload.model_dump()

    # Tự động phát hiện số lượng kênh nếu chưa xác định hoặc = 0
    if (not new_dev.get("channel_count") or new_dev.get("channel_count") <= 0) and not new_dev.get("is_mock"):
        detected_count = await DahuaService.detect_channel_count(payload.ip, payload.port, payload.username, payload.password)
        new_dev["channel_count"] = detected_count

    new_dev.update({
        "status": "unknown",
        "created_at": now,
        "last_seen": None,
        "last_check": None,
        "mock_loss_channels": []
    })
    result = await db.devices.insert_one(new_dev)
    new_dev["id"] = str(result.inserted_id)

    # Chạy quét ngay cho thiết bị mới
    asyncio.create_task(MonitorService.run_single_scan())
    return serialize_doc(new_dev)

@app.put("/api/devices/{device_id}")
async def update_device(device_id: str, payload: DeviceUpdate, current_admin: dict = Depends(get_current_admin)):
    db = get_db()
    if not ObjectId.is_valid(device_id):
        raise HTTPException(status_code=400, detail="Invalid Device ID")

    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Không có dữ liệu cập nhật")

    res = await db.devices.update_one({"_id": ObjectId(device_id)}, {"$set": update_data})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy đầu thu")

    # Quét lại
    asyncio.create_task(MonitorService.run_single_scan())
    updated = await db.devices.find_one({"_id": ObjectId(device_id)})
    return serialize_doc(updated)

@app.delete("/api/devices/{device_id}")
async def delete_device(device_id: str, current_admin: dict = Depends(get_current_admin)):
    db = get_db()
    if not ObjectId.is_valid(device_id):
        raise HTTPException(status_code=400, detail="Invalid Device ID")

    await db.devices.delete_one({"_id": ObjectId(device_id)})
    await db.channels.delete_many({"device_id": device_id})
    await db.events.delete_many({"device_id": device_id})
    return {"success": True, "message": "Đã xóa đầu thu và các dữ liệu liên quan"}

@app.post("/api/devices/test-connect")
async def test_dahua_connection(payload: TestConnectionRequest, current_admin: dict = Depends(get_current_admin)):
    """Kiểm tra trực tiếp thông số kết nối tới đầu thu Dahua."""
    result = await DahuaService.test_connection(
        ip=payload.ip,
        port=payload.port,
        username=payload.username,
        password=payload.password,
        is_mock=payload.is_mock
    )
    return result

# 2. Channel Endpoints
@app.get("/api/channels")
async def list_channels(device_id: Optional[str] = None):
    db = get_db()
    query = {}
    if device_id:
        query["device_id"] = device_id
    cursor = db.channels.find(query).sort([("device_id", 1), ("channel_no", 1)])
    channels = await cursor.to_list(500)
    return [serialize_doc(c) for c in channels]

@app.put("/api/channels/{channel_id}")
async def update_channel(channel_id: str, payload: ChannelUpdate, current_admin: dict = Depends(get_current_admin)):
    db = get_db()
    if not ObjectId.is_valid(channel_id):
        raise HTTPException(status_code=400, detail="Invalid Channel ID")

    res = await db.channels.update_one(
        {"_id": ObjectId(channel_id)},
        {"$set": {"name": payload.name}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy camera")

    updated = await db.channels.find_one({"_id": ObjectId(channel_id)})
    return serialize_doc(updated)

@app.post("/api/channels/{channel_id}/toggle-simulation")
async def toggle_mock_channel_loss(channel_id: str, current_admin: dict = Depends(get_current_admin)):
    """Nút bấm nhanh để giả lập mất tín hiệu / phục hồi camera (dùng kiểm thử hệ thống)."""
    db = get_db()
    if not ObjectId.is_valid(channel_id):
        raise HTTPException(status_code=400, detail="Invalid Channel ID")

    channel = await db.channels.find_one({"_id": ObjectId(channel_id)})
    if not channel:
        raise HTTPException(status_code=404, detail="Camera không tồn tại")

    dev_id = ObjectId(channel["device_id"])
    dev = await db.devices.find_one({"_id": dev_id})
    if not dev:
        raise HTTPException(status_code=404, detail="Đầu thu không tồn tại")

    ch_num = channel["channel_no"]
    loss_list = dev.get("mock_loss_channels", [])

    if ch_num in loss_list:
        loss_list.remove(ch_num)
        action = "phục hồi"
    else:
        loss_list.append(ch_num)
        action = "mất tín hiệu"

    await db.devices.update_one({"_id": dev_id}, {"$set": {"mock_loss_channels": loss_list, "is_mock": True}})
    await MonitorService.run_single_scan()

    return {"success": True, "message": f"Đã giả lập {action} cho Camera số {ch_num}"}

@app.post("/api/channels/{channel_id}/toggle-enable")
async def toggle_channel_enable(channel_id: str, current_admin: dict = Depends(get_current_admin)):
    """Bật hoặc tắt theo dõi kênh camera (ví dụ kênh chưa lắp camera hoặc bỏ qua không giám sát)."""
    db = get_db()
    if not ObjectId.is_valid(channel_id):
        raise HTTPException(status_code=400, detail="Invalid Channel ID")

    channel = await db.channels.find_one({"_id": ObjectId(channel_id)})
    if not channel:
        raise HTTPException(status_code=404, detail="Camera không tồn tại")

    current_enabled = channel.get("enabled", True)
    new_enabled = not current_enabled
    new_status = "unconnected" if not new_enabled else "online"

    await db.channels.update_one(
        {"_id": ObjectId(channel_id)},
        {"$set": {"enabled": new_enabled, "status": new_status}}
    )
    asyncio.create_task(MonitorService.run_single_scan())
    return {"success": True, "enabled": new_enabled, "message": "Đã cập nhật trạng thái theo dõi kênh"}

@app.post("/api/devices/{device_id}/sync-channels")
async def sync_device_channels(device_id: str, current_admin: dict = Depends(get_current_admin)):
    """Đồng bộ lại toàn bộ danh sách tên và trạng thái camera từ đầu thu Dahua thực tế."""
    db = get_db()
    if not ObjectId.is_valid(device_id):
        raise HTTPException(status_code=400, detail="Invalid Device ID")

    dev = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not dev:
        raise HTTPException(status_code=404, detail="Đầu thu không tồn tại")

    ip = dev.get("ip")
    port = dev.get("port", 80)
    username = dev.get("username", "admin")
    password = dev.get("password", "")
    channel_count = dev.get("channel_count", 8)
    is_mock = dev.get("is_mock", False)

    # 1. Lấy tên kênh từ Dahua CGI
    titles = await DahuaService.get_channel_titles(ip, port, username, password, channel_count, is_mock)

    # 2. Lấy trạng thái từng kênh
    _, ch_status_map = await DahuaService.get_channel_statuses(
        ip, port, username, password, channel_count, is_mock, dev.get("mock_loss_channels", [])
    )

    # 3. Xóa các kênh cũ của thiết bị và tạo lại chính xác
    await db.channels.delete_many({"device_id": device_id})

    now = get_vn_now()
    for ch_num in range(1, channel_count + 1):
        st = ch_status_map.get(ch_num, "unconnected")
        await db.channels.insert_one({
            "device_id": device_id,
            "device_name": dev.get("name", "NVR"),
            "channel_no": ch_num,
            "name": titles.get(ch_num, f"Camera {ch_num}"),
            "status": st,
            "enabled": True,
            "last_seen": now if st == "online" else None,
            "last_check": now
        })

    return {"success": True, "message": f"Đã đồng bộ {channel_count} kênh từ đầu thu Dahua thành công!"}

# 3. Monitor Control Endpoints
@app.post("/api/monitor/scan-now")
async def trigger_scan(current_admin: dict = Depends(get_current_admin)):
    """Kích hoạt quét toàn bộ hệ thống ngay lập tức."""
    await MonitorService.run_single_scan()
    return {"success": True, "message": "Đã hoàn thành quét hệ thống"}

@app.post("/api/channels/{channel_id}/toggle-maintenance")
async def toggle_channel_maintenance(channel_id: str, current_admin: dict = Depends(get_current_admin)):
    """Chuyển đổi trạng thái Bảo Trì cho kênh camera (không tính downtime, không cảnh báo)."""
    db = get_db()
    if not ObjectId.is_valid(channel_id):
        raise HTTPException(status_code=400, detail="Invalid Channel ID")

    channel = await db.channels.find_one({"_id": ObjectId(channel_id)})
    if not channel:
        raise HTTPException(status_code=404, detail="Camera không tồn tại")

    current_status = channel.get("status", "online")
    is_maintenance = current_status == "maintenance"
    now = get_vn_now()

    if is_maintenance:
        new_status = "online"
        new_enabled = True
        msg = f"Đã kết thúc bảo trì cho {channel.get('name', 'Camera')}. Tiếp tục giám sát tự động."
    else:
        new_status = "maintenance"
        new_enabled = False
        msg = f"Đã chuyển {channel.get('name', 'Camera')} sang Chế độ Bảo trì (Tạm ngưng tính lỗi SLA)."

        # Tự động chốt sự cố đang gián đoạn nếu có, ghi chú chuyển bảo trì để dừng tính downtime
        open_event = await db.events.find_one({
            "target_type": "channel",
            "$or": [
                {"target_id": str(channel_id)},
                {"device_id": str(channel.get("device_id")), "channel_no": channel.get("channel_no")}
            ],
            "resolved_at": None
        }, sort=[("timestamp", -1)])
        if open_event:
            ev_time = to_aware_vn(open_event.get("timestamp")) or now
            dur = max(0, int((now - ev_time).total_seconds()))
            curr_note = open_event.get("note") or ""
            updated_note = f"{curr_note} [Đã chuyển sang bảo trì lúc {now.strftime('%H:%M:%S %d/%m/%Y')}]".strip()
            await db.events.update_one(
                {"_id": open_event["_id"]},
                {"$set": {
                    "resolved_at": now,
                    "duration_seconds": dur,
                    "note": updated_note
                }}
            )

    await db.channels.update_one(
        {"_id": ObjectId(channel_id)},
        {"$set": {"status": new_status, "enabled": new_enabled}}
    )
    return {"success": True, "status": new_status, "is_maintenance": not is_maintenance, "message": msg}

@app.post("/api/devices/{device_id}/toggle-maintenance")
async def toggle_device_maintenance(device_id: str, current_admin: dict = Depends(get_current_admin)):
    """Chuyển đổi trạng thái Bảo Trì cho toàn bộ Đầu Thu NVR (tạm ngưng tính downtime)."""
    db = get_db()
    if not ObjectId.is_valid(device_id):
        raise HTTPException(status_code=400, detail="Invalid Device ID")

    device = await db.devices.find_one({"_id": ObjectId(device_id)})
    if not device:
        raise HTTPException(status_code=404, detail="Đầu thu không tồn tại")

    current_status = device.get("status", "online")
    is_maintenance = current_status == "maintenance"
    now = get_vn_now()

    if is_maintenance:
        new_status = "online"
        msg = f"Đã kết thúc bảo trì cho đầu thu {device.get('name', 'NVR')}. Tiếp tục giám sát tự động."
    else:
        new_status = "maintenance"
        msg = f"Đã chuyển đầu thu {device.get('name', 'NVR')} sang Chế độ Bảo trì (Tạm ngưng tính lỗi SLA)."

        # Tự động chốt sự cố đang gián đoạn nếu có
        open_event = await db.events.find_one({
            "target_type": "device",
            "target_id": str(device_id),
            "resolved_at": None
        }, sort=[("timestamp", -1)])
        if open_event:
            ev_time = to_aware_vn(open_event.get("timestamp")) or now
            dur = max(0, int((now - ev_time).total_seconds()))
            curr_note = open_event.get("note") or ""
            updated_note = f"{curr_note} [Đã chuyển sang bảo trì lúc {now.strftime('%H:%M:%S %d/%m/%Y')}]".strip()
            await db.events.update_one(
                {"_id": open_event["_id"]},
                {"$set": {
                    "resolved_at": now,
                    "duration_seconds": dur,
                    "note": updated_note
                }}
            )

    await db.devices.update_one(
        {"_id": ObjectId(device_id)},
        {"$set": {"status": new_status}}
    )
    return {"success": True, "status": new_status, "is_maintenance": not is_maintenance, "message": msg}

# 4. Events Endpoints
@app.get("/api/events")
async def list_events(limit: int = Query(100, ge=1, le=500)):
    db = get_db()
    cursor = db.events.find().sort("timestamp", -1).limit(limit)
    events = await cursor.to_list(limit)
    return [serialize_doc(e) for e in events]

@app.put("/api/events/{event_id}/note")
async def update_event_note(event_id: str, payload: EventNoteUpdate, current_admin: dict = Depends(get_current_admin)):
    """Cập nhật tiến độ / lý do giải trình sự cố trực tiếp (sẽ xuất ra file Excel Hải quan)."""
    db = get_db()
    if not ObjectId.is_valid(event_id):
        raise HTTPException(status_code=400, detail="Invalid Event ID")

    res = await db.events.update_one(
        {"_id": ObjectId(event_id)},
        {"$set": {"note": payload.note}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự cố")

    updated = await db.events.find_one({"_id": ObjectId(event_id)})
    return serialize_doc(updated)

# 5. Monthly Reports Endpoints
@app.get("/api/reports/monthly")
async def get_monthly_report(
    year: int = Query(default=None),
    month: int = Query(default=None)
):
    """Lấy dữ liệu tổng quan báo cáo theo tháng."""
    vn_now = get_vn_now()
    y = year if year is not None else vn_now.year
    m = month if month is not None else vn_now.month
    return await ReportService.get_monthly_summary(y, m)

@app.get("/api/reports/export-excel")
async def export_monthly_report_excel(
    year: int = Query(default=None),
    month: int = Query(default=None)
):
    """Xuất file Excel báo cáo tháng."""
    vn_now = get_vn_now()
    y = year if year is not None else vn_now.year
    m = month if month is not None else vn_now.month
    excel_stream = await ReportService.export_excel_report(y, m)
    filename = f"BaoCao_HoatDong_Camera_Thang_{m:02d}_{y}.xlsx"
    return Response(
        content=excel_stream.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# 6. Email Alert Settings Endpoints
@app.get("/api/settings/email")
async def get_email_settings():
    """Lấy thông tin cấu hình gửi email cảnh báo hiện tại."""
    cfg = await EmailService.get_email_config()
    if not cfg:
        return {
            "enabled": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password": "",
            "sender_email": "",
            "recipient_emails": "",
            "use_tls": True
        }
    cfg["id"] = str(cfg["_id"])
    del cfg["_id"]
    return cfg

@app.post("/api/settings/email")
async def update_email_settings(payload: EmailConfigSchema, current_admin: dict = Depends(get_current_admin)):
    """Lưu cấu hình gửi email cảnh báo."""
    data = payload.model_dump()
    await EmailService.save_email_config(data)
    return {"success": True, "message": "Đã lưu cấu hình email cảnh báo thành công!"}

@app.post("/api/settings/email/test")
async def test_email_alert(current_admin: dict = Depends(get_current_admin)):
    """Gửi một email thử nghiệm để kiểm tra thông số SMTP và danh sách người nhận."""
    now_str = get_vn_now().strftime("%H:%M:%S ngày %d/%m/%Y")
    html = EmailService.build_incident_html(
        "HỆ THỐNG THỬ NGHIỆM", 
        "Toàn bộ camera & đầu thu", 
        "online", 
        now_str, 
        "Đây là email kiểm tra chức năng thông báo sự cố từ Hệ Thống Quản Lý Camera Dahua. Cấu hình SMTP của bạn hoạt động hoàn hảo!"
    )
    res = await EmailService.send_alert("🔔 [TEST] Kiểm tra Email cảnh báo Hệ thống Camera Dahua", html)
    return res

# 7. Hải Quan Daily Report & Data Retention Endpoints
@app.get("/api/reports/export-haiquan-excel")
async def export_haiquan_excel(
    year: int = Query(default=None),
    month: int = Query(default=None),
    reporter: Optional[str] = Query(default="")
):
    """Xuất file Excel theo đúng biểu mẫu 'KIỂM TRA HOẠT ĐỘNG CỦA CAMERA HẢI QUAN' theo 31 ngày."""
    vn_now = get_vn_now()
    y = year if year is not None else vn_now.year
    m = month if month is not None else vn_now.month
    excel_stream = await ReportService.export_haiquan_daily_excel(y, m, reporter)
    filename = f"KiemTra_Camera_HaiQuan_Thang_{m:02d}_{y}.xlsx"
    return Response(
        content=excel_stream.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/data/retention-stats")
async def get_retention_stats(year: Optional[int] = Query(None, ge=2020, le=2050)):
    """Lấy danh sách các tháng và thống kê sự cố (kể cả tháng 0 sự cố) để người dùng quản lý chốt sổ và tải báo cáo."""
    return await ReportService.get_data_retention_stats(year)

@app.delete("/api/data/cleanup-month")
async def cleanup_month_data(
    year: int = Query(..., ge=2020, le=2050),
    month: int = Query(..., ge=1, le=12),
    current_admin: dict = Depends(get_current_admin)
):
    """Xóa dữ liệu sự cố của một tháng sau khi người dùng đã chốt sổ."""
    return await ReportService.delete_monthly_events(year, month)

@app.delete("/api/data/cleanup-year")
async def cleanup_year_data(
    year: int = Query(..., ge=2020, le=2050),
    current_admin: dict = Depends(get_current_admin)
):
    """Xóa toàn bộ dữ liệu sự cố của cả năm."""
    return await ReportService.delete_yearly_events(year)


