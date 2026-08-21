# 新板子快速接入 AI 运维方案

## 目标

将新开发板快速接入 GitHub Actions + Self-hosted Runner + AI 自动部署体系。

目标：

> 新板子上线后，通过一次初始化即可接入 AI 运维，不再重复人工部署调试。

---

# 一、最终架构

```
新开发板
    |
    | bootstrap.sh
    |
    v
安装基础环境
    |
    v
安装 GitHub Runner
    |
    v
注册设备身份
    |
    v
部署 edge-agent
    |
    v
control.sh 接管
    |
    v
GitHub Actions 自动部署业务项目
```

---

# 二、核心组件

## GitHub Runner

作用：

- 接收 GitHub Actions 任务
- 在设备本地执行命令
- 返回日志和结果

Runner 不负责业务逻辑。

---

## control.sh

位置：

```
/opt/server-project-control/control.sh
```

负责：

- 环境检测
- 依赖安装
- 配置生成
- systemd 服务创建
- 服务启动
- 健康检查
- 自动修复

---

# 三、公共设备管理仓库

建议建立：

```
wulisususu/edge-agent
```

结构：

```
edge-agent
|
├── bootstrap.sh
├── install-runner.sh
├── collect-info.sh
|
├── control/
│   ├── deploy.sh
│   ├── backup.sh
│   ├── rollback.sh
│   └── healthcheck.sh
|
└── templates/
    ├── fastapi.service
    ├── golang.service
    └── docker-compose.yml
```

---

# 四、新设备接入流程

## 1. 初始化

执行：

```bash
curl -fsSL https://raw.githubusercontent.com/wulisususu/edge-agent/main/bootstrap.sh | bash
```

完成：

- 安装 git
- 安装 curl
- 检测 CPU 架构
- 创建工作目录
- 安装基础依赖

---

## 2. 安装 Runner

自动根据架构选择：

- ARM64
- x64

注册标签：

```
self-hosted
linux
arm64
rk3588
```

通过标签区分设备。

---

## 3. 生成设备身份

例如：

```
/etc/edge-agent/device.env
```

内容：

```env
DEVICE_ID=rk3588-001
ARCH=arm64
ROLE=medical
```

---

# 五、自动部署流程

标准流程：

```
代码提交
 ↓
GitHub Actions
 ↓
Self-hosted Runner
 ↓
control.sh deploy
 ↓
安装依赖
 ↓
生成配置
 ↓
创建服务
 ↓
健康检查
```

---

# 六、项目接入方式

每个项目只需要自己的 workflow：

```
.github/workflows/deploy.yml
```

示例：

```yaml
runs-on:
  - self-hosted
  - arm64
  - rk3588
```

然后执行：

```bash
control.sh deploy
```

---

# 七、部署耗时目标

|步骤|时间|
|-|-:|
|bootstrap|1分钟|
|Runner注册|2分钟|
|环境检测|1分钟|
|首次部署|5分钟|

目标：10分钟以内完成新设备接入。

---

# 八、未来扩展

## 设备状态中心

统一查看：

- CPU
- 内存
- 服务状态
- 当前版本
- 部署记录

## 自动故障恢复

```
服务异常
 ↓
Agent发现
 ↓
AI分析
 ↓
自动修复
 ↓
生成报告
```

## 多设备边缘集群

```
GitHub
  |
server-ops
  |
----------------
|      |       |
RK3588 RK3576 云服务器
```

---

# 总结

最终沉淀：

```
edge-agent
+
GitHub Runner
+
control.sh
+
systemd模板
+
AI运维流程
```

以后新增设备：

```
安装系统
 ↓
运行 bootstrap
 ↓
注册 Runner
 ↓
选择项目部署
```

即可接入 AI 自动部署体系。
