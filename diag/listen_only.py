# -*- coding: utf-8 -*-
"""
纯监听: 不发任何命令, 在所有 248A 接口上听 15 秒
目的: 找设备是否周期性主动上报 (IN10 就是靠 5 字节推送报文)
运行期间请晃动鼠标/按键, 唤醒设备
"""
import sys
import time
import ctypes
sys.path.insert(0, '.')
import diag as D

k32 = D.k32


def main():
    secs = 15
    if len(sys.argv) > 1:
        try:
            secs = int(sys.argv[1])
        except ValueError:
            pass

    devs = D.enumerate_hids()
    ls = []
    for d in devs:
        if d.vid != 0x248A:
            continue
        if d.inlen <= 0:
            continue
        h = k32.CreateFileW(d.path, D.GENERIC_READ, 3, None, 3, D.FILE_FLAG_OVERLAPPED, None)
        if h == D.INVALID_HANDLE_VALUE or h is None:
            print("[跳过] %s (打不开 err=%d)" % (d, ctypes.get_last_error()))
            continue
        ev = k32.CreateEventW(None, True, False, None)
        ov = D.OVERLAPPED()
        ov.hEvent = ev
        ls.append((d, h, ev, ov, ctypes.create_string_buffer(d.inlen), d.inlen))

    print("监听 %d 个接口, 持续 %d 秒 (请晃动鼠标/按键)" % (len(ls), secs))
    for (d, h, ev, ov, buf, L) in ls:
        print("  %s" % d)
    print()

    total = 0
    t0 = time.time()
    while time.time() - t0 < secs:
        for (d, h, ev, ov, buf, L) in ls:
            k32.ResetEvent(ev)
            rn = ctypes.c_uint32(0)
            r = k32.ReadFile(h, buf, L, ctypes.byref(rn), ctypes.byref(ov))
            if r:
                total += 1
                print("[%5.1fs] %s -> %d字节: %s"
                      % (time.time() - t0, d.product, rn.value, D.hexs(bytes(buf[:rn.value]))))
                sys.stdout.flush()
                continue
            if ctypes.get_last_error() != 997:
                continue
            rc = k32.WaitForSingleObject(ev, 150)
            g = ctypes.c_uint32(0)
            if rc == 0:
                if k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(g), False) and g.value > 0:
                    total += 1
                    print("[%5.1fs] %s -> %d字节: %s"
                          % (time.time() - t0, d.product, g.value, D.hexs(bytes(buf[:g.value]))))
                    sys.stdout.flush()
            else:
                k32.CancelIoEx(h, ctypes.byref(ov))
                k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(g), True)

    print("\n共收到 %d 帧" % total)
    for (d, h, ev, ov, buf, L) in ls:
        k32.CloseHandle(ev)
        k32.CloseHandle(h)


if __name__ == "__main__":
    main()
