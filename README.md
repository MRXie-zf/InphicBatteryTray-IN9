# InphicBatteryTray9 — 英菲克 IN9 系列鼠标任务栏电量显示

给英菲克 **IN9 系列**无线鼠标（已在 IN09 上实测）加一个任务栏电量显示，并在电量 ≤10% 时发 Windows 系统通知。

> ### 本项目从哪来
>
> 本工具是 [**Tan-TanZi/InphicBatteryTray**](https://github.com/Tan-TanZi/InphicBatteryTray) 的 **IN9 衍生版**（上游为 MIT 协议，Copyright © 2026 Tan-TanZi，本项目沿用 MIT，见 [LICENSE](LICENSE)）。
>
> 上游只支持 **IN10**（作者自己的型号）；**IN9 与 IN10 协议完全不通用**，所以原版在你的 IN09 上读不到电量。本版本相对上游的改动：
>
> - 按 IN9 真实协议**重写设备定位与读取逻辑**（Feature Report 通道，不再是输入报告推送）
> - 新增**低电量 Windows 系统通知**（≤10% 可配）+ 托盘开关 + `--notify-test` 自检
> - 新增 `--list` / `--test` / `--probe` 诊断模式，便于适配其它批次
>
> 协议另有参考 [**RuiShu1024/InphicMouse**](https://github.com/RuiShu1024/InphicMouse) 的 `docs/hid-protocol.md`，但**那份文档与本机实测不符**（按其写法下发一律被拒）。本机真实协议是从原厂 `Inphic IN9 GM.exe` 逆向得到并实测通过的，完整过程见 [协议破解记录.md](协议破解记录.md)。
>
> 如果你用的是 IN10，请直接用上游原版，不要用这个。

---

## 一、为什么原版工具读不到你的 IN09

原版 `InphicBatteryTray` 只在作者自己的 **IN10** 上实测过，README 的"已知限制"第 1 条写明了这一点。你的 IN09 读不到，是**双重不匹配**：

| | IN10（原版工具） | IN09（本机实测） |
|---|---|---|
| VID/PID | `1D57:FA60` / `1D57:FA65` / `045E:*` 共 9 组 | `248A:5B2E`（有线）/ `248A:5B2F`（2.4G 接收器）——**不在原版列表里** |
| 通道 | Input Report，设备主动推送 | **Feature Report**（`HidD_Set/GetFeature`），报告 ID `0x0C` |
| 帧格式 | **5 字节**简报文 `03 [type] 40 [dev] [level]` | **33 字节**命令帧 `0C 01 20 00 <seq> ...` |
| 上报方式 | 设备**主动推送**，每 2 秒一次 | **不推送**，必须主机发命令 `0x20` **主动查询** |
| 电量位置 | 报文第 5 字节 | 响应 `buf[0x12]` |

即使把 VID/PID 加进原版列表也没用——IN9 根本没有那种 5 字节推送报文，原版的读取循环一条都不会命中。所以本工具按 IN9 协议重写了读取逻辑。

## 二、快速上手

编译后（见第五节），**按这个顺序验证**：

```powershell
# 1. 列出所有 HID 接口, 确认能看到你的鼠标 (VID 248A/249A)
.\InphicBatteryTray9.exe --list

# 2. 对鼠标发 Feature 0x20 查询, 看原始响应和解析出的电量
.\InphicBatteryTray9.exe --test

# 3. 验证系统通知能不能弹出来 (低电量提醒用的就是它)
.\InphicBatteryTray9.exe --notify-test

# 4. 没问题了, 无参数常驻托盘
.\InphicBatteryTray9.exe
```

托盘行为与原版一致：图标按电量从下往上填充，>40% 青绿、16–40% 黄、≤15% 红；8 秒查不到 → 灰显（休眠/断开，悬停显示最后电量）；充电时图标里有黄色闪电。右键菜单：显示详情 / 重新扫描 / 低电量提醒开关 / 发送测试通知 / 开机自动启动 / 退出。

### 如果第 1 步看不到你的鼠标

说明你的 IN09 VID 不是 248A/249A（不同批次/固件可能有差异）。从 `--list` 输出里找到产品名含 `INPHIC` 或 `IN9` 的那行，记下 VID，然后：

```powershell
.\InphicBatteryTray9.exe --vids=XXXX --test        # XXXX = 你的 VID, 十六进制
.\InphicBatteryTray9.exe --vids=XXXX               # 确认能读后再常驻
```

### 如果第 2 步写入成功但收不到响应

1. 确认鼠标**没休眠**（动一下鼠标再测）；
2. 用 `--probe` 看这个接口到底讲不讲话、讲什么；
3. 厂商通道不在 MI_02 的批次，用 `--mi=XX` 强制指定接口号再试。

## 三、命令行参数

| 参数 | 说明 |
|---|---|
| `--list` | 列出所有 HID 接口（VID/PID/MI/报告长度/UsagePage） |
| `--test` | 对匹配设备发 3 次 Feature `0x20` 查询，打印原始响应 + 解析结果 |
| `--probe` | 探测匹配 VID 的所有接口，对每个接口做一次 Feature `0x20` 探测 |
| `--probe-all` | 探测全部非键鼠接口（自动跳过 UsagePage 0x0001） |
| `--vids=248A,249A` | 覆盖默认 VID 列表（十六进制） |
| `--pids=XXXX` | 限定 PID（默认不限） |
| `--mi=02` | 强制只用指定 MI 接口号 |
| `--interval=2500` | 查询间隔 ms |
| `--offline=8000` | 离线判定超时 ms |
| `--low=10` | 低电量提醒阈值（电量 ≤ 该值发系统通知） |
| `--low-release=15` | 解除阈值：电量回升到该值以上才重新武装提醒 |
| `--low-mins=30` | 持续低电量时，两次提醒的最小间隔（分钟） |
| `--no-low-notify` | 关闭低电量提醒 |
| `--notify-test` | 立即发一次系统通知，用来验证通知能不能弹出来 |
| `--log=路径` | 日志文件（也可用环境变量 `INPHIC_TRAY_LOG`） |

### 低电量提醒

电量 **≤ 10%**（可用 `--low=N` 改）时发一次 Windows 系统通知：

- 充电中不提醒；
- 电量回升到 **> 15%**（阈值 +5，可用 `--low-release=N` 改）才解除，避免在阈值附近反复弹；
- 一直低着不放的话，每 **30 分钟**最多提醒一次（`--low-mins=N`）；
- 托盘右键菜单里有开关和测试入口；
- 程序启动时注册了 AppUserModelID，所以通知会带应用名、在 Win10/11 上以系统通知横幅呈现（可进操作中心）。

没看到通知时先跑 `--notify-test` 排除：Windows 设置 → 系统 → 通知 是否开启、焦点助手/免打扰是否开启。

## 四、工作原理（IN9 协议）

> 网传的 `docs/hid-protocol.md`（33B + 报告ID 0 + 命令 0x10 + 校验和）**在这台设备上完全不适用**，那套写法全部被拒（ERROR_INVALID_PARAMETER）。下面是从本机原厂 `Inphic IN9 GM.exe` 逆向出来并实测通过的真实协议，详见 `协议破解记录.md`。

**传输**：Feature Report（`HidD_SetFeature` / `HidD_GetFeature`），**不是 WriteFile**；报告 ID `0x0C`，长度 33 字节。以 `FILE_SHARE_READ|WRITE` 共享打开，可与原厂软件同时运行。

**握手**：`0C 01 F0 00 <seq> 01 01 FF`（只发不收）
**查电量**：`0C 01 20 00 <seq> 00 00`，发出后 Sleep 10ms 再 GetFeature 读回 33 字节

| 响应偏移 | 含义 |
|---|---|
| `buf[2]` | `0x20` 命令回显 |
| `buf[6]` | `!= 0` 才算有效响应 |
| `buf[8..0x0B]` | `"M909"` 型号魔数 |
| `buf[0x0F]` | IC 型号（本机 `0x25`） |
| `buf[0x12]` | **电量百分比（0–100）** |
| `buf[0x13]` | `2` = 充电中 |
| `buf[0x15]` | 在线标志 |

实测帧：`0C 01 20 00 08 01 10 00 4D 39 30 39 33 01 00 25 45 FF 5E 00 FF ...` → `0x5E` = 94%。

**设备定位**（同原厂软件的判定）：VID `0x248A` 且 PID ∈ {`0x5B2E` 有线, `0x5B2F` 接收器} 且 报告长度 == 33。本机命中的是 **Feature 长度 33 的那个接口**，不是 MI_02。

本工具每 2.5 秒查一次，查询失败超过 8 秒判离线。关机/休眠时设备静默，所以离线只能靠超时推断，和 IN10 工具同样的策略。

## 五、编译

只需要 Windows 自带的 .NET Framework 编译器，**不需要装任何 SDK**。三种方式任选：

**方式 A：双击 `编译.cmd`（最省事）**

双击目录里的 `编译.cmd`，自动完成编译，成功后窗口里会显示下一步操作提示。编译失败时窗口会停在错误信息处，把内容贴出来即可排查。

**方式 B：PowerShell 脚本**

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

**方式 C：手动**

```
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:winexe /platform:x64 /codepage:65001 ^
  /out:InphicBatteryTray9.exe ^
  /reference:System.dll /reference:System.Windows.Forms.dll ^
  /reference:System.Drawing.dll /reference:System.Core.dll ^
  src\InphicBatteryTray9.cs
```

源码 `src/InphicBatteryTray9.cs` 为 UTF-8 with BOM；如果你用 Visual Studio 打开，直接建个 WinForms 控制台工程把文件加进去也行。

## 六、隐私与安全

- 只发送官方软件同款的**读取**命令 `0x10`，不修改鼠标任何设置；
- 主动跳过 Usage Page `0x0001`（键鼠本体）接口，**不采集任何按键/移动数据**；
- 不联网、无遥测、单文件 EXE；
- 与原厂软件（INPHIC HUB / Inphic Mouse）共享方式打开，可同时运行。

首次使用建议先 `--test` 观察几轮，确认电量读数正常后再常驻。

## 七、已知限制

1. 协议实测依据是「IN9 升级版」（ic_type 0x11）。其它 IN9 变体如果帧布局有差异，`--test` 会打印原始响应，可据此核对 `0x0D` 偏移；
2. 电量精度 1%，硬件层面没有小数/电压/健康度；
3. 查询间隔 2.5s 是软件定的，协议里没有"设置上报间隔"的命令；
4. 鼠标休眠时会判离线——这和"关机"无法区分（设备不发通知，只能靠沉默推断）；
5. 多只鼠标同时插入时托盘只显示最近活跃的一只，详情浮层列出全部。

## 八、致谢

- [Tan-TanZi/InphicBatteryTray](https://github.com/Tan-TanZi/InphicBatteryTray) — IN10 版托盘，本项目的 UI 与共享打开思路来源；
- [RuiShu1024/InphicMouse](https://github.com/RuiShu1024/InphicMouse) — IN9 协议逆向还原，本项目协议实现的唯一依据。

## 免责声明

非官方第三方工具，与英菲克（INPHIC）无关。使用风险自负。
