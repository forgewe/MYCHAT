# MyChat Android

与 Windows 电脑版同一 Wi‑Fi 可互发文字。  
**纯 Windows 推荐用 GitHub 云端出 APK**；本机可用 Docker 或 WSL。

---

## 一、GitHub 云端打包（推荐，无需本机 Linux）

### 1. 注册/登录 GitHub，新建仓库
例如：`MyChat-Android`（可设为 Private）

### 2. 上传本文件夹全部文件
需要包含：
- `main.py`
- `buildozer.spec`
- `.github/workflows/build-apk.yml`
- `README.md`

可用网页上传，或用 GitHub Desktop。

### 3. 触发编译
1. 打开仓库页面 → 上方 **Actions**
2. 左侧选 **Build MyChat APK**
3. 点 **Run workflow** → **Run workflow**
4. 等待 30～90 分钟（首次较慢）

### 4. 下载 APK
1. 进入刚跑完的那次 workflow（绿色勾）
2. 拉到页面底部 **Artifacts**
3. 下载 **MyChat-APK**
4. 解压得到 `.apk`，拷到手机安装（允许未知来源）

> Artifacts 默认约保留 90 天。

---

## 二、本机打包（纯 Windows）

Buildozer **不能直接在原生 Windows CMD 里跑**，可选：

### 方式 B1：Docker Desktop（较省事）

1. 安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 在本目录打开 PowerShell：

```powershell
docker run --rm -v ${PWD}:/home/user/hostcwd -w /home/user/hostcwd kivy/buildozer android debug
```

3. 完成后看 `bin\*.apk`

> 首次会拉镜像并下载 SDK，时间较长。若命令失败，可改用下面 WSL。

### 方式 B2：WSL2 Ubuntu（官方更稳）

管理员 PowerShell：

```powershell
wsl --install
```

重启后打开 **Ubuntu**：

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool \
  pkg-config zlib1g-dev cmake libffi-dev libssl-dev
pip3 install --user "cython<3.0" buildozer

# 进入已拷到 WSL 的工程目录，例如：
cd /mnt/c/Users/你的用户名/Desktop/MyChat_Android
buildozer android debug
```

APK 在 `bin/` 下。

---

## 三、安装与联调

1. 手机允许「安装未知应用」
2. 安装 APK，连与电脑 **同一 Wi‑Fi**（不要用访客网络）
3. 电脑运行桌面版 MyChat，手机打开本 App
4. 双方点「刷新」，互发文字

---

## 电脑预览界面（可选）

```powershell
pip install kivy
python main.py
```

---

## 版本

- Android A1：发现用户 + 私聊文字（协议兼容桌面版）
