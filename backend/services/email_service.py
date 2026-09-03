import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
import logging
from database import get_db

logger = logging.getLogger("camera_manager.email")

class EmailService:
    @staticmethod
    async def get_email_config():
        """Lấy cấu hình email cảnh báo từ MongoDB."""
        db = get_db()
        if db is None:
            return None
        config = await db.settings.find_one({"_id": "email_config"})
        return config

    @staticmethod
    async def save_email_config(config_data: dict):
        """Lưu cấu hình email cảnh báo vào MongoDB."""
        db = get_db()
        await db.settings.update_one(
            {"_id": "email_config"},
            {"$set": config_data},
            upsert=True
        )
        return True

    @staticmethod
    async def send_alert(subject: str, html_content: str) -> dict:
        """Gửi email cảnh báo tới danh sách email đã cấu hình."""
        config = await EmailService.get_email_config()
        if not config or not config.get("enabled", False):
            logger.info("Email alert is disabled or not configured.")
            return {"success": False, "message": "Chức năng gửi email chưa bật hoặc chưa cấu hình"}

        smtp_host = config.get("smtp_host", "").strip()
        smtp_port = int(config.get("smtp_port", 587))
        smtp_user = config.get("smtp_user", "").strip()
        smtp_password = config.get("smtp_password", "").strip()
        sender = config.get("sender_email", smtp_user).strip()
        recipients_str = config.get("recipient_emails", "").strip()
        use_tls = config.get("use_tls", True)

        if not smtp_host or not smtp_user or not recipients_str:
            return {"success": False, "message": "Thiếu thông tin SMTP Host, User hoặc danh sách người nhận"}

        recipients = [r.strip() for r in recipients_str.replace(";", ",").split(",") if r.strip()]
        if not recipients:
            return {"success": False, "message": "Danh sách email nhận rỗng"}

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Hệ Thống Camera Dahua <{sender}>"
        msg["To"] = ", ".join(recipients)

        part = MIMEText(html_content, "html", "utf-8")
        msg.attach(part)

        try:
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                if use_tls:
                    server.starttls()

            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.sendmail(sender, recipients, msg.as_string())
            server.quit()
            logger.info(f"Sent email alert '{subject}' to {len(recipients)} recipient(s).")
            return {"success": True, "message": f"Đã gửi email thành công tới {len(recipients)} người nhận!"}
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return {"success": False, "message": f"Lỗi gửi email: {str(e)}"}

    @staticmethod
    def build_incident_html(device_name: str, channel_name: str, event_type: str, time_str: str, note: str) -> str:
        """Tạo giao diện email thông báo sự cố HTML chuyên nghiệp."""
        is_loss = event_type in ["video_loss", "offline"]
        header_color = "#ef4444" if is_loss else "#10b981"
        header_title = "CẢNH BÁO MẤT TÍN HIỆU CAMERA" if is_loss else "THÔNG BÁO PHỤC HỒI TÍN HIỆU"
        badge_text = "MẤT TÍN HIỆU" if is_loss else "ĐÃ HOẠT ĐỘNG TRỞ LẠI"
        icon = "🚨" if is_loss else "✅"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 24px; }}
                .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }}
                .header {{ background-color: {header_color}; color: #ffffff; padding: 24px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 20px; letter-spacing: 0.5px; }}
                .content {{ padding: 24px; color: #374151; }}
                .status-box {{ background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 16px 0; }}
                .row {{ display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px; }}
                .row:last-child {{ margin-bottom: 0; }}
                .label {{ color: #6b7280; font-weight: 500; }}
                .value {{ color: #111827; font-weight: 600; text-align: right; }}
                .footer {{ text-align: center; padding: 16px; font-size: 12px; color: #9ca3af; border-top: 1px solid #e5e7eb; background: #fafafa; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="header">
                    <h1>{icon} {header_title}</h1>
                </div>
                <div class="content">
                    <p style="font-size: 15px; margin-top: 0;">
                        Hệ thống giám sát phát hiện sự thay đổi trạng thái tín hiệu thiết bị:
                    </p>
                    <div class="status-box">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr style="border-bottom: 1px solid #f3f4f6;">
                                <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Thiết bị / Đầu thu:</td>
                                <td style="padding: 8px 0; color: #111827; font-weight: bold; text-align: right; font-size: 14px;">{device_name}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #f3f4f6;">
                                <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Đối tượng:</td>
                                <td style="padding: 8px 0; color: #111827; font-weight: bold; text-align: right; font-size: 14px;">{channel_name}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #f3f4f6;">
                                <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Trạng thái:</td>
                                <td style="padding: 8px 0; color: {header_color}; font-weight: bold; text-align: right; font-size: 14px;">{badge_text}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #f3f4f6;">
                                <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Thời điểm ghi nhận:</td>
                                <td style="padding: 8px 0; color: #111827; text-align: right; font-size: 14px;">{time_str}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Chi tiết:</td>
                                <td style="padding: 8px 0; color: #4b5563; text-align: right; font-size: 13px;">{note}</td>
                            </tr>
                        </table>
                    </div>
                    <p style="font-size: 13px; color: #6b7280; margin-bottom: 0;">
                        Vui lòng kiểm tra cáp mạng, nguồn điện camera hoặc kết nối switch nội bộ / VPN.
                    </p>
                </div>
                <div class="footer">
                    Email tự động từ Hệ thống Quản lý & Giám sát Camera Dahua
                </div>
            </div>
        </body>
        </html>
        """
