import asyncio
import socket
import httpx
import re
import logging
from typing import Dict, List, Optional, Tuple

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
