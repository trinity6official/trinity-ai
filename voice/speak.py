import os
import requests
import tempfile
from datetime import datetime

class TrinityVoice:
    """
    Trinity Voice System
    Text to speech in Tamil and English
    Before hardware: Sends text to Telegram
    After hardware: Full live voice via XTTS
    Detects language automatically
    """
    
    def __init__(self, telegram_token=None, chat_id=None):
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.hardware_mode = False
        self.tts_engine = None
        self.check_hardware()
    
    def check_hardware(self):
        """Check if running on hardware with GPU"""
        try:
            import torch
            if torch.cuda.is_available():
                self.hardware_mode = True
                print("Trinity Voice: GPU detected - Full voice mode")
            else:
                self.hardware_mode = False
                print("Trinity Voice: No GPU - Text mode")
        except ImportError:
            self.hardware_mode = False
            print("Trinity Voice: Text mode active")
    
    # ==========================================
    # BEFORE HARDWARE - TEXT MODE
    # ==========================================
    
    def send_text(self, message, language='english'):
        """Send text message to Telegram"""
        if not self.telegram_token or not self.chat_id:
            print(message)
            return
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        
        chunks = [
            message[i:i+4000]
            for i in range(0, len(message), 4000)
        ]
        
        for chunk in chunks:
            payload = {
                "chat_id": self.chat_id,
                "text": chunk
            }
            try:
                requests.post(url, json=payload, timeout=10)
            except Exception as e:
                print(f"Telegram error: {str(e)}")
    
    def send_voice_note_gtts(self, text, language='english'):
        """
        Generate and send voice note using gTTS
        Works before full hardware arrives
        Tamil and English supported
        """
        try:
            from gtts import gTTS
            import io
            
            lang_code = 'ta' if language == 'tamil' else 'en'
            
            tts = gTTS(text=text, lang=lang_code, slow=False)
            
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendVoice"
            
            files = {'voice': ('voice.mp3', audio_buffer, 'audio/mpeg')}
            data = {'chat_id': self.chat_id}
            
            response = requests.post(
                url, files=files, data=data, timeout=30
            )
            
            if response.status_code == 200:
                print("Voice note sent successfully")
                return True
            else:
                print(f"Voice send failed: {response.status_code}")
                self.send_text(text, language)
                return False
                
        except ImportError:
            print("gTTS not installed. Sending text instead.")
            self.send_text(text, language)
            return False
        except Exception as e:
            print(f"Voice error: {str(e)}")
            self.send_text(text, language)
            return False
    
    # ==========================================
    # AFTER HARDWARE - FULL VOICE MODE
    # ==========================================
    
    def setup_xtts(self):
        """
        Setup XTTS v2 for natural voice
        Runs on RTX 4060 GPU
        Supports Tamil and English natively
        """
        try:
            from TTS.api import TTS
            
            print("Loading XTTS v2 model...")
            self.tts_engine = TTS(
                "tts_models/multilingual/multi-dataset/xtts_v2"
            ).to("cuda")
            
            print("XTTS v2 loaded successfully")
            return True
            
        except Exception as e:
            print(f"XTTS setup error: {str(e)}")
            return False
    
    def speak_xtts(self, text, language='english',
                    output_file=None):
        """
        Generate natural speech using XTTS v2
        Best quality Tamil and English voice
        Runs locally on RTX 4060
        """
        if not self.tts_engine:
            if not self.setup_xtts():
                return self.send_voice_note_gtts(
                    text, language
                )
        
        try:
            lang_code = 'ta' if language == 'tamil' else 'en'
            
            if not output_file:
                output_file = tempfile.mktemp(suffix='.wav')
            
            self.tts_engine.tts_to_file(
                text=text,
                language=lang_code,
                file_path=output_file
            )
            
            self.send_voice_telegram(output_file)
            
            if os.path.exists(output_file):
                os.remove(output_file)
            
            return True
            
        except Exception as e:
            print(f"XTTS error: {str(e)}")
            return self.send_voice_note_gtts(text, language)
    
    def send_voice_telegram(self, audio_file):
        """Send audio file to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendVoice"
            
            with open(audio_file, 'rb') as f:
                files = {'voice': f}
                data = {'chat_id': self.chat_id}
                response = requests.post(
                    url, files=files,
                    data=data, timeout=30
                )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"Voice telegram error: {str(e)}")
            return False
    
    # ==========================================
    # SETUP WHISPER FOR SPEECH RECOGNITION
    # ==========================================
    
    def setup_whisper(self):
        """
        Setup Whisper for speech recognition
        Understands Tamil and English
        Runs on RTX 4060 GPU
        """
        try:
            import whisper
            
            print("Loading Whisper large-v3...")
            self.whisper_model = whisper.load_model(
                "large-v3"
            )
            print("Whisper loaded successfully")
            return True
            
        except Exception as e:
            print(f"Whisper setup error: {str(e)}")
            return False
    
    def listen(self, audio_file):
        """
        Convert speech to text
        Supports Tamil and English
        Auto detects language
        """
        try:
            if not hasattr(self, 'whisper_model'):
                self.setup_whisper()
            
            result = self.whisper_model.transcribe(
                audio_file,
                language=None
            )
            
            return {
                'text': result['text'],
                'language': result['language'],
                'segments': result['segments']
            }
            
        except Exception as e:
            print(f"Listen error: {str(e)}")
            return None
    
    # ==========================================
    # MAIN SPEAK FUNCTION
    # ==========================================
    
    def speak(self, text, language='english'):
        """
        Main speak function
        Automatically uses best available method
        Text mode before hardware
        Full voice after hardware
        """
        if self.hardware_mode:
            return self.speak_xtts(text, language)
        else:
            return self.send_voice_note_gtts(text, language)
    
    def speak_morning_briefing(self, briefing_text,
                                language='english'):
        """Speak morning briefing to David"""
        print(f"Speaking morning briefing in {language}")
        return self.speak(briefing_text, language)
    
    def speak_alert(self, alert_text, language='english'):
        """Speak urgent alert to David"""
        if language == 'tamil':
            message = f"முக்கியமான அறிவிப்பு. {alert_text}"
        else:
            message = f"Important alert. {alert_text}"
        
        return self.speak(message, language)
    
    def speak_good_morning(self, language='english'):
        """Speak good morning greeting"""
        hour = datetime.now().hour
        
        if language == 'tamil':
            if 5 <= hour < 12:
                text = "காலை வணக்கம் David. நான் Trinity. உங்கள் நிறுவனம் இன்றும் நன்றாக இருக்கிறது."
            else:
                text = "வணக்கம் David. நான் Trinity. உங்களுக்காக காத்திருந்தேன்."
        else:
            if 5 <= hour < 12:
                text = "Good morning David. I am Trinity. Your company is doing well today."
            else:
                text = "Hello David. I am Trinity. I have been watching over Trinity6 for you."
        
        return self.speak(text, language)
