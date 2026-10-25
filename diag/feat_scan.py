# -*- coding: utf-8 -*-
"""
Feature Report 穷举: 对所有 feat>0 的 248A 接口, 试报告ID 0-255 的 HidD_GetFeature
(之前只试了 0-8)。SetFeature 已知在 rid=5(mi_02) / rid=7(feat=8) 上能成功。
另测: SetFeature 发命令后, 用 ReadFile 看有没有响应。
"""
import sys
import time
import ctypes
sys.path.insert(0, '.')
import diag as D

k32 = D.k32
hid = D.hid
hid.HidD_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
hid.HidD_SetFeature.restype = D.wt.BOOL
hid.HidD_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
hid.HidD_GetFeature.restype = D.wt.BOOL


def caps_of(path):
    h = k32.CreateFileW(path, 0, 3, None, 3, 0, None)
    if h == D.INVALID_HANDLE_VALUE or h is None:
        return None
    try:
        pp = ctypes.c_void_p()
        if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)) or not pp:
            return None
        try:
            c = D.HIDP_CAPS()
            if hid.HidP_GetCaps(pp, ctypes.byref(c)) == D.HIDP_STATUS_SUCCESS:
                return (c.InputReportByteLength, c.OutputReportByteLength,
                        c.FeatureReportByteLength, c.UsagePage)
        finally:
            hid.HidD_FreePreparsedData(pp)
    finally:
        k32.CloseHandle(h)
    return None


def main():
    devs = D.enumerate_hids()
    for d in devs:
        if d.vid != 0x248A:
            continue
        cp = caps_of(d.path)
        if not cp or cp[2] <= 0:
            continue
        feat = cp[2]
        print("=" * 70)
        print("接口 %s  feat=%d up=0x%04X" % (d, feat, cp[3]))
        h = k32.CreateFileW(d.path, D.GENERIC_READ | D.GENERIC_WRITE, 3, None, 3, 0, None)
        if h == D.INVALID_HANDLE_VALUE or h is None:
            print("  打开失败 err=%d" % ctypes.get_last_error())
            continue
        ok_ids = []
        try:
            for rid in range(256):
                buf = ctypes.create_string_buffer(feat)
                buf[0] = rid
                if hid.HidD_GetFeature(h, buf, feat):
                    raw = bytes(buf[:feat])
                    ok_ids.append(rid)
                    print("  GetFeature rid=0x%02X 成功: %s" % (rid, D.hexs(raw[:min(feat, 40)])))
        finally:
            k32.CloseHandle(h)
        if not ok_ids:
            print("  GetFeature 全部失败 (rid 0-255)")
        else:
            print("  可用报告ID: %s" % ", ".join("0x%02X" % r for r in ok_ids))

    # 附加: SetFeature(0x10) 后用 ReadFile 听
    print("\n" + "=" * 70)
    print("附加: SetFeature 发 0x10 后用 ReadFile 监听")
    for d in devs:
        if d.vid != 0x248A or d.mi != 0x02:
            continue
        cp = caps_of(d.path)
        if not cp:
            continue
        feat = cp[2]
        h = k32.CreateFileW(d.path, D.GENERIC_READ | D.GENERIC_WRITE, 3, None, 3,
                            D.FILE_FLAG_OVERLAPPED, None)
        ev = k32.CreateEventW(None, True, False, None)
        ov = D.OVERLAPPED()
        ov.hEvent = ev
        rb = ctypes.create_string_buffer(256)
        print("\n-- %s --" % d)
        for rid in (5, 0, 1):
            data = bytearray(feat)
            data[0] = rid
            data[1] = 0x00
            data[2] = 0x10
            data[3] = 0x00
            data[4] = 0x01
            if feat > 33:
                data[33] = sum(data[6:33]) & 0xFF
            ok = hid.HidD_SetFeature(h, ctypes.create_string_buffer(bytes(data), feat), feat)
            print("  SetFeature(rid=0x%02X, cmd=0x10): %s err=%d" % (rid, ok, ctypes.get_last_error()))
            if not ok:
                continue
            t0 = time.time()
            while time.time() - t0 < 1.0:
                k32.ResetEvent(ev)
                rn = ctypes.c_uint32(0)
                r = k32.ReadFile(h, rb, 256, ctypes.byref(rn), ctypes.byref(ov))
                if r and rn.value > 0:
                    print("     读到 %d 字节: %s" % (rn.value, D.hexs(bytes(rb[:rn.value])[:40])))
                    break
                if r:
                    continue
                if ctypes.get_last_error() != 997:
                    break
                rc = k32.WaitForSingleObject(ev, 200)
                g = ctypes.c_uint32(0)
                if rc == 0:
                    if k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(g), False) and g.value > 0:
                        print("     读到 %d 字节: %s" % (g.value, D.hexs(bytes(rb[:g.value])[:40])))
                        break
                else:
                    k32.CancelIoEx(h, ctypes.byref(ov))
                    k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(g), True)
        try:
            g = ctypes.c_uint32(0)
            k32.CancelIoEx(h, ctypes.byref(ov))
            k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(g), True)
        except Exception:
            pass
        k32.CloseHandle(ev)
        k32.CloseHandle(h)


if __name__ == "__main__":
    main()
