#!/usr/bin/env python3
"""
JARVIS Voice Interface — macOS (ffmpeg + Whisper + say)
Roda FORA do Claude Code, direto do Terminal.app para ter acesso ao microfone.
"""
import subprocess, threading, time, os, sys, json, urllib.request, tempfile

JARVIS_URL = "http://localhost:3000"
DOTENV_PATH = os.path.expanduser("~/Downloads/jarvis iz 2.0/.env")
FFMPEG = "/opt/homebrew/bin/ffmpeg"
AUDIO_FILE = "/tmp/jarvis_voice.wav"

# ─── Carregar chave OpenAI ────────────────────────────────────────────────────
def load_openai_key():
    try:
        with open(DOTENV_PATH) as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except:
        pass
    return os.environ.get("OPENAI_API_KEY", "")

OPENAI_KEY = load_openai_key()

# ─── Encontrar microfone disponível ───────────────────────────────────────────
def find_mic_device():
    """Detecta qual dispositivo de microfone usar (0 = externo, 1 = MacBook)"""
    try:
        result = subprocess.run(
            [FFMPEG, "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=5
        )
        output = result.stderr
        # Preferir Iz Caliel (iPhone/iPad via Continuity) se disponível
        if "Iz Caliel" in output:
            return "0"
        return "1"  # MacBook Air built-in
    except:
        return "0"

MIC_DEVICE = find_mic_device()

# ─── Gravação de áudio ────────────────────────────────────────────────────────
def record(seconds=5, device=None):
    """Grava N segundos via ffmpeg AVFoundation"""
    dev = device or MIC_DEVICE
    if os.path.exists(AUDIO_FILE):
        os.remove(AUDIO_FILE)

    cmd = [
        FFMPEG, "-y",
        "-f", "avfoundation",
        "-framerate", "30",
        "-i", f":{dev}",
        "-t", str(seconds),
        "-ar", "16000",
        "-ac", "1",
        "-f", "wav",
        AUDIO_FILE
    ]

    print(f"🎤 Gravando {seconds}s... fale agora! (mic:{dev})")
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=seconds + 8
        )
        if os.path.exists(AUDIO_FILE) and os.path.getsize(AUDIO_FILE) > 2000:
            print(f"✅ Gravação OK ({os.path.getsize(AUDIO_FILE)} bytes)")
            return True
        else:
            print(f"❌ Arquivo inválido: {os.path.getsize(AUDIO_FILE) if os.path.exists(AUDIO_FILE) else 'não existe'} bytes")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Timeout na gravação")
        return False
    except Exception as e:
        print(f"❌ Erro gravação: {e}")
        return False

# ─── Transcrição Whisper ──────────────────────────────────────────────────────
def transcribe():
    if not OPENAI_KEY or OPENAI_KEY == "COLE_SUA_CHAVE_AQUI":
        print("❌ Chave OpenAI não configurada")
        return None

    try:
        with open(AUDIO_FILE, 'rb') as f:
            audio_data = f.read()

        boundary = "----JARVISBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode() + audio_data + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="model"\r\n\r\nwhisper-1'
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="language"\r\n\r\npt'
            f"\r\n--{boundary}--\r\n"
        ).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": f"multipart/form-data; boundary={boundary}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            text = result.get("text", "").strip()
            if text:
                print(f"📝 Transcrição: {text}")
            return text

    except Exception as e:
        print(f"❌ Whisper: {e}")
        return None

# ─── Enviar ao JARVIS ─────────────────────────────────────────────────────────
def send_to_jarvis(message):
    try:
        data = json.dumps({
            "message": message,
            "language": "BR",
            "fromVoice": True
        }).encode()

        req = urllib.request.Request(
            f"{JARVIS_URL}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        response_text = ""
        with urllib.request.urlopen(req, timeout=60) as resp:
            while True:
                chunk = resp.read(1024)
                if not chunk:
                    break
                response_text += chunk.decode('utf-8', errors='ignore')

        return response_text.strip()
    except Exception as e:
        print(f"❌ JARVIS: {e}")
        return None

# ─── TTS ──────────────────────────────────────────────────────────────────────
def speak(text):
    if not text:
        return
    clean = text.replace('"', "'")
    # Primeira frase apenas (resposta de voz rápida)
    sentences = [s.strip() for s in clean.split('.') if len(s.strip()) > 8]
    speak_text = sentences[0] if sentences else clean[:200]
    try:
        subprocess.run(['say', '-v', 'Luciana', speak_text], timeout=15)
    except:
        pass

# ─── Ciclo único ─────────────────────────────────────────────────────────────
def run_once(seconds=5):
    print("\n" + "="*50)
    print("🎤 JARVIS — Ciclo de Voz")
    print("="*50)

    if not record(seconds):
        print("❌ Falhou ao gravar — verifique permissão do microfone")
        print("   Abra: System Settings → Privacy → Microphone → Terminal ✓")
        return

    text = transcribe()
    if not text:
        print("❌ Nada transcrito (silêncio ou erro)")
        return

    print("⚡ Enviando ao JARVIS...")
    response = send_to_jarvis(text)
    if response:
        print(f"🤖 JARVIS: {response[:300]}")
        speak(response)

# ─── Modo contínuo com wake word ─────────────────────────────────────────────
def continuous():
    print("\n🟢 JARVIS Voice Interface — Modo Contínuo")
    print(f"   Microfone: dispositivo :{MIC_DEVICE}")
    print("   Diga 'JARVIS' para ativar | Ctrl+C para sair\n")

    while True:
        try:
            print("👂 Escutando wake word... (3s)")
            if record(3):
                text = transcribe()
                if text and 'jarvis' in text.lower():
                    speak("Sim, senhor?")
                    print("✅ Wake word! Gravando comando...")
                    time.sleep(0.3)
                    if record(6):
                        cmd_text = transcribe()
                        if cmd_text:
                            print("⚡ Enviando ao JARVIS...")
                            response = send_to_jarvis(cmd_text)
                            if response:
                                print(f"🤖 {response[:300]}")
                                speak(response)
                elif text:
                    print(f"   (ignorado: '{text[:50]}')")
        except KeyboardInterrupt:
            print("\n👋 Encerrando JARVIS Voice...")
            break
        except Exception as e:
            print(f"Erro: {e}")
            time.sleep(1)

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🔍 Microfone detectado: dispositivo :{MIC_DEVICE}")
    print(f"🔑 OpenAI Key: {'OK' if OPENAI_KEY and len(OPENAI_KEY) > 20 else 'NÃO CONFIGURADA'}")
    print(f"🤖 JARVIS URL: {JARVIS_URL}")

    if "--test" in sys.argv:
        run_once(4)
    elif "--continuous" in sys.argv or "-c" in sys.argv:
        continuous()
    else:
        run_once(5)
