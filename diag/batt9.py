# -*- coding: utf-8 -*-
"""
batt9: IN9 电量读取 (最终验证版)
协议来自官方 Inphic IN9 GM.exe 逆向:
  Feature Report, 报告ID 0x0C, 33字节
  握手: [0]=0C [1]=01 [2]=F0 [3]=00 [4]=seq [5]=01 [6]=01 [7]=FF   (Set only)
  查询: [0]=0C [1]=01 [2]=20 [3]=00 [4]=seq [5]=00 [6]=00
        Set -> Sleep(10ms) -> Get
  响应: [2]=20 回显, [6]!=0 有效, [8..B]='M909', [0x0F]=IC,
        [0x12]=电量%, [0x13]=1正常/2充电, [0x15]=在线
"""
import sys
import time
import ctypes
sys.path.insert(0, '.')
import diag as D

k32 = D.k32
hid = D.hid
hid.HidD_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
hid.HidD_SetFeature.restype = ctypes.c_bool
hid.HidD_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
hid.HidD_GetFeature.restype = ctypes.c_bool

seq = [0]


def frame(cmd, b1=1, b5=0, b6=0, b7=None):
    b = bytearray(33)
    b[0] = 0x0C
    b[1] = b1
    b[2] = cmd
    b[3] = 0x00
    b[4] = seq[0] & 0xFF
    seq[0] = (seq[0] + 1) & 0xFF
    b[5] = b5
    b[6] = b6
    if b7 is not None:
        b[7] = b7
    return bytes(b)


def setf(h, req):
    rb = ctypes.create_string_buffer(req, 33)
    return hid.HidD_SetFeature(h, rb, 33)


def getf(h):
    gb = ctypes.create_string_buffer(33)
    gb[0] = b"\x0C"
    if not hid.HidD_GetFeature(h, gb, 33):
        return None
    return bytes(gb[:33])


def query(h, handshake=True, tries=4):
    if handshake:
        setf(h, frame(0xF0, b1=1, b5=1, b6=1, b7=0xFF))
        time.sleep(0.02)
    last = None
    for _ in range(tries):
        setf(h, frame(0x20, b1=1))
        time.sleep(0.02)
        r = getf(h)
        if r is None:
            return None
        last = r
        if r[6] != 0:
            return r
    return last


def main():
    devs = D.enumerate_hids()
    tg = [d for d in devs if d.vid in (0x248A, 0x249A) and getattr(d, 'featlen', 33) == 33]
    if not tg:
        tg = [d for d in devs if d.vid in (0x248A, 0x249A)]
    print("=" * 84)
    print("IN9 电量读取 - 最终验证")
    print("=" * 84)

    best = None
    for d in tg:
        h = k32.CreateFileW(d.path, D.GENERIC_READ | D.GENERIC_WRITE, 3, None, 3, 0, None)
        if h == D.INVALID_HANDLE_VALUE or h is None:
            continue
        try:
            for hs in (True, False):
                r = query(h, hs)
                if r is None:
                    continue
                print()
                print("接口 %s" % d)
                print("  握手=%s" % hs)
                print("  原始: %s" % D.hexs(r))
                if r[2] != 0x20:
                    print("  (buf[2]=%02X 不是 0x20 回显, 跳过)" % r[2])
                    continue
                magic = bytes(r[8:12]).decode('latin1')
                lv = r[0x12]
                st = r[0x13]
                on = r[0x15]
                print("  型号魔数=%s  IC=0x%02X" % (magic, r[0x0F]))
                print("  buf[0x12]=%d  buf[0x13]=%d  buf[0x15]=%d  buf[0x10]=%d  buf[0x11]=%d"
                      % (lv, st, on, r[0x10], r[0x11]))
                print("  >>> 电量 = %d%%   状态 = %s   在线 = %s"
                      % (100 if st == 2 else lv,
                         {0: "未知/离线", 1: "正常(放电)", 2: "充电中"}.get(st, str(st)),
                         bool(on)))
                if best is None:
                    best = (d, r)
        finally:
            k32.CloseHandle(h)
        if best:
            break

    print()
    print("=" * 84)
    if best:
        print("成功: 目标接口 = %s" % best[0])
    else:
        print("未读到")
    print("=" * 84)


if __name__ == "__main__":
    main()
