import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import settings
from database import connect_to_mongo, close_mongo_connection, get_db
from services.dahua_service import DahuaService
from services.monitor_service import MonitorService
from services.report_service import ReportService
from services.email_service import EmailService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("camera_manager.api")

# Pydantic Schemas
class EmailConfigSchema(BaseModel):
    enabled: bool = False
    smtp_host: str = Field("smtp.gmail.com", example="smtp.gmail.com")
    smtp_port: int = Field(587, example=587)
    smtp_user: str = Field("", example="your_email@gmail.com")
    smtp_password: str = Field("", example="app_password")
    sender_email: str = Field("", example="your_email@gmail.com")
    recipient_emails: str = Field("", example="admin@gmail.com, it@gmail.com")
    use_tls: bool = True
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

# Lifespan: connect DB, seed demo Dahua devices if empty, start worker
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    db = get_db()

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

# Helper ObjectId serializer
def serialize_doc(doc):
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc

# --- API ROUTES ---

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

# 1. Device Endpoints
@app.get("/api/devices")
async def list_devices():
    db = get_db()
    cursor = db.devices.find().sort("created_at", 1)
    devices = await cursor.to_list(100)
    return [serialize_doc(d) for d in devices]

@app.post("/api/devices")
async def create_device(payload: DeviceCreate):
    db = get_db()
    now = datetime.now(timezone.utc)
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
async def update_device(device_id: str, payload: DeviceUpdate):
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
async def delete_device(device_id: str):
    db = get_db()
    if not ObjectId.is_valid(device_id):
        raise HTTPException(status_code=400, detail="Invalid Device ID")

    await db.devices.delete_one({"_id": ObjectId(device_id)})
    await db.channels.delete_many({"device_id": device_id})
    await db.events.delete_many({"device_id": device_id})
    return {"success": True, "message": "Đã xóa đầu thu và các dữ liệu liên quan"}

@app.post("/api/devices/test-connect")
async def test_dahua_connection(payload: TestConnectionRequest):
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
async def update_channel(channel_id: str, payload: ChannelUpdate):
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
async def toggle_mock_channel_loss(channel_id: str):
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
async def toggle_channel_enable(channel_id: str):
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
async def sync_device_channels(device_id: str):
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

    now = datetime.now(timezone.utc)
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
async def trigger_scan():
    """Kích hoạt quét toàn bộ hệ thống ngay lập tức."""
    await MonitorService.run_single_scan()
    return {"success": True, "message": "Đã hoàn thành quét hệ thống"}

# 4. Events Endpoints
@app.get("/api/events")
async def list_events(limit: int = Query(50, ge=1, le=200)):
    db = get_db()
    cursor = db.events.find().sort("timestamp", -1).limit(limit)
    events = await cursor.to_list(limit)
    return [serialize_doc(e) for e in events]

# 5. Monthly Reports Endpoints
@app.get("/api/reports/monthly")
async def get_monthly_report(
    year: int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month, ge=1, le=12)
):
    """Lấy dữ liệu tổng quan báo cáo theo tháng."""
    return await ReportService.get_monthly_summary(year, month)

@app.get("/api/reports/export-excel")
async def export_monthly_report_excel(
    year: int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month, ge=1, le=12)
):
    """Xuất file Excel báo cáo tháng."""
    excel_stream = await ReportService.export_excel_report(year, month)
    filename = f"BaoCao_HoatDong_Camera_Thang_{month:02d}_{year}.xlsx"
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
async def update_email_settings(payload: EmailConfigSchema):
    """Lưu cấu hình gửi email cảnh báo."""
    data = payload.model_dump()
    await EmailService.save_email_config(data)
    return {"success": True, "message": "Đã lưu cấu hình email cảnh báo thành công!"}

@app.post("/api/settings/email/test")
async def test_email_alert():
    """Gửi một email thử nghiệm để kiểm tra thông số SMTP và danh sách người nhận."""
    now_str = datetime.now().strftime("%H:%M:%S ngày %d/%m/%Y")
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
    year: int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month, ge=1, le=12),
    reporter: Optional[str] = Query(default="")
):
    """Xuất file Excel theo đúng biểu mẫu 'KIỂM TRA HOẠT ĐỘNG CỦA CAMERA HẢI QUAN' theo 31 ngày."""
    excel_stream = await ReportService.export_haiquan_daily_excel(year, month, reporter)
    filename = f"KiemTra_Camera_HaiQuan_Thang_{month:02d}_{year}.xlsx"
    return Response(
        content=excel_stream.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/data/retention-stats")
async def get_retention_stats():
    """Lấy danh sách các tháng có dữ liệu sự cố để người dùng quản lý chốt sổ và xóa."""
    return await ReportService.get_data_retention_stats()

@app.delete("/api/data/cleanup-month")
async def cleanup_month_data(
    year: int = Query(..., ge=2020, le=2050),
    month: int = Query(..., ge=1, le=12)
):
    """Xóa dữ liệu sự cố của một tháng sau khi người dùng đã chốt sổ."""
    return await ReportService.delete_monthly_events(year, month)

@app.delete("/api/data/cleanup-year")
async def cleanup_year_data(
    year: int = Query(..., ge=2020, le=2050)
):
    """Xóa toàn bộ dữ liệu sự cố của cả năm."""
    return await ReportService.delete_yearly_events(year)


