# -*- coding: utf-8 -*-
"""
新通道: Feature Report, 报告ID=0x0C, 33 字节 (up=0xFF00 接口)
按协议文档的 33 字节帧布局:
  [0]=报告ID(0x0C) [1]=命令码 [2]=00 [3]=01 [4]=载荷长 [5..31]=载荷 [32]=校验和
操作: SetFeature(请求) -> 等一会 -> GetFeature(读响应)
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

LEN = 33
RID = 0x0C


def mk(cmd, plen=0x00, payload=b""):
    b = bytearray(LEN)
    b[0] = RID
    b[1] = cmd
    b[2] = 0x00
    b[3] = 0x01
    b[4] = plen
    for i, x in enumerate(payload[:27]):
        b[5 + i] = x
    b[32] = sum(b[5:32]) & 0xFF
    return bytes(b)


def find_targets():
    """返回所有 feat=33 且 up=0xFF00 的 248A 接口"""
    out = []
    for d in D.enumerate_hids():
        if d.vid != 0x248A:
            continue
        h = k32.CreateFileW(d.path, 0, 3, None, 3, 0, None)
        if h == D.INVALID_HANDLE_VALUE or h is None:
            continue
        try:
            pp = ctypes.c_void_p()
            if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)) and pp:
                try:
                    c = D.HIDP_CAPS()
                    if hid.HidP_GetCaps(pp, ctypes.byref(c)) == D.HIDP_STATUS_SUCCESS:
                        if c.FeatureReportByteLength == 33 and c.UsagePage == 0xFF00:
                            out.append(d)
                finally:
                    hid.HidD_FreePreparsedData(pp)
        finally:
            k32.CloseHandle(h)
    return out


def session(d, cmd, delay=0.15):
    h = k32.CreateFileW(d.path, D.GENERIC_READ | D.GENERIC_WRITE, 3, None, 3, 0, None)
    if h == D.INVALID_HANDLE_VALUE or h is None:
        return None, None
    try:
        data = mk(cmd)
        sb = ctypes.create_string_buffer(data, LEN)
        ok = hid.HidD_SetFeature(h, sb, LEN)
        e1 = ctypes.get_last_error()
        if not ok:
            return (False, e1), None
        time.sleep(delay)
        rb = ctypes.create_string_buffer(LEN)
        rb[0] = RID
        r2 = hid.HidD_GetFeature(h, rb, LEN)
        e2 = ctypes.get_last_error()
        if not r2:
            return (True, 0), None
        return (True, 0), bytes(rb[:LEN])
    finally:
        k32.CloseHandle(h)


def main():
    ts = find_targets()
    print("找到 %d 个 feat=33/up=0xFF00 接口" % len(ts))
    for t in ts:
        print("  %s" % t)
    if not ts:
        return

    for t in ts:
        print("\n" + "=" * 70)
        print("设备: %s" % t)
        # 1) 直接 GetFeature (不先写命令) 看基线
        h = k32.CreateFileW(t.path, D.GENERIC_READ | D.GENERIC_WRITE, 3, None, 3, 0, None)
        rb = ctypes.create_string_buffer(LEN)
        rb[0] = RID
        if hid.HidD_GetFeature(h, rb, LEN):
            print("  基线 GetFeature: %s" % D.hexs(bytes(rb[:LEN])))
        k32.CloseHandle(h)

        # 2) 依次发命令
        for cmd in (0x11, 0x10, 0x12, 0x13, 0x15, 0x16, 0x17, 0x20):
            st, resp = session(t, cmd)
            if st is None or not st[0]:
                print("  cmd=0x%02X SetFeature 失败 err=%s" % (cmd, st[1] if st else "?"))
                continue
            if resp is None:
                print("  cmd=0x%02X Set成功但 GetFeature 失败" % cmd)
                continue
            nz = any(resp[1:])
            print("  cmd=0x%02X -> %s%s" % (cmd, D.hexs(resp), "" if nz else "   (全零)"))
            if nz:
                # 按文档解析: frame[0x0A]=ic frame[0x0C]=充电 frame[0x0D]=电量 frame[0x0E]=在线
                print("       frame[0x0A]=%d(ic) [0x0C]=%d(充电) [0x0D]=%d(电量) [0x0E]=%d(在线)"
                      % (resp[0x0A], resp[0x0C], resp[0x0D], resp[0x0E]))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
