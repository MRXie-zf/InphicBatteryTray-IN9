# -*- coding: utf-8 -*-
"""
feat20: 按官方软件逆向出的真实协议读取 IN9 电量

协议(官方 Inphic IN9 GM.exe 逆向):
  通道 = Feature Report, 报告ID 0x0C, 长度 33 (0x21)
  请求 buf: [0]=0x0C [1]=0x01 [2]=0x20 [3]=0x00 [4]=seq++ [5]=0x00 [6]=0x00
  流程: SetFeature -> Sleep(10) -> GetFeature(同buf, [0]=0x0C)
  响应判定: buf[6] != 0
  解析: buf[0x0F]=ic型号  buf[0x12]=电量%  buf[0x13]=1放电/2充电  buf[0x15]=在线
        buf[8..0xB] == 'M','9','0','9'
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
hid.HidD_GetInputReport.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
hid.HidD_GetInputReport.restype = ctypes.c_bool

SEQ = [0]


def mkframe(cmd_hi, p1=0, p2=0, sel=1):
    b = bytearray(33)
    b[0] = 0x0C
    b[1] = sel
    b[2] = cmd_hi
    b[3] = 0x00
    b[4] = SEQ[0] & 0xFF
    SEQ[0] += 1
    b[5] = p1
    b[6] = p2
    return bytes(b)


def exch(h, req, sleep_ms=10, tries=3):
    """SetFeature -> Sleep -> GetFeature, 返回 (ok, resp)"""
    last = None
    for t in range(tries):
        rb = ctypes.create_string_buffer(req, 33)
        if not hid.HidD_SetFeature(h, rb, 33):
            return (False, None, "SetFeature失败 err=%d" % ctypes.get_last_error())
        time.sleep(sleep_ms / 1000.0)
        gb = ctypes.create_string_buffer(33)
        gb[0] = b"\x0C"
        if not hid.HidD_GetFeature(h, gb, 33):
            return (False, None, "GetFeature失败 err=%d" % ctypes.get_last_error())
        r = bytes(gb[:33])
        last = r
        if r[6] != 0:
            return (True, r, None)
    return (False, last, "3次尝试后 buf[6] 仍为 0")


def probe(d, tag=""):
    h = k32.CreateFileW(d.path, D.GENERIC_READ | D.GENERIC_WRITE, 3, None, 3, 0, None)
    if h == D.INVALID_HANDLE_VALUE or h is None:
        h = k32.CreateFileW(d.path, D.GENERIC_READ, 3, None, 3, 0, None)
    if h == D.INVALID_HANDLE_VALUE or h is None:
        print("   [打不开 err=%d]" % ctypes.get_last_error())
        return False
    ok_any = False
    try:
        for sel in (1, 0):
            for cmd in (0x20, 0xF0):
                p1, p2 = (0x01, 0x01) if cmd == 0xF0 else (0x00, 0x00)
                req = mkframe(cmd, p1, p2, sel)
                ok, r, err = exch(h, req)
                if err:
                    print("   sel=%d cmd=%02X  %s" % (sel, cmd, err))
                    continue
                ok_any = True
                print("   sel=%d cmd=%02X  响应: %s" % (sel, cmd, D.hexs(r)))
                if cmd == 0x20 and r[2] == 0x20:
                    magic = "".join(chr(x) for x in r[8:12]) if all(32 <= x < 127 for x in r[8:12]) else "?"
                    st = r[0x13]
                    lv = r[0x12] if st != 2 else 100
                    print("      >>> 魔数=%s  IC=0x%02X  电量=%d%%  状态=%s  在线=%s"
                          % (magic, r[0x0F], lv,
                             {1: "放电", 2: "充电中"}.get(st, str(st)),
                             bool(r[0x15])))
    finally:
        k32.CloseHandle(h)
    return ok_any


def main():
    devs = D.enumerate_hids()
    tg = [d for d in devs if d.vid in (0x248A, 0x249A)]
    print("=" * 88)
    print("IN9 真实协议读取 (Feature Report ID=0x0C, 33字节)")
    print("=" * 88)
    for d in tg:
        print("  %s" % d)
    print()
    hit = False
    for d in tg:
        print("-" * 88)
        print("接口 %s" % d)
        hit = probe(d) or hit
    print()
    print("=" * 88)
    print("结果: %s" % ("读到数据" if hit else "全部失败"))
    print("=" * 88)


if __name__ == "__main__":
    main()
