import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional
from database import get_db
from services.dahua_service import DahuaService
from services.email_service import EmailService

logger = logging.getLogger("camera_manager.monitor")

class MonitorService:
    _is_running: bool = False

    @staticmethod
    async def run_single_scan():
        """Thực hiện một chu kỳ quét toàn bộ đầu thu và camera."""
        db = get_db()
        if db is None:
            logger.warning("Database not connected, skipping scan.")
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        devices_cursor = db.devices.find()
        devices = await devices_cursor.to_list(length=100)

        for dev in devices:
            dev_id = dev["_id"]
            dev_name = dev.get("name", "NVR")
            ip = dev.get("ip")
            port = dev.get("port", 80)
            username = dev.get("username", "admin")
            password = dev.get("password", "")
            channel_count = dev.get("channel_count", 8)
            is_mock = dev.get("is_mock", False)
            prev_status = dev.get("status", "unknown")
            mock_loss = dev.get("mock_loss_channels", [])

            try:
                # Quét trạng thái đầu thu và các kênh chi tiết (phân biệt có camera và chưa gắn camera)
                nvr_online, channel_status_map = await DahuaService.get_channel_statuses(
                    ip=ip,
                    port=port,
                    username=username,
                    password=password,
                    total_channels=channel_count,
                    is_mock=is_mock,
                    mock_loss_channels=mock_loss,
                    mock_unconnected_channels=dev.get("mock_unconnected_channels", [])
                )

                # Chống báo động giả do độ trễ mạng VPN: Nếu lần 1 thấy rớt, thử lại lần 2 sau 2.5s
                if not nvr_online and prev_status == "online":
                    await asyncio.sleep(2.5)
                    nvr_online, channel_status_map = await DahuaService.get_channel_statuses(
                        ip=ip, port=port, username=username, password=password,
                        total_channels=channel_count, is_mock=is_mock,
                        mock_loss_channels=mock_loss,
                        mock_unconnected_channels=dev.get("mock_unconnected_channels", [])
                    )

                new_nvr_status = "online" if nvr_online else "offline"

                # 1. Xử lý sự kiện Đầu thu thay đổi trạng thái
                if prev_status != new_nvr_status:
                    if new_nvr_status == "offline":
                        # Ghi nhận sự cố đầu thu mất tín hiệu
                        note = f"Đầu thu {dev_name} ({ip}) mất kết nối/mất nguồn."
                        await db.events.insert_one({
                            "target_type": "device",
                            "target_id": str(dev_id),
                            "target_name": dev_name,
                            "device_id": str(dev_id),
                            "device_name": dev_name,
                            "event": "offline",
                            "timestamp": now,
                            "resolved_at": None,
                            "duration_seconds": None,
                            "note": note
                        })
                        logger.warning(f"ALERT: Device {dev_name} ({ip}) went OFFLINE!")

                        # Gửi email cảnh báo
                        now_str = now.strftime("%H:%M:%S ngày %d/%m/%Y")
                        html = EmailService.build_incident_html(dev_name, dev_name, "offline", now_str, note)
                        asyncio.create_task(EmailService.send_alert(f"🚨 [CẢNH BÁO] Đầu thu {dev_name} ({ip}) MẤT KẾT NỐI", html))

                    elif new_nvr_status == "online" and prev_status == "offline":
                        # Đầu thu phục hồi -> Đóng sự cố cũ
                        dur = 0
                        open_event = await db.events.find_one({
                            "target_type": "device",
                            "target_id": str(dev_id),
                            "event": "offline",
                            "resolved_at": None
                        }, sort=[("timestamp", -1)])
                        
                        if open_event:
                            ev_time = open_event["timestamp"].replace(tzinfo=None) if getattr(open_event["timestamp"], 'tzinfo', None) else open_event["timestamp"]
                            dur = int((now - ev_time).total_seconds())
                            await db.events.update_one(
                                {"_id": open_event["_id"]},
                                {"$set": {"resolved_at": now, "duration_seconds": dur}}
                            )

                        # Ghi log phục hồi
                        note = f"Đầu thu {dev_name} ({ip}) đã kết nối trở lại sau {round(dur/60, 1)} phút."
                        await db.events.insert_one({
                            "target_type": "device",
                            "target_id": str(dev_id),
                            "target_name": dev_name,
                            "device_id": str(dev_id),
                            "device_name": dev_name,
                            "event": "online",
                            "timestamp": now,
                            "resolved_at": now,
                            "duration_seconds": 0,
                            "note": note
                        })
                        logger.info(f"RESOLVED: Device {dev_name} ({ip}) is back ONLINE.")

                        # Gửi email thông báo phục hồi
                        now_str = now.strftime("%H:%M:%S ngày %d/%m/%Y")
                        html = EmailService.build_incident_html(dev_name, dev_name, "online", now_str, note)
                        asyncio.create_task(EmailService.send_alert(f"✅ [PHỤC HỒI] Đầu thu {dev_name} ({ip}) ĐÃ KẾT NỐI LẠI", html))

                # Cập nhật thông tin đầu thu
                update_fields = {
                    "status": new_nvr_status,
                    "last_check": now
                }
                if new_nvr_status == "online":
                    update_fields["last_seen"] = now

                await db.devices.update_one({"_id": dev_id}, {"$set": update_fields})

                # 2. Xử lý các kênh camera con
                if nvr_online:
                    # Lấy danh sách kênh hiện tại trong DB
                    curr_channels = await db.channels.find({"device_id": str(dev_id)}).to_list(100)
                    ch_dict = {c["channel_no"]: c for c in curr_channels}

                    # Đồng bộ tên kênh nếu chưa có
                    if len(curr_channels) == 0:
                        titles = await DahuaService.get_channel_titles(ip, port, username, password, channel_count, is_mock)
                        for ch_num in range(1, channel_count + 1):
                            init_status = channel_status_map.get(ch_num, "online")
                            await db.channels.insert_one({
                                "device_id": str(dev_id),
                                "device_name": dev_name,
                                "channel_no": ch_num,
                                "name": titles.get(ch_num, f"Camera {ch_num}"),
                                "status": init_status,
                                "last_seen": now if init_status == "online" else None,
                                "last_check": now
                            })
                    else:
                        # Đã có kênh -> cập nhật trạng thái từng kênh
                        for ch_num in range(1, channel_count + 1):
                            ch_info = ch_dict.get(ch_num)
                            if not ch_info:
                                continue

                            prev_ch_status = ch_info.get("status", "online")
                            new_ch_status = channel_status_map.get(ch_num, "online")

                            # Nếu kênh bị tắt bởi người dùng thì bỏ qua
                            if not ch_info.get("enabled", True):
                                new_ch_status = "disabled"

                            if prev_ch_status != new_ch_status:
                                ch_name = ch_info.get("name", f"Camera {ch_num}")
                                
                                # Chỉ cảnh báo Video Loss khi kênh đó là kênh đang dùng mà bị rớt tín hiệu
                                if new_ch_status == "video_loss" and prev_ch_status == "online":
                                    # Mất tín hiệu camera
                                    note = f"Camera {ch_name} (Kênh {ch_num}) bị mất tín hiệu hình ảnh (Video Loss)."
                                    await db.events.insert_one({
                                        "target_type": "channel",
                                        "target_id": str(ch_info["_id"]),
                                        "target_name": f"{dev_name} - {ch_name} (Kênh {ch_num})",
                                        "device_id": str(dev_id),
                                        "device_name": dev_name,
                                        "channel_no": ch_num,
                                        "event": "video_loss",
                                        "timestamp": now,
                                        "resolved_at": None,
                                        "duration_seconds": None,
                                        "note": note
                                    })
                                    logger.warning(f"ALERT: Camera {ch_name} (Ch {ch_num}) on {dev_name} VIDEO LOSS!")

                                    # Gửi email cảnh báo
                                    now_str = now.strftime("%H:%M:%S ngày %d/%m/%Y")
                                    html = EmailService.build_incident_html(dev_name, f"{ch_name} (Kênh {ch_num})", "video_loss", now_str, note)
                                    asyncio.create_task(EmailService.send_alert(f"🚨 [CẢNH BÁO] Camera {ch_name} ({dev_name}) MẤT TÍN HIỆU", html))

                                elif new_ch_status == "online":
                                    # Kiểm tra xem có sự cố video_loss cũ nào chưa đóng cho kênh này không
                                    open_ch_event = await db.events.find_one({
                                        "target_type": "channel",
                                        "$or": [
                                            {"target_id": str(ch_info["_id"])},
                                            {"device_id": str(dev_id), "channel_no": ch_num}
                                        ],
                                        "event": "video_loss",
                                        "resolved_at": None
                                    }, sort=[("timestamp", -1)])

                                    if open_ch_event:
                                        ev_time = open_ch_event["timestamp"].replace(tzinfo=None) if getattr(open_ch_event["timestamp"], 'tzinfo', None) else open_ch_event["timestamp"]
                                        dur = int((now - ev_time).total_seconds())
                                        await db.events.update_one(
                                            {"_id": open_ch_event["_id"]},
                                            {"$set": {"resolved_at": now, "duration_seconds": dur}}
                                        )

                                        note = f"Camera {ch_name} (Kênh {ch_num}) đã có tín hiệu hình ảnh trở lại sau {round(dur/60, 1)} phút."
                                        await db.events.insert_one({
                                            "target_type": "channel",
                                            "target_id": str(ch_info["_id"]),
                                            "target_name": f"{dev_name} - {ch_name} (Kênh {ch_num})",
                                            "device_id": str(dev_id),
                                            "device_name": dev_name,
                                            "channel_no": ch_num,
                                            "event": "recovered",
                                            "timestamp": now,
                                            "resolved_at": now,
                                            "duration_seconds": 0,
                                            "note": note
                                        })
                                        logger.info(f"RESOLVED: Camera {ch_name} (Ch {ch_num}) on {dev_name} RECOVERED.")

                                        # Gửi email thông báo phục hồi
                                        now_str = now.strftime("%H:%M:%S ngày %d/%m/%Y")
                                        html = EmailService.build_incident_html(dev_name, f"{ch_name} (Kênh {ch_num})", "recovered", now_str, note)
                                        asyncio.create_task(EmailService.send_alert(f"✅ [PHỤC HỒI] Camera {ch_name} ({dev_name}) ĐÃ CÓ TÍN HIỆU LẠI", html))

                            # Cập nhật kênh
                            ch_update = {
                                "status": new_ch_status,
                                "last_check": now
                            }
                            if new_ch_status == "online":
                                ch_update["last_seen"] = now

                            await db.channels.update_one({"_id": ch_info["_id"]}, {"$set": ch_update})
                else:
                    # Nếu NVR offline thì các camera thuộc NVR cũng tạm coi là rớt theo
                    await db.channels.update_many(
                        {"device_id": str(dev_id)},
                        {"$set": {"status": "offline", "last_check": now}}
                    )

            except Exception as e:
                logger.error(f"Error scanning device {dev_name} ({ip}): {e}")

    @classmethod
    async def start_background_loop(cls, interval_seconds: int = 60):
        cls._is_running = True
        logger.info(f"Monitor background worker started (interval: {interval_seconds}s)")
        while cls._is_running:
            try:
                await cls.run_single_scan()
            except Exception as e:
                logger.error(f"Unhandled error in monitor loop: {e}")
            await asyncio.sleep(interval_seconds)

    @classmethod
    def stop_background_loop(cls):
        cls._is_running = False
        logger.info("Monitor background worker stopped.")
