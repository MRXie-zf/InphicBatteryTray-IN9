# -*- coding: utf-8 -*-
"""
最后三种时序变体 (在鼠标本体 5B2E 上):
 A. 先挂起读, 再发命令 —— 捕获"立即响应"的正确姿势
 B. 连发两次命令再读
 C. 握手 -> 等1秒 -> 查询 -> 等1秒 -> 读
"""
import sys
import time
import ctypes
sys.path.insert(0, '.')
import diag as D

k32 = D.k32
LEN = 64
RID = 0x05

T = None
for d in D.enumerate_hids():
    if d.vid == 0x248A and d.pid == 0x5B2E and d.mi == 0x02:
        T = d.path
if not T:
    print("未找到鼠标本体 5B2E (请插 USB 线)")
    sys.exit(1)


def mk(cmd):
    b = bytearray(LEN)
    b[0] = RID
    b[1] = cmd
    b[2] = 0x00
    b[3] = 0x01
    b[4] = 0x00
    b[32] = sum(b[5:32]) & 0xFF
    return bytes(b)


class Sess(object):
    def __init__(self):
        self.h = k32.CreateFileW(T, D.GENERIC_READ | D.GENERIC_WRITE, 3, None, 3,
                                 D.FILE_FLAG_OVERLAPPED, None)
        self.ev = k32.CreateEventW(None, True, False, None)
        self.ov = D.OVERLAPPED()
        self.ov.hEvent = self.ev
        self.buf = ctypes.create_string_buffer(LEN)

    def post_read(self):
        k32.ResetEvent(self.ev)
        rn = ctypes.c_uint32(0)
        r = k32.ReadFile(self.h, self.buf, LEN, ctypes.byref(rn), ctypes.byref(self.ov))
        if r:
            return bytes(self.buf[:rn.value])
        ctypes.set_last_error(0)
        return None   # pending

    def wait_read(self, ms):
        rc = k32.WaitForSingleObject(self.ev, ms)
        g = ctypes.c_uint32(0)
        if rc == 0 and k32.GetOverlappedResult(self.h, ctypes.byref(self.ov), ctypes.byref(g), False):
            return bytes(self.buf[:g.value])
        return None

    def write(self, data):
        k32.ResetEvent(self.ev)
        wn = ctypes.c_uint32(0)
        r = k32.WriteFile(self.h, ctypes.create_string_buffer(data, LEN), LEN, ctypes.byref(wn), ctypes.byref(self.ov))
        if r:
            return True
        if ctypes.get_last_error() != 997:
            return False
        rc = k32.WaitForSingleObject(self.ev, 800)
        g = ctypes.c_uint32(0)
        return rc == 0 and k32.GetOverlappedResult(self.h, ctypes.byref(self.ov), ctypes.byref(g), False)

    def read(self, ms=250):
        k32.ResetEvent(self.ev)
        rn = ctypes.c_uint32(0)
        r = k32.ReadFile(self.h, self.buf, LEN, ctypes.byref(rn), ctypes.byref(self.ov))
        if r:
            return bytes(self.buf[:rn.value])
        if ctypes.get_last_error() != 997:
            return None
        rc = k32.WaitForSingleObject(self.ev, ms)
        g = ctypes.c_uint32(0)
        if rc == 0 and k32.GetOverlappedResult(self.h, ctypes.byref(self.ov), ctypes.byref(g), False):
            return bytes(self.buf[:g.value])
        return None

    def close(self):
        try:
            g = ctypes.c_uint32(0)
            k32.CancelIoEx(self.h, ctypes.byref(self.ov))
            k32.GetOverlappedResult(self.h, ctypes.byref(self.ov), ctypes.byref(g), True)
        except Exception:
            pass
        k32.CloseHandle(self.ev)
        k32.CloseHandle(self.h)


def show(tag, f, data):
    if f is None:
        print("   %s: 无帧" % tag)
    elif bytes(f) == bytes(data):
        print("   %s: 回显 %s" % (tag, D.hexs(f[:20])))
    else:
        print("   %s: ★数据 %s" % (tag, D.hexs(f[:40])))


print("=== A. 先挂起读, 再发命令 ===")
s = Sess()
data = mk(0x10)
pre = s.post_read()          # 先挂起
time.sleep(0.02)
ok = s.write(data)
print("   写入: %s" % ok)
f = pre if pre is not None else s.wait_read(600)
show("A", f, data)
# 再看后续
for i in range(3):
    f = s.read(250)
    if f is None:
        break
    show("A-后续%d" % (i + 1), f, data)
s.close()

print("\n=== B. 连发两次 0x10 再读 ===")
s = Sess()
s.write(data)
time.sleep(0.05)
s.write(data)
for i in range(3):
    f = s.read(300)
    if f is None:
        break
    show("B-%d" % (i + 1), f, data)
s.close()

print("\n=== C. 握手 -> 等1s -> 查询 -> 等1s -> 读 ===")
s = Sess()
s.write(mk(0x11))
time.sleep(1.0)
s.write(data)
time.sleep(1.0)
for i in range(3):
    f = s.read(300)
    if f is None:
        break
    show("C-%d" % (i + 1), f, data)
s.close()
print("\n完成")
