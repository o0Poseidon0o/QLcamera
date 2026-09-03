import React, { useState, useEffect } from 'react';
import { 
  Camera, 
  Server, 
  Wifi, 
  AlertTriangle, 
  CheckCircle2, 
  RefreshCw, 
  Plus, 
  FileSpreadsheet, 
  Clock, 
  ShieldAlert, 
  Activity, 
  Globe, 
  Edit3, 
  Trash2, 
  Power, 
  Sliders, 
  X,
  Mail,
  Send,
  Save,
  Check,
  Download,
  Database,
  Calendar,
  Search,
  Wrench,
  FileEdit
} from 'lucide-react';

const API_BASE = '/api';

// Helper định dạng ngày giờ chuẩn Việt Nam (UTC+7, bắt buộc DD/MM/YYYY)
const formatDateTimeVN = (dateInput, includeSeconds = true) => {
  if (!dateInput) return '-';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return '-';

  const formatter = new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: includeSeconds ? '2-digit' : undefined,
    hour12: false
  });

  const parts = formatter.formatToParts(d);
  const map = {};
  parts.forEach(p => (map[p.type] = p.value));

  const timePart = includeSeconds 
    ? `${map.hour || '00'}:${map.minute || '00'}:${map.second || '00'}`
    : `${map.hour || '00'}:${map.minute || '00'}`;

  return `${map.day}/${map.month}/${map.year} ${timePart}`;
};

const formatDateOnlyVN = (dateInput) => {
  if (!dateInput) return '-';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return '-';
  const formatter = new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
  const parts = formatter.formatToParts(d);
  const map = {};
  parts.forEach(p => (map[p.type] = p.value));
  return `${map.day}/${map.month}/${map.year}`;
};

const formatDurationVN = (seconds, startTime) => {
  if (seconds !== null && seconds !== undefined) {
    const m = Math.round(seconds / 60);
    if (m < 60) return `${m} phút`;
    const h = Math.floor(m / 60);
    const remM = m % 60;
    return `${h} giờ ${remM} phút`;
  }
  if (startTime) {
    const diffSec = Math.max(0, Math.floor((Date.now() - new Date(startTime).getTime()) / 1000));
    const m = Math.round(diffSec / 60);
    if (m < 60) return `Đang tiếp diễn (${m} phút)`;
    const h = Math.floor(m / 60);
    const remM = m % 60;
    return `Đang tiếp diễn (${h}h ${remM}p)`;
  }
  return 'Đang tiếp diễn';
};

export default function App() {
  const [activeTab, setActiveTab] = useState('monitor'); // 'monitor' | 'reports' | 'events'
  const [devices, setDevices] = useState([]);
  const [channels, setChannels] = useState([]);
  const [events, setEvents] = useState([]);
  const [monthlyReport, setMonthlyReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [lastScanTime, setLastScanTime] = useState(new Date());
  const [locationFilter, setLocationFilter] = useState('all'); // 'all' | 'lan' | 'vpn' | 'issues'

  // Event tab filter & search
  const [eventFilterStatus, setEventFilterStatus] = useState('all'); // 'all' | 'unresolved' | 'resolved'
  const [eventSearchText, setEventSearchText] = useState('');
  const [editingEvent, setEditingEvent] = useState(null); // Sự cố đang được cập nhật tiến độ / ghi chú
  const [noteText, setNoteText] = useState('');
  const [noteSaving, setNoteSaving] = useState(false);

  // Report filters
  const [reportYear, setReportYear] = useState(new Date().getFullYear());
  const [reportMonth, setReportMonth] = useState(new Date().getMonth() + 1);

  // Add / Edit Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingDevice, setEditingDevice] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    ip: '',
    port: 80,
    username: 'admin',
    password: '',
    location: 'Nội bộ (LAN)',
    channel_count: 8,
    is_mock: true
  });
  const [testResult, setTestResult] = useState(null);
  const [testingConnection, setTestingConnection] = useState(false);

  const [emailConfig, setEmailConfig] = useState({
    enabled: false,
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_user: '',
    smtp_password: '',
    sender_email: '',
    recipient_emails: '',
    use_tls: true
  });
  const [emailSaveStatus, setEmailSaveStatus] = useState(null);
  const [emailTesting, setEmailTesting] = useState(false);
  const [emailTestResult, setEmailTestResult] = useState(null);

  // Fetch email config
  const fetchEmailConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/settings/email`);
      const data = await res.json();
      if (data) setEmailConfig(data);
    } catch (err) {
      console.error('Failed to load email settings:', err);
    }
  };

  // Fetch all initial data
  const fetchData = async () => {
    try {
      setLoading(true);
      const [devRes, chRes, evRes] = await Promise.all([
        fetch(`${API_BASE}/devices`),
        fetch(`${API_BASE}/channels`),
        fetch(`${API_BASE}/events?limit=100`)
      ]);
      const devData = await devRes.json();
      const chData = await chRes.json();
      const evData = await evRes.json();

      setDevices(devData);
      setChannels(chData);
      setEvents(evData);
      setLastScanTime(new Date());
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch monthly report
  const fetchReport = async () => {
    try {
      const res = await fetch(`${API_BASE}/reports/monthly?year=${reportYear}&month=${reportMonth}`);
      const data = await res.json();
      setMonthlyReport(data);
    } catch (err) {
      console.error('Failed to load report:', err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Polling every 30s
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 'reports') {
      fetchReport();
      fetchRetentionStats();
    }
    if (activeTab === 'email') {
      fetchEmailConfig();
    }
  }, [activeTab, reportYear, reportMonth]);

  // Scan Now trigger
  const handleScanNow = async () => {
    try {
      setScanning(true);
      await fetch(`${API_BASE}/monitor/scan-now`, { method: 'POST' });
      await fetchData();
      if (activeTab === 'reports') {
        await fetchReport();
      }
    } catch (err) {
      console.error('Scan error:', err);
    } finally {
      setScanning(false);
    }
  };

  // Quick toggle simulation for test loss
  const handleToggleSimulation = async (channelId) => {
    try {
      await fetch(`${API_BASE}/channels/${channelId}/toggle-simulation`, { method: 'POST' });
      await fetchData();
      if (activeTab === 'reports') {
        await fetchReport();
      }
    } catch (err) {
      console.error('Toggle sim error:', err);
    }
  };

  // Toggle enable/disable tracking for a channel slot
  const handleToggleEnable = async (channelId) => {
    try {
      await fetch(`${API_BASE}/channels/${channelId}/toggle-enable`, { method: 'POST' });
      await fetchData();
    } catch (err) {
      console.error('Toggle enable error:', err);
    }
  };

  // Toggle maintenance mode for a channel
  const handleToggleMaintenance = async (channelId, channelName) => {
    try {
      const res = await fetch(`${API_BASE}/channels/${channelId}/toggle-maintenance`, { method: 'POST' });
      const data = await res.json();
      alert(data.message || `Đã cập nhật trạng thái bảo trì cho ${channelName}`);
      await fetchData();
    } catch (err) {
      alert(`Lỗi khi chuyển trạng thái bảo trì: ${err.message}`);
    }
  };

  // Toggle maintenance mode for a device (NVR)
  const handleToggleDeviceMaintenance = async (deviceId, deviceName) => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/toggle-maintenance`, { method: 'POST' });
      const data = await res.json();
      alert(data.message || `Đã cập nhật trạng thái bảo trì cho đầu thu ${deviceName}`);
      await fetchData();
    } catch (err) {
      alert(`Lỗi khi chuyển trạng thái bảo trì đầu thu: ${err.message}`);
    }
  };

  // Open note edit modal
  const openNoteModal = (eventItem) => {
    setEditingEvent(eventItem);
    setNoteText(eventItem.note || '');
  };

  // Save event note (lý do / tiến độ khắc phục)
  const handleSaveEventNote = async (e) => {
    e.preventDefault();
    if (!editingEvent) return;
    try {
      setNoteSaving(true);
      const res = await fetch(`${API_BASE}/events/${editingEvent.id}/note`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: noteText })
      });
      if (res.ok) {
        setEditingEvent(null);
        await fetchData();
      } else {
        alert('Không thể lưu ghi chú sự cố');
      }
    } catch (err) {
      alert(`Lỗi lưu ghi chú: ${err.message}`);
    } finally {
      setNoteSaving(false);
    }
  };

  // Resync channels directly from real Dahua NVR
  const handleSyncChannels = async (deviceId, devName) => {
    try {
      setScanning(true);
      const res = await fetch(`${API_BASE}/devices/${deviceId}/sync-channels`, { method: 'POST' });
      const data = await res.json();
      alert(data.message || `Đã đồng bộ lại kênh từ đầu thu ${devName}`);
      await fetchData();
    } catch (err) {
      alert(`Lỗi đồng bộ: ${err.message}`);
    } finally {
      setScanning(false);
    }
  };

  // Delete device
  const handleDeleteDevice = async (id, name) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa đầu thu "${name}" không?`)) return;
    try {
      await fetch(`${API_BASE}/devices/${id}`, { method: 'DELETE' });
      await fetchData();
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  // Open Add/Edit Modal
  const openModal = (device = null) => {
    setTestResult(null);
    if (device) {
      setEditingDevice(device);
      setFormData({
        name: device.name,
        ip: device.ip,
        port: device.port || 80,
        username: device.username || 'admin',
        password: device.password || '',
        location: device.location || 'Nội bộ (LAN)',
        channel_count: device.channel_count || 8,
        is_mock: device.is_mock || false
      });
    } else {
      setEditingDevice(null);
      setFormData({
        name: '',
        ip: '',
        port: 80,
        username: 'admin',
        password: '',
        location: 'Nội bộ (LAN)',
        channel_count: 8,
        is_mock: false
      });
    }
    setIsModalOpen(true);
  };

  // Test Dahua Connection
  const handleTestConnection = async () => {
    try {
      setTestingConnection(true);
      setTestResult(null);
      const res = await fetch(`${API_BASE}/devices/test-connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ip: formData.ip,
          port: Number(formData.port),
          username: formData.username,
          password: formData.password,
          is_mock: formData.is_mock
        })
      });
      const data = await res.json();
      setTestResult(data);

      // Tự động gán số kênh phát hiện được từ đầu thu
      if (data.success && data.details && data.details.channels) {
        setFormData(prev => ({ ...prev, channel_count: data.details.channels }));
      }
    } catch (err) {
      setTestResult({ success: false, message: 'Lỗi mạng khi kiểm tra kết nối' });
    } finally {
      setTestingConnection(false);
    }
  };

  // Lưu cấu hình Email
  const handleSaveEmailConfig = async (e) => {
    e.preventDefault();
    try {
      setEmailSaveStatus('saving');
      const res = await fetch(`${API_BASE}/settings/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(emailConfig)
      });
      const data = await res.json();
      setEmailSaveStatus('success');
      setTimeout(() => setEmailSaveStatus(null), 3000);
    } catch (err) {
      setEmailSaveStatus('error');
    }
  };

  // Gửi thử email cảnh báo
  const handleTestEmailAlert = async () => {
    try {
      setEmailTesting(true);
      setEmailTestResult(null);
      const res = await fetch(`${API_BASE}/settings/email/test`, { method: 'POST' });
      const data = await res.json();
      setEmailTestResult(data);
    } catch (err) {
      setEmailTestResult({ success: false, message: 'Lỗi khi gửi email thử nghiệm: ' + err.message });
    } finally {
      setEmailTesting(false);
    }
  };

  // Submit Device Form
  const handleSubmitDevice = async (e) => {
    e.preventDefault();
    try {
      if (editingDevice) {
        await fetch(`${API_BASE}/devices/${editingDevice.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData)
        });
      } else {
        await fetch(`${API_BASE}/devices`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData)
        });
      }
      setIsModalOpen(false);
      await fetchData();
    } catch (err) {
      console.error('Save error:', err);
    }
  };

  const [reporterName, setReporterName] = useState('');
  const [retentionStats, setRetentionStats] = useState([]);
  const [cleaningStatus, setCleaningStatus] = useState(null);

  const fetchRetentionStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/data/retention-stats`);
      const data = await res.json();
      setRetentionStats(data);
    } catch (err) {
      console.error('Failed to fetch retention stats:', err);
    }
  };

  // Download Excel Report (SLA & Downtime tổng quan)
  const handleDownloadExcel = () => {
    window.open(`${API_BASE}/reports/export-excel?year=${reportYear}&month=${reportMonth}`, '_blank');
  };

  // Download Biểu Mẫu Hải Quan (31 Ngày theo đúng mẫu chuẩn)
  const handleDownloadHaiQuanExcel = (year = reportYear, month = reportMonth) => {
    const rep = encodeURIComponent(reporterName.trim());
    window.open(`${API_BASE}/reports/export-haiquan-excel?year=${year}&month=${month}&reporter=${rep}`, '_blank');
  };

  // Xóa dữ liệu sự cố của 1 tháng sau khi chốt sổ
  const handleDeleteMonthData = async (year, month) => {
    const confirmMsg = `XÁC NHẬN CHỐT SỔ & GIẢI PHÓNG BỘ NHỚ:\n\nBạn có chắc chắn muốn xóa toàn bộ lịch sử sự cố của Tháng ${month}/${year}?\n\n(Hãy đảm bảo bạn đã tải file Excel báo cáo Hải Quan về máy lưu trữ trước khi xóa)`;
    if (!window.confirm(confirmMsg)) return;

    try {
      setCleaningStatus(`deleting-${year}-${month}`);
      const res = await fetch(`${API_BASE}/data/cleanup-month?year=${year}&month=${month}`, { method: 'DELETE' });
      const data = await res.json();
      alert(data.message || 'Đã xóa dữ liệu thành công!');
      await fetchRetentionStats();
      if (activeTab === 'reports') await fetchReport();
      await fetchData();
    } catch (err) {
      alert('Lỗi khi xóa dữ liệu: ' + err.message);
    } finally {
      setCleaningStatus(null);
    }
  };

  // KPI calculations
  const onlineDevicesCount = devices.filter(d => d.status === 'online').length;
  const totalChannelsCount = channels.length;
  const unconnectedCount = channels.filter(c => c.status === 'unconnected' || c.status === 'disabled' || c.enabled === false).length;
  const configuredCount = totalChannelsCount - unconnectedCount;
  const lossChannelsCount = channels.filter(c => c.status === 'video_loss' && c.enabled !== false).length;
  const onlineChannelsCount = channels.filter(c => c.status === 'online').length;
  const vpnDevices = devices.filter(d => d.location && d.location.toLowerCase().includes('vpn'));

  // Filtering devices
  const filteredDevices = devices.filter(d => {
    if (locationFilter === 'lan') return !d.location || !d.location.toLowerCase().includes('vpn');
    if (locationFilter === 'vpn') return d.location && d.location.toLowerCase().includes('vpn');
    if (locationFilter === 'issues') {
      const hasDeviceLoss = d.status === 'offline';
      const hasChannelLoss = channels.some(c => c.device_id === d.id && c.status === 'video_loss');
      return hasDeviceLoss || hasChannelLoss;
    }
    return true;
  });

  // Event filtering & counters
  const unresolvedEventsCount = events.filter(e => !e.resolved_at).length;
  const resolvedEventsCount = events.filter(e => !!e.resolved_at).length;

  const filteredEvents = events.filter(ev => {
    if (eventFilterStatus === 'unresolved' && ev.resolved_at) return false;
    if (eventFilterStatus === 'resolved' && !ev.resolved_at) return false;
    if (eventSearchText.trim()) {
      const q = eventSearchText.toLowerCase();
      const targetMatch = (ev.target_name || '').toLowerCase().includes(q);
      const noteMatch = (ev.note || '').toLowerCase().includes(q);
      const eventTypeMatch = (ev.event || '').toLowerCase().includes(q);
      if (!targetMatch && !noteMatch && !eventTypeMatch) return false;
    }
    return true;
  });

  return (
    <div className="app-container">
      {/* HEADER */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-logo">
            <Camera size={26} color="#ffffff" />
          </div>
          <div className="brand-title">
            <h1>
              Quản Lý Đầu Thu & Camera Dahua
              <span className="badge-vpn"><Globe size={11} style={{ display: 'inline', marginRight: 4 }} />Hỗ trợ VPN Tỉnh</span>
            </h1>
            <p>Hệ thống giám sát mất tín hiệu, tính tỷ lệ sẵn sàng SLA & lập báo cáo tháng</p>
          </div>
        </div>

        <div className="header-actions">
          <button 
            className="btn btn-secondary" 
            onClick={handleScanNow}
            disabled={scanning}
          >
            <RefreshCw size={16} className={scanning ? 'spin' : ''} />
            {scanning ? 'Đang Quét...' : 'Quét Ngay'}
          </button>
          
          <button className="btn btn-primary" onClick={() => openModal()}>
            <Plus size={16} />
            Thêm Đầu Thu
          </button>
        </div>
      </header>

      {/* KPI STATS OVERVIEW */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Đầu Thu (NVR / DVR)</span>
            <div className="kpi-icon" style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa' }}>
              <Server size={18} />
            </div>
          </div>
          <div className="kpi-value">
            {onlineDevicesCount} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>/ {devices.length}</span>
          </div>
          <div className="kpi-subtext">
            {devices.length - onlineDevicesCount > 0 ? (
              <span style={{ color: '#f87171' }}>⚠️ {devices.length - onlineDevicesCount} đầu thu rớt mạng</span>
            ) : (
              <span style={{ color: '#34d399' }}>✓ Tất cả đầu thu đang hoạt động tốt</span>
            )}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Mắt Camera Con</span>
            <div className="kpi-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' }}>
              <Camera size={18} />
            </div>
          </div>
          <div className="kpi-value">
            {onlineChannelsCount} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>/ {configuredCount > 0 ? configuredCount : totalChannelsCount} có gắn cam</span>
          </div>
          <div className="kpi-subtext">
            {lossChannelsCount > 0 ? (
              <span style={{ color: '#f87171', fontWeight: 600 }}>⚠️ {lossChannelsCount} camera mất tín hiệu (Video Loss)</span>
            ) : (
              <span style={{ color: '#34d399' }}>✓ Hoạt động tốt {unconnectedCount > 0 ? `(${unconnectedCount} kênh trống)` : ''}</span>
            )}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Đầu Thu Tỉnh (VPN)</span>
            <div className="kpi-icon" style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#c4b5fd' }}>
              <Globe size={18} />
            </div>
          </div>
          <div className="kpi-value">
            {vpnDevices.filter(d => d.status === 'online').length} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>/ {vpnDevices.length}</span>
          </div>
          <div className="kpi-subtext">
            Kết nối Site-to-Site VPN an toàn, tối ưu băng thông
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">Tỷ Lệ SLA Tháng Này</span>
            <div className="kpi-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>
              <Activity size={18} />
            </div>
          </div>
          <div className="kpi-value">
            {monthlyReport ? `${monthlyReport.avg_uptime_percent}%` : '99.8%'}
          </div>
          <div className="kpi-subtext">
            Tháng {reportMonth}/{reportYear} (Mục tiêu SLA &ge; 99.0%)
          </div>
        </div>
      </div>

      {/* TABS NAVIGATION */}
      <div className="tabs-nav">
        <button 
          className={`tab-btn ${activeTab === 'monitor' ? 'active' : ''}`}
          onClick={() => setActiveTab('monitor')}
        >
          <Activity size={17} />
          Giám Sát Trực Quan
        </button>

        <button 
          className={`tab-btn ${activeTab === 'reports' ? 'active' : ''}`}
          onClick={() => setActiveTab('reports')}
        >
          <FileSpreadsheet size={17} />
          Báo Cáo Hoạt Động Tháng (Excel)
        </button>

        <button 
          className={`tab-btn ${activeTab === 'events' ? 'active' : ''}`}
          onClick={() => setActiveTab('events')}
        >
          <ShieldAlert size={17} />
          Nhật Ký Sự Cố ({events.length})
        </button>

        <button 
          className={`tab-btn ${activeTab === 'email' ? 'active' : ''}`}
          onClick={() => setActiveTab('email')}
        >
          <Mail size={17} />
          Cảnh Báo Email {emailConfig.enabled && <span style={{ width: 7, height: 7, background: '#10b981', borderRadius: '50%', display: 'inline-block', marginLeft: 4 }} />}
        </button>
      </div>

      {/* TAB 1: MONITOR */}
      {activeTab === 'monitor' && (
        <div className="devices-container">
          {/* Filter Bar */}
          <div className="filter-bar">
            <div className="filter-group">
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginRight: 6 }}>Phân loại:</span>
              <button 
                className={`filter-chip ${locationFilter === 'all' ? 'active' : ''}`}
                onClick={() => setLocationFilter('all')}
              >
                Tất cả ({devices.length})
              </button>
              <button 
                className={`filter-chip ${locationFilter === 'lan' ? 'active' : ''}`}
                onClick={() => setLocationFilter('lan')}
              >
                Nội bộ LAN ({devices.length - vpnDevices.length})
              </button>
              <button 
                className={`filter-chip ${locationFilter === 'vpn' ? 'active' : ''}`}
                onClick={() => setLocationFilter('vpn')}
              >
                Chi nhánh Tỉnh VPN ({vpnDevices.length})
              </button>
              <button 
                className={`filter-chip ${locationFilter === 'issues' ? 'active' : ''}`}
                onClick={() => setLocationFilter('issues')}
                style={{ borderColor: lossChannelsCount > 0 ? 'rgba(239, 68, 68, 0.4)' : '' }}
              >
                ⚠️ Chỉ thiết bị có lỗi ({lossChannelsCount > 0 ? 'Có cảnh báo' : '0'})
              </button>
            </div>

            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Tự động cập nhật mỗi 30s • Quét lúc: <span style={{ color: '#38bdf8', fontWeight: 600 }}>{formatDateTimeVN(lastScanTime)}</span> (Giờ VN +7)
            </div>
          </div>

          {/* List NVR Cards */}
          {filteredDevices.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-secondary)' }}>
              Không tìm thấy đầu thu nào phù hợp với bộ lọc hiện tại.
            </div>
          ) : (
            filteredDevices.map(dev => {
              const devChannels = channels.filter(c => c.device_id === dev.id);
              const devLossCount = devChannels.filter(c => c.status === 'video_loss').length;
              const isOffline = dev.status === 'offline';

              return (
                <div key={dev.id} className={`nvr-card ${isOffline ? 'offline-device' : dev.status === 'maintenance' ? 'maintenance-device' : ''}`}>
                  {/* NVR Header */}
                  <div className="nvr-card-header">
                    <div className="nvr-info-main">
                      <span className={`status-dot ${dev.status}`} />
                      <div className="nvr-titles">
                        <h2>{dev.name}</h2>
                        <div className="nvr-meta">
                          <span className="nvr-ip">{dev.ip}:{dev.port || 80}</span>
                          <span>•</span>
                          <span>{dev.location}</span>
                          <span>•</span>
                          <span>{dev.channel_count} Kênh</span>
                          {dev.last_check && (
                            <>
                              <span>•</span>
                              <span title="Thời điểm quét gần nhất" style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                                <Clock size={11} style={{ display: 'inline', marginRight: 3 }} />
                                {formatDateTimeVN(dev.last_check)}
                              </span>
                            </>
                          )}
                          {dev.is_mock && (
                            <span style={{ color: '#f59e0b', fontSize: '0.75rem', border: '1px dashed #f59e0b', padding: '1px 6px', borderRadius: 4 }}>
                              Chế độ Demo/Mock
                            </span>
                          )}
                          {dev.status === 'maintenance' && (
                            <span style={{ color: '#fbbf24', fontSize: '0.75rem', background: 'rgba(245,158,11,0.15)', border: '1px solid #f59e0b', padding: '1px 7px', borderRadius: 4, fontWeight: 600 }}>
                              🔧 Đang Bảo Trì Đầu Thu
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="nvr-actions">
                      {devLossCount > 0 && (
                        <span style={{ color: '#f87171', fontSize: '0.82rem', fontWeight: 600, marginRight: 8 }}>
                          ⚠️ {devLossCount} Camera mất tín hiệu
                        </span>
                      )}

                      {/* Nút Bảo Trì cho cả Đầu thu NVR */}
                      <button 
                        className={`btn-maint ${dev.status === 'maintenance' ? 'active' : ''}`}
                        onClick={() => handleToggleDeviceMaintenance(dev.id, dev.name)}
                        title={dev.status === 'maintenance' ? "Kết thúc bảo trì đầu thu, tiếp tục giám sát" : "Chuyển toàn bộ đầu thu sang Chế độ Bảo trì (tạm ngưng tính SLA)"}
                      >
                        <Wrench size={13} /> {dev.status === 'maintenance' ? "Xong bảo trì NVR" : "Bảo trì NVR"}
                      </button>

                      <button 
                        className="btn btn-secondary btn-sm" 
                        onClick={() => handleSyncChannels(dev.id, dev.name)}
                        title="Gọi API lấy lại danh sách và trạng thái camera thật từ đầu thu Dahua"
                      >
                        <RefreshCw size={13} /> Đồng Bộ Kênh
                      </button>

                      <button className="btn btn-secondary btn-sm" onClick={() => openModal(dev)}>
                        <Edit3 size={13} /> Sửa
                      </button>

                      <button className="btn btn-danger-outline btn-sm" onClick={() => handleDeleteDevice(dev.id, dev.name)}>
                        <Trash2 size={13} /> Xóa
                      </button>
                    </div>
                  </div>

                  {/* Channels Grid */}
                  <div className="channels-grid">
                    {devChannels.map(ch => {
                      const isLoss = ch.status === 'video_loss';
                      const isMaint = ch.status === 'maintenance';
                      const isUnconn = ch.status === 'unconnected' || ch.status === 'disabled' || (ch.enabled === false && !isMaint);
                      const isOnline = ch.status === 'online';

                      return (
                        <div key={ch.id} className={`camera-card ${isLoss ? 'video-loss' : isMaint ? 'maintenance' : isUnconn ? 'unconnected' : ''}`}>
                          <div className="camera-card-top">
                            <span className="camera-index">CH {ch.channel_no.toString().padStart(2, '0')}</span>
                            {isLoss && (
                              <span className="camera-status-badge video-loss">
                                <AlertTriangle size={12} /> MẤT TÍN HIỆU
                              </span>
                            )}
                            {isMaint && (
                              <span className="camera-status-badge maintenance">
                                <Wrench size={12} /> ĐANG BẢO TRÌ
                              </span>
                            )}
                            {isOnline && (
                              <span className="camera-status-badge online">
                                <CheckCircle2 size={12} /> Tín hiệu tốt
                              </span>
                            )}
                            {isUnconn && (
                              <span className="camera-status-badge unconnected">
                                <Power size={11} /> Chưa gắn camera
                              </span>
                            )}
                          </div>

                          <div className="camera-name" title={ch.name} style={{ opacity: isUnconn ? 0.7 : 1 }}>
                            {ch.name}
                          </div>

                          <div className="camera-card-footer">
                            <span style={{ fontSize: '0.72rem', color: isMaint ? '#fbbf24' : 'var(--text-muted)' }}>
                              {isLoss ? 'Cần kiểm tra dây/nguồn' : isMaint ? 'Tạm ngưng tính SLA' : isOnline ? 'Đang ghi hình' : 'Kênh trống / Tắt'}
                            </span>
                            
                            <div style={{ display: 'flex', gap: 6 }}>
                              {/* Nút Chế độ Bảo trì (Tạm ngưng tính lỗi SLA) - Nổi bật & Rõ ràng */}
                              <button 
                                className={`btn-maint ${isMaint ? 'active' : ''}`}
                                title={isMaint ? "Kết thúc bảo trì, tiếp tục giám sát kênh này" : "Tạm ngưng giám sát (Chế độ bảo trì, chờ sửa chữa)"}
                                onClick={() => handleToggleMaintenance(ch.id, ch.name)}
                              >
                                <Wrench size={12} />
                                {isMaint ? "Xong bảo trì" : "Bảo trì"}
                              </button>

                              {/* Nút bật / tắt theo dõi kênh trống */}
                              <button 
                                className="sim-btn"
                                title={isUnconn ? "Bật theo dõi kênh này" : "Bỏ qua / Kênh này không cắm camera"}
                                onClick={() => handleToggleEnable(ch.id)}
                              >
                                {isUnconn ? "Bật" : "Bỏ qua"}
                              </button>

                              {/* Nút giả lập sự cố nếu là chế độ mock */}
                              {dev.is_mock && (
                                <button 
                                  className="sim-btn"
                                  title="Thử nghiệm giả lập mất tín hiệu / phục hồi"
                                  onClick={() => handleToggleSimulation(ch.id)}
                                >
                                  {isLoss ? '↺' : '⚡'}
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* TAB 2: MONTHLY REPORTS */}
      {activeTab === 'reports' && (
        <div className="report-panel">
          <div className="report-controls" style={{ flexWrap: 'wrap', gap: 14 }}>
            <div className="report-date-selector" style={{ flexWrap: 'wrap', gap: 10 }}>
              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Tháng:</label>
                <select 
                  className="form-select" 
                  value={reportMonth} 
                  onChange={(e) => setReportMonth(Number(e.target.value))}
                >
                  {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                    <option key={m} value={m}>Tháng {m}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Năm:</label>
                <select 
                  className="form-select" 
                  value={reportYear} 
                  onChange={(e) => setReportYear(Number(e.target.value))}
                >
                  <option value={2025}>2025</option>
                  <option value={2026}>2026</option>
                  <option value={2027}>2027</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Người thực hiện:</label>
                <input 
                  type="text" 
                  className="form-input" 
                  style={{ padding: '6px 12px', width: '150px' }}
                  placeholder="Họ tên ký duyệt..."
                  value={reporterName}
                  onChange={(e) => setReporterName(e.target.value)}
                />
              </div>

              <button className="btn btn-secondary" style={{ alignSelf: 'flex-end' }} onClick={fetchReport}>
                <RefreshCw size={15} /> Xem Số Liệu
              </button>
            </div>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignSelf: 'flex-end' }}>
              <button 
                className="btn btn-success" 
                style={{ background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)', boxShadow: '0 4px 14px rgba(16, 185, 129, 0.35)' }}
                onClick={() => handleDownloadHaiQuanExcel()}
                title="Tải biểu mẫu Kiểm tra hoạt động của Camera Hải Quan theo 31 ngày"
              >
                <FileSpreadsheet size={18} />
                Xuất Báo Cáo Hải Quan Theo Ngày (.xlsx)
              </button>

              <button className="btn btn-secondary" onClick={handleDownloadExcel} title="Tải báo cáo tổng quan SLA & thời gian gián đoạn">
                <Download size={16} />
                Báo Cáo SLA
              </button>
            </div>
          </div>

          {monthlyReport && (
            <div>
              {/* Summary Highlights */}
              <div style={{ 
                background: 'rgba(59, 130, 246, 0.08)', 
                border: '1px solid rgba(59, 130, 246, 0.2)', 
                borderRadius: 'var(--radius-md)', 
                padding: '16px 20px', 
                marginBottom: '24px',
                display: 'flex',
                justifyContent: 'space-around',
                flexWrap: 'wrap',
                gap: '16px'
              }}>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Kỳ Báo Cáo:</span>
                  <div style={{ fontWeight: 700, color: '#ffffff' }}>Tháng {monthlyReport.month}/{monthlyReport.year} ({monthlyReport.total_days} ngày)</div>
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Uptime Trung Bình:</span>
                  <div style={{ fontWeight: 800, color: '#34d399', fontSize: '1.2rem' }}>{monthlyReport.avg_uptime_percent}%</div>
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Tổng Sự Cố Mất Tín Hiệu:</span>
                  <div style={{ fontWeight: 700, color: monthlyReport.total_incidents > 0 ? '#f87171' : '#34d399' }}>
                    {monthlyReport.total_incidents} lần
                  </div>
                </div>
              </div>

              {/* Table NVR Summary */}
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '10px', color: '#ffffff' }}>
                I. Thống Kê Hoạt Động Từng Đầu Thu (NVR/DVR)
              </h3>
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Tên Đầu Thu</th>
                      <th>Địa chỉ IP</th>
                      <th>Vị trí</th>
                      <th>Số Kênh</th>
                      <th>Số Lần Rớt</th>
                      <th>Thời Gian Gián Đoạn</th>
                      <th>Tỷ Lệ Uptime</th>
                      <th>Đánh Giá SLA</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monthlyReport.devices.map(d => (
                      <tr key={d.id}>
                        <td style={{ fontWeight: 600 }}>{d.name}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{d.ip}</td>
                        <td>{d.location}</td>
                        <td>{d.channel_count}</td>
                        <td style={{ color: d.incident_count > 0 ? '#f87171' : 'inherit' }}>{d.incident_count}</td>
                        <td>{d.downtime_hours} giờ ({d.downtime_minutes} phút)</td>
                        <td style={{ fontWeight: 700, color: d.uptime_percent >= 99 ? '#34d399' : '#f87171' }}>
                          {d.uptime_percent}%
                        </td>
                        <td>
                          {d.uptime_percent >= 99 ? (
                            <span style={{ color: '#34d399', fontSize: '0.8rem' }}>✓ Đạt SLA (&ge;99%)</span>
                          ) : (
                            <span style={{ color: '#f87171', fontSize: '0.8rem' }}>⚠️ Cần bảo trì</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Table Channels Summary */}
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginTop: '32px', marginBottom: '10px', color: '#ffffff' }}>
                II. Thống Kê Chi Tiết Từng Mắt Camera
              </h3>
              <div className="table-responsive" style={{ maxHeight: '420px' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Tên Camera</th>
                      <th>Thuộc Đầu Thu</th>
                      <th>Kênh</th>
                      <th>Số Lần Mất Tín Hiệu</th>
                      <th>Thời Gian Mất Tín Hiệu</th>
                      <th>Tỷ Lệ Uptime</th>
                      <th>Trạng Thái Hiện Tại</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monthlyReport.channels.map(c => (
                      <tr key={c.id}>
                        <td style={{ fontWeight: 600 }}>{c.name}</td>
                        <td>{c.device_name}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>CH {c.channel_no}</td>
                        <td style={{ color: c.incident_count > 0 ? '#f87171' : 'inherit' }}>{c.incident_count}</td>
                        <td>{c.downtime_hours} giờ ({c.downtime_minutes} phút)</td>
                        <td style={{ fontWeight: 700, color: c.uptime_percent >= 99 ? '#34d399' : '#f87171' }}>
                          {c.uptime_percent}%
                        </td>
                        <td>
                          <span className={`camera-status-badge ${c.status}`} style={{ padding: '2px 8px' }}>
                            {c.status === 'online' ? 'Tốt' : 'Mất tín hiệu'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* PHẦN CHỐT SỔ & QUẢN LÝ DUNG LƯỢNG ATLAS */}
              <div style={{ marginTop: '40px', padding: '20px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: 10 }}>
                  <div>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Database size={18} color="#38bdf8" /> Quản Lý Lưu Trữ & Chốt Sổ Báo Cáo (Tối Ưu 500MB Atlas)
                    </h3>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                      Sau khi kết thúc tháng, bạn tải file báo cáo Hải Quan về máy lưu trữ nội bộ và bấm <strong>"Xóa Dữ Liệu Tháng Này"</strong> để làm sạch database, dung lượng MongoDB Atlas sẽ không bao giờ bị đầy!
                    </p>
                  </div>
                  <button className="btn btn-secondary btn-sm" onClick={fetchRetentionStats}>
                    <RefreshCw size={13} /> Làm Mới
                  </button>
                </div>

                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Kỳ Báo Cáo</th>
                        <th>Số Lượng Bản Ghi Sự Cố</th>
                        <th>Trạng Thái Phục Hồi</th>
                        <th>Thao Tác Chốt Sổ & Giải Phóng Bộ Nhớ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {retentionStats.length === 0 ? (
                        <tr>
                          <td colSpan={4} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
                            Chưa có dữ liệu sự cố nào trong cơ sở dữ liệu. Bộ nhớ đang ở mức tối ưu 100%!
                          </td>
                        </tr>
                      ) : (
                        retentionStats.map(item => (
                          <tr key={`${item.year}-${item.month}`}>
                            <td style={{ fontWeight: 700, color: '#ffffff' }}>
                              Tháng {item.month < 10 ? `0${item.month}` : item.month}/{item.year}
                            </td>
                            <td>
                              <span style={{ fontWeight: 600, color: item.total_events > 0 ? '#f87171' : '#34d399' }}>
                                {item.total_events} sự cố được ghi nhận
                              </span>
                            </td>
                            <td>
                              <span style={{ color: '#34d399', fontSize: '0.82rem' }}>
                                ✓ Đã phục hồi: {item.resolved_events}/{item.total_events}
                              </span>
                            </td>
                            <td>
                              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                <button 
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => handleDownloadHaiQuanExcel(item.year, item.month)}
                                  title="Tải biểu mẫu Hải Quan của tháng này về máy"
                                >
                                  <Download size={13} /> Tải Báo Cáo Hải Quan
                                </button>

                                <button 
                                  className="btn btn-danger btn-sm"
                                  disabled={cleaningStatus === `deleting-${item.year}-${item.month}`}
                                  onClick={() => handleDeleteMonthData(item.year, item.month)}
                                  title="Xóa toàn bộ sự cố tháng này để giải phóng dung lượng"
                                >
                                  <Trash2 size={13} /> 
                                  {cleaningStatus === `deleting-${item.year}-${item.month}` ? 'Đang xóa...' : 'Xóa Dữ Liệu Tháng Này'}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: EVENTS LOG (BÁO CÁO & NHẬT KÝ SỰ CỐ CHI TIẾT) */}
      {activeTab === 'events' && (
        <div className="report-panel">
          {/* Header & Thao tác */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8, color: '#ffffff' }}>
                <ShieldAlert size={22} color="#f87171" /> Nhật Ký & Báo Cáo Sự Cố Mất Tín Hiệu
              </h3>
              <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                Thời gian ghi nhận chuẩn <strong>Múi giờ Việt Nam (UTC+7)</strong> định dạng <strong>DD/MM/YYYY HH:mm:ss</strong>.
              </p>
            </div>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button 
                className="btn btn-secondary btn-sm" 
                onClick={handleDownloadExcel}
                title="Tải bảng tính Excel nhật ký sự cố & tỷ lệ SLA"
              >
                <Download size={14} /> Xuất Báo Cáo Excel
              </button>
              <button className="btn btn-secondary btn-sm" onClick={fetchData}>
                <RefreshCw size={14} /> Làm Mới
              </button>
            </div>
          </div>

          {/* Mini KPI Cards cho Sự Cố */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', marginBottom: '20px' }}>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '14px 18px' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Tổng Số Sự Cố Ghi Nhận</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#ffffff', marginTop: 4 }}>{events.length}</div>
            </div>

            <div style={{ background: unresolvedEventsCount > 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255, 255, 255, 0.03)', border: unresolvedEventsCount > 0 ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '14px 18px' }}>
              <div style={{ fontSize: '0.8rem', color: unresolvedEventsCount > 0 ? '#f87171' : 'var(--text-secondary)' }}>Đang Gián Đoạn (Chưa Phục Hồi)</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: unresolvedEventsCount > 0 ? '#f87171' : '#34d399', marginTop: 4 }}>
                {unresolvedEventsCount > 0 ? `⚠️ ${unresolvedEventsCount}` : '0'}
              </div>
            </div>

            <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: 'var(--radius-md)', padding: '14px 18px' }}>
              <div style={{ fontSize: '0.8rem', color: '#34d399' }}>Đã Khắc Phục / Phục Hồi Xong</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#34d399', marginTop: 4 }}>{resolvedEventsCount}</div>
            </div>
          </div>

          {/* Bộ lọc & Tìm kiếm sự cố */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: 12 }}>
            <div className="filter-group">
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginRight: 4 }}>Trạng thái:</span>
              <button 
                className={`filter-chip ${eventFilterStatus === 'all' ? 'active' : ''}`}
                onClick={() => setEventFilterStatus('all')}
              >
                Tất cả ({events.length})
              </button>
              <button 
                className={`filter-chip ${eventFilterStatus === 'unresolved' ? 'active' : ''}`}
                onClick={() => setEventFilterStatus('unresolved')}
                style={{ borderColor: unresolvedEventsCount > 0 ? 'rgba(239, 68, 68, 0.4)' : '' }}
              >
                ⚠️ Đang gián đoạn ({unresolvedEventsCount})
              </button>
              <button 
                className={`filter-chip ${eventFilterStatus === 'resolved' ? 'active' : ''}`}
                onClick={() => setEventFilterStatus('resolved')}
              >
                ✓ Đã phục hồi ({resolvedEventsCount})
              </button>
            </div>

            {/* Ô tìm kiếm nhanh sự cố */}
            <div style={{ position: 'relative', minWidth: '240px' }}>
              <Search size={15} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="text"
                className="form-input"
                style={{ paddingLeft: '32px', fontSize: '0.84rem' }}
                placeholder="Tìm camera, đầu thu, chi tiết..."
                value={eventSearchText}
                onChange={(e) => setEventSearchText(e.target.value)}
              />
              {eventSearchText && (
                <button 
                  onClick={() => setEventSearchText('')}
                  style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                >
                  <X size={13} />
                </button>
              )}
            </div>
          </div>

          {/* Bảng dữ liệu sự cố chi tiết */}
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ minWidth: '170px' }}>Thời Điểm Ghi Nhận (DD/MM/YYYY)</th>
                  <th>Đối Tượng</th>
                  <th>Loại Sự Kiện</th>
                  <th style={{ minWidth: '170px' }}>Thời Điểm Phục Hồi (DD/MM/YYYY)</th>
                  <th>Thời Lượng Gián Đoạn</th>
                  <th>Chi Tiết & Tiến Độ Khắc Phục</th>
                  <th style={{ textAlign: 'center' }}>Thao Tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '36px', color: 'var(--text-muted)' }}>
                      {events.length === 0 
                        ? 'Chưa có sự cố mất tín hiệu nào được ghi nhận. Hệ thống camera đang hoạt động ổn định 24/7!'
                        : 'Không có sự cố nào khớp với bộ lọc hoặc từ khóa tìm kiếm.'}
                    </td>
                  </tr>
                ) : (
                  filteredEvents.map(ev => {
                    const isResolved = !!ev.resolved_at;
                    return (
                      <tr key={ev.id}>
                        {/* Thời điểm ghi nhận chuẩn DD/MM/YYYY HH:mm:ss */}
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', fontWeight: 600, color: '#e2e8f0' }}>
                          {formatDateTimeVN(ev.timestamp)}
                        </td>

                        <td style={{ fontWeight: 600, color: '#ffffff' }}>
                          {ev.target_name}
                        </td>

                        <td>
                          <span className={`camera-status-badge ${ev.event === 'video_loss' || ev.event === 'offline' ? 'video-loss' : 'online'}`}>
                            {ev.event === 'video_loss' && 'Mất Tín Hiệu'}
                            {ev.event === 'offline' && 'Đầu Thu Mất Kết Nối'}
                            {ev.event === 'recovered' && 'Phục Hồi'}
                            {ev.event === 'online' && 'Đã Kết Nối Lại'}
                          </span>
                        </td>

                        {/* Thời điểm phục hồi chuẩn DD/MM/YYYY HH:mm:ss */}
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
                          {isResolved ? (
                            <span style={{ color: '#34d399', fontWeight: 600 }}>{formatDateTimeVN(ev.resolved_at)}</span>
                          ) : (
                            <span style={{ color: '#f87171', fontWeight: 700 }}>⚠️ Đang gián đoạn...</span>
                          )}
                        </td>

                        {/* Thời lượng gián đoạn */}
                        <td style={{ fontWeight: 600 }}>
                          {formatDurationVN(ev.duration_seconds, ev.timestamp)}
                        </td>

                        <td style={{ color: '#e2e8f0', fontSize: '0.83rem' }}>
                          {ev.note}
                        </td>

                        <td style={{ textAlign: 'center' }}>
                          <div style={{ display: 'flex', gap: 6, justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap' }}>
                            <button
                              className="btn btn-secondary btn-sm"
                              style={{ padding: '4px 8px', fontSize: '0.78rem' }}
                              title="Nhập lý do sự cố / tiến độ khắc phục (sẽ xuất ra file Excel Hải quan)"
                              onClick={() => openNoteModal(ev)}
                            >
                              <FileEdit size={12} style={{ display: 'inline', marginRight: 3 }} />
                              Ghi chú lý do
                            </button>

                            {/* Nút Chuyển Bảo Trì trực tiếp từ bảng sự cố */}
                            {(() => {
                              if (ev.target_type === 'channel') {
                                const relatedChannel = channels.find(c => 
                                  String(c.id) === String(ev.target_id) || 
                                  (String(c.device_id) === String(ev.device_id) && Number(c.channel_no) === Number(ev.channel_no))
                                );
                                if (!relatedChannel) return null;
                                const isChMaint = relatedChannel.status === 'maintenance';
                                return (
                                  <button
                                    className={`btn-maint ${isChMaint ? 'active' : ''}`}
                                    style={{ padding: '4px 8px', fontSize: '0.78rem' }}
                                    title={isChMaint 
                                      ? `Kênh ${ev.target_name} đang ở chế độ bảo trì. Bấm để kết thúc bảo trì.` 
                                      : `Chuyển ngay ${ev.target_name} sang chế độ bảo trì (dừng cảnh báo và ngưng tính lỗi SLA).`}
                                    onClick={() => handleToggleMaintenance(relatedChannel.id, ev.target_name)}
                                  >
                                    <Wrench size={12} />
                                    {isChMaint ? 'Xong bảo trì' : 'Chuyển bảo trì'}
                                  </button>
                                );
                              } else if (ev.target_type === 'device') {
                                const devItem = devices.find(d => String(d.id) === String(ev.target_id) || String(d.id) === String(ev.device_id));
                                if (!devItem) return null;
                                const isDevMaint = devItem.status === 'maintenance';
                                return (
                                  <button
                                    className={`btn-maint ${isDevMaint ? 'active' : ''}`}
                                    style={{ padding: '4px 8px', fontSize: '0.78rem' }}
                                    title={isDevMaint 
                                      ? `Đầu thu ${ev.target_name} đang bảo trì. Bấm để kết thúc.` 
                                      : `Chuyển đầu thu ${ev.target_name} sang chế độ bảo trì.`}
                                    onClick={() => handleToggleDeviceMaintenance(devItem.id, ev.target_name)}
                                  >
                                    <Wrench size={12} />
                                    {isDevMaint ? 'Xong bảo trì' : 'Chuyển bảo trì'}
                                  </button>
                                );
                              }
                              return null;
                            })()}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: EMAIL SETTINGS */}
      {activeTab === 'email' && (
        <div className="report-panel" style={{ maxWidth: '820px', margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Mail size={22} color="#60a5fa" /> Cấu Hình Cảnh Báo Qua Email (SMTP)
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                Tự động gửi email cảnh báo tức thời khi có đầu thu hoặc camera bị mất tín hiệu / rớt mạng.
              </p>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(255,255,255,0.04)', padding: '6px 14px', borderRadius: 'var(--radius-full)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.85rem', color: emailConfig.enabled ? '#34d399' : 'var(--text-muted)', fontWeight: 600 }}>
                {emailConfig.enabled ? '✓ Đang bật cảnh báo' : '○ Đang tắt'}
              </span>
              <input 
                type="checkbox" 
                id="email-enable-toggle"
                style={{ width: 18, height: 18, cursor: 'pointer' }}
                checked={emailConfig.enabled}
                onChange={(e) => setEmailConfig({ ...emailConfig, enabled: e.target.checked })}
              />
            </div>
          </div>

          <form onSubmit={handleSaveEmailConfig}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div className="form-row">
                <div className="form-group">
                  <label>Máy chủ SMTP (SMTP Host) *</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    placeholder="Ví dụ: smtp.gmail.com hoặc smtp.office365.com" 
                    required 
                    value={emailConfig.smtp_host}
                    onChange={(e) => setEmailConfig({ ...emailConfig, smtp_host: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Cổng SMTP (Port) *</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    placeholder="587 (TLS) hoặc 465 (SSL)" 
                    required 
                    value={emailConfig.smtp_port}
                    onChange={(e) => setEmailConfig({ ...emailConfig, smtp_port: Number(e.target.value) })}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Email gửi cảnh báo (Tài khoản SMTP) *</label>
                  <input 
                    type="email" 
                    className="form-input" 
                    placeholder="cameranotify@gmail.com" 
                    required 
                    value={emailConfig.smtp_user}
                    onChange={(e) => setEmailConfig({ ...emailConfig, smtp_user: e.target.value, sender_email: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Mật khẩu Ứng dụng (App Password) *</label>
                  <input 
                    type="password" 
                    className="form-input" 
                    placeholder="Mật khẩu ứng dụng 16 ký tự" 
                    value={emailConfig.smtp_password}
                    onChange={(e) => setEmailConfig({ ...emailConfig, smtp_password: e.target.value })}
                  />
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: 2 }}>
                    (Với Gmail: Bật Xác minh 2 bước &rarr; Tạo <em>Mật khẩu ứng dụng</em>)
                  </span>
                </div>
              </div>

              <div className="form-group">
                <label>Danh sách Email Nhận Cảnh Báo (Hỗ trợ 1 hoặc nhiều email) *</label>
                <textarea 
                  className="form-input" 
                  rows={3} 
                  placeholder="admin@company.com, kythuat@gmail.com, giamsat@company.com"
                  required
                  value={emailConfig.recipient_emails}
                  onChange={(e) => setEmailConfig({ ...emailConfig, recipient_emails: e.target.value })}
                  style={{ resize: 'vertical', lineHeight: 1.6 }}
                />
                <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                  Nhập các email cách nhau bởi dấu phẩy (,). Khi phát hiện mất tín hiệu, hệ thống sẽ tự động gửi email tới tất cả người nhận trong danh sách này.
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px', flexWrap: 'wrap', gap: 12 }}>
                <button 
                  type="button" 
                  className="btn btn-secondary"
                  onClick={handleTestEmailAlert}
                  disabled={emailTesting || !emailConfig.smtp_host || !emailConfig.smtp_user}
                  title="Gửi 1 email thử nghiệm để kiểm tra cấu hình SMTP"
                >
                  <Send size={15} className={emailTesting ? 'spin' : ''} />
                  {emailTesting ? 'Đang gửi thử...' : 'Gửi Thử Email Cảnh Báo'}
                </button>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {emailSaveStatus === 'success' && (
                    <span style={{ color: '#34d399', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Check size={16} /> Đã lưu cấu hình!
                    </span>
                  )}
                  {emailSaveStatus === 'error' && (
                    <span style={{ color: '#f87171', fontSize: '0.85rem' }}>
                      Lỗi khi lưu cấu hình!
                    </span>
                  )}
                  <button type="submit" className="btn btn-primary" disabled={emailSaveStatus === 'saving'}>
                    <Save size={16} />
                    {emailSaveStatus === 'saving' ? 'Đang lưu...' : 'Lưu Cấu Hình'}
                  </button>
                </div>
              </div>

              {emailTestResult && (
                <div className={`test-result-box ${emailTestResult.success ? 'success' : 'error'}`} style={{ marginTop: '12px' }}>
                  {emailTestResult.message}
                </div>
              )}
            </div>
          </form>
        </div>
      )}

      {/* MODAL THÊM / SỬA ĐẦU THU DAHUA */}
      {isModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingDevice ? 'Chỉnh Sửa Thông Tin Đầu Thu' : 'Thêm Đầu Thu Dahua Mới'}</h3>
              <button className="close-btn" onClick={() => setIsModalOpen(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmitDevice}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Tên Đầu Thu *</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    placeholder="Ví dụ: NVR Chi Nhánh Tỉnh, NVR Kho Tổng..."
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Địa chỉ IP (LAN hoặc IP VPN) *</label>
                    <input 
                      type="text" 
                      className="form-input" 
                      placeholder="192.168.1.100 hoặc 10.8.0.x"
                      required
                      value={formData.ip}
                      onChange={(e) => setFormData({ ...formData, ip: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label>Cổng HTTP (Port) *</label>
                    <input 
                      type="number" 
                      className="form-input" 
                      placeholder="80"
                      required
                      value={formData.port}
                      onChange={(e) => setFormData({ ...formData, port: Number(e.target.value) })}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Tài khoản Quản trị NVR</label>
                    <input 
                      type="text" 
                      className="form-input" 
                      placeholder="admin"
                      value={formData.username}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label>Mật khẩu Đầu thu</label>
                    <input 
                      type="password" 
                      className="form-input" 
                      placeholder="Mật khẩu NVR Dahua"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Vị trí / Phân loại Mạng</label>
                    <select 
                      className="form-select"
                      value={formData.location}
                      onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    >
                      <option value="Nội bộ (LAN)">Nội bộ (LAN)</option>
                      <option value="Chi nhánh Tỉnh (VPN)">Chi nhánh Tỉnh (VPN)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Số Lượng Kênh (Channels)</label>
                    <select 
                      className="form-select"
                      value={formData.channel_count}
                      onChange={(e) => setFormData({ ...formData, channel_count: Number(e.target.value) })}
                    >
                      <option value={0}>✨ Tự động nhận diện từ đầu thu</option>
                      <option value={4}>4 Kênh</option>
                      <option value={8}>8 Kênh</option>
                      <option value={16}>16 Kênh</option>
                      <option value={32}>32 Kênh</option>
                      <option value={64}>64 Kênh</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
                  <input 
                    type="checkbox" 
                    id="mock-checkbox"
                    checked={formData.is_mock}
                    onChange={(e) => setFormData({ ...formData, is_mock: e.target.checked })}
                  />
                  <label htmlFor="mock-checkbox" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                    Bật chế độ mô phỏng (Dùng để test thử khi chưa cắm mạng trực tiếp tới đầu thu thật)
                  </label>
                </div>

                {/* TEST CONNECTION BUTTON */}
                <div style={{ marginTop: 8 }}>
                  <button 
                    type="button" 
                    className="btn btn-secondary btn-sm"
                    onClick={handleTestConnection}
                    disabled={testingConnection || !formData.ip}
                  >
                    <Activity size={14} className={testingConnection ? 'spin' : ''} />
                    {testingConnection ? 'Đang gửi gói tin test...' : 'Kiểm tra kết nối Dahua ngay'}
                  </button>

                  {testResult && (
                    <div className={`test-result-box ${testResult.success ? 'success' : 'error'}`}>
                      {testResult.message}
                      {testResult.details && (
                        <div style={{ marginTop: 4, fontSize: '0.78rem' }}>
                          Model: <strong>{testResult.details.model}</strong> | Serial: <strong>{testResult.details.serial}</strong>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>
                  Hủy Bỏ
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingDevice ? 'Lưu Thay Đổi' : 'Thêm Thiết Bị'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL CẬP NHẬT TIẾN ĐỘ / LÝ DO SỰ CỐ DÀI NGÀY */}
      {editingEvent && (
        <div className="modal-backdrop" onClick={() => setEditingEvent(null)}>
          <div className="modal-content" style={{ maxWidth: '560px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <FileEdit size={20} color="#38bdf8" /> Cập Nhật Lý Do & Tiến Độ Khắc Phục
              </h3>
              <button className="modal-close" onClick={() => setEditingEvent(null)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveEventNote}>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.85rem' }}>
                  <div style={{ color: 'var(--text-secondary)' }}>Đối tượng sự cố:</div>
                  <div style={{ fontWeight: 700, color: '#ffffff', fontSize: '0.95rem', marginTop: 2 }}>{editingEvent.target_name}</div>
                  <div style={{ marginTop: 6, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    Thời điểm ghi nhận: {formatDateTimeVN(editingEvent.timestamp)}
                  </div>
                </div>

                <div className="form-group">
                  <label style={{ fontSize: '0.88rem', fontWeight: 600 }}>
                    Nội dung giải trình / Tiến độ sửa chữa:
                  </label>
                  <textarea 
                    className="form-input" 
                    rows={4}
                    style={{ resize: 'vertical', fontSize: '0.88rem', lineHeight: '1.5' }}
                    placeholder="Ví dụ: Đang chờ thợ thay nguồn 12V / Đã gửi hãng bảo hành, hẹn ngày 05/09 lắp lại / Đứt cáp quang nội bộ đang kéo dây mới..."
                    required
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                  />
                  <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 4 }}>
                    💡 <em>Ghi chú này sẽ được tự động xuất thẳng vào cột Ghi chú trên <strong>Biểu mẫu Hải quan 31 ngày</strong> và file Excel SLA để phục vụ công tác thanh tra.</em>
                  </div>
                </div>

                {/* Gợi ý lý do nhanh */}
                <div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: 6 }}>Chọn nhanh mẫu lý do thường gặp:</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {[
                      "Đang chờ thợ thay adapter nguồn 12V",
                      "Đã gửi hãng bảo hành, hẹn ngày lắp lại",
                      "Đứt cáp tín hiệu do thi công, đang xử lý kéo lại dây",
                      "Hỏng mắt camera, đang chờ mua thiết bị thay thế",
                      "Mất nguồn điện tổng khu vực, đang liên hệ điện lực"
                    ].map((sample, idx) => (
                      <button
                        key={idx}
                        type="button"
                        className="sim-btn"
                        style={{ fontSize: '0.75rem', padding: '4px 8px', borderRadius: 4 }}
                        onClick={() => setNoteText(sample)}
                      >
                        + {sample}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setEditingEvent(null)}>
                  Đóng
                </button>
                <button type="submit" className="btn btn-primary" disabled={noteSaving}>
                  {noteSaving ? 'Đang lưu...' : 'Lưu Ghi Chú Giải Trình'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
