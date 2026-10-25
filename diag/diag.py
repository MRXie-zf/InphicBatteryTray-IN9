# -*- coding: utf-8 -*-
"""
IN9 HID 诊断脚本 — 不编译 C# 也能验证协议
枚举所有 HID 接口 -> 找出英菲克鼠标 -> 发 33 字节 0x10 查询 -> 打印原始响应 hex
用法:  python diag.py            自动探测
       python diag.py --all      探测所有非键鼠接口
       python diag.py --vids=248A,249A
"""
import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time

setupapi = ctypes.WinDLL('setupapi', use_last_error=True)
hid = ctypes.WinDLL('hid', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0
HIDP_STATUS_SUCCESS = 0x00110000

MAX_PATH = 260


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("InterfaceClassGuid", GUID),
                ("Flags", ctypes.c_uint32), ("Reserved", ctypes.c_void_p)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", ctypes.c_uint32), ("VendorID", ctypes.c_uint16),
                ("ProductID", ctypes.c_uint16), ("VersionNumber", ctypes.c_uint16)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", ctypes.c_uint16), ("UsagePage", ctypes.c_uint16),
                ("InputReportByteLength", ctypes.c_uint16), ("OutputReportByteLength", ctypes.c_uint16),
                ("FeatureReportByteLength", ctypes.c_uint16), ("Reserved", ctypes.c_uint16 * 17),
                ("NumberLinkCollectionNodes", ctypes.c_uint16), ("NumberInputButtonCaps", ctypes.c_uint16),
                ("NumberInputValueCaps", ctypes.c_uint16), ("NumberInputDataIndices", ctypes.c_uint16),
                ("NumberOutputButtonCaps", ctypes.c_uint16), ("NumberOutputValueCaps", ctypes.c_uint16),
                ("NumberOutputDataIndices", ctypes.c_uint16), ("NumberFeatureButtonCaps", ctypes.c_uint16),
                ("NumberFeatureValueCaps", ctypes.c_uint16), ("NumberFeatureDataIndices", ctypes.c_uint16)]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", ctypes.c_uint32), ("OffsetHigh", ctypes.c_uint32),
                ("hEvent", ctypes.c_void_p)]


setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
                                                 ctypes.c_uint32, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiEnumDeviceInterfaces.restype = wt.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      ctypes.c_void_p, ctypes.c_uint32,
                                                      ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wt.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wt.BOOL

hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wt.BOOL
hid.HidD_GetProductString.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
hid.HidD_GetProductString.restype = wt.BOOL
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wt.BOOL
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_FreePreparsedData.restype = wt.BOOL
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_uint32

k32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
k32.CreateFileW.restype = ctypes.c_void_p
k32.CloseHandle.argtypes = [ctypes.c_void_p]
k32.CloseHandle.restype = wt.BOOL
k32.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                         ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
k32.ReadFile.restype = wt.BOOL
k32.WriteFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                          ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
k32.WriteFile.restype = wt.BOOL
k32.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, ctypes.c_wchar_p]
k32.CreateEventW.restype = ctypes.c_void_p
k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
k32.WaitForSingleObject.restype = ctypes.c_uint32
k32.GetOverlappedResult.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), wt.BOOL]
k32.GetOverlappedResult.restype = wt.BOOL
k32.ResetEvent.argtypes = [ctypes.c_void_p]
k32.ResetEvent.restype = wt.BOOL
k32.CancelIoEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
k32.CancelIoEx.restype = wt.BOOL


class Dev(object):
    def __init__(self):
        self.path = ""
        self.vid = 0
        self.pid = 0
        self.product = ""
        self.mi = -1
        self.inlen = 0
        self.outlen = 0
        self.usage_page = 0

    def __str__(self):
        return "%04X:%04X mi=%s in=%d out=%d up=0x%04X %s" % (
            self.vid, self.pid, ("--" if self.mi < 0 else "%02X" % self.mi),
            self.inlen, self.outlen, self.usage_page, self.product or "?")


def parse_mi(path):
    p = path.lower()
    i = p.find("&mi_")
    if i < 0:
        return -1
    i += 4
    j = i
    while j < len(p) and p[j] in "0123456789abcdef":
        j += 1
    if j <= i:
        return -1
    try:
        return int(p[i:j], 16)
    except ValueError:
        return -1


def enumerate_hids():
    g = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(g))
    hdevs = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None,
                                          DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hdevs == INVALID_HANDLE_VALUE or hdevs is None:
        return []
    out = []
    try:
        idx = 0
        while True:
            did = SP_DEVICE_INTERFACE_DATA()
            did.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(hdevs, None, ctypes.byref(g), idx, ctypes.byref(did)):
                break
            idx += 1

            need = ctypes.c_uint32(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(hdevs, ctypes.byref(did), None, 0,
                                                      ctypes.byref(need), None)
            sz = need.value
            if sz <= 0 or sz > 65536:
                continue
            buf = ctypes.create_string_buffer(sz)
            # cbSize: x64 -> 8, x86 -> 6
            struct.pack_into("<I", buf, 0, 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdevs, ctypes.byref(did), buf, sz,
                                                              ctypes.byref(need), None):
                continue
            # 注意: cbSize 字段值在 x64 是 8, 但 DevicePath 的偏移恒为 4。
            # 两个偏移都试探一次, 以 "\\?\" 开头为准。
            path = None
            for off in (4, 8):
                p = ctypes.wstring_at(ctypes.addressof(buf) + off)
                if p.startswith("\\\\?\\"):
                    path = p
                    break
            if path is None:
                continue

            d = Dev()
            d.path = path
            d.mi = parse_mi(path)

            h = k32.CreateFileW(path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
            if h != INVALID_HANDLE_VALUE and h is not None:
                try:
                    attr = HIDD_ATTRIBUTES()
                    attr.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
                    if hid.HidD_GetAttributes(h, ctypes.byref(attr)):
                        d.vid = attr.VendorID
                        d.pid = attr.ProductID
                    sbuf = ctypes.create_unicode_buffer(256)
                    if hid.HidD_GetProductString(h, sbuf, 256):
                        d.product = sbuf.value
                    pp = ctypes.c_void_p()
                    if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)) and pp:
                        try:
                            caps = HIDP_CAPS()
                            if hid.HidP_GetCaps(pp, ctypes.byref(caps)) == HIDP_STATUS_SUCCESS:
                                d.inlen = caps.InputReportByteLength
                                d.outlen = caps.OutputReportByteLength
                                d.usage_page = caps.UsagePage
                        finally:
                            hid.HidD_FreePreparsedData(pp)
                finally:
                    k32.CloseHandle(h)
            if d.vid or d.pid:
                out.append(d)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdevs)
    return out


# 尝试的帧格式 (总长度, 报告ID):
#   实测本机接收器只接受 (64, 0x05); 文档记载的是 (33, 0x00)。
#   换连接方式(如 USB 线直连)后设备可能不同, 所以两种都试。
FRAMINGS = [(64, 0x05), (33, 0x00), (64, 0x00)]


def build_frame(cmd, total=64, rid=0x05):
    b = bytearray(total)
    b[0] = rid           # HID 报告ID
    b[1] = cmd
    b[2] = 0x00
    b[3] = 0x01
    b[4] = 0x00
    if total > 32:
        b[32] = sum(b[5:32]) & 0xFF
    return bytes(b)


class Comm(object):
    def __init__(self, path):
        self.h = k32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                                 FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                                 OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
        if self.h == INVALID_HANDLE_VALUE or self.h is None:
            self.h = k32.CreateFileW(path, GENERIC_READ,
                                     FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                                     OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
        self.ok = not (self.h == INVALID_HANDLE_VALUE or self.h is None)
        self.ev = k32.CreateEventW(None, True, False, None)
        self.ov = OVERLAPPED()
        self.ov.hEvent = self.ev
        self.buf = ctypes.create_string_buffer(256)

    def _io(self, write, data, timeout):
        ctypes.set_last_error(0)
        n = ctypes.c_uint32(0)
        k32.ResetEvent(self.ev)
        if write:
            src = ctypes.create_string_buffer(data, len(data))
            r = k32.WriteFile(self.h, src, len(data), ctypes.byref(n), ctypes.byref(self.ov))
        else:
            r = k32.ReadFile(self.h, self.buf, 256, ctypes.byref(n), ctypes.byref(self.ov))
        if r:
            return n.value
        err = ctypes.get_last_error()
        if err != ERROR_IO_PENDING:
            return -1
        rc = k32.WaitForSingleObject(self.ev, timeout)
        if rc != WAIT_OBJECT_0:
            k32.CancelIoEx(self.h, ctypes.byref(self.ov))
            return 0
        got = ctypes.c_uint32(0)
        if not k32.GetOverlappedResult(self.h, ctypes.byref(self.ov), ctypes.byref(got), False):
            return -1
        return got.value

    def write(self, data, timeout=500):
        n = self._io(True, data, timeout)
        return n == len(data)

    def read(self, timeout=150):
        n = self._io(False, None, timeout)
        if n is None or n <= 0:
            return None
        return bytes(self.buf[:n])

    def close(self):
        try:
            k32.CloseHandle(self.ev)
        except Exception:
            pass
        try:
            k32.CloseHandle(self.h)
        except Exception:
            pass


def hexs(b):
    return " ".join("%02X" % x for x in b)


def probe(d, rounds=2, listen_ms=1200):
    print("=" * 78)
    print("探测: %s" % d)
    print("  路径: %s" % d.path)
    c = Comm(d.path)
    if not c.ok:
        print("  打开失败 (共享模式可能被独占)")
        return False
    any_ok = False
    try:
        for (total, rid) in FRAMINGS:
            tag = "[%d字节/ID%02X]" % (total, rid)
            hs = build_frame(0x11, total, rid)
            if not c.write(hs):
                print("  %s 握手写入被拒 (设备不接受该长度/报告ID)" % tag)
                continue
            print("  %s 握手 0x11 写入: 成功" % tag)
            for _ in range(3):
                if c.read(100) is None:
                    break
            time.sleep(0.05)

            for r in range(1, rounds + 1):
                print("  %s -- 0x10 查询 第 %d 次 --" % (tag, r))
                data = build_frame(0x10, total, rid)
                if not c.write(data):
                    print("     写入失败")
                    break
                got = False
                t0 = time.time()
                while (time.time() - t0) * 1000 < listen_ms:
                    b = c.read(150)
                    if b is None:
                        continue
                    print("     收到 %2d 字节: %s" % (len(b), hexs(b)))
                    if bytes(b) == bytes(data):
                        print("     (回显: 与发送内容完全相同 —— 设备没有应答)")
                        continue
                    info = try_parse(b)
                    if info:
                        print("     >>> 电量 %d%%  充电=%s  在线=%s" % info)
                        got = True
                        any_ok = True
                        break
                if not got:
                    print("     (本轮无有效响应)")
                time.sleep(0.4)
            if any_ok:
                break
        return any_ok
    finally:
        c.close()


def try_parse(b):
    """按 IN9 协议解析。返回 (level, charging, online) 或 None"""
    if len(b) < 16:
        return None
    if b[1] == 0xC0:
        return None
    if b[2] == 0x00:
        off = 1
    elif b[1] == 0x00:
        off = 0
    else:
        return None
    bi, ci, oi = 0x0D + off, 0x0C + off, 0x0E + off
    if max(bi, ci, oi) >= len(b):
        return None
    lv = b[bi]
    if lv > 100:
        return None
    return (lv, bool(b[ci]), bool(b[oi]))


def main():
    args = sys.argv[1:]
    vids = None
    probe_all = False
    for a in args:
        if a.startswith("--vids="):
            vids = [int(x, 16) for x in a[7:].replace(";", ",").split(",") if x.strip()]
        if a == "--all":
            probe_all = True

    devs = enumerate_hids()
    print("共发现 %d 个 HID 接口\n" % len(devs))
    for i, d in enumerate(devs):
        print("[%2d] %s" % (i, d))

    # 候选: 名字像英菲克, 或 VID 命中, 或(--all 时)非键鼠接口
    cands = []
    for d in devs:
        nm = (d.product or "").lower()
        looks_inphic = ("inphic" in nm) or ("in9" in nm) or ("in09" in nm) or ("英菲克" in nm)
        vid_hit = (vids is not None and d.vid in vids) or (vids is None and d.vid in (0x248A, 0x249A))
        if vid_hit or looks_inphic:
            cands.append(d)
        elif probe_all and d.usage_page != 0x0001:
            cands.append(d)
        elif vids is None and d.usage_page != 0x0001 and (d.outlen >= 33 or d.inlen >= 33) and not looks_inphic:
            pass  # 名字不像就不主动打扰, 用 --all 才会探测

    print()
    if not cands:
        print("未找到明显候选。请从上面列表里找出你的鼠标 (名字含 INPHIC / IN9),")
        print("记下它的 VID, 重跑:  python diag.py --vids=XXXX")
        print("或者跑:  python diag.py --all   (探测所有非键鼠接口)")
        return

    print("候选接口 %d 个, 开始发 0x10 查询...\n" % len(cands))
    any_ok = False
    for d in cands:
        if probe(d):
            any_ok = True
    print()
    if any_ok:
        print("=== 成功读到电量 ===")
    else:
        print("=== 全部候选均无有效响应 ===")
        print("可能原因: 鼠标休眠(动一下再试) / 厂商通道不在这些接口 / 帧格式不同")
        print("建议: python diag.py --all   探测所有非键鼠接口, 看哪个接口讲话")


if __name__ == "__main__":
    main()
