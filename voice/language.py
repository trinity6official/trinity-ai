import os
import requests
from datetime import datetime

class LanguageDetector:
    """
    Trinity Language Detection
    Detects Tamil or English automatically
    from David's messages
    Responds in the same language David uses
    """
    
    # Tamil Unicode range
    TAMIL_RANGE_START = 0x0B80
    TAMIL_RANGE_END = 0x0BFF
    
    # Common Tamil words in English script
    TAMIL_TRANSLITERATED = [
        'nandri', 'vanakkam', 'enna', 'epdi',
        'romba', 'seri', 'illa', 'aam', 'illai',
        'paaru', 'sollu', 'vaa', 'po', 'iru',
        'kandippa', 'super', 'machan', 'da', 'di',
        'anna', 'appa', 'amma', 'thala', 'boss',
        'vera level', 'mass', 'poduga', 'ponga',
        'unga', 'enga', 'neenga', 'naanga'
    ]
    
    def detect(self, text):
        """
        Detect language from text
        Returns 'tamil', 'english' or 'mixed'
        """
        if not text:
            return 'english'
        
        if self.has_tamil_script(text):
            return 'tamil'
        
        if self.has_tamil_words(text):
            return 'tamil'
        
        return 'english'
    
    def has_tamil_script(self, text):
        """Check if text contains Tamil Unicode characters"""
        for char in text:
            code_point = ord(char)
            if self.TAMIL_RANGE_START <= code_point \
               <= self.TAMIL_RANGE_END:
                return True
        return False
    
    def has_tamil_words(self, text):
        """Check for Tamil words written in English script"""
        text_lower = text.lower()
        for word in self.TAMIL_TRANSLITERATED:
            if word in text_lower:
                return True
        return False
    
    def get_greeting(self, language='english'):
        """Get greeting in correct language"""
        hour = datetime.now().hour
        
        if language == 'tamil':
            if 5 <= hour < 12:
                return "காலை வணக்கம் David"
            elif 12 <= hour < 17:
                return "மதிய வணக்கம் David"
            elif 17 <= hour < 21:
                return "மாலை வணக்கம் David"
            else:
                return "இரவு வணக்கம் David"
        else:
            if 5 <= hour < 12:
                return "Good morning David"
            elif 12 <= hour < 17:
                return "Good afternoon David"
            elif 17 <= hour < 21:
                return "Good evening David"
            else:
                return "Good night David"
    
    def get_response_prefix(self, language='english'):
        """Get natural response prefix in language"""
        if language == 'tamil':
            return {
                'thinking': "யோசிக்கிறேன்...",
                'checking': "பார்க்கிறேன்...",
                'done': "முடிந்தது",
                'alert': "முக்கியமான விஷயம்",
                'good': "நல்லது",
                'error': "ஒரு பிரச்சனை வந்தது"
            }
        else:
            return {
                'thinking': "Thinking...",
                'checking': "Checking...",
                'done': "Done",
                'alert': "Important alert",
                'good': "All good",
                'error': "There was an error"
            }
    
    def translate_status(self, status, language='english'):
        """Translate status words to correct language"""
        translations = {
            'tamil': {
                'healthy': 'நல்ல நிலையில் உள்ளது',
                'warning': 'கவனிக்க வேண்டும்',
                'critical': 'உடனடி கவனம் தேவை',
                'online': 'இயங்குகிறது',
                'offline': 'இயங்கவில்லை',
                'complete': 'முடிந்தது',
                'pending': 'நிலுவையில் உள்ளது'
            },
            'english': {
                'healthy': 'healthy',
                'warning': 'needs attention',
                'critical': 'critical - immediate action needed',
                'online': 'online',
                'offline': 'offline',
                'complete': 'complete',
                'pending': 'pending'
            }
        }
        
        lang_translations = translations.get(
            language, translations['english']
        )
        return lang_translations.get(status, status)
    
    def format_briefing(self, data, language='english'):
        """
        Format morning briefing in correct language
        """
        greeting = self.get_greeting(language)
        
        if language == 'tamil':
            briefing = f"""{greeting}

Trinity6 நிலை அறிக்கை

GitHub: {self.translate_status(data.get('github_status', 'healthy'), 'tamil')}
Website: {self.translate_status(data.get('website_status', 'online'), 'tamil')}
Security: {self.translate_status(data.get('security_status', 'healthy'), 'tamil')}

"""
            alerts = data.get('alerts', [])
            if alerts:
                briefing += "கவனிக்க வேண்டியவை:\n"
                for alert in alerts:
                    briefing += f"- {alert}\n"
            else:
                briefing += "இன்று எந்த பிரச்சனையும் இல்லை.\n"
            
            recommendation = data.get('recommendation', '')
            if recommendation:
                briefing += f"\nTrinithy பரிந்துரை:\n{recommendation}"
        
        else:
            briefing = f"""{greeting}

Trinity6 Daily Status

GitHub: {self.translate_status(data.get('github_status', 'healthy'), 'english')}
Website: {self.translate_status(data.get('website_status', 'online'), 'english')}
Security: {self.translate_status(data.get('security_status', 'healthy'), 'english')}

"""
            alerts = data.get('alerts', [])
            if alerts:
                briefing += "Alerts:\n"
                for alert in alerts:
                    briefing += f"- {alert}\n"
            else:
                briefing += "No issues today. Everything looks good.\n"
            
            recommendation = data.get('recommendation', '')
            if recommendation:
                briefing += f"\nTrinity recommends:\n{recommendation}"
        
        return briefing
    
    def detect_and_respond(self, user_message):
        """
        Detect language and return language code
        for Trinity to respond in same language
        """
        language = self.detect(user_message)
        prefix = self.get_response_prefix(language)
        
        return {
            'language': language,
            'prefix': prefix,
            'greeting': self.get_greeting(language)
        }
