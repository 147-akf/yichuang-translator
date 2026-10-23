# 译窗 Translator

一个简洁的 Windows 中英互译小工具：**窗口置顶、手动粘贴、一键翻译**。

外观有四个同级选项：**黑色 / 白色 / 米白色 / 自定义壁纸**，四选一、互斥切换。

不需要 API Key。翻译功能只用 Python 标准库；壁纸功能可选安装 Pillow 和 OpenCV。

![界面截图](screenshot.png)

## 外观：四选一

![四套外观](screenshots/appearance.png)

- 点标题栏右侧的「外观：… ▾」按钮打开外观列表；每一项都有色块和勾选状态，选择后立即生效并自动收起。
- **黑色 / 白色 / 米白色**：纯色主题，切换立即生效并记住。
- **自定义壁纸**：图片或视频铺满整个窗口，顶部和底部使用半透明主题色蒙层保证文字可读；原文/译文窗口默认是实色卡片。
- 列表底部还有「文字窗口透明度」滑块：0% 完全不透明，数值越大壁纸越明显；设置会保存。
- 四个选项是一个级别的：选中主题会关闭自定义壁纸，选中自定义壁纸会取消三个主题的高亮。
- 自定义壁纸沿用当前主题的配色（蒙层、卡片、按钮颜色）；再次选择列表中的「自定义壁纸」可以更换文件。

## 功能

- **中 ⇄ 英互译**：自动检测语言方向，也可以手动锁定「中文 → 英文」或「英文 → 中文」。
- **窗口置顶**：默认勾选「窗口置顶」，翻译时窗口不会跑到浏览器后面；随时可以取消。
- **外观四选一**：黑色、白色、米白色、自定义壁纸，互斥切换。
- **全窗口自定义壁纸**：支持图片和视频；视频静音循环播放，最高约 15 FPS，窗口最小化时自动暂停。
- **原文/译文窗口透明度**：在外观列表底部拖动滑块（0%–70%），决定文字窗口遮挡壁纸的程度；0% 完全不透明，数值越大壁纸越明显。
- **默认不监听剪贴板**：只有点击「粘贴」或按 `Ctrl+V` 时才会读取剪贴板，程序不会在后台偷看。
- **可选的「自动读取剪贴板」**：勾选后，复制任意文字会自动填入并翻译；默认关闭，想保持完全手动就不勾选。
- **粘贴后自动翻译**：默认开启，粘贴完立刻出结果；取消勾选后可以先粘贴、修改，再按 `Ctrl+Enter` 翻译。
- **一键复制译文**：点击「复制结果」或按 `Ctrl+Shift+C`。
- **记住设置**：窗口位置、置顶状态、翻译方向、剪贴板开关、外观主题、壁纸路径和文字窗口透明度都会保存。

## 壁纸支持

- 图片：PNG、JPG/JPEG、BMP、GIF（显示首帧）、WebP、TIFF
- 视频：MP4、MKV、MOV、AVI、WMV、WebM、M4V、MPG/MPEG 等（取决于 OpenCV 的解码支持）
- 视频壁纸无声播放，最多约 15 FPS，并会在窗口最小化时暂停，避免持续占用资源
- 选择黑色 / 白色 / 米白色主题会自动关闭壁纸，恢复纯色界面
- 文字窗口透明度只影响原文/译文输入框，不改变整体界面；0% 为完全不透明

壁纸只在本机读取，不会上传到任何服务器。

## 快捷键

| 快捷键 | 作用 |
| --- | --- |
| `Ctrl+V` | 手动粘贴（开启「粘贴后自动翻译」时会立即翻译） |
| `Ctrl+Enter` | 翻译 |
| `Ctrl+Shift+C` | 复制译文 |

## 使用

1. 双击桌面快捷方式或 `translator.pyw` 启动。
2. 在窗口里按 `Ctrl+V`（或点「粘贴」）粘贴文字。
3. 程序会自动识别方向并翻译；也可以按 `Ctrl+Enter` 手动触发。
4. 点「复制结果」或按 `Ctrl+Shift+C` 复制译文。
5. 点标题栏右侧的「外观：… ▾」打开列表，选择黑色 / 白色 / 米白色 / 自定义壁纸；点「自定义壁纸」会打开图片/视频选择框。
6. 需要让壁纸从原文/译文窗口中透出来时，在同一个外观列表底部拖动「文字窗口透明度」滑块。

如果想让程序在你复制文字后自动填入并翻译，勾选「自动读取剪贴板」（默认关闭）。开启后复制任何文字都会自动填入窗口，处理密码等敏感内容时请先关闭该选项。

## 运行

### 环境要求

- Windows 10 / 11
- Python 3.9 或更高版本
  - 安装 Python 时请勾选 **tcl/tk and IDLE**（Tkinter 是标准库的一部分）

### 启动方式

1. 双击 `translator.pyw`（不会弹出黑色命令行窗口）。
2. 或者双击 `run.bat`。
3. 或者在命令行运行：

   ```bat
   pythonw translator.pyw
   ```

### 创建桌面快捷方式

双击 `create_shortcut.py`（或运行 `python create_shortcut.py`），会自动在桌面创建「译窗 Translator」快捷方式，使用项目自带的蓝色图标。

### 安装壁纸依赖（可选）

主题和翻译不需要额外依赖。使用图片/视频壁纸前，安装：

```bat
pip install -r requirements.txt
```

或者双击 `install_deps.bat`。没有安装依赖时程序仍可正常启动，选择壁纸时会提示安装。

- 图片壁纸需要 **Pillow**
- 视频壁纸需要 **Pillow + opencv-python-headless**

## 打包成 exe（可选）

先安装依赖，再打包成单文件 exe：

```bat
build_exe.bat
```

脚本会安装 PyInstaller 和壁纸依赖，并生成 `dist\YiChuangTranslator.exe`。由于包含 OpenCV，exe 体积会比较大（约 100 MB 左右）。生成后可以放到桌面双击运行，也可以作为 GitHub Release 的附件。

## 工作原理与隐私

- 点击「翻译」时，输入框中的文字会通过 HTTPS 发送到 Google 的公开翻译接口；如果请求失败，会自动改用 MyMemory 的公开接口。
- 默认情况下程序**不监听剪贴板**，只有手动粘贴时才读取。
- 如果主动勾选「自动读取剪贴板」，程序会每隔约 0.7 秒检查剪贴板是否有新文字，并自动填入翻译。该选项默认关闭；处理敏感内容时请勿开启。
- 程序**不会把原文或译文保存到本地**。
- 壁纸图片/视频只在本机读取和显示，不会上传。
- 唯一写入磁盘的是设置文件 `~/.desktop_translator.json`（窗口位置、开关状态、主题、壁纸路径），不含任何翻译内容。
- 这两个公开接口适合个人、轻量使用。它们可能限流、变更或无法访问；如果要用于商业或高频场景，建议把 `engine.py` 中的请求替换成 Google Cloud Translation、DeepL 等官方 API。

## 已知限制

- 翻译需要联网。
- 免费公开接口可能偶发超时或限流；程序会自动尝试备用接口。
- 一次翻译很长的文本时会自动分块请求，速度取决于网络。
- 视频壁纸会占用一定的 CPU/GPU 解码资源；低配置电脑建议使用图片壁纸。
- 视频格式支持取决于 OpenCV 内置的解码器；无法解码时会给出提示。
- 壁纸路径保存在设置文件中，移动或删除原文件后需要重新选择。
- 自定义壁纸模式使用当前主题的颜色作为蒙层和控件配色；如果需要换配色，先选主题再重新选择壁纸。
- 文字窗口透明度越高，文字与壁纸的对比度越低；如果觉得难读，把滑块调低到 0% 即可恢复实色卡片。

## 发布到 GitHub

```bat
git init
git add .
git commit -m "Initial commit: 译窗 Translator"
git branch -M main
git remote add origin https://github.com/<your-name>/desktop-translator.git
git push -u origin main
```

建议在仓库的 **About** 里填写：

> A tiny always-on-top Chinese ↔ English translator for Windows with four appearance modes and image/video wallpapers.

推荐 topics：`translator`、`chinese`、`english`、`tkinter`、`windows`、`desktop-app`、`themes`、`wallpaper`。

## English

**译窗 Translator** is a tiny always-on-top Chinese ↔ English translator for Windows.

- Four equal, mutually exclusive appearance options: **dark, light, cream, or a custom image/video wallpaper**.
- Open the appearance list from the summary button in the title bar. Each row has a colour swatch and a check mark; choosing an option applies it and closes the list.
- Choosing a colour theme closes the custom wallpaper; choosing a wallpaper removes the theme highlight.
- Custom wallpapers fill the whole window. Translucent theme-coloured bands at the top and bottom keep labels readable.
- Adjustable input/output text-window transparency (0%–70%) from the bottom of the appearance list: 0% is fully opaque, higher values let more of the wallpaper show through.
- Images: PNG/JPG/BMP/GIF/WebP/TIFF. Videos: MP4/MKV/MOV/AVI/WMV/WebM and more, looping silently at up to ~15 FPS and pausing when minimised.
- Paste text manually by default (the app never monitors your clipboard unless you opt in).
- Optional "auto-read clipboard" mode: copied text is filled in and translated automatically. Off by default.
- Translation uses only the Python standard library. Wallpapers optionally require Pillow and opencv-python-headless (`pip install -r requirements.txt`).
- Run `translator.pyw`, or double-click `run.bat`.
- `Ctrl+Enter` translates, `Ctrl+Shift+C` copies the result.
- Optional: `build_exe.bat` builds a single-file executable with PyInstaller.

Translation text is sent over HTTPS to Google's public translation endpoint, with MyMemory as a fallback. No text is stored locally. Wallpaper files stay on your computer. For commercial or high-volume use, replace the endpoint in `engine.py` with an official API.

## License

[MIT](LICENSE)
