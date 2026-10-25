# -*- coding: utf-8 -*-
"""
probe_v2: 重新枚举(带 Feature 长度) + 校验和变体扫描
只为验证: 是不是"校验和算法不对"导致设备把我们当无效帧原样回显。
"""
import sys
import time
import ctypes
sys.path.insert(0, '.')
import diag as D
from diag import Dev, parse_mi, hexs, INVALID_HANDLE_VALUE, FILE_FLAG_OVERLAPPED

k32 = D.k32
hid = D.hid


# ---- 带 FeatureReportByteLength 的枚举 ----
class GUID(D.GUID):
    pass


def enum_full():
    g = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(g))
    DIGCF_PRESENT = 0x2
    DIGCF_DEVICEINTERFACE = 0x10
    hdevs = D.setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None,
                                            DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hdevs == INVALID_HANDLE_VALUE or hdevs is None:
        return []
    out = []
    try:
        idx = 0
        while True:
            did = D.SP_DEVICE_INTERFACE_DATA()
            did.cbSize = ctypes.sizeof(D.SP_DEVICE_INTERFACE_DATA)
            if not D.setupapi.SetupDiEnumDeviceInterfaces(hdevs, None, ctypes.byref(g), idx, ctypes.byref(did)):
                break
            idx += 1
            need = ctypes.c_uint32(0)
            D.setupapi.SetupDiGetDeviceInterfaceDetailW(hdevs, ctypes.byref(did), None, 0,
                                                        ctypes.byref(need), None)
            sz = need.value
            if sz <= 0 or sz > 65536:
                continue
            buf = ctypes.create_string_buffer(sz)
            import struct
            struct.pack_into("<I", buf, 0, 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            if not D.setupapi.SetupDiGetDeviceInterfaceDetailW(hdevs, ctypes.byref(did), buf, sz,
                                                               ctypes.byref(need), None):
                continue
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
            h = k32.CreateFileW(path, 0, 3, None, 3, 0, None)
            if h != INVALID_HANDLE_VALUE and h is not None:
                try:
                    a = D.HIDD_ATTRIBUTES()
                    a.Size = ctypes.sizeof(D.HIDD_ATTRIBUTES)
                    if hid.HidD_GetAttributes(h, ctypes.byref(a)):
                        d.vid, d.pid = a.VendorID, a.ProductID
                    sb = ctypes.create_unicode_buffer(256)
                    if hid.HidD_GetProductString(h, sb, 256):
                        d.product = sb.value
                    mb = ctypes.create_unicode_buffer(256)
                    if hid.HidD_GetManufacturerString(h, mb, 256):
                        d.mfg = mb.value
                    pp = ctypes.c_void_p()
                    if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)) and pp:
                        try:
                            c = D.HIDP_CAPS()
                            if hid.HidP_GetCaps(pp, ctypes.byref(c)) == 0x00110000:
                                d.inlen = c.InputReportByteLength
                                d.outlen = c.OutputReportByteLength
                                d.featlen = c.FeatureReportByteLength
                                d.usage_page = c.UsagePage
                        finally:
                            hid.HidD_FreePreparsedData(pp)
                finally:
                    k32.CloseHandle(h)
            out.append(d)
    finally:
        D.setupapi.SetupDiDestroyDeviceInfoList(hdevs)
    return out


Dev.mfg = ""
Dev.featlen = 0


class Safe(object):
    """异步读写, 带完整排空(避免段错误)"""

    def __init__(self, path):
        self.h = k32.CreateFileW(path, D.GENERIC_READ | D.GENERIC_WRITE, 3, None, 3,
                                 FILE_FLAG_OVERLAPPED, None)
        if self.h == INVALID_HANDLE_VALUE or self.h is None:
            self.h = k32.CreateFileW(path, D.GENERIC_READ, 3, None, 3, FILE_FLAG_OVERLAPPED, None)
        self.ok = self.h != INVALID_HANDLE_VALUE and self.h is not None
        self.ev = k32.CreateEventW(None, True, False, None)
        self.ov = D.OVERLAPPED()
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
        if err != 997:
            return -1
        rc = k32.WaitForSingleObject(self.ev, timeout)
        if rc != 0:
            self.drain()
            return 0
        got = ctypes.c_uint32(0)
        if not k32.GetOverlappedResult(self.h, ctypes.byref(self.ov), ctypes.byref(got), False):
            return -1
        return got.value

    def drain(self):
        try:
            g = ctypes.c_uint32(0)
            k32.CancelIoEx(self.h, ctypes.byref(self.ov))
            k32.GetOverlappedResult(self.h, ctypes.byref(self.ov), ctypes.byref(g), True)
        except Exception:
            pass

    def write(self, data, timeout=500):
        return self._io(True, data, timeout) == len(data)

    def read(self, timeout=150):
        n = self._io(False, None, timeout)
        if n is None or n <= 0:
            return None
        return bytes(self.buf[:n])

    def flush(self, ms=300):
        t0 = time.time()
        while (time.time() - t0) * 1000 < ms:
            if self.read(100) is None:
                break

    def close(self):
        self.drain()
        try:
            k32.CloseHandle(self.ev)
        except Exception:
            pass
        try:
            k32.CloseHandle(self.h)
        except Exception:
            pass


# ---- 校验和变体 ----
def ck_variants(b):
    """返回 [(名字, 校验和字节)]"""
    p = b[5:32]
    s = sum(p) & 0xFF
    return [
        ("sum[5..31]", s),
        ("sum[1..31]", sum(b[1:32]) & 0xFF),
        ("sum[0..31]", sum(b[0:32]) & 0xFF),
        ("sum[2..31]", sum(b[2:32]) & 0xFF),
        ("sum[4..31]", sum(b[4:32]) & 0xFF),
        ("sum[5..32]", sum(b[5:33]) & 0xFF),
        ("sum[1..63]", sum(b[1:64]) & 0xFF),
        ("sum[0..63]", sum(b[0:64]) & 0xFF),
        ("sum[5..63]", sum(b[5:64]) & 0xFF),
        ("xor[5..31]", __import__("functools").reduce(lambda a, x: a ^ x, p, 0)),
        ("neg-sum", (0x100 - s) & 0xFF),
        ("sum+1", (s + 1) & 0xFF),
        ("sum+AA", (s + 0xAA) & 0xFF),
        ("0x5A", 0x5A),
        ("0xFF", 0xFF),
    ]


def main():
    devs = enum_full()
    print("=" * 90)
    print("全部 HID 接口中与 248A/249A 相关的:")
    print("=" * 90)
    tg = []
    for d in devs:
        if d.vid in (0x248A, 0x249A):
            print("  mi=%s  %04X:%04X  in=%3d out=%3d feat=%3d up=0x%04X  %s | %s"
                  % ("--" if d.mi < 0 else "%02X" % d.mi, d.vid, d.pid, d.inlen, d.outlen,
                     d.featlen, d.usage_page, d.product or "?", d.mfg or ""))
            tg.append(d)
    print()
    if not tg:
        print("没找到 248A/249A 设备! 当前可能没插接收器。")
        return

    # 主目标: mi_02 (文档指定)
    cand = [d for d in tg if d.mi == 0x02 and d.outlen >= 33]
    if not cand:
        cand = [d for d in tg if d.outlen >= 33]
    if not cand:
        print("没有可写(out>=33)的接口")
        return

    d = cand[0]
    print("目标接口: %s" % d)
    print("路径: %s\n" % d.path)

    c = Safe(d.path)
    if not c.ok:
        print("打开失败 err=%d" % ctypes.get_last_error())
        return

    try:
        TOTAL, RID = 64, 0x05
        print("-" * 90)
        print("阶段1: 校验和变体扫描 (cmd=0x10, %d字节, 报告ID=0x%02X)" % (TOTAL, RID))
        print("-" * 90)
        for name, ck in ck_variants(bytearray(TOTAL)):
            b = bytearray(TOTAL)
            b[0] = RID
            b[1] = 0x10
            b[2] = 0x00
            b[3] = 0x01
            b[4] = 0x00
            b[32] = ck
            frame = bytes(b)
            c.flush(200)
            if not c.write(frame):
                print("  %-12s 写入失败" % name)
                continue
            got = None
            t0 = time.time()
            while (time.time() - t0) * 1000 < 400:
                r = c.read(120)
                if r is None:
                    continue
                if bytes(r) == frame:
                    continue          # 回显, 忽略
                got = r
                break
            if got is None:
                print("  %-12s ck=%02X  无响应(仅回显)" % (name, ck))
            else:
                print("  %-12s ck=%02X  *** 非回显响应 %d字节: %s" % (name, ck, len(got), hexs(got)))

        print()
        print("-" * 90)
        print("阶段2: 校验和放不同位置 (sum[5..31])")
        print("-" * 90)
        base = bytearray(TOTAL)
        base[0] = RID
        base[1] = 0x10
        base[2] = 0x00
        base[3] = 0x01
        base[4] = 0x00
        s = sum(base[5:32]) & 0xFF
        for pos in (32, 31, 33, 63, 5):
            if pos >= TOTAL:
                continue
            b = bytearray(base)
            b[pos] = s
            frame = bytes(b)
            c.flush(200)
            if not c.write(frame):
                print("  pos=%2d 写入失败" % pos)
                continue
            got = None
            t0 = time.time()
            while (time.time() - t0) * 1000 < 400:
                r = c.read(120)
                if r is None:
                    continue
                if bytes(r) == frame:
                    continue
                got = r
                break
            if got is None:
                print("  pos=%2d  无响应(仅回显)" % pos)
            else:
                print("  pos=%2d  *** 非回显响应 %d字节: %s" % (pos, len(got), hexs(got)))

        print()
        print("-" * 90)
        print("阶段3: 先握手 0x11 再 0x10 (用 sum[1..31] 与 sum[5..31] 两种)")
        print("-" * 90)
        import functools
        for ckmode in ("sum[5..31]", "sum[1..31]", "sum[0..31]"):
            def mk(cmd):
                b = bytearray(TOTAL)
                b[0] = RID
                b[1] = cmd
                b[2] = 0x00
                b[3] = 0x01
                b[4] = 0x00
                if ckmode == "sum[5..31]":
                    b[32] = sum(b[5:32]) & 0xFF
                elif ckmode == "sum[1..31]":
                    b[32] = sum(b[1:32]) & 0xFF
                else:
                    b[32] = sum(b[0:32]) & 0xFF
                return bytes(b)
            c.flush(200)
            c.write(mk(0x11))
            c.flush(300)
            c.write(mk(0x10))
            got = None
            t0 = time.time()
            while (time.time() - t0) * 1000 < 600:
                r = c.read(120)
                if r is None:
                    continue
                if bytes(r) == mk(0x10) or bytes(r) == mk(0x11):
                    continue
                got = r
                break
            print("  %-12s %s" % (ckmode, ("*** " + hexs(got)) if got else "仅回显"))
    finally:
        c.close()

    print()
    print("=" * 90)
    print("结束")


if __name__ == "__main__":
    main()
