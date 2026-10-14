# 开发组任务登记及志愿时长分配系统

开发组内部使用的任务登记与志愿时长统计工具。系统支持记录各项开发任务、指派参与组员并核算志愿时长，同时提供成员时长汇总排行与个人任务明细查询。

## 功能

### 人员管理
- 录入组员姓名与学号
- 查看组员列表与总志愿时长
- 查询指定组员的历史任务明细与每次获得的工时
- 删除组员及其关联的时长分配记录

### 任务管理
- 登记新任务：支持任务名称、日期、多选参与人员与志愿时长
- 时长计算：单次时长支持 0.1 到 100 小时（步长 0.1），按全额分配给所有参与人员
- 任务修改：支持重新调整任务内容、日期、参与人员与时长，系统自动重新核算各成员工时
- 任务删除：删除任务并同步撤销对应的工时分配

### 统计排行
- 汇总全局成员的志愿时长，按时长降序生成排行榜

## 技术栈

- 前端：HTML5、CSS3、原生 JavaScript
- 后端：Python 3、FastAPI、Uvicorn、Pydantic
- 数据库：SQLite 3

## 目录结构

```text
.
├── backend/
│   ├── main.py        # FastAPI 后端服务与路由
│   └── data.db        # SQLite 数据库文件
├── frontend/
│   └── index.html     # 前端单页面交互界面
├── requirements.txt   # Python 依赖清单
└── README.md          # 项目说明文档
```

## 本地运行

1. 克隆仓库：
   ```bash
   git clone https://github.com/hhchhc2799/volunteer-system.git
   cd volunteer-system
   ```

2. 安装依赖：
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. 启动后端服务：
   ```bash
   python backend/main.py
   ```
   服务默认运行在 `http://127.0.0.1:32004`。

4. 访问系统：
   浏览器直接打开 `http://127.0.0.1:32004/`，或双击打开 `frontend/index.html`。

## 生产部署 (Linux Systemd)

系统可通过 systemd 作为后台守护服务运行。创建服务文件 `/etc/systemd/system/volunteer.service`：

```ini
[Unit]
Description=Volunteer System Python Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/volunteer-system
ExecStart=/root/volunteer-system/venv/bin/python3 backend/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动并设置开机自启：
```bash
systemctl daemon-reload
systemctl enable volunteer
systemctl start volunteer
```