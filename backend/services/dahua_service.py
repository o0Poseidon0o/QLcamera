import asyncio
import socket
import httpx
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, date
import calendar

logger = logging.getLogger("camera_manager.dahua")

class DahuaService:
    @staticmethod
    async def check_tcp_port(ip: str, port: int, timeout: float = 4.5, retries: int = 1) -> bool:
        """Kiểm tra cổng TCP với timeout rộng và cơ chế retry phù hợp cho đường truyền VPN độ trễ cao."""
        loop = asyncio.get_running_loop()
        for attempt in range(retries + 1):
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setblocking(False)
                await asyncio.wait_for(
                    loop.sock_connect(sock, (ip, port)),
                    timeout=timeout
                )
                sock.close()
                return True
            except Exception:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                if attempt < retries:
                    await asyncio.sleep(0.4)
        return False

    @staticmethod
    async def detect_channel_count(ip: str, port: int, username: str, password: str, timeout: float = 3.5) -> int:
        """Tự động phát hiện số lượng kênh tối đa của đầu thu Dahua."""
        auth = httpx.DigestAuth(username, password)
        detected = 0

        async with httpx.AsyncClient(timeout=timeout) as client:
            # Cách 1: Đếm số lượng ChannelTitle
            try:
                url_title = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=ChannelTitle"
                r = await client.get(url_title, auth=auth)
                if r.status_code == 200:
                    indices = [int(m) for m in re.findall(r'table\.ChannelTitle\[(\d+)\]', r.text)]
                    if indices:
                        detected = max(detected, max(indices) + 1)
            except Exception:
                pass

            # Cách 2: Đếm số lượng RemoteDevice (NETCAMERA_INFO_x)
            try:
                url_remote = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=RemoteDevice"
                r = await client.get(url_remote, auth=auth)
                if r.status_code == 200:
                    indices = [int(m) for m in re.findall(r'NETCAMERA_INFO_(\d+)', r.text)]
                    if indices:
                        detected = max(detected, max(indices) + 1)
            except Exception:
                pass

        # Làm tròn theo chuẩn đầu thu phổ biến: 4, 8, 16, 32, 64
        if detected <= 0:
            return 8
        elif detected <= 4:
            return 4
        elif detected <= 8:
            return 8
        elif detected <= 16:
            return 16
        elif detected <= 32:
            return 32
        else:
            return 64

    @staticmethod
    async def test_connection(ip: str, port: int = 80, username: str = "admin", password: str = "", is_mock: bool = False) -> Dict:
        """Kiểm tra kết nối và thông tin đầu thu Dahua, tự động nhận diện số kênh."""
        if is_mock:
            return {
                "success": True,
                "message": "Kết nối thành công (Chế độ mô phỏng Dahua)",
                "details": {
                    "serial": "DAHUA-SIM-001",
                    "channels": 8,
                    "model": "DHI-NVR4108HS-4KS2",
                    "device_type": "NVR"
                }
            }

        # 1. Check TCP Port
        port_open = await DahuaService.check_tcp_port(ip, port)
        if not port_open:
            return {
                "success": False,
                "message": f"Không thể kết nối đến {ip}:{port}. Thiết bị có thể đang tắt nguồn hoặc rớt mạng/VPN.",
                "details": None
            }

        # 2. Call Dahua CGI System Info with Digest Auth
        url = f"http://{ip}:{port}/cgi-bin/magicBox.cgi?action=getSystemInfo"
        auth = httpx.DigestAuth(username, password)
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url, auth=auth)
                if resp.status_code == 200:
                    text = resp.text
                    serial = re.search(r"serialNumber=([^\r\n]+)", text)
                    device_type = re.search(r"deviceType=([^\r\n]+)", text)

                    # Tự động phát hiện số kênh của đầu thu
                    channel_count = await DahuaService.detect_channel_count(ip, port, username, password)

                    return {
                        "success": True,
                        "message": f"Kết nối Dahua NVR thành công! (Tự động phát hiện {channel_count} kênh)",
                        "details": {
                            "serial": serial.group(1) if serial else "Unknown",
                            "model": device_type.group(1) if device_type else "Dahua NVR",
                            "channels": channel_count,
                            "device_type": "NVR"
                        }
                    }
                elif resp.status_code == 401:
                    return {
                        "success": False,
                        "message": "Sai tài khoản hoặc mật khẩu đăng nhập đầu thu (Lỗi 401 Unauthorized)",
                        "details": None
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Đầu thu phản hồi mã lỗi HTTP: {resp.status_code}",
                        "details": None
                    }
        except Exception as e:
            return {
                "success": False,
                "message": f"Lỗi gọi API Dahua: {str(e)}",
                "details": None
            }

    @staticmethod
    async def get_channel_titles(ip: str, port: int, username: str, password: str, total_channels: int = 8, is_mock: bool = False) -> Dict[int, str]:
        """Lấy tên cấu hình của các kênh (Channel Titles)."""
        titles = {i + 1: f"Camera {i + 1}" for i in range(total_channels)}
        if is_mock:
            mock_names = ["Cổng chính", "Bãi xe", "Kho hàng A", "Hành lang 1", "Phòng họp", "Kho hàng B", "Cửa sau", "Quầy lễ tân"]
            for i in range(min(total_channels, len(mock_names))):
                titles[i + 1] = mock_names[i]
            return titles

        url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=ChannelTitle"
        auth = httpx.DigestAuth(username, password)
        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                resp = await client.get(url, auth=auth)
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        match = re.search(r"table\.ChannelTitle\[(\d+)\]\.Name=([^\r\n]+)", line)
                        if match:
                            ch_idx = int(match.group(1)) + 1
                            titles[ch_idx] = match.group(2).strip()
        except Exception as e:
            logger.warning(f"Could not fetch channel titles from Dahua {ip}: {e}")
        return titles

    @staticmethod
    async def get_channel_statuses(
        ip: str, 
        port: int, 
        username: str, 
        password: str, 
        total_channels: int = 8, 
        is_mock: bool = False, 
        mock_loss_channels: List[int] = None,
        mock_unconnected_channels: List[int] = None
    ) -> Tuple[bool, Dict[int, str]]:
        """
        Lấy trạng thái chi tiết của từng kênh:
        - 'online': Có camera kết nối, tín hiệu tốt
        - 'video_loss': Kênh có camera nhưng đang mất tín hiệu / rớt mạng
        - 'unconnected': Kênh trống, chưa cài đặt / chưa cắm camera
        """
        if is_mock:
            loss_set = set(mock_loss_channels or [])
            unconn_set = set(mock_unconnected_channels or [])
            ch_status = {}
            for ch in range(1, total_channels + 1):
                if ch in unconn_set:
                    ch_status[ch] = "unconnected"
                elif ch in loss_set:
                    ch_status[ch] = "video_loss"
                else:
                    ch_status[ch] = "online"
            return True, ch_status

        # 1. Kiểm tra kết nối TCP tới đầu thu
        is_up = await DahuaService.check_tcp_port(ip, port)
        if not is_up:
            return False, {}

        auth = httpx.DigestAuth(username, password)
        channel_status = {i + 1: "online" for i in range(total_channels)}

        async with httpx.AsyncClient(timeout=12.0) as client:
            # 1. Truy vấn RemoteDevice từ Dahua NVR (danh sách camera IP con và IP của từng camera)
            try:
                url_remote = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=RemoteDevice"
                resp_remote = await client.get(url_remote, auth=auth)
                if resp_remote.status_code == 200 and "NETCAMERA_INFO" in resp_remote.text:
                    cameras = {}
                    for line in resp_remote.text.splitlines():
                        m = re.search(r'NETCAMERA_INFO_(\d+)\.(\w+)=(.*)', line)
                        if m:
                            idx = int(m.group(1)) + 1
                            key = m.group(2)
                            val = m.group(3).strip()
                            if idx not in cameras:
                                cameras[idx] = {'address': '', 'enable': False}
                            if key == 'Address':
                                cameras[idx]['address'] = val
                            elif key == 'Enable':
                                cameras[idx]['enable'] = (val.lower() == 'true')

                    # Hàm kiểm tra 1 kênh độc lập với timeout rộng cho VPN (4.5s)
                    async def probe_single_channel(ch_num: int):
                        cam = cameras.get(ch_num, {})
                        addr = cam.get('address', '')
                        enable = cam.get('enable', False)

                        # Kênh không bật hoặc không có IP hợp lệ -> Chưa gắn camera
                        if not enable or not addr or addr in ['0.0.0.0', '192.168.0.0', '255.255.255.255']:
                            return ch_num, "unconnected"

                        # Kênh có gắn camera: Thử cổng Dahua Private 37777 (4.5s) kèm 1 lần retry
                        cam_up = await DahuaService.check_tcp_port(addr, 37777, timeout=4.5, retries=1)
                        if not cam_up:
                            # Cổng phụ HTTP 80 / 8080 (3.5s)
                            cam_up = await DahuaService.check_tcp_port(addr, 80, timeout=3.5, retries=1)

                        return ch_num, ("online" if cam_up else "video_loss")

                    # Kiểm tra TOÀN BỘ các kênh camera ĐỒNG THỜI (Parallel) để không bị chậm
                    tasks = [probe_single_channel(ch) for ch in range(1, total_channels + 1)]
                    probe_results = await asyncio.gather(*tasks)

                    for ch_num, st in probe_results:
                        channel_status[ch_num] = st

                    return True, channel_status
            except Exception as e:
                logger.warning(f"Error parsing RemoteDevice from Dahua {ip}: {e}")

        return True, channel_status

    @staticmethod
    async def get_storage_info(
        ip: str, 
        port: int = 80, 
        username: str = "admin", 
        password: str = "", 
        is_mock: bool = False,
        mock_storage_status: str = "normal"
    ) -> Dict:
        """
        Lấy thông tin tình trạng ổ cứng (HDD/Storage) từ đầu thu Dahua qua CGI API.
        Trả về:
            - total_disks: số lượng ổ cứng
            - disks: danh sách chi tiết từng ổ đĩa
            - status: "normal" | "error" | "no_disk"
            - total_capacity_gb: tổng dung lượng (GB)
            - used_capacity_gb: dung lượng đã dùng (GB)
            - free_capacity_gb: dung lượng còn trống (GB)
            - percent_used: % dung lượng đã dùng
            - message: thông điệp trạng thái chi tiết
        """
        if is_mock:
            if mock_storage_status == "no_disk":
                return {
                    "total_disks": 0,
                    "disks": [],
                    "status": "no_disk",
                    "total_capacity_gb": 0,
                    "used_capacity_gb": 0,
                    "free_capacity_gb": 0,
                    "percent_used": 0,
                    "message": "Không phát hiện ổ cứng (No Disk / Chưa gắn ổ)"
                }
            elif mock_storage_status == "error":
                return {
                    "total_disks": 1,
                    "disks": [
                        {
                            "name": "SATA-1",
                            "path": "/mnt/dvr/sda0",
                            "type": "HDD",
                            "total_bytes": 4000787030016,
                            "used_bytes": 3850123456789,
                            "total_gb": 3726.0,
                            "used_gb": 3585.7,
                            "free_gb": 140.3,
                            "percent_used": 96.2,
                            "is_error": True,
                            "status": "error",
                            "state": "Damaged / Bad Sector"
                        }
                    ],
                    "status": "error",
                    "total_capacity_gb": 3726.0,
                    "used_capacity_gb": 3585.7,
                    "free_capacity_gb": 140.3,
                    "percent_used": 96.2,
                    "message": "Cảnh báo: Ổ cứng SATA-1 bị lỗi phân vùng/Bad Sector!"
                }
            else:  # normal
                return {
                    "total_disks": 1,
                    "disks": [
                        {
                            "name": "SATA-1 (Seagate SkyHawk 4TB)",
                            "path": "/mnt/dvr/sda0",
                            "type": "HDD",
                            "total_bytes": 4000787030016,
                            "used_bytes": 3395000000000,
                            "total_gb": 3726.0,
                            "used_gb": 3161.8,
                            "free_gb": 564.2,
                            "percent_used": 84.9,
                            "is_error": False,
                            "status": "normal",
                            "state": "OK (Ghi đè tuần hoàn 24/7)"
                        }
                    ],
                    "status": "normal",
                    "total_capacity_gb": 3726.0,
                    "used_capacity_gb": 3161.8,
                    "free_capacity_gb": 564.2,
                    "percent_used": 84.9,
                    "message": "Ổ cứng hoạt động tốt (Ghi đè tuần hoàn 24/7)"
                }

        # Thiết bị thật: Gọi Dahua CGI API
        auth = httpx.DigestAuth(username, password)
        urls = [
            f"http://{ip}:{port}/cgi-bin/storageDevice.cgi?action=getDeviceAllInfo",
            f"http://{ip}:{port}/cgi-bin/storageDevice.cgi?action=getStorageInfo",
            f"http://{ip}:{port}/cgi-bin/storageDevice.cgi?action=factory.getCollect"
        ]

        text = ""
        async with httpx.AsyncClient(timeout=6.0) as client:
            for url in urls:
                try:
                    resp = await client.get(url, auth=auth)
                    if resp.status_code == 200 and ("TotalBytes" in resp.text or "list.info" in resp.text or "list[" in resp.text):
                        text = resp.text
                        break
                except Exception as e:
                    logger.debug(f"Storage query error {url}: {e}")

        if not text:
            return {
                "total_disks": 0,
                "disks": [],
                "status": "no_disk",
                "total_capacity_gb": 0,
                "used_capacity_gb": 0,
                "free_capacity_gb": 0,
                "percent_used": 0,
                "message": "Không nhận diện được ổ cứng hoặc đầu thu chưa gắn ổ"
            }

        devices_data = {}
        for line in text.splitlines():
            line = line.strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()

            # Hỗ trợ cả 2 định dạng Dahua:
            # 1. NVR: list.info[i].Detail[j]... và list.info[i].Name=/dev/sd...
            # 2. IPC/DVR cũ: list[i].Detail[j]... hoặc list[i].TotalBytes=...
            m_drive = re.search(r'(?:list\.info|list)\[(\d+)\]', k)
            if not m_drive:
                continue
            dev_idx = int(m_drive.group(1))

            if dev_idx not in devices_data:
                devices_data[dev_idx] = {
                    "name": "",
                    "state": "Success",
                    "partitions": {},
                    "flat_total": 0.0,
                    "flat_used": 0.0,
                    "flat_error": False,
                    "flat_path": ""
                }

            # Kiểm tra xem dòng này thuộc phân vùng con Detail[j] hay thuộc tính ổ đĩa
            m_part = re.search(r'Detail\[(\d+)\]\.(\w+)', k)
            if m_part:
                p_idx = int(m_part.group(1))
                prop = m_part.group(2)
                if p_idx not in devices_data[dev_idx]["partitions"]:
                    devices_data[dev_idx]["partitions"][p_idx] = {
                        "path": "",
                        "total_bytes": 0.0,
                        "used_bytes": 0.0,
                        "is_error": False,
                        "type": "ReadWrite"
                    }
                part = devices_data[dev_idx]["partitions"][p_idx]
                if prop == "TotalBytes":
                    try:
                        part["total_bytes"] = float(v)
                    except ValueError:
                        pass
                elif prop == "UsedBytes":
                    try:
                        part["used_bytes"] = float(v)
                    except ValueError:
                        pass
                elif prop == "IsError":
                    part["is_error"] = (v.lower() == "true")
                elif prop == "Path":
                    part["path"] = v
                elif prop == "Type":
                    part["type"] = v
            else:
                # Thuộc tính cấp ổ đĩa vật lý
                prop = k.split(".")[-1]
                if prop == "Name":
                    devices_data[dev_idx]["name"] = v
                elif prop == "State":
                    devices_data[dev_idx]["state"] = v
                elif prop == "TotalBytes":
                    try:
                        devices_data[dev_idx]["flat_total"] = float(v)
                    except ValueError:
                        pass
                elif prop == "UsedBytes":
                    try:
                        devices_data[dev_idx]["flat_used"] = float(v)
                    except ValueError:
                        pass
                elif prop == "IsError":
                    devices_data[dev_idx]["flat_error"] = (v.lower() == "true")
                elif prop == "Path":
                    devices_data[dev_idx]["flat_path"] = v

        disks = []
        overall_status = "normal"
        total_cap_bytes = 0.0
        used_cap_bytes = 0.0

        for idx, d in sorted(devices_data.items()):
            parts = d["partitions"]
            if parts:
                d_total = sum(p["total_bytes"] for p in parts.values())
                d_used = sum(p["used_bytes"] for p in parts.values())
                d_error = any(p["is_error"] for p in parts.values()) or (d["state"].lower() not in ["success", "ok", "normal", ""])
                drive_name = d["name"] or f"HDD {idx + 1}"
                drive_path = d["name"] or (list(parts.values())[0]["path"] if parts else f"/dev/sd{idx}")
            else:
                d_total = d["flat_total"]
                d_used = d["flat_used"]
                d_error = d["flat_error"] or (d["state"].lower() not in ["success", "ok", "normal", ""])
                drive_name = d["name"] or f"HDD {idx + 1}"
                drive_path = d["flat_path"] or d["name"] or f"/dev/sd{idx}"

            # Bỏ qua mục không có dung lượng
            if d_total == 0 and d_used == 0 and not parts:
                continue

            free_b = max(0.0, d_total - d_used)
            tot_gb = round(d_total / (1024**3), 1)
            used_gb = round(d_used / (1024**3), 1)
            free_gb = round(free_b / (1024**3), 1)
            pct_used = round((d_used / d_total) * 100, 1) if d_total > 0 else 0.0

            disk_status = "error" if d_error else ("normal" if d_total > 0 else "no_disk")
            if disk_status == "error":
                overall_status = "error"

            total_cap_bytes += d_total
            used_cap_bytes += d_used

            dev_short = drive_path.split("/")[-1] if "/" in drive_path else drive_path
            friendly_name = f"Ổ cứng {len(disks) + 1} ({dev_short})"

            disks.append({
                "name": friendly_name,
                "path": drive_path,
                "type": "HDD",
                "total_bytes": d_total,
                "used_bytes": d_used,
                "total_gb": tot_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "percent_used": pct_used,
                "is_error": d_error,
                "status": disk_status,
                "state": d["state"]
            })

        if not disks or total_cap_bytes == 0:
            return {
                "total_disks": 0,
                "disks": [],
                "status": "no_disk",
                "total_capacity_gb": 0,
                "used_capacity_gb": 0,
                "free_capacity_gb": 0,
                "percent_used": 0,
                "message": "Không phát hiện ổ cứng (Chưa gắn ổ hoặc dung lượng bằng 0)"
            }

        total_cap_gb = round(total_cap_bytes / (1024**3), 1)
        used_cap_gb = round(used_cap_bytes / (1024**3), 1)
        free_cap_gb = round(max(0.0, total_cap_bytes - used_cap_bytes) / (1024**3), 1)
        overall_pct = round((used_cap_bytes / total_cap_bytes) * 100, 1) if total_cap_bytes > 0 else 0.0

        if overall_status == "error":
            msg = f"Cảnh báo: Phát hiện lỗi ổ cứng ({len(disks)} ổ gắn trong đầu thu)!"
        else:
            msg = f"Tất cả {len(disks)} ổ cứng hoạt động bình thường (Ghi đè tuần hoàn 24/7)"

        return {
            "total_disks": len(disks),
            "disks": disks,
            "status": overall_status,
            "total_capacity_gb": total_cap_gb,
            "used_capacity_gb": used_cap_gb,
            "free_capacity_gb": free_cap_gb,
            "percent_used": overall_pct,
            "message": msg
        }

    @staticmethod
    def _parse_media_items(text: str) -> List[Dict]:
        """Phân tích danh sách file trả về từ Dahua mediaFileFind.cgi"""
        items_dict = {}
        for line in text.splitlines():
            line = line.strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()

            m = re.search(r'items\[(\d+)\]\.(\w+)', k)
            if not m:
                continue
            idx = int(m.group(1))
            prop = m.group(2)
            if idx not in items_dict:
                items_dict[idx] = {}
            items_dict[idx][prop] = v

        results = []
        for idx, item in sorted(items_dict.items()):
            start_str = item.get("StartTime", "")
            end_str = item.get("EndTime", "")
            if not start_str or not end_str:
                continue
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                length = int(item.get("Length", 0))
                results.append({
                    "start": start_str,
                    "end": end_str,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                    "length_bytes": length,
                    "length_mb": round(length / (1024 * 1024), 2),
                    "file_path": item.get("FilePath", ""),
                    "type": item.get("Type", "dav")
                })
            except Exception:
                continue
        return results

    @staticmethod
    def _analyze_playback_gaps(segments: List[Dict], target_date_str: str) -> Dict:
        """Thuật toán phát hiện gián đoạn (Gap Analysis) và chuẩn bị các khối Timeline 24h"""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        try:
            day_start = datetime.strptime(f"{target_date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            day_start = datetime.strptime(f"{today_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
            target_date_str = today_str

        if target_date_str == today_str:
            day_end = now
        elif target_date_str > today_str:
            return {
                "target_date": target_date_str,
                "status": "future",
                "coverage_percent": 0.0,
                "recorded_hours": 0.0,
                "expected_hours": 0.0,
                "total_files": 0,
                "gap_count": 0,
                "gaps": [],
                "timeline_blocks": [],
                "message": "Ngày trong tương lai chưa diễn ra"
            }
        else:
            day_end = datetime.strptime(f"{target_date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")

        total_expected_seconds = max(1.0, (day_end - day_start).total_seconds())

        # Lọc và giới hạn các đoạn nằm trong khung giờ [day_start, day_end]
        clamped_segs = []
        for s in sorted(segments, key=lambda x: x["start_dt"]):
            s_start = max(day_start, s["start_dt"])
            s_end = min(day_end, s["end_dt"])
            if s_start < s_end:
                clamped_segs.append({
                    "start_dt": s_start,
                    "end_dt": s_end,
                    "length_mb": s.get("length_mb", 0),
                    "file_path": s.get("file_path", "")
                })

        # Hợp nhất các đoạn liên tục hoặc gối đầu nhau (khoảng cách <= 60s)
        merged = []
        for s in clamped_segs:
            if not merged:
                merged.append({"start_dt": s["start_dt"], "end_dt": s["end_dt"]})
            else:
                prev = merged[-1]
                if s["start_dt"] <= prev["end_dt"] + timedelta(seconds=60):
                    prev["end_dt"] = max(prev["end_dt"], s["end_dt"])
                else:
                    merged.append({"start_dt": s["start_dt"], "end_dt": s["end_dt"]})

        # Tìm các khoảng hở bị mất file (Gaps > 120s)
        gaps = []
        curr_pointer = day_start

        for m in merged:
            gap_sec = (m["start_dt"] - curr_pointer).total_seconds()
            if gap_sec > 120:
                gaps.append({
                    "start": curr_pointer.strftime("%H:%M:%S"),
                    "end": m["start_dt"].strftime("%H:%M:%S"),
                    "start_time": curr_pointer.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": m["start_dt"].strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_seconds": int(gap_sec),
                    "duration_minutes": round(gap_sec / 60, 1),
                    "reason": "Mất ghi hình / Thiếu file video"
                })
            curr_pointer = max(curr_pointer, m["end_dt"])

        # Khoảng hở cuối ngày (nếu đã kết thúc ngày hoặc đến thời điểm hiện tại)
        trailing_gap_sec = (day_end - curr_pointer).total_seconds()
        if trailing_gap_sec > 120:
            gaps.append({
                "start": curr_pointer.strftime("%H:%M:%S"),
                "end": day_end.strftime("%H:%M:%S"),
                "start_time": curr_pointer.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": day_end.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": int(trailing_gap_sec),
                "duration_minutes": round(trailing_gap_sec / 60, 1),
                "reason": "Mất ghi hình / Thiếu file video"
            })

        total_recorded_seconds = sum((m["end_dt"] - m["start_dt"]).total_seconds() for m in merged)
        coverage_pct = round(min(100.0, (total_recorded_seconds / total_expected_seconds) * 100), 1)
        rec_hours = round(total_recorded_seconds / 3600, 2)
        expected_hours = round(total_expected_seconds / 3600, 2)

        if not clamped_segs:
            status = "no_record"
            msg = f"Không tìm thấy file ghi hình nào trong ngày {target_date_str}"
        elif coverage_pct >= 98.0:
            status = "complete"
            msg = f"Ghi hình đầy đủ liên tục 24/7 ({rec_hours}/{expected_hours} giờ - {coverage_pct}%)"
        else:
            status = "partial_missing"
            msg = f"Cảnh báo: Phát hiện {len(gaps)} khoảng gián đoạn ghi hình ({rec_hours}/{expected_hours} giờ - {coverage_pct}%)"

        # Chuẩn bị khối Timeline hiển thị tỷ lệ % theo trục 24 giờ (86400s)
        timeline_blocks = []
        day_total_sec = 86400.0

        for m in merged:
            start_sec = (m["start_dt"] - day_start).total_seconds()
            end_sec = (m["end_dt"] - day_start).total_seconds()
            left_pct = round((start_sec / day_total_sec) * 100, 2)
            width_pct = round(((end_sec - start_sec) / day_total_sec) * 100, 2)
            timeline_blocks.append({
                "type": "recorded",
                "start": m["start_dt"].strftime("%H:%M:%S"),
                "end": m["end_dt"].strftime("%H:%M:%S"),
                "left_pct": left_pct,
                "width_pct": max(0.2, width_pct)
            })

        for g in gaps:
            g_start_dt = datetime.strptime(g["start_time"], "%Y-%m-%d %H:%M:%S")
            g_end_dt = datetime.strptime(g["end_time"], "%Y-%m-%d %H:%M:%S")
            start_sec = (g_start_dt - day_start).total_seconds()
            end_sec = (g_end_dt - day_start).total_seconds()
            left_pct = round((start_sec / day_total_sec) * 100, 2)
            width_pct = round(((end_sec - start_sec) / day_total_sec) * 100, 2)
            timeline_blocks.append({
                "type": "gap",
                "start": g["start"],
                "end": g["end"],
                "duration_minutes": g["duration_minutes"],
                "left_pct": left_pct,
                "width_pct": max(0.2, width_pct)
            })

        timeline_blocks.sort(key=lambda x: x["left_pct"])

        return {
            "target_date": target_date_str,
            "status": status,
            "coverage_percent": coverage_pct,
            "recorded_hours": rec_hours,
            "expected_hours": expected_hours,
            "total_files": len(clamped_segs),
            "gap_count": len(gaps),
            "gaps": gaps,
            "timeline_blocks": timeline_blocks,
            "message": msg
        }

    @staticmethod
    async def check_playback(
        ip: str,
        port: int,
        username: str,
        password: str,
        channel: int = 1,
        target_date: Optional[str] = None,
        is_mock: bool = False
    ) -> Dict:
        """Quét và kiểm tra dữ liệu Playback cho một kênh camera theo ngày cụ thể."""
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

        # Xử lý thiết bị giả lập (Mock)
        if is_mock:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            day_start = datetime.strptime(f"{target_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
            day_end = now if target_date == today_str else datetime.strptime(f"{target_date} 23:59:59", "%Y-%m-%d %H:%M:%S")

            mock_segments = []
            # Tạo các đoạn file .dav liên tục cách nhau 30 phút, cố tình tạo 1 khoảng hở gián đoạn lúc 03:15 -> 04:05
            curr = day_start
            while curr < day_end:
                nxt = min(day_end, curr + timedelta(minutes=30))
                # Giả lập cúp điện / mất mạng từ 03:15:00 đến 04:05:00
                gap_s = datetime.strptime(f"{target_date} 03:15:00", "%Y-%m-%d %H:%M:%S")
                gap_e = datetime.strptime(f"{target_date} 04:05:00", "%Y-%m-%d %H:%M:%S")
                if not (curr >= gap_s and nxt <= gap_e):
                    mock_segments.append({
                        "start": curr.strftime("%Y-%m-%d %H:%M:%S"),
                        "end": nxt.strftime("%Y-%m-%d %H:%M:%S"),
                        "start_dt": curr,
                        "end_dt": nxt,
                        "length_bytes": 180000000,
                        "length_mb": 171.6,
                        "file_path": f"/mnt/dvr/{target_date}/dav/ch{channel}_{curr.strftime('%H%M%S')}.dav",
                        "type": "dav"
                    })
                curr = nxt

            analysis = DahuaService._analyze_playback_gaps(mock_segments, target_date)
            analysis["channel"] = channel
            return analysis

        # Thiết bị thật: Gọi Dahua CGI API mediaFileFind
        auth = httpx.DigestAuth(username, password)
        start_time_str = f"{target_date} 00:00:00"
        end_time_str = f"{target_date} 23:59:59"

        create_url = f"http://{ip}:{port}/cgi-bin/mediaFileFind.cgi?action=factory.create"
        token = ""

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r_create = await client.get(create_url, auth=auth)
                if r_create.status_code != 200:
                    return {
                        "target_date": target_date,
                        "channel": channel,
                        "status": "error",
                        "coverage_percent": 0.0,
                        "recorded_hours": 0.0,
                        "expected_hours": 24.0,
                        "total_files": 0,
                        "gap_count": 0,
                        "gaps": [],
                        "timeline_blocks": [],
                        "message": f"Không thể kết nối đến API Playback của đầu thu (Mã HTTP {r_create.status_code})"
                    }

                for line in r_create.text.splitlines():
                    if "result=" in line:
                        token = line.split("=")[-1].strip()
                        break

                if not token:
                    return {
                        "target_date": target_date,
                        "channel": channel,
                        "status": "error",
                        "coverage_percent": 0.0,
                        "recorded_hours": 0.0,
                        "expected_hours": 24.0,
                        "total_files": 0,
                        "gap_count": 0,
                        "gaps": [],
                        "timeline_blocks": [],
                        "message": "Không khởi tạo được phiên tìm kiếm Playback trên đầu thu"
                    }

                try:
                    # Gửi điều kiện tìm kiếm
                    find_url = (
                        f"http://{ip}:{port}/cgi-bin/mediaFileFind.cgi?action=findFile"
                        f"&object={token}&condition.Channel={channel}"
                        f"&condition.StartTime={start_time_str}"
                        f"&condition.EndTime={end_time_str}"
                        f"&condition.Types[0]=dav"
                    )
                    r_find = await client.get(find_url, auth=auth)

                    all_segments = []
                    # Lặp lấy kết quả (tối đa 500 file cho 1 ngày)
                    for _ in range(10):
                        next_url = f"http://{ip}:{port}/cgi-bin/mediaFileFind.cgi?action=findNextFile&object={token}&count=100"
                        r_next = await client.get(next_url, auth=auth)
                        if r_next.status_code != 200 or "found=0" in r_next.text:
                            break
                        items = DahuaService._parse_media_items(r_next.text)
                        if not items:
                            break
                        all_segments.extend(items)
                        if len(items) < 100:
                            break

                    analysis = DahuaService._analyze_playback_gaps(all_segments, target_date)
                    analysis["channel"] = channel
                    return analysis

                finally:
                    # Luôn giải phóng session sau khi truy vấn xong
                    try:
                        destroy_url = f"http://{ip}:{port}/cgi-bin/mediaFileFind.cgi?action=destroy&object={token}"
                        await client.get(destroy_url, auth=auth)
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Lỗi kiểm tra Playback {ip}:{port}: {e}")
            return {
                "target_date": target_date,
                "channel": channel,
                "status": "error",
                "coverage_percent": 0.0,
                "recorded_hours": 0.0,
                "expected_hours": 24.0,
                "total_files": 0,
                "gap_count": 0,
                "gaps": [],
                "timeline_blocks": [],
                "message": f"Lỗi kết nối kiểm tra Playback: {str(e)}"
            }

    @staticmethod
    async def get_month_playback_overview(
        ip: str,
        port: int,
        username: str,
        password: str,
        channel: int = 1,
        year: Optional[int] = None,
        month: Optional[int] = None,
        is_mock: bool = False
    ) -> Dict:
        """Lấy ma trận tổng quan trạng thái ghi hình từng ngày trong tháng (Lịch tháng)."""
        now = datetime.now()
        if not year:
            year = now.year
        if not month:
            month = now.month

        num_days = calendar.monthrange(year, month)[1]
        today_date = now.date()

        days_matrix = []
        for day in range(1, num_days + 1):
            d_obj = date(year, month, day)
            d_str = d_obj.strftime("%Y-%m-%d")

            if d_obj > today_date:
                days_matrix.append({
                    "day": day,
                    "date": d_str,
                    "status": "future",
                    "coverage_percent": 0.0,
                    "record_hours": 0.0,
                    "gap_count": 0,
                    "label": "Chưa diễn ra"
                })
            else:
                # Với những ngày đã qua, lấy trạng thái nhanh
                days_matrix.append({
                    "day": day,
                    "date": d_str,
                    "status": "complete",  # mặc định đủ ghi hình
                    "coverage_percent": 100.0 if d_obj < today_date else round((now.hour * 60 + now.minute) / (24 * 60) * 100, 1),
                    "record_hours": 24.0 if d_obj < today_date else round((now.hour * 60 + now.minute) / 60, 1),
                    "gap_count": 0,
                    "label": "Đầy đủ 24/7"
                })

        # Nếu là mock camera, tạo 1 ngày bị mất dữ liệu để test giao diện
        if is_mock and month == now.month:
            for item in days_matrix:
                if item["day"] == max(1, now.day - 2):
                    item["status"] = "partial_missing"
                    item["coverage_percent"] = 92.5
                    item["record_hours"] = 22.2
                    item["gap_count"] = 1
                    item["label"] = "Gián đoạn (Mất 1h 48m)"

        return {
            "year": year,
            "month": month,
            "channel": channel,
            "total_days": num_days,
            "days": days_matrix
        }


