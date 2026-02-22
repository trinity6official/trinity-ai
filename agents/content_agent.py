import os
import requests
from datetime import datetime

class ContentAgent:
    """
    Trinity Content Agent
    Manages Trinity6 social media content
    Creates and posts autonomously
    LinkedIn, Twitter, Instagram
    Acts alone - no approval needed
    """
    
    def __init__(self, memory=None, llm=None):
        self.memory = memory
        self.llm = llm
    
    # ==========================================
    # CONTENT GENERATION
    # ==========================================
    
    def generate_linkedin_post(self, topic=None):
        """Generate LinkedIn post using AI"""
        if not self.llm:
            return None
        
        if not topic:
            topic = self.get_todays_topic()
        
        prompt = f"""Write one LinkedIn post for Trinity6.

Topic: {topic}

Requirements:
- Under 200 words
- Strong opening line
- Professional but conversational
- End with one question
- 5 relevant hashtags
- No markdown stars or symbols
- Plain text only
- Ready to publish immediately"""
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content="""You are Trinity6 content writer.
Trinity6 is an AI powered cybersecurity company.
Write content that builds thought leadership.
No markdown. No stars. Plain text only."""),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            print(f"Content generation error: {str(e)}")
            return None
    
    def generate_youtube_script(self, topic=None):
        """Generate YouTube Shorts script"""
        if not self.llm:
            return None
        
        if not topic:
            topic = self.get_todays_topic()
        
        prompt = f"""Write one YouTube Shorts script for Trinity6.

Topic: {topic}

Requirements:
- Maximum 60 seconds when read aloud
- Powerful hook in first 3 seconds
- Visual directions in brackets
- End with follow Trinity6 call to action
- Suggested title
- 5 hashtags
- No markdown stars or symbols
- Plain text only"""
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content="""You are Trinity6 YouTube content creator.
Create viral short form cybersecurity content.
No markdown. No stars. Plain text only."""),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            print(f"Script generation error: {str(e)}")
            return None
    
    def get_todays_topic(self):
        """Pick todays content topic"""
        topics = [
            "Zero trust security architecture",
            "CIS benchmark compliance for SMBs",
            "Why 60 percent of SMBs fail after a cyberattack",
            "AI in cybersecurity threat detection",
            "What is GRC compliance and why it matters",
            "Network security basics every business needs",
            "The cost of a data breach in 2026",
            "How to prepare for SOC 2 certification",
            "NIST cybersecurity framework explained simply",
            "ISO 27001 vs SOC 2 which do you need",
            "Ransomware protection strategies for small business",
            "Why patch management is your first line of defense",
            "Multi factor authentication saves businesses",
            "Incident response planning for small teams",
            "Cloud security mistakes most companies make"
        ]
        
        day = datetime.now().day
        return topics[day % len(topics)]
    
    # ==========================================
    # CONTENT DELIVERY
    # ==========================================
    
    def send_to_telegram(self, content_type,
                          content, telegram_token,
                          chat_id):
        """Send content to David via Telegram"""
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        
        if content_type == 'linkedin':
            header = "LinkedIn Post\n\n"
        elif content_type == 'youtube':
            header = "YouTube Shorts Script\n\n"
        else:
            header = "Content\n\n"
        
        message = header + content
        
        chunks = [
            message[i:i+4000]
            for i in range(0, len(message), 4000)
        ]
        
        for chunk in chunks:
            payload = {
                "chat_id": chat_id,
                "text": chunk
            }
            try:
                requests.post(url, json=payload, timeout=10)
            except Exception as e:
                print(f"Telegram error: {str(e)}")
    
    # ==========================================
    # CONTENT CALENDAR
    # ==========================================
    
    def get_content_calendar(self):
        """Get content plan for the week"""
        days = [
            'Monday',
            'Tuesday',
            'Wednesday',
            'Thursday',
            'Friday',
            'Saturday',
            'Sunday'
        ]
        
        themes = [
            'Cybersecurity threat awareness',
            'GRC compliance tips',
            'AI in security',
            'Technology trends',
            'Trinity6 product insights',
            'Weekend learning - security basics',
            'Weekly security roundup'
        ]
        
        calendar = []
        for i, day in enumerate(days):
            calendar.append({
                'day': day,
                'theme': themes[i],
                'platforms': ['LinkedIn', 'Twitter', 'Instagram'],
                'content_type': 'post'
            })
        
        return calendar
    
    def get_content_stats(self):
        """Get content performance summary"""
        if not self.memory:
            return {}
        
        logs = self.memory.get_recent_logs(7)
        
        content_logs = [
            log for log in logs
            if 'content' in str(log.get('entry', '')).lower()
            or 'post' in str(log.get('entry', '')).lower()
        ]
        
        return {
            'posts_this_week': len(content_logs),
            'platforms_active': [
                'LinkedIn',
                'Twitter',
                'Instagram'
            ],
            'next_post_topic': self.get_todays_topic(),
            'content_calendar': self.get_content_calendar()
        }
    
    def run_daily_content(self, telegram_token, chat_id):
        """
        Run daily content generation
        Trinity does this alone every morning
        No approval needed
        """
        print("Trinity generating daily content...")
        
        topic = self.get_todays_topic()
        print(f"Today's topic: {topic}")
        
        linkedin_post = self.generate_linkedin_post(topic)
        if linkedin_post:
            self.send_to_telegram(
                'linkedin',
                linkedin_post,
                telegram_token,
                chat_id
            )
            
            if self.memory:
                self.memory.add_daily_log(
                    f"LinkedIn post generated about: {topic}"
                )
        
        youtube_script = self.generate_youtube_script(topic)
        if youtube_script:
            self.send_to_telegram(
                'youtube',
                youtube_script,
                telegram_token,
                chat_id
            )
            
            if self.memory:
                self.memory.add_daily_log(
                    f"YouTube script generated about: {topic}"
                )
        
        print("Daily content complete!")
        
        return {
            'topic': topic,
            'linkedin': linkedin_post is not None,
            'youtube': youtube_script is not None
        }
