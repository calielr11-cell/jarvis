#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS Clipboard Intelligence Daemon — Cross-platform.
macOS: uses pbpaste. Windows: uses Win32 clipboard API.
Monitors clipboard changes and classifies content in real-time.
Outputs JSON lines to stdout.
"""
import sys, json, re, time, platform, subprocess, signal

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

IS_MAC = platform.system() == 'Darwin'
IS_WIN = platform.system() == 'Windows'

def classify(text):
    if not text:
        return 'empty'
    if re.search(r'https?://', text):
        return 'url'
    if re.search(r'\b(def |class |import |function |const |var |let )\b', text):
        return 'code'
    if re.search(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b', text):
        return 'date'
    if re.search(r'\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b', text, re.I):
        return 'email'
    if len(text) > 200:
        return 'text_long'
    return 'text'

def get_clipboard_mac():
    try:
        result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=2)
        return result.stdout if result.returncode == 0 else ''
    except Exception:
        return ''

def get_clipboard_win():
    try:
        import ctypes, ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        CF_UNICODETEXT = 13
        if not user32.OpenClipboard(None):
            return ''
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ''
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return ''
            text = ctypes.wstring_at(ptr)
            kernel32.GlobalUnlock(handle)
            return text
        finally:
            user32.CloseClipboard()
    except Exception:
        return ''

def running():
    return True

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

last_text = None

while True:
    try:
        if IS_MAC:
            text = get_clipboard_mac()
        elif IS_WIN:
            text = get_clipboard_win()
        else:
            time.sleep(5)
            continue

        if text != last_text:
            last_text = text
            kind = classify(text)
            preview = text[:120].replace('\n', ' ') if text else ''
            print(json.dumps({
                'type': 'clipboard',
                'ts': int(time.time() * 1000),
                'kind': kind,
                'len': len(text),
                'preview': preview
            }), flush=True)
    except Exception as e:
        print(json.dumps({'type': 'error', 'msg': str(e)}), flush=True)

    time.sleep(1)
