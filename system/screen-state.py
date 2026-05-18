#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screen-state.py — Cross-platform desktop state monitor daemon.
macOS: uses osascript + subprocess. Windows: falls back to Win32 APIs.
Outputs JSON lines to stdout on every state change or heartbeat (2s).
"""
import sys, os, json, time, platform, subprocess

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

IS_MAC = platform.system() == 'Darwin'
IS_WIN = platform.system() == 'Windows'

def get_mac_state():
    try:
        script = '''tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            set allApps to name of every application process whose visible is true
        end tell
        return frontApp & "|" & (allApps as string)'''
        result = subprocess.run(['osascript', '-e', script],
                                capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            parts = result.stdout.strip().split('|', 1)
            foreground = parts[0].strip() if parts else ''
            windows_raw = parts[1].strip() if len(parts) > 1 else ''
            windows = [w.strip() for w in windows_raw.split(',') if w.strip()]
            return {'foreground': foreground, 'windows': windows}
    except Exception:
        pass
    return {'foreground': '', 'windows': []}

def get_cursor_mac():
    try:
        script = 'tell application "System Events" to get position of mouse'
        result = subprocess.run(['osascript', '-e', script],
                                capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            coords = result.stdout.strip().split(',')
            if len(coords) == 2:
                return {'x': int(coords[0].strip()), 'y': int(coords[1].strip())}
    except Exception:
        pass
    return {'x': 0, 'y': 0}

def get_win_state():
    try:
        import ctypes, ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return {'foreground': buf.value, 'windows': [buf.value]}
    except Exception:
        return {'foreground': '', 'windows': []}

last_state = {}

def emit(state):
    global last_state
    if state != last_state:
        print(json.dumps(state), flush=True)
        last_state = state

while True:
    try:
        if IS_MAC:
            s = get_mac_state()
            cursor = get_cursor_mac()
        elif IS_WIN:
            s = get_win_state()
            cursor = {'x': 0, 'y': 0}
        else:
            s = {'foreground': '', 'windows': []}
            cursor = {'x': 0, 'y': 0}

        state = {
            'type': 'state',
            'ts': int(time.time() * 1000),
            'foreground': s.get('foreground', ''),
            'windows': s.get('windows', []),
            'cursor': cursor,
            'platform': platform.system()
        }
        emit(state)
    except Exception as e:
        print(json.dumps({'type': 'error', 'msg': str(e)}), flush=True)

    time.sleep(2)
